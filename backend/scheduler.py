import asyncio
import inspect
import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, time as time_of_day, timedelta, tzinfo
from typing import Any, Callable, Optional

from fubon_quote_provider import build_fubon_quote_payload, fubon_timestamp_to_iso
from fubon_symbols import fubon_market_to_ticker
from realtime_performance import realtime_performance_metrics


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
    tracked_market_sync_time: time_of_day | None = None
    taiwan_chip_sync_time: time_of_day | None = None
    fubon_market_snapshot_sync_time: time_of_day | None = None
    institutional_sync_time: time_of_day | None = None
    paper_margin_sync_time: time_of_day | None = None
    market_intelligence_sync_interval_seconds: int = 6 * 60 * 60
    realtime_poll_interval_seconds: float = 15.0
    realtime_per_ticker_delay_seconds: float = 0.2
    fubon_ws_session_refresh_seconds: float = 30.0
    latest_sync_startup_delay_seconds: float = 15.0
    fubon_market_snapshot_startup_delay_seconds: float = 20.0
    tw_full_history_startup_delay_seconds: float = 35.0
    paper_margin_startup_delay_seconds: float = 25.0
    realtime_poll_startup_delay_seconds: float = 5.0
    alert_startup_delay_seconds: float = 10.0
    market_intelligence_startup_delay_seconds: float = 12.0
    startup_download_delay_seconds: float = 2.5
    futopt_recorder_enabled: bool = False
    futopt_recorder_poll_seconds: int = 30
    futopt_recorder_backfill_interval_seconds: int = 300
    paper_margin_auto_sync_enabled: bool = True
    tw_full_history_sync_enabled: bool = False
    tw_full_history_sync_start_time: time_of_day = time_of_day(14, 0)
    tw_full_history_sync_stop_time: time_of_day = time_of_day(8, 0)
    tw_full_history_retry_interval_seconds: int = 1800
    tw_full_history_retry_min_latest_coverage_pct: float = 80.0
    auto_backup_enabled: bool = False
    auto_backup_scope: str = "critical"
    auto_backup_interval_hours: float = 24.0
    auto_backup_max_age_hours: float = 36.0
    auto_backup_initial_delay_seconds: float = 300.0


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
    sync_paper_trading_margins: Any = None
    sync_taiwan_full_history: Any = None
    get_taiwan_analysis_kline_coverage: Any = None
    create_mysql_backup: Any = None
    get_mysql_backup_status: Any = None


async def automatic_mysql_backup_loop(
    *,
    create_backup,
    get_backup_status,
    interval_hours: float,
    initial_delay_seconds: float,
    record_result=None,
    logger: logging.Logger | None = None,
) -> None:
    """Keep a recent verified backup without blocking the event loop."""
    log = logger or logging.getLogger(__name__)
    if initial_delay_seconds > 0:
        await asyncio.sleep(initial_delay_seconds)
    while True:
        started = time.perf_counter()
        try:
            status = await asyncio.to_thread(get_backup_status)
            created = None
            if not status.get("healthy"):
                created = await asyncio.to_thread(create_backup)
                status = await asyncio.to_thread(get_backup_status)
            details = {
                "created": bool(created),
                "backup_id": (created or status).get("backup_id"),
                "scope": (created or status).get("scope"),
                "age_hours": status.get("age_hours"),
            }
            if record_result:
                record_result("mysql-auto-backup", success=True, duration_seconds=time.perf_counter() - started, details=details)
            log.info("Automatic MySQL backup check finished: %s", details)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if record_result:
                record_result(
                    "mysql-auto-backup",
                    success=False,
                    duration_seconds=time.perf_counter() - started,
                    error=str(exc),
                )
            log.exception("Automatic MySQL backup failed: %s", exc)
        await asyncio.sleep(max(60.0, float(interval_hours) * 3600.0))


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


