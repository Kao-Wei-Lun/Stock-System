from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from datetime import datetime, tzinfo
from typing import Any

from futopt_session import is_futopt_trading_time
from fubon_symbols import normalize_futopt_symbol_query

log = logging.getLogger(__name__)


def date_range_to_futopt_period(start_date: str, end_date: str) -> str:
    """Map a replay date range to the nearest Fubon intraday period bucket."""
    try:
        start = date.fromisoformat(str(start_date)[:10])
        end = date.fromisoformat(str(end_date)[:10])
    except ValueError:
        return "1d"

    days = max(1, (end - start).days + 1)
    if days <= 1:
        return "1d"
    if days <= 5:
        return "5d"
    if days <= 31:
        return "1mo"
    if days <= 93:
        return "3mo"
    return "6mo"


def intraday_end_bound(end_date: str) -> str:
    """Expand YYYY-MM-DD to an end-of-day string for lexicographic timestamp columns."""
    raw = str(end_date or "").strip()
    if len(raw) == 10:
        return f"{raw}T23:59:59"
    return raw


def build_futopt_storage_tickers(symbol: str, payload: dict[str, Any]) -> list[str]:
    """Store rows under both replay aliases and the resolved execution contract."""
    requested = str(payload.get("requested_symbol") or symbol or "").strip().upper()
    canonical = normalize_futopt_symbol_query(requested)
    resolved = str(payload.get("resolved_symbol") or payload.get("ticker") or "").strip().upper()

    tickers: list[str] = []
    for ticker in (requested, canonical, resolved):
        if ticker and ticker not in tickers:
            tickers.append(ticker)
    return tickers


async def persist_futopt_ohlc_payload(
    db,
    symbol: str,
    payload: dict[str, Any],
    *,
    interval: str,
    record_resolution: bool = True,
) -> dict[str, Any]:
    rows = list(payload.get("data") or [])
    tickers = build_futopt_storage_tickers(symbol, payload)
    counts: dict[str, int] = {}

    for ticker in tickers:
        counts[ticker] = await db.upsert_ohlcv_batch(ticker, rows, interval)

    resolved = str(payload.get("resolved_symbol") or payload.get("ticker") or "").strip().upper()
    if record_resolution and resolved and hasattr(db, "save_paper_trading_contract_resolution"):
        today = date.today().isoformat()
        for ticker in tickers:
            await db.save_paper_trading_contract_resolution(
                {
                    "requested_symbol": ticker,
                    "resolved_symbol": resolved,
                    "resolution_date": today,
                    "contract_type": payload.get("contract_type"),
                    "end_date": payload.get("end_date"),
                    "instrument_type": payload.get("instrument_type") or "future",
                    "source": "fubon_neo",
                }
            )

    return {
        "requested_symbol": str(payload.get("requested_symbol") or symbol or "").strip().upper(),
        "resolved_symbol": resolved,
        "interval": interval,
        "row_count": len(rows),
        "stored_tickers": tickers,
        "stored_counts": counts,
    }


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def row_from_futopt_ws_candle(payload: dict[str, Any]) -> dict[str, Any] | None:
    date_value = payload.get("date") or payload.get("time")
    close_price = _coerce_float(payload.get("close"))
    if not date_value or close_price is None:
        return None

    open_price = _coerce_float(payload.get("open"))
    high_price = _coerce_float(payload.get("high"))
    low_price = _coerce_float(payload.get("low"))
    return {
        "date": str(date_value).replace("Z", "+00:00"),
        "open": open_price if open_price is not None else close_price,
        "high": high_price if high_price is not None else close_price,
        "low": low_price if low_price is not None else close_price,
        "close": close_price,
        "volume": _coerce_int(payload.get("volume")),
        "adj_close": close_price,
        "source": "fubon_neo_ws",
    }


