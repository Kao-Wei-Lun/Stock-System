from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from datetime import datetime, timezone, tzinfo
from typing import Any

from futopt_session import is_futopt_trading_time
from fubon_symbols import is_exact_futopt_contract, normalize_futopt_symbol_query

log = logging.getLogger(__name__)

FUTOPT_REFRESH_MODES = {"none", "background", "blocking"}


def _futopt_data_age_seconds(row: dict[str, Any] | None, *, now: datetime | None = None) -> float | None:
    if not row or not row.get("date"):
        return None
    current = now or datetime.now().astimezone()
    try:
        parsed = datetime.fromisoformat(str(row["date"]).strip().replace(" ", "T").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=current.tzinfo)
    return max(0.0, (current - parsed.astimezone(current.tzinfo)).total_seconds())


class FutoptRefreshCoordinator:
    """Deduplicate REST refreshes without creating another Fubon provider session."""

    def __init__(
        self,
        *,
        provider,
        db,
        stale_after_seconds: float = 90.0,
        empty_wait_seconds: float = 8.0,
        max_concurrent_refreshes: int = 2,
        logger: logging.Logger | None = None,
    ) -> None:
        self.provider = provider
        self.db = db
        self.stale_after_seconds = max(1.0, float(stale_after_seconds))
        self.empty_wait_seconds = max(0.1, float(empty_wait_seconds))
        self.max_concurrent_refreshes = max(1, min(int(max_concurrent_refreshes), 8))
        self._refresh_semaphore = asyncio.Semaphore(self.max_concurrent_refreshes)
        self.log = logger or log
        self._tasks: dict[tuple[str, str, str, str], asyncio.Task] = {}
        self._last_outcomes: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self._closed = False

    @staticmethod
    def build_key(symbol: str, period: str, interval: str, session: str = "AUTO") -> tuple[str, str, str, str]:
        canonical = normalize_futopt_symbol_query(str(symbol or "").strip().upper())
        return canonical, str(period).lower(), str(interval).lower(), str(session or "AUTO").strip().upper()

    def begin(self, symbol: str, *, period: str, interval: str, session: str = "AUTO") -> asyncio.Task:
        if self._closed:
            raise RuntimeError("Futopt refresh coordinator is shutting down")
        key = self.build_key(symbol, period, interval, session)
        current = self._tasks.get(key)
        if current is not None and not current.done():
            return current

        async def bounded_refresh():
            async with self._refresh_semaphore:
                return await sync_futopt_intraday_ohlc(
                    self.provider,
                    self.db,
                    symbol,
                    period=period,
                    interval=interval,
                )

        task = asyncio.create_task(
            bounded_refresh(),
            name=f"futopt-refresh:{key[0]}:{interval}:{session}",
        )
        self._tasks[key] = task
        self._last_outcomes[key] = {"status": "running", "error": None}
        task.add_done_callback(lambda completed, task_key=key: self._finish(task_key, completed))
        return task

    def _finish(self, key: tuple[str, str, str, str], task: asyncio.Task) -> None:
        if self._tasks.get(key) is task:
            self._tasks.pop(key, None)
        try:
            result = task.result()
        except asyncio.CancelledError:
            self._last_outcomes[key] = {"status": "cancelled", "error": None}
        except Exception as exc:
            self._last_outcomes[key] = {"status": "failed", "error": str(exc)}
            self.log.warning("Futopt background refresh failed for %s: %s", key, exc)
        else:
            self._last_outcomes[key] = {
                "status": "refreshed" if result else "empty",
                "error": None,
                "result": result,
            }

    def get_status(self, symbol: str, *, period: str, interval: str, session: str = "AUTO") -> dict[str, Any]:
        key = self.build_key(symbol, period, interval, session)
        task = self._tasks.get(key)
        if task is not None and not task.done():
            return {"status": "running", "error": None}
        return dict(self._last_outcomes.get(key) or {"status": "idle", "error": None})

    def startup(self) -> None:
        self._closed = False

    async def shutdown(self) -> None:
        self._closed = True
        tasks = list(self._tasks.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()


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


def _row_time_key(row: dict[str, Any]) -> str:
    raw = str(row.get("date") or "").strip().replace(" ", "T")
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    return parsed.isoformat(timespec="seconds")


def merge_futopt_ohlcv_rows(*row_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge alias/contract rows into one deterministic minute series."""
    merged: dict[str, dict[str, Any]] = {}
    for rows in row_groups:
        for row in rows or []:
            key = _row_time_key(row)
            if key:
                merged[key] = dict(row)
    return [merged[key] for key in sorted(merged)]


def resolve_futopt_database_period(
    requested_period: str,
    *,
    limit: int | None,
    since: str | None,
) -> str:
    """Select the DB display window independently from the provider refresh range.

    A bounded initial chart load needs the latest N persisted bars even when a
    weekend or holiday falls inside a short calendar period. The repository
    still applies LIMIT, so using ``max`` here does not load the full history.
    Incremental and legacy unbounded reads keep their existing time boundary.
    """
    if limit is not None and since is None:
        return "max"
    return requested_period


async def load_futopt_ohlc_db_first(
    provider,
    db,
    symbol: str,
    *,
    period: str,
    interval: str,
    refresh: bool = True,
    refresh_mode: str | None = None,
    refresh_coordinator: FutoptRefreshCoordinator | None = None,
    session: str = "AUTO",
    limit: int | None = None,
    since: str | None = None,
    warmup: int = 0,
) -> dict[str, Any]:
    """Read persisted futures candles first, then use Fubon only to fill/correct the requested range."""
    selected_refresh_mode = str(refresh_mode or ("blocking" if refresh else "none")).strip().lower()
    if selected_refresh_mode not in FUTOPT_REFRESH_MODES:
        raise ValueError(f"Unsupported futopt refresh mode: {selected_refresh_mode}")
    requested = str(symbol or "").strip().upper()
    canonical = normalize_futopt_symbol_query(requested)
    storage_tickers = list(dict.fromkeys(item for item in (requested, canonical) if item))
    database_period = resolve_futopt_database_period(
        period,
        limit=limit,
        since=since,
    )
    query_options: dict[str, Any] = {}
    if limit is not None:
        query_options["limit"] = max(1, min(max(int(limit), int(warmup or 0)), 5000))
    if since is not None:
        query_options["since"] = since

    initial_groups = [
        await db.get_ohlcv(ticker, period=database_period, interval=interval, **query_options)
        for ticker in storage_tickers
    ]
    initial_rows = merge_futopt_ohlcv_rows(*initial_groups)
    if query_options.get("limit") is not None:
        initial_rows = initial_rows[-query_options["limit"]:]
    sync_result: dict[str, Any] | None = None
    sync_error: str | None = None
    refresh_status = "skipped"
    initial_age_seconds = _futopt_data_age_seconds(initial_rows[-1] if initial_rows else None)
    stale_after_seconds = refresh_coordinator.stale_after_seconds if refresh_coordinator else 90.0
    is_stale = initial_age_seconds is None or initial_age_seconds > stale_after_seconds

    if selected_refresh_mode == "blocking":
        try:
            sync_result = await sync_futopt_intraday_ohlc(
                provider,
                db,
                requested,
                period=period,
                interval=interval,
            )
            refresh_status = "refreshed" if sync_result else "empty"
        except Exception as exc:
            sync_error = str(exc)
            refresh_status = "failed"
            log.warning("Futopt DB-first refresh failed for %s (%s/%s): %s", requested, period, interval, exc)
    elif selected_refresh_mode == "background" and is_stale:
        if refresh_coordinator is None:
            raise ValueError("background refresh mode requires a refresh coordinator")
        task = refresh_coordinator.begin(requested, period=period, interval=interval, session=session)
        await asyncio.sleep(0)
        if not initial_rows:
            try:
                sync_result = await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=refresh_coordinator.empty_wait_seconds,
                )
                refresh_status = "refreshed" if sync_result else "empty"
            except asyncio.TimeoutError:
                refresh_status = "timeout"
                sync_error = "Futopt background refresh timed out before initial data became available"
            except Exception as exc:
                refresh_status = "failed"
                sync_error = str(exc)
        elif task.done():
            try:
                sync_result = task.result()
                refresh_status = "refreshed" if sync_result else "empty"
            except Exception as exc:
                refresh_status = "failed"
                sync_error = str(exc)
        else:
            refresh_status = "running"
    elif selected_refresh_mode == "background":
        refresh_status = "not_needed"

    resolved = str((sync_result or {}).get("resolved_symbol") or "").strip().upper()
    for ticker in (resolved, *((sync_result or {}).get("stored_tickers") or [])):
        normalized = str(ticker or "").strip().upper()
        if normalized and normalized not in storage_tickers:
            storage_tickers.append(normalized)

    if sync_result:
        refreshed_groups = [
            await db.get_ohlcv(ticker, period=database_period, interval=interval, **query_options)
            for ticker in storage_tickers
        ]
        rows = merge_futopt_ohlcv_rows(*refreshed_groups)
        if query_options.get("limit") is not None:
            rows = rows[-query_options["limit"]:]
    else:
        rows = initial_rows

    data_age_seconds = _futopt_data_age_seconds(rows[-1] if rows else None)
    is_stale = data_age_seconds is None or data_age_seconds > stale_after_seconds

    return {
        "ticker": requested or canonical,
        "requested_symbol": requested,
        "resolved_symbol": resolved or (canonical if is_exact_futopt_contract(canonical) else None),
        "period": period,
        "database_period": database_period,
        "history_window_expanded": database_period != period,
        "interval": interval,
        "data": rows,
        "row_count": len(rows),
        "latest_date": rows[-1].get("date") if rows else None,
        "data_age_seconds": round(data_age_seconds, 3) if data_age_seconds is not None else None,
        "is_stale": is_stale,
        "data_source": "database",
        "refresh_mode": selected_refresh_mode,
        "refresh_status": refresh_status,
        "refreshed_from": "fubon_neo" if sync_result else None,
        "sync_status": "refreshed" if sync_result else "failed" if sync_error else "skipped",
        "sync_error": sync_error,
        "storage_tickers": storage_tickers,
    }


def latest_row_to_futopt_period(row: dict[str, Any] | None, *, now: datetime | None = None) -> str:
    """Choose the smallest Fubon period bucket that can repair a restart gap."""
    if not row or not row.get("date"):
        return "1d"
    current = now or datetime.now().astimezone()
    try:
        parsed = datetime.fromisoformat(str(row.get("date")).replace(" ", "T").replace("Z", "+00:00"))
    except ValueError:
        return "1d"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=current.tzinfo)
    age_days = max(0.0, (current - parsed.astimezone(current.tzinfo)).total_seconds() / 86400)
    if age_days <= 1:
        return "1d"
    if age_days <= 5:
        return "5d"
    if age_days <= 31:
        return "1mo"
    if age_days <= 93:
        return "3mo"
    return "6mo"


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
        queue_maxsize: int = 2000,
        shutdown_drain_seconds: float = 5.0,
        logger: logging.Logger | None = None,
    ):
        self.provider = provider
        self.db = db
        self.realtime_pool = realtime_pool
        self.symbols = tuple(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
        self.interval = interval
        self.source = source
        self.queue_maxsize = max(10, int(queue_maxsize))
        self.shutdown_drain_seconds = max(0.1, float(shutdown_drain_seconds))
        self.log = logger or log

        self._handler = None
        self._queue: asyncio.Queue | None = None
        self._consumer_task: asyncio.Task | None = None
        self._active = False
        self._source_registered = False
        self._subscription_ready = False
        self._subscription_error: str | None = None
        self._last_backfill_summary: dict[str, Any] | None = None
        self._last_persisted_at: str | None = None
        self._last_error: str | None = None
        self._dropped_messages = 0

    @property
    def active(self) -> bool:
        return self._active

    async def start_ws(self) -> bool:
        if self._active:
            return self.subscription_ready
        self._queue = asyncio.Queue(maxsize=self.queue_maxsize)
        loop = asyncio.get_running_loop()

        def _handler(message: dict) -> None:
            if loop.is_closed() or self._queue is None:
                return
            if str(message.get("event") or "").strip().lower() != "data":
                return
            if str(message.get("channel") or "").strip().lower() != "candles":
                return

            def _enqueue_latest() -> None:
                if self._queue is None:
                    return
                if self._queue.full():
                    try:
                        self._queue.get_nowait()
                        self._queue.task_done()
                        self._dropped_messages += 1
                    except asyncio.QueueEmpty:
                        pass
                self._queue.put_nowait(message)

            try:
                loop.call_soon_threadsafe(_enqueue_latest)
            except RuntimeError:
                return

        self._handler = _handler
        self.realtime_pool.register_message_handler(_handler)
        ensure_source = getattr(self.realtime_pool, "ensure_source_tickers", None)
        if callable(ensure_source):
            assignment_status = await ensure_source(self.source, self.symbols)
            self._source_registered = True
            self._subscription_ready = bool(assignment_status.get("ready"))
            if not self._subscription_ready:
                missing = assignment_status.get("missing_tickers") or []
                unhealthy = assignment_status.get("unhealthy_tickers") or []
                self._subscription_error = (
                    "futures realtime subscriptions are not ready "
                    f"(missing={missing}, unhealthy={unhealthy})"
                )
                self.realtime_pool.unregister_message_handler(_handler)
                self._handler = None
                self._queue = None
                self.log.warning("Futopt candle recorder start deferred: %s", self._subscription_error)
                return False
        else:
            for symbol in self.symbols:
                self.realtime_pool.track_ticker(symbol, source=self.source)
            self._source_registered = True
            self._subscription_ready = True
        self._consumer_task = asyncio.create_task(self._consume(), name="futopt-candle-recorder:consumer")
        self._active = True
        self._subscription_error = None
        self.log.info("Futopt candle recorder started for %s", ", ".join(self.symbols))
        return True

    async def stop_ws(self) -> None:
        if not self._active and self._handler is None and not self._source_registered:
            return
        set_source = getattr(self.realtime_pool, "set_source_tickers", None)
        if callable(set_source):
            await set_source(self.source, [], wait_for_assignments=True)
        else:
            for symbol in self.symbols:
                self.realtime_pool.untrack_ticker(symbol, source=self.source)
        self._source_registered = False
        if self._handler is not None:
            self.realtime_pool.unregister_message_handler(self._handler)
            self._handler = None
        if self._queue is not None:
            try:
                await asyncio.wait_for(self._queue.join(), timeout=self.shutdown_drain_seconds)
            except asyncio.TimeoutError:
                self.log.warning("Futopt candle recorder shutdown drain timed out with %s queued messages", self._queue.qsize())
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None
        self._queue = None
        self._active = False
        self._subscription_ready = False
        self.log.info("Futopt candle recorder stopped")

    @property
    def subscription_ready(self) -> bool:
        if not self._active:
            return False
        get_status = getattr(self.realtime_pool, "get_source_assignment_status", None)
        if not callable(get_status):
            return self._subscription_ready
        status = get_status(self.source, self.symbols)
        self._subscription_ready = bool(status.get("ready"))
        return self._subscription_ready

    def get_status(self) -> dict[str, Any]:
        assignment_status = None
        get_assignment_status = getattr(self.realtime_pool, "get_source_assignment_status", None)
        if callable(get_assignment_status):
            assignment_status = get_assignment_status(self.source, self.symbols)
        return {
            "active": self.active,
            "subscription_ready": self.subscription_ready,
            "subscription_error": self._subscription_error,
            "assignment_status": assignment_status,
            "symbols": list(self.symbols),
            "interval": self.interval,
            "queue_size": self._queue.qsize() if self._queue is not None else 0,
            "queue_capacity": self.queue_maxsize,
            "dropped_messages": self._dropped_messages,
            "last_persisted_at": self._last_persisted_at,
            "last_error": self._subscription_error or self._last_error,
            "last_backfill": self._last_backfill_summary,
        }

    async def backfill(self, *, period: str | None = "1d") -> dict[str, Any]:
        results = []
        total_rows = 0
        for symbol in self.symbols:
            selected_period = period
            if selected_period is None:
                latest = await self.db.get_latest_ohlcv(symbol, self.interval)
                selected_period = latest_row_to_futopt_period(latest)
            try:
                result = await sync_futopt_intraday_ohlc(
                    self.provider,
                    self.db,
                    symbol,
                    period=selected_period,
                    interval=self.interval,
                )
            except Exception as exc:
                self._last_error = str(exc)
                self.log.warning("Futopt candle recorder backfill failed for %s: %s", symbol, exc)
                results.append({"symbol": symbol, "period": selected_period, "error": str(exc)})
                continue
            if result:
                total_rows += int(result.get("row_count") or 0)
                results.append(result)
        summary = {"period": period or "auto", "interval": self.interval, "row_count": total_rows, "results": results}
        self._last_backfill_summary = summary
        if not any(item.get("error") for item in results):
            self._last_error = None
        return summary

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
                    started = await self.start_ws()
                    if time.monotonic() - last_backfill_at >= backfill_interval_seconds:
                        await self.backfill(period=None)
                        last_backfill_at = time.monotonic()
                    if not started:
                        await asyncio.sleep(max(5, poll_seconds))
                        continue
                elif not in_session and self.active:
                    await self.stop_ws()

                if in_session and self.active and not self.subscription_ready:
                    ensure_source = getattr(self.realtime_pool, "ensure_source_tickers", None)
                    if callable(ensure_source):
                        status = await ensure_source(self.source, self.symbols)
                        self._subscription_ready = bool(status.get("ready"))
                        if not self._subscription_ready:
                            self._subscription_error = (
                                "futures realtime subscriptions became unavailable "
                                f"(missing={status.get('missing_tickers') or []}, "
                                f"unhealthy={status.get('unhealthy_tickers') or []})"
                            )
                        else:
                            self._subscription_error = None

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
                self._last_error = str(exc)
                self.log.warning("Futopt candle recorder failed to process message: %s", exc)
            finally:
                self._queue.task_done()

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
        self._last_persisted_at = str(row.get("date") or "") or datetime.now().astimezone().isoformat()
        self._last_error = None


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
