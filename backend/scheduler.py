import asyncio
import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, time as time_of_day, timedelta, tzinfo
from typing import Any, Callable, Optional

from fubon_quote_provider import build_fubon_quote_payload, fubon_timestamp_to_iso
from fubon_symbols import fubon_market_to_ticker


@dataclass(slots=True)
class SchedulerSettings:
    startup_download_enabled: bool
    institutional_auto_sync_enabled: bool
    taiwan_chip_auto_sync_enabled: bool
    latest_data_sync_on_startup: bool
    alert_evaluator_enabled: bool
    market_intelligence_sync_enabled: bool
    market_intelligence_startup_sync: bool
    alert_poll_interval_seconds: int
    app_tz: tzinfo
    daily_latest_sync_time: time_of_day
    startup_download_delay_seconds: float = 2.5
    futopt_recorder_enabled: bool = False
    futopt_recorder_poll_seconds: int = 30
    futopt_recorder_backfill_interval_seconds: int = 300


@dataclass(slots=True)
class SchedulerDependencies:
    startup_download_tickers: list[str]
    fetch_history_for_ticker: Any
    sync_institutional_snapshot: Any
    sync_taiwan_chip_snapshot: Any
    sync_tracked_market_data: Any
    fetch_and_store_quote_snapshot: Any
    evaluate_active_alerts: Any
    sync_market_intelligence_snapshot: Any
    get_subscribed_tickers: Any
    broadcast_to_ticker: Any
    store_quote_to_db: Any = None
    fubon_manager: Any = None
    skip_poll_for_ticker: Callable[[str], bool] | None = None
    archive_fubon_market_snapshot: Any = None
    futopt_candle_recorder: Any = None


