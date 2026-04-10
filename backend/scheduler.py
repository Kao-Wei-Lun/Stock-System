import asyncio
import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, time as time_of_day, timedelta, tzinfo
from typing import Any


@dataclass(slots=True)
class SchedulerSettings:
    startup_download_enabled: bool
    institutional_auto_sync_enabled: bool
    latest_data_sync_on_startup: bool
    alert_evaluator_enabled: bool
    market_intelligence_sync_enabled: bool
    market_intelligence_startup_sync: bool
    alert_poll_interval_seconds: int
    app_tz: tzinfo
    daily_latest_sync_time: time_of_day
    startup_download_delay_seconds: float = 2.5


@dataclass(slots=True)
class SchedulerDependencies:
    startup_download_tickers: list[str]
    fetch_history_for_ticker: Any
    sync_institutional_snapshot: Any
    sync_tracked_market_data: Any
    fetch_and_store_quote_snapshot: Any
    evaluate_active_alerts: Any
    sync_market_intelligence_snapshot: Any
    get_subscribed_tickers: Any
    broadcast_to_ticker: Any


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


async def realtime_polling_loop(
    get_subscribed_tickers,
    fetch_and_store_quote_snapshot,
    broadcast_to_ticker,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger(__name__)
    await asyncio.sleep(5)
    while True:
        subscribed = list(get_subscribed_tickers())
        if subscribed:
            for ticker in subscribed:
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
                logger=self._log,
            ),
        )

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