class FutoptCandleRecorder:
    """Record TXF/TMF realtime candles to ohlcv for paper-trading replay."""

    def __init__(
        self,
        *,
        provider,
        db,
        realtime_pool,
        symbols: list[str] | tuple[str, ...] = ("TXF", "TMF"),
        interval: str = "1m",
        source: str = "futopt_recorder",
        logger: logging.Logger | None = None,
    ):
        self.provider = provider
        self.db = db
        self.realtime_pool = realtime_pool
        self.symbols = tuple(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
        self.interval = interval
        self.source = source
        self.log = logger or log

        self._handler = None
        self._queue: asyncio.Queue | None = None
        self._consumer_task: asyncio.Task | None = None
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    async def start_ws(self) -> None:
        if self._active:
            return
        self._queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _handler(message: dict) -> None:
            if loop.is_closed() or self._queue is None:
                return
            try:
                loop.call_soon_threadsafe(self._queue.put_nowait, message)
            except RuntimeError:
                return

        self._handler = _handler
        self.realtime_pool.register_message_handler(_handler)
        for symbol in self.symbols:
            self.realtime_pool.track_ticker(symbol, source=self.source)
        self._consumer_task = asyncio.create_task(self._consume(), name="futopt-candle-recorder:consumer")
        self._active = True
        self.log.info("Futopt candle recorder started for %s", ", ".join(self.symbols))

    async def stop_ws(self) -> None:
        if not self._active and self._handler is None:
            return
        for symbol in self.symbols:
            self.realtime_pool.untrack_ticker(symbol, source=self.source)
        if self._handler is not None:
            self.realtime_pool.unregister_message_handler(self._handler)
            self._handler = None
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None
        self._queue = None
        self._active = False
        self.log.info("Futopt candle recorder stopped")

    async def backfill(self, *, period: str = "1d") -> dict[str, Any]:
        results = []
        total_rows = 0
        for symbol in self.symbols:
            try:
                result = await sync_futopt_intraday_ohlc(
                    self.provider,
                    self.db,
                    symbol,
                    period=period,
                    interval=self.interval,
                )
            except Exception as exc:
                self.log.warning("Futopt candle recorder backfill failed for %s: %s", symbol, exc)
                results.append({"symbol": symbol, "error": str(exc)})
                continue
            if result:
                total_rows += int(result.get("row_count") or 0)
                results.append(result)
        return {"period": period, "interval": self.interval, "row_count": total_rows, "results": results}

    async def run(
        self,
        *,
        app_tz: tzinfo,
        poll_seconds: int = 30,
        backfill_interval_seconds: int = 300,
    ) -> None:
        last_backfill_at = 0.0
        try:
            while True:
                now = datetime.now(app_tz)
                in_session = is_futopt_trading_time(now)
                if in_session and not self.active:
                    await self.start_ws()
                    await self.backfill(period="1d")
                    last_backfill_at = time.monotonic()
                elif not in_session and self.active:
                    await self.stop_ws()

                if in_session and time.monotonic() - last_backfill_at >= backfill_interval_seconds:
                    await self.backfill(period="1d")
                    last_backfill_at = time.monotonic()

                await asyncio.sleep(max(5, poll_seconds))
        finally:
            await self.stop_ws()

    async def _consume(self) -> None:
        while True:
            if self._queue is None:
                await asyncio.sleep(0)
                continue
            message = await self._queue.get()
            try:
                await self._process_message(message)
            except Exception as exc:
                self.log.warning("Futopt candle recorder failed to process message: %s", exc)

    async def _process_message(self, message: dict) -> None:
        if str(message.get("event") or "").strip().lower() != "data":
            return
        if str(message.get("channel") or "").strip().lower() != "candles":
            return
        data = message.get("data")
        if not isinstance(data, dict):
            return
        if str(data.get("timeframe") or "1").strip().lower() not in {"1", "1m"}:
            return

        resolved_symbol = str(data.get("symbol") or "").strip().upper()
        if not resolved_symbol:
            return
        row = row_from_futopt_ws_candle(data)
        if not row:
            return

        target_tickers: tuple[str, ...] = (resolved_symbol,)
        resolver = getattr(self.realtime_pool, "resolve_broadcast_tickers", None)
        if callable(resolver):
            target_tickers = resolver(resolved_symbol)

        stored: set[str] = set()
        for requested_symbol in target_tickers:
            payload = {
                "ticker": resolved_symbol,
                "requested_symbol": requested_symbol,
                "resolved_symbol": resolved_symbol,
                "data": [row],
            }
            for ticker in build_futopt_storage_tickers(requested_symbol, payload):
                if ticker in stored:
                    continue
                await self.db.upsert_ohlcv_batch(ticker, [row], self.interval)
                stored.add(ticker)


async def sync_futopt_intraday_ohlc(
    provider,
    db,
    symbol: str,
    *,
    period: str,
    interval: str,
) -> dict[str, Any] | None:
    payload = await provider.fetch_intraday_ohlc(symbol, period=period, interval=interval)
    if not payload:
        return None

    persisted = await persist_futopt_ohlc_payload(db, symbol, payload, interval=interval)
    return {
        **persisted,
        "period": period,
        "source": "fubon_neo",
        "synced": sum(persisted["stored_counts"].values()),
    }