async def startup_download(
    tickers: list[str],
    delay_seconds: float,
    fetch_history_for_ticker,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    log.info("Starting history download for %s tickers...", len(tickers))
    for index, ticker in enumerate(tickers):
        try:
            count = await fetch_history_for_ticker(ticker)
            if count:
                log.info("  %s: %s candle rows stored", ticker, count)
            else:
                log.warning("  %s: no history fetched, will retry on demand", ticker)
        except Exception as exc:
            log.warning("  %s download failed: %s", ticker, exc)
        if index < len(tickers) - 1:
            await asyncio.sleep(delay_seconds)
    log.info("History download finished")


async def startup_institutional_snapshot(sync_snapshot, logger: logging.Logger | None = None) -> None:
    log = logger or logging.getLogger(__name__)
    try:
        payload = await sync_snapshot()
        log.info(
            "Institutional snapshot ready: query=%s resolved=%s",
            payload.get("query_date"),
            payload.get("resolved_date"),
        )
    except Exception as exc:
        log.warning("Institutional snapshot sync failed: %s", exc)


async def daily_taiwan_chip_sync_loop(
    sync_snapshot,
    app_tz: tzinfo,
    daily_sync_time: time_of_day,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    try:
        payload = await sync_snapshot()
        log.info(
            "Taiwan chip snapshot ready: requested=%s resolved=%s rows=%s source=%s",
            payload.get("requested_date"),
            payload.get("resolved_date"),
            payload.get("row_count"),
            payload.get("source"),
        )
    except Exception as exc:
        log.warning("Startup Taiwan chip sync failed: %s", exc)

    while True:
        now = datetime.now(app_tz)
        next_run_date = now.date()
        next_run = datetime.combine(next_run_date, daily_sync_time, tzinfo=app_tz)
        if now >= next_run:
            next_run_date += timedelta(days=1)
            next_run = datetime.combine(next_run_date, daily_sync_time, tzinfo=app_tz)
        sleep_seconds = max(60, int((next_run - now).total_seconds()))
        await asyncio.sleep(sleep_seconds)
        target_date = datetime.now(app_tz).date()
        try:
            payload = await sync_snapshot(target_date)
            log.info(
                "Taiwan chip snapshot synced: requested=%s resolved=%s rows=%s source=%s",
                payload.get("requested_date"),
                payload.get("resolved_date"),
                payload.get("row_count"),
                payload.get("source"),
            )
        except Exception as exc:
            log.warning("Daily Taiwan chip sync failed: %s", exc)


async def daily_market_snapshot_sync_loop(
    archive_snapshot,
    app_tz: tzinfo,
    daily_sync_time: time_of_day,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(20) # Start slightly after latest_sync

    while True:
        now = datetime.now(app_tz)
        next_run_date = now.date()
        next_run = datetime.combine(next_run_date, daily_sync_time, tzinfo=app_tz)
        if now >= next_run:
            next_run_date += timedelta(days=1)
            next_run = datetime.combine(next_run_date, daily_sync_time, tzinfo=app_tz)
        
        sleep_seconds = max(60, int((next_run - now).total_seconds()))
        await asyncio.sleep(sleep_seconds)
        
        target_date = datetime.now(app_tz).strftime("%Y-%m-%d")
        try:
            for market in ["TSE", "OTC"]:
                success = await archive_snapshot(market, target_date)
                if success:
                    log.info("Fubon market %s snapshot achieved for %s", market, target_date)
                else:
                    log.warning("Fubon market %s snapshot skipped or failed for %s", market, target_date)
        except Exception as exc:
            log.warning("Daily Fubon market snapshot sync failed: %s", exc)


async def daily_latest_sync_loop(
    sync_tracked_market_data,
    app_tz: tzinfo,
    daily_latest_sync_time: time_of_day,
    latest_data_sync_on_startup: bool = True,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(15)
    if latest_data_sync_on_startup:
        try:
            await sync_tracked_market_data(reason="startup-latest")
        except Exception as exc:
            log.warning("Startup latest market sync failed: %s", exc)

    while True:
        now = datetime.now(app_tz)
        next_run_date = now.date()
        next_run = datetime.combine(next_run_date, daily_latest_sync_time, tzinfo=app_tz)
        if now >= next_run:
            next_run_date += timedelta(days=1)
            next_run = datetime.combine(next_run_date, daily_latest_sync_time, tzinfo=app_tz)
        sleep_seconds = max(60, int((next_run - now).total_seconds()))
        await asyncio.sleep(sleep_seconds)
        try:
            await sync_tracked_market_data(reason="daily-latest")
        except Exception as exc:
            log.warning("Daily latest market sync failed: %s", exc)


def _normalize_order_levels(levels: Any) -> list[dict]:
    if not isinstance(levels, list):
        return []
    normalized = []
    for item in levels[:5]:
        if not isinstance(item, dict):
            continue
        try:
            normalized.append(
                {
                    "price": float(item.get("price")) if item.get("price") is not None else None,
                    "size": int(item.get("size")) if item.get("size") is not None else None,
                }
            )
        except (TypeError, ValueError):
            continue
    return normalized


def _coerce_positive_float(value: Any) -> Optional[float]:
    try:
        numeric = float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
    return numeric if numeric is not None and numeric > 0 else None


def _resolve_fubon_ticker(market_type: str, payload: dict) -> Optional[str]:
    symbol = str(payload.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    if market_type == "stock":
        return fubon_market_to_ticker(symbol, payload.get("market"))
    return symbol


def _build_fubon_book_payload(ticker: str, payload: dict) -> dict:
    bids = _normalize_order_levels(payload.get("bids"))
    asks = _normalize_order_levels(payload.get("asks"))
    return {
        "ticker": ticker,
        "bid": bids[0].get("price") if bids else None,
        "ask": asks[0].get("price") if asks else None,
        "bid_size": bids[0].get("size") if bids else None,
        "ask_size": asks[0].get("size") if asks else None,
        "bids": bids,
        "asks": asks,
        "quote_timestamp": fubon_timestamp_to_iso(payload.get("time") or payload.get("lastUpdated")),
        "ts": int(time.time() * 1000),
    }


def _build_fubon_candle_payload(ticker: str, payload: dict) -> Optional[dict]:
    date_value = payload.get("date")
    if not date_value:
        return None
    close_price = _coerce_positive_float(payload.get("close"))
    if close_price is None:
        return None
    open_price = _coerce_positive_float(payload.get("open")) or close_price
    raw_high = _coerce_positive_float(payload.get("high"))
    raw_low = _coerce_positive_float(payload.get("low"))
    high_candidates = [value for value in [raw_high, open_price, close_price] if value is not None]
    low_candidates = [value for value in [raw_low, open_price, close_price] if value is not None]
    try:
        return {
            "ticker": ticker,
            "date": str(date_value).replace("Z", "+00:00"),
            "timeframe": str(payload.get("timeframe") or "1"),
            "open": open_price,
            "high": max(high_candidates),
            "low": min(low_candidates),
            "close": close_price,
            "volume": int(payload.get("volume") or 0),
            "average": float(payload.get("average")) if payload.get("average") is not None else None,
            "source": "fubon_neo",
            "ts": int(time.time() * 1000),
        }
    except (TypeError, ValueError):
        return None


async def fubon_ws_listener_loop(
    fubon_manager,
    broadcast_to_ticker,
    store_quote_to_db=None,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    if not fubon_manager:
        return

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def _on_fubon_message(message: dict) -> None:
        if loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(queue.put_nowait, message)
        except RuntimeError:
            return

    fubon_manager.register_message_handler(_on_fubon_message)
    try:
        await asyncio.sleep(3)
        if fubon_manager.connected:
            log.info("Fubon websocket listener is active")

        last_session_refresh = 0.0

        while True:
            refresh_sessions = getattr(fubon_manager, "refresh_session_assignments", None)
            if callable(refresh_sessions) and time.monotonic() - last_session_refresh >= 30:
                try:
                    await refresh_sessions()
                except Exception as exc:
                    log.debug("Fubon realtime session refresh skipped: %s", exc)
                last_session_refresh = time.monotonic()

            try:
                message = await asyncio.wait_for(queue.get(), timeout=60)
            except asyncio.TimeoutError:
                continue

            try:
                if str(message.get("event") or "").strip().lower() != "data":
                    continue
                raw = message.get("data")
                if not isinstance(raw, dict):
                    continue
                market_type = str(message.get("market_type") or "stock").strip().lower()
                channel = str(message.get("channel") or "").strip().lower()
                ticker = _resolve_fubon_ticker(market_type, raw)
                if not ticker or not channel:
                    continue
                target_tickers = [ticker]
                resolver = getattr(fubon_manager, "resolve_broadcast_tickers", None)
                if callable(resolver):
                    resolved_targets = [item for item in resolver(ticker) if item]
                    if resolved_targets:
                        target_tickers = resolved_targets

                if channel == "aggregates":
                    for target_ticker in target_tickers:
                        quote_payload = build_fubon_quote_payload(target_ticker, raw, source="fubon_neo")
                        if not quote_payload:
                            continue
                        if callable(store_quote_to_db):
                            await store_quote_to_db(quote_payload)
                        await broadcast_to_ticker(
                            target_ticker,
                            {
                                "type": "quote",
                                "ticker": target_ticker,
                                "data": quote_payload,
                                "ts": int(time.time() * 1000),
                            },
                        )
                    continue

                if channel == "trades":
                    for target_ticker in target_tickers:
                        quote_payload = build_fubon_quote_payload(target_ticker, raw, source="fubon_neo")
                        if not quote_payload:
                            continue
                        if callable(store_quote_to_db):
                            await store_quote_to_db(quote_payload)
                        await broadcast_to_ticker(
                            target_ticker,
                            {
                                "type": "quote",
                                "ticker": target_ticker,
                                "data": quote_payload,
                                "ts": int(time.time() * 1000),
                            },
                        )
                    continue

                if channel == "books":
                    for target_ticker in target_tickers:
                        await broadcast_to_ticker(
                            target_ticker,
                            {
                                "type": "books",
                                "ticker": target_ticker,
                                "data": _build_fubon_book_payload(target_ticker, raw),
                                "ts": int(time.time() * 1000),
                            },
                        )
                    continue

                if channel == "candles":
                    for target_ticker in target_tickers:
                        candle_payload = _build_fubon_candle_payload(target_ticker, raw)
                        if not candle_payload:
                            continue
                        await broadcast_to_ticker(
                            target_ticker,
                            {
                                "type": "candle",
                                "ticker": target_ticker,
                                "data": candle_payload,
                                "ts": int(time.time() * 1000),
                            },
                        )
            except Exception as exc:
                log.warning("Fubon websocket message handling failed: %s", exc)
                await asyncio.sleep(1)
    finally:
        unregister = getattr(fubon_manager, "unregister_message_handler", None)
        if callable(unregister):
            with suppress(Exception):
                unregister(_on_fubon_message)


async def realtime_polling_loop(
    get_subscribed_tickers,
    fetch_and_store_quote_snapshot,
    broadcast_to_ticker,
    *,
    use_fubon_ws: bool = False,
    skip_poll_for_ticker: Callable[[str], bool] | None = None,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(5)
    while True:
        subscribed = list(get_subscribed_tickers())
        if subscribed:
            for ticker in subscribed:
                if use_fubon_ws and callable(skip_poll_for_ticker) and skip_poll_for_ticker(ticker):
                    continue
                try:
                    quote = await fetch_and_store_quote_snapshot(ticker)
                    if quote:
                        await broadcast_to_ticker(
                            ticker,
                            {
                                "type": "quote",
                                "ticker": ticker,
                                "data": quote,
                                "ts": int(time.time() * 1000),
                            },
                        )
                except Exception as exc:
                    log.debug("quote error %s: %s", ticker, exc)
                await asyncio.sleep(0.2)
        await asyncio.sleep(15)


async def alert_evaluator_loop(
    evaluate_active_alerts,
    poll_interval_seconds: int,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(10)
    while True:
        try:
            triggered = await evaluate_active_alerts()
            if triggered:
                log.info("Alert evaluator triggered %s alert(s)", triggered)
        except Exception as exc:
            log.warning("Alert evaluator loop failed: %s", exc)
        await asyncio.sleep(poll_interval_seconds)


async def market_intelligence_sync_loop(
    sync_market_intelligence_snapshot,
    startup_sync_enabled: bool = True,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(12)
    if startup_sync_enabled:
        try:
            summary = await sync_market_intelligence_snapshot(reason="startup-market-intelligence")
            log.info("Market intelligence startup sync finished: %s", summary)
        except Exception as exc:
            log.warning("Market intelligence startup sync failed: %s", exc)
    while True:
        await asyncio.sleep(6 * 60 * 60)
        try:
            summary = await sync_market_intelligence_snapshot(reason="scheduled-market-intelligence")
            log.info("Market intelligence scheduled sync finished: %s", summary)
        except Exception as exc:
            log.warning("Market intelligence scheduled sync failed: %s", exc)


class BackgroundScheduler:
    def __init__(
        self,
        settings: SchedulerSettings,
        dependencies: SchedulerDependencies,
        logger: logging.Logger | None = None,
    ):
        self._settings = settings
        self._deps = dependencies
        self._log = logger or logging.getLogger(__name__)
        self._tasks: list[asyncio.Task] = []

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    def health_summary(self) -> dict:
        tasks = [
            {
                "name": task.get_name().replace("quantvision:", "", 1),
                "done": task.done(),
                "cancelled": task.cancelled(),
            }
            for task in self._tasks
        ]
        return {
            "running": bool(self._tasks),
            "task_count": len(self._tasks),
            "active_count": sum(1 for task in self._tasks if not task.done()),
            "tasks": tasks,
        }

    def start(self) -> None:
        if self._tasks:
            return

        if self._settings.startup_download_enabled:
            self._create_task(
                "startup-download",
                startup_download(
                    tickers=self._deps.startup_download_tickers,
                    delay_seconds=self._settings.startup_download_delay_seconds,
                    fetch_history_for_ticker=self._deps.fetch_history_for_ticker,
                    logger=self._log,
                ),
            )
        else:
            self._log.info("Startup Yahoo history prefetch skipped (STARTUP_DOWNLOAD_ENABLED=false).")

        if self._settings.institutional_auto_sync_enabled:
            self._create_task(
                "startup-institutional-sync",
                startup_institutional_snapshot(
                    sync_snapshot=self._deps.sync_institutional_snapshot,
                    logger=self._log,
                ),
            )
        else:
            self._log.info("Startup institutional snapshot sync skipped (INSTITUTIONAL_AUTO_SYNC_ENABLED=false).")

        if self._settings.taiwan_chip_auto_sync_enabled and self._deps.sync_taiwan_chip_snapshot:
            self._create_task(
                "taiwan-chip-sync",
                daily_taiwan_chip_sync_loop(
                    sync_snapshot=self._deps.sync_taiwan_chip_snapshot,
                    app_tz=self._settings.app_tz,
                    daily_sync_time=self._settings.daily_latest_sync_time,
                    logger=self._log,
                ),
            )
        else:
            self._log.info("Taiwan chip auto sync skipped (TAIWAN_CHIP_AUTO_SYNC_ENABLED=false).")

        if self._deps.archive_fubon_market_snapshot:
            self._create_task(
                "fubon-market-snapshot-sync",
                daily_market_snapshot_sync_loop(
                    archive_snapshot=self._deps.archive_fubon_market_snapshot,
                    app_tz=self._settings.app_tz,
                    daily_sync_time=self._settings.daily_latest_sync_time,
                    logger=self._log,
                ),
            )

        self._create_task(
            "daily-latest-sync",
            daily_latest_sync_loop(
                sync_tracked_market_data=self._deps.sync_tracked_market_data,
                app_tz=self._settings.app_tz,
                daily_latest_sync_time=self._settings.daily_latest_sync_time,
                latest_data_sync_on_startup=self._settings.latest_data_sync_on_startup,
                logger=self._log,
            ),
        )
        self._create_task(
            "realtime-polling",
            realtime_polling_loop(
                get_subscribed_tickers=self._deps.get_subscribed_tickers,
                fetch_and_store_quote_snapshot=self._deps.fetch_and_store_quote_snapshot,
                broadcast_to_ticker=self._deps.broadcast_to_ticker,
                use_fubon_ws=bool(self._deps.fubon_manager),
                skip_poll_for_ticker=self._deps.skip_poll_for_ticker,
                logger=self._log,
            ),
        )

        if self._deps.fubon_manager:
            self._create_task(
                "fubon-ws-listener",
                fubon_ws_listener_loop(
                    fubon_manager=self._deps.fubon_manager,
                    broadcast_to_ticker=self._deps.broadcast_to_ticker,
                    store_quote_to_db=self._deps.store_quote_to_db,
                    logger=self._log,
                ),
            )

        if self._settings.futopt_recorder_enabled and self._deps.futopt_candle_recorder:
            self._create_task(
                "futopt-candle-recorder",
                self._deps.futopt_candle_recorder.run(
                    app_tz=self._settings.app_tz,
                    poll_seconds=self._settings.futopt_recorder_poll_seconds,
                    backfill_interval_seconds=self._settings.futopt_recorder_backfill_interval_seconds,
                ),
            )
        else:
            self._log.info("Futopt candle recorder skipped (FUTOPT_RECORDER_ENABLED=false).")

        if self._settings.alert_evaluator_enabled:
            self._create_task(
                "alert-evaluator",
                alert_evaluator_loop(
                    evaluate_active_alerts=self._deps.evaluate_active_alerts,
                    poll_interval_seconds=self._settings.alert_poll_interval_seconds,
                    logger=self._log,
                ),
            )
        else:
            self._log.info("Alert evaluator skipped (ALERT_EVALUATOR_ENABLED=false).")

        if self._settings.market_intelligence_sync_enabled:
            self._create_task(
                "market-intelligence-sync",
                market_intelligence_sync_loop(
                    sync_market_intelligence_snapshot=self._deps.sync_market_intelligence_snapshot,
                    startup_sync_enabled=self._settings.market_intelligence_startup_sync,
                    logger=self._log,
                ),
            )
        else:
            self._log.info("Market intelligence sync skipped (MARKET_INTELLIGENCE_SYNC_ENABLED=false).")

    async def shutdown(self) -> None:
        for task in self._tasks:
            if not task.done():
                task.cancel()
        for task in self._tasks:
            with suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

    def _create_task(self, name: str, coroutine) -> asyncio.Task:
        task = asyncio.create_task(coroutine, name=f"quantvision:{name}")
        self._tasks.append(task)
        return task