async def daily_institutional_sync_loop(
    sync_snapshot,
    app_tz: tzinfo,
    daily_sync_time: time_of_day,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await startup_institutional_snapshot(sync_snapshot, log)

    while True:
        now = datetime.now(app_tz)
        next_run_date = now.date()
        next_run = datetime.combine(next_run_date, daily_sync_time, tzinfo=app_tz)
        if now >= next_run:
            next_run_date += timedelta(days=1)
            next_run = datetime.combine(next_run_date, daily_sync_time, tzinfo=app_tz)
        sleep_seconds = max(60, int((next_run - now).total_seconds()))
        await asyncio.sleep(sleep_seconds)
        try:
            payload = await sync_snapshot()
            log.info(
                "Institutional snapshot daily sync finished: query=%s resolved=%s",
                payload.get("query_date"),
                payload.get("resolved_date"),
            )
        except Exception as exc:
            log.warning("Daily institutional snapshot sync failed: %s", exc)


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
    startup_delay_seconds: float = 20.0,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(max(0, startup_delay_seconds))

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
    startup_delay_seconds: float = 15.0,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(max(0, startup_delay_seconds))
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


def _next_daily_window_start(now: datetime, start_time: time_of_day) -> datetime:
    candidate = datetime.combine(now.date(), start_time, tzinfo=now.tzinfo)
    if now >= candidate:
        candidate += timedelta(days=1)
    return candidate


def _window_stop_after(start_at: datetime, stop_time: time_of_day) -> datetime:
    stop_at = datetime.combine(start_at.date(), stop_time, tzinfo=start_at.tzinfo)
    if stop_at <= start_at:
        stop_at += timedelta(days=1)
    return stop_at


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _tw_history_retry_needed(
    coverage: dict | None,
    *,
    target_date: str,
    min_latest_coverage_pct: float,
) -> bool:
    if not isinstance(coverage, dict):
        return True
    latest_date = str(
        coverage.get("expected_latest_date")
        or coverage.get("newest_latest_date")
        or ""
    )[:10]
    latest_pct = _safe_float(coverage.get("latest_coverage_pct"))
    if latest_pct is None:
        latest_pct = _safe_float(coverage.get("coverage_pct"))
    if latest_date != target_date:
        return True
    return latest_pct is None or latest_pct < min_latest_coverage_pct


async def _fetch_tw_history_retry_coverage(get_coverage, summary: dict | None) -> dict | None:
    if callable(get_coverage):
        return await get_coverage("1d")
    if isinstance(summary, dict):
        coverage = summary.get("analysis_coverage") or summary.get("coverage")
        return coverage if isinstance(coverage, dict) else None
    return None


async def taiwan_full_history_sync_loop(
    sync_taiwan_full_history,
    app_tz: tzinfo,
    start_time: time_of_day,
    stop_time: time_of_day,
    startup_delay_seconds: float = 35.0,
    retry_interval_seconds: int = 1800,
    min_latest_coverage_pct: float = 80.0,
    get_analysis_coverage=None,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(max(0, startup_delay_seconds))

    while True:
        now = datetime.now(app_tz)
        start_at = _next_daily_window_start(now, start_time)
        sleep_seconds = max(60, int((start_at - now).total_seconds()))
        await asyncio.sleep(sleep_seconds)

        run_started_at = datetime.now(app_tz)
        stop_at = _window_stop_after(run_started_at, stop_time)
        target_date = run_started_at.date().isoformat()
        attempt = 1

        while datetime.now(app_tz) < stop_at:
            summary = None
            try:
                summary = await sync_taiwan_full_history(
                    reason="scheduled-tw-full-history" if attempt == 1 else "scheduled-tw-full-history-retry",
                    stop_at=stop_at,
                )
                log.info("Taiwan full history sync attempt %s finished: %s", attempt, summary)
            except Exception as exc:
                log.warning("Taiwan full history sync attempt %s failed: %s", attempt, exc)

            try:
                coverage = await _fetch_tw_history_retry_coverage(get_analysis_coverage, summary)
            except Exception as exc:
                coverage = None
                log.warning("Taiwan full history coverage check failed after attempt %s: %s", attempt, exc)

            if not _tw_history_retry_needed(
                coverage,
                target_date=target_date,
                min_latest_coverage_pct=min_latest_coverage_pct,
            ):
                log.info(
                    "Taiwan full history coverage ready for %s after attempt %s: %s",
                    target_date,
                    attempt,
                    coverage,
                )
                break

            if retry_interval_seconds <= 0:
                log.info("Taiwan full history retry disabled; latest coverage after attempt %s: %s", attempt, coverage)
                break

            next_retry_at = datetime.now(app_tz) + timedelta(seconds=retry_interval_seconds)
            if next_retry_at >= stop_at:
                log.warning(
                    "Taiwan full history still not ready for %s, but retry window closes at %s: %s",
                    target_date,
                    stop_at.isoformat(),
                    coverage,
                )
                break

            log.warning(
                "Taiwan full history not ready for %s after attempt %s; retrying in %ss. Coverage=%s",
                target_date,
                attempt,
                retry_interval_seconds,
                coverage,
            )
            await asyncio.sleep(retry_interval_seconds)
            attempt += 1


async def daily_paper_margin_sync_loop(
    sync_paper_trading_margins,
    app_tz: tzinfo,
    daily_sync_time: time_of_day,
    startup_delay_seconds: float = 25.0,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(max(0, startup_delay_seconds))
    try:
        summary = await sync_paper_trading_margins(reason="startup-paper-margin")
        log.info("Paper trading margin startup sync finished: %s", summary)
    except Exception as exc:
        log.warning("Startup paper trading margin sync failed: %s", exc)

    while True:
        now = datetime.now(app_tz)
        next_run_date = now.date()
        next_run = datetime.combine(next_run_date, daily_sync_time, tzinfo=app_tz)
        if now >= next_run:
            next_run_date += timedelta(days=1)
            next_run = datetime.combine(next_run_date, daily_sync_time, tzinfo=app_tz)
        sleep_seconds = max(60, int((next_run - now).total_seconds()))
        await asyncio.sleep(sleep_seconds)
        try:
            summary = await sync_paper_trading_margins(reason="daily-paper-margin")
            log.info("Paper trading margin daily sync finished: %s", summary)
        except Exception as exc:
            log.warning("Daily paper trading margin sync failed: %s", exc)


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
    session_refresh_seconds: float = 30.0,
    logger: logging.Logger | None = None,
    performance_metrics=None,
) -> None:
    log = logger or logging.getLogger(__name__)
    if not fubon_manager:
        return

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    metrics = performance_metrics or realtime_performance_metrics

    def _on_fubon_message(message: dict) -> None:
        if loop.is_closed():
            return
        received_at = time.perf_counter()

        def _enqueue() -> None:
            queue.put_nowait((received_at, message))
            metrics.record_ingress(message.get("channel"), queue.qsize())

        try:
            loop.call_soon_threadsafe(_enqueue)
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
            if callable(refresh_sessions) and time.monotonic() - last_session_refresh >= session_refresh_seconds:
                try:
                    await refresh_sessions()
                except Exception as exc:
                    log.debug("Fubon realtime session refresh skipped: %s", exc)
                last_session_refresh = time.monotonic()

            try:
                received_at, message = await asyncio.wait_for(queue.get(), timeout=60)
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
                recorder = getattr(fubon_manager, "record_ws_message", None)
                if callable(recorder):
                    diagnostic_channel = "quote" if channel in {"aggregates", "trades"} else channel
                    recorder(
                        ticker,
                        diagnostic_channel,
                        market_type=market_type,
                        account_id=message.get("account_id"),
                        target_tickers=tuple(target_tickers),
                    )

                if channel == "aggregates":
                    for target_ticker in target_tickers:
                        quote_payload = build_fubon_quote_payload(target_ticker, raw, source="fubon_neo")
                        if not quote_payload:
                            continue
                        await broadcast_to_ticker(
                            target_ticker,
                            {
                                "type": "quote",
                                "ticker": target_ticker,
                                "data": quote_payload,
                                "ts": int(time.time() * 1000),
                            },
                        )
                        metrics.record_broadcast((time.perf_counter() - received_at) * 1000)
                        if callable(store_quote_to_db):
                            await store_quote_to_db(quote_payload)
                    continue

                if channel == "trades":
                    for target_ticker in target_tickers:
                        quote_payload = build_fubon_quote_payload(target_ticker, raw, source="fubon_neo")
                        if not quote_payload:
                            continue
                        await broadcast_to_ticker(
                            target_ticker,
                            {
                                "type": "quote",
                                "ticker": target_ticker,
                                "data": quote_payload,
                                "ts": int(time.time() * 1000),
                            },
                        )
                        metrics.record_broadcast((time.perf_counter() - received_at) * 1000)
                        if callable(store_quote_to_db):
                            await store_quote_to_db(quote_payload)
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
                        metrics.record_broadcast((time.perf_counter() - received_at) * 1000)
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
                        metrics.record_broadcast((time.perf_counter() - received_at) * 1000)
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
    poll_interval_seconds: float = 15.0,
    per_ticker_delay_seconds: float = 0.2,
    startup_delay_seconds: float = 5.0,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(max(0, startup_delay_seconds))
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
                await asyncio.sleep(max(0, per_ticker_delay_seconds))
        await asyncio.sleep(max(1, poll_interval_seconds))


async def alert_evaluator_loop(
    evaluate_active_alerts,
    poll_interval_seconds: int,
    startup_delay_seconds: float = 10.0,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(max(0, startup_delay_seconds))
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
    interval_seconds: int = 6 * 60 * 60,
    startup_delay_seconds: float = 12.0,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(max(0, startup_delay_seconds))
    if startup_sync_enabled:
        try:
            summary = await sync_market_intelligence_snapshot(reason="startup-market-intelligence")
            log.info("Market intelligence startup sync finished: %s", summary)
        except Exception as exc:
            log.warning("Market intelligence startup sync failed: %s", exc)
    while True:
        await asyncio.sleep(max(60, int(interval_seconds)))
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
        self._task_states: dict[str, dict[str, Any]] = {}
        self._job_runs: dict[str, dict[str, Any]] = {}

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    def health_summary(self) -> dict:
        tasks = []
        for task in self._tasks:
            name = task.get_name().replace("quantvision:", "", 1)
            tasks.append({
                "name": name,
                "done": task.done(),
                "cancelled": task.cancelled(),
                **self._task_states.get(name, {}),
            })
        failed_count = sum(1 for item in tasks if item.get("state") == "failed")
        unexpected_stopped_count = sum(
            1 for item in tasks
            if item.get("persistent") and item.get("state") == "completed"
        )
        active_count = sum(1 for task in self._tasks if not task.done())
        return {
            "running": active_count > 0,
            "task_count": len(self._tasks),
            "active_count": active_count,
            "failed_count": failed_count,
            "unexpected_stopped_count": unexpected_stopped_count,
            "tasks": tasks,
            "jobs": dict(self._job_runs),
        }

    def record_job_result(
        self,
        name: str,
        *,
        success: bool,
        duration_seconds: float,
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        finished_at = datetime.now().astimezone().isoformat()
        previous = self._job_runs.get(name, {})
        self._job_runs[name] = {
            **previous,
            "last_run_at": finished_at,
            "last_duration_seconds": round(max(0.0, duration_seconds), 3),
            "last_success_at": finished_at if success else previous.get("last_success_at"),
            "last_failure_at": finished_at if not success else previous.get("last_failure_at"),
            "last_error": None if success else str(error or "unknown error")[:500],
            "details": details or {},
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
                persistent=False,
            )
        else:
            self._log.info("Startup Yahoo history prefetch skipped (STARTUP_DOWNLOAD_ENABLED=false).")

        if self._settings.institutional_auto_sync_enabled:
            self._create_task(
                "institutional-sync",
                daily_institutional_sync_loop(
                    sync_snapshot=self._deps.sync_institutional_snapshot,
                    app_tz=self._settings.app_tz,
                    daily_sync_time=self._settings.institutional_sync_time or self._settings.daily_latest_sync_time,
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
                    daily_sync_time=self._settings.taiwan_chip_sync_time or self._settings.daily_latest_sync_time,
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
                    daily_sync_time=self._settings.fubon_market_snapshot_sync_time
                    or self._settings.daily_latest_sync_time,
                    startup_delay_seconds=self._settings.fubon_market_snapshot_startup_delay_seconds,
                    logger=self._log,
                ),
            )

        self._create_task(
            "daily-latest-sync",
            daily_latest_sync_loop(
                sync_tracked_market_data=self._deps.sync_tracked_market_data,
                app_tz=self._settings.app_tz,
                daily_latest_sync_time=self._settings.tracked_market_sync_time
                or self._settings.daily_latest_sync_time,
                latest_data_sync_on_startup=self._settings.latest_data_sync_on_startup,
                startup_delay_seconds=self._settings.latest_sync_startup_delay_seconds,
                logger=self._log,
            ),
        )
        if self._settings.tw_full_history_sync_enabled and self._deps.sync_taiwan_full_history:
            self._create_task(
                "tw-full-history-sync",
                taiwan_full_history_sync_loop(
                    sync_taiwan_full_history=self._deps.sync_taiwan_full_history,
                    app_tz=self._settings.app_tz,
                    start_time=self._settings.tw_full_history_sync_start_time,
                    stop_time=self._settings.tw_full_history_sync_stop_time,
                    startup_delay_seconds=self._settings.tw_full_history_startup_delay_seconds,
                    retry_interval_seconds=self._settings.tw_full_history_retry_interval_seconds,
                    min_latest_coverage_pct=self._settings.tw_full_history_retry_min_latest_coverage_pct,
                    get_analysis_coverage=self._deps.get_taiwan_analysis_kline_coverage,
                    logger=self._log,
                ),
            )
        else:
            self._log.info("Taiwan full history sync skipped (TW_FULL_HISTORY_SYNC_ENABLED=false).")
        self._create_task(
            "realtime-polling",
            realtime_polling_loop(
                get_subscribed_tickers=self._deps.get_subscribed_tickers,
                fetch_and_store_quote_snapshot=self._deps.fetch_and_store_quote_snapshot,
                broadcast_to_ticker=self._deps.broadcast_to_ticker,
                use_fubon_ws=bool(self._deps.fubon_manager),
                skip_poll_for_ticker=self._deps.skip_poll_for_ticker,
                poll_interval_seconds=self._settings.realtime_poll_interval_seconds,
                per_ticker_delay_seconds=self._settings.realtime_per_ticker_delay_seconds,
                startup_delay_seconds=self._settings.realtime_poll_startup_delay_seconds,
                logger=self._log,
            ),
        )

        if self._settings.paper_margin_auto_sync_enabled and self._deps.sync_paper_trading_margins:
            self._create_task(
                "paper-margin-sync",
                daily_paper_margin_sync_loop(
                    sync_paper_trading_margins=self._deps.sync_paper_trading_margins,
                    app_tz=self._settings.app_tz,
                    daily_sync_time=self._settings.paper_margin_sync_time or self._settings.daily_latest_sync_time,
                    startup_delay_seconds=self._settings.paper_margin_startup_delay_seconds,
                    logger=self._log,
                ),
            )
        else:
            self._log.info("Paper trading margin auto sync skipped (PAPER_MARGIN_AUTO_SYNC_ENABLED=false).")

        if self._deps.fubon_manager:
            self._create_task(
                "fubon-ws-listener",
                fubon_ws_listener_loop(
                    fubon_manager=self._deps.fubon_manager,
                    broadcast_to_ticker=self._deps.broadcast_to_ticker,
                    store_quote_to_db=self._deps.store_quote_to_db,
                    session_refresh_seconds=self._settings.fubon_ws_session_refresh_seconds,
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
                    startup_delay_seconds=self._settings.alert_startup_delay_seconds,
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
                    interval_seconds=self._settings.market_intelligence_sync_interval_seconds,
                    startup_delay_seconds=self._settings.market_intelligence_startup_delay_seconds,
                    logger=self._log,
                ),
            )
        else:
            self._log.info("Market intelligence sync skipped (MARKET_INTELLIGENCE_SYNC_ENABLED=false).")

        if (
            self._settings.auto_backup_enabled
            and self._deps.create_mysql_backup
            and self._deps.get_mysql_backup_status
        ):
            self._create_task(
                "mysql-auto-backup",
                automatic_mysql_backup_loop(
                    create_backup=self._deps.create_mysql_backup,
                    get_backup_status=self._deps.get_mysql_backup_status,
                    interval_hours=self._settings.auto_backup_interval_hours,
                    initial_delay_seconds=self._settings.auto_backup_initial_delay_seconds,
                    record_result=self.record_job_result,
                    logger=self._log,
                ),
            )
        else:
            self._log.info("Automatic MySQL backup skipped (AUTO_BACKUP_ENABLED=false or backup dependencies unavailable).")

    async def shutdown(self) -> None:
        for task in self._tasks:
            if not task.done():
                task.cancel()
        for task in self._tasks:
            # Failures are already logged and retained in task telemetry.
            with suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()

    def _create_task(self, name: str, coroutine, *, persistent: bool = True) -> asyncio.Task:
        async def tracked():
            state = self._task_states[name]
            state["state"] = "running"
            state["started_at"] = datetime.now().astimezone().isoformat()
            try:
                result = await coroutine
                state["state"] = "completed"
                return result
            except asyncio.CancelledError:
                state["state"] = "cancelled"
                raise
            except Exception as exc:
                state["state"] = "failed"
                state["last_error"] = str(exc)[:500]
                self._log.exception("Background task %s stopped unexpectedly: %s", name, exc)
                raise
            finally:
                state["stopped_at"] = datetime.now().astimezone().isoformat()

        self._task_states[name] = {
            "state": "scheduled",
            "persistent": bool(persistent),
            "started_at": None,
            "stopped_at": None,
            "last_error": None,
        }
        task = asyncio.create_task(tracked(), name=f"quantvision:{name}")

        def consume_result(finished: asyncio.Task) -> None:
            if finished.cancelled():
                # A task can be cancelled before ``tracked`` gets its first turn.
                # Explicitly close the original coroutine to avoid leaking it.
                if self._task_states[name]["state"] == "scheduled" and inspect.iscoroutine(coroutine):
                    coroutine.close()
                return
            finished.exception()

        task.add_done_callback(consume_result)
        self._tasks.append(task)
        return task
