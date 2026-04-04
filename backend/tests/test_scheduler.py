from datetime import time, timezone
import asyncio

import pytest

from scheduler import BackgroundScheduler, SchedulerDependencies, SchedulerSettings


@pytest.mark.asyncio
async def test_scheduler_starts_enabled_tasks_and_shutdowns():
    events = []

    async def fetch_history_for_ticker(ticker):
        events.append(("history", ticker))
        await asyncio.sleep(0)
        return 24

    async def sync_institutional_snapshot():
        events.append(("institutional",))
        await asyncio.sleep(0)
        return {"query_date": "2026-04-04", "resolved_date": "2026-04-03"}

    async def sync_tracked_market_data(**kwargs):
        events.append(("sync", kwargs.get("reason")))
        await asyncio.sleep(0)
        return {"reason": kwargs.get("reason")}

    async def fetch_and_store_quote_snapshot(_ticker):
        return None

    async def evaluate_active_alerts():
        return 0

    async def sync_market_intelligence_snapshot(**kwargs):
        events.append(("market-intelligence", kwargs.get("reason")))
        await asyncio.sleep(0)
        return {"reason": kwargs.get("reason")}

    def get_subscribed_tickers():
        return []

    async def broadcast_to_ticker(_ticker, _payload):
        return None

    scheduler = BackgroundScheduler(
        settings=SchedulerSettings(
            startup_download_enabled=True,
            institutional_auto_sync_enabled=True,
            latest_data_sync_on_startup=False,
            alert_evaluator_enabled=True,
            market_intelligence_sync_enabled=True,
            market_intelligence_startup_sync=False,
            alert_poll_interval_seconds=3600,
            app_tz=timezone.utc,
            daily_latest_sync_time=time(23, 59),
            startup_download_delay_seconds=0,
        ),
        dependencies=SchedulerDependencies(
            startup_download_tickers=["AAPL"],
            fetch_history_for_ticker=fetch_history_for_ticker,
            sync_institutional_snapshot=sync_institutional_snapshot,
            sync_tracked_market_data=sync_tracked_market_data,
            fetch_and_store_quote_snapshot=fetch_and_store_quote_snapshot,
            evaluate_active_alerts=evaluate_active_alerts,
            sync_market_intelligence_snapshot=sync_market_intelligence_snapshot,
            get_subscribed_tickers=get_subscribed_tickers,
            broadcast_to_ticker=broadcast_to_ticker,
        ),
    )

    scheduler.start()
    await asyncio.sleep(0.05)

    assert scheduler.task_count == 6
    assert ("history", "AAPL") in events
    assert ("institutional",) in events

    await scheduler.shutdown()

    assert scheduler.task_count == 0


@pytest.mark.asyncio
async def test_scheduler_skips_optional_jobs_when_disabled():
    async def noop_async(*_args, **_kwargs):
        await asyncio.sleep(0)
        return {}

    scheduler = BackgroundScheduler(
        settings=SchedulerSettings(
            startup_download_enabled=False,
            institutional_auto_sync_enabled=False,
            latest_data_sync_on_startup=False,
            alert_evaluator_enabled=False,
            market_intelligence_sync_enabled=False,
            market_intelligence_startup_sync=False,
            alert_poll_interval_seconds=3600,
            app_tz=timezone.utc,
            daily_latest_sync_time=time(23, 59),
        ),
        dependencies=SchedulerDependencies(
            startup_download_tickers=[],
            fetch_history_for_ticker=noop_async,
            sync_institutional_snapshot=noop_async,
            sync_tracked_market_data=noop_async,
            fetch_and_store_quote_snapshot=noop_async,
            evaluate_active_alerts=noop_async,
            sync_market_intelligence_snapshot=noop_async,
            get_subscribed_tickers=lambda: [],
            broadcast_to_ticker=noop_async,
        ),
    )

    scheduler.start()

    assert scheduler.task_count == 2

    await scheduler.shutdown()

    assert scheduler.task_count == 0
