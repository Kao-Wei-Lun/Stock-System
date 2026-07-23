"""Non-blocking, coalescing persistence for realtime quote snapshots."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from datetime import datetime
from typing import Any, Awaitable, Callable

from data_fetcher import normalize_ticker
from realtime_performance import realtime_performance_metrics


def _timestamp_rank(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        while numeric > 10_000_000_000:
            numeric /= 1000
        return numeric
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _meaningful(value: Any) -> bool:
    return value is not None and value != "" and value != []


def merge_quote_updates(current: dict | None, incoming: dict | None) -> dict | None:
    """Merge latest-state quotes while protecting event-time order and session extrema."""
    if not current and not incoming:
        return None
    if not current:
        return dict(incoming or {})
    if not incoming:
        return dict(current)

    merged = dict(current)
    source = dict(incoming)
    current_rank = _timestamp_rank(current.get("quote_timestamp") or current.get("ts"))
    incoming_rank = _timestamp_rank(source.get("quote_timestamp") or source.get("ts"))
    incoming_is_latest = current_rank is None or incoming_rank is None or incoming_rank >= current_rank

    if incoming_is_latest:
        for key, value in source.items():
            if key in {"high", "low"} or not _meaningful(value):
                continue
            merged[key] = value

    highs = [value for value in (current.get("high"), source.get("high")) if isinstance(value, (int, float))]
    lows = [value for value in (current.get("low"), source.get("low")) if isinstance(value, (int, float))]
    if highs:
        merged["high"] = max(highs)
    if lows:
        merged["low"] = min(lows)
    return merged


class RealtimeQuotePersistenceBuffer:
    """Bounded per-ticker latest-state buffer flushed outside the broadcast path."""

    def __init__(
        self,
        persist_quote: Callable[[dict], Awaitable[Any]],
        *,
        flush_interval_ms: int = 500,
        capacity: int = 500,
        logger: logging.Logger | None = None,
        performance_metrics=None,
    ) -> None:
        self._persist_quote = persist_quote
        self.flush_interval_seconds = max(0.25, min(2.0, int(flush_interval_ms) / 1000))
        self.capacity = max(1, int(capacity))
        self._log = logger or logging.getLogger(__name__)
        self._metrics = performance_metrics or realtime_performance_metrics
        self._pending: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._worker: asyncio.Task | None = None
        self._closing = False
        self._coalesced_since_flush = 0
        self._dropped_since_flush = 0
        self._persisted = 0
        self._failures = 0
        self._last_error: str | None = None

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def status(self) -> dict:
        return {
            "running": bool(self._worker and not self._worker.done()),
            "closing": self._closing,
            "pending": len(self._pending),
            "capacity": self.capacity,
            "flush_interval_ms": round(self.flush_interval_seconds * 1000),
            "persisted": self._persisted,
            "failures": self._failures,
            "last_error": self._last_error,
        }

    async def enqueue(self, quote: dict | None) -> bool:
        if not quote or self._closing:
            return False
        ticker = normalize_ticker(quote.get("ticker"))
        if not ticker:
            return False
        payload = dict(quote)
        payload["ticker"] = ticker

        async with self._lock:
            existing = self._pending.get(ticker)
            if existing:
                enqueued_at, existing_payload = existing
                self._pending[ticker] = (enqueued_at, merge_quote_updates(existing_payload, payload) or payload)
                self._pending.move_to_end(ticker)
                self._coalesced_since_flush += 1
            else:
                if len(self._pending) >= self.capacity:
                    self._pending.popitem(last=False)
                    self._dropped_since_flush += 1
                self._pending[ticker] = (time.perf_counter(), payload)
            self._event.set()
            self._ensure_worker()
        return True

    def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run(), name="quantvision:quote-persistence")

    async def _take_pending(self) -> tuple[list[tuple[float, dict]], int, int]:
        async with self._lock:
            items = list(self._pending.values())
            self._pending.clear()
            coalesced = self._coalesced_since_flush
            dropped = self._dropped_since_flush
            self._coalesced_since_flush = 0
            self._dropped_since_flush = 0
            self._event.clear()
            return items, coalesced, dropped

    async def flush_once(self) -> int:
        items, coalesced, dropped = await self._take_pending()
        if not items:
            return 0

        failed: list[tuple[float, dict]] = []
        now = time.perf_counter()
        for enqueued_at, payload in items:
            try:
                await self._persist_quote(payload)
                self._persisted += 1
                self._last_error = None
                self._metrics.record_persistence_flush(
                    (now - enqueued_at) * 1000,
                    coalesced=coalesced,
                    dropped=dropped,
                )
                coalesced = 0
                dropped = 0
            except asyncio.CancelledError:
                failed.append((enqueued_at, payload))
                raise
            except Exception as exc:
                self._failures += 1
                self._last_error = str(exc)[:500]
                failed.append((enqueued_at, payload))
                self._log.warning("Realtime quote persistence failed for %s: %s", payload.get("ticker"), exc)

        if failed:
            async with self._lock:
                for enqueued_at, payload in failed:
                    ticker = payload["ticker"]
                    newer = self._pending.get(ticker)
                    if newer:
                        newer_at, newer_payload = newer
                        payload = merge_quote_updates(payload, newer_payload) or newer_payload
                        enqueued_at = min(enqueued_at, newer_at)
                    self._pending[ticker] = (enqueued_at, payload)
                self._event.set()
        return len(items) - len(failed)

    async def _run(self) -> None:
        try:
            while True:
                await self._event.wait()
                if not self._closing:
                    await asyncio.sleep(self.flush_interval_seconds)
                await self.flush_once()
                if self._closing:
                    break
        except asyncio.CancelledError:
            raise
        finally:
            self._worker = None

    async def shutdown(self, timeout_seconds: float = 5.0) -> None:
        self._closing = True
        self._event.set()
        worker = self._worker
        if worker is None:
            return
        try:
            await asyncio.wait_for(worker, timeout=max(0.1, timeout_seconds))
        except asyncio.TimeoutError:
            self._log.warning("Realtime quote persistence shutdown timed out with %s pending quotes", len(self._pending))
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
