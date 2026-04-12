from datetime import time, timezone
import asyncio

import pytest

from scheduler import (
    BackgroundScheduler,
    SchedulerDependencies,
    SchedulerSettings,
    fubon_ws_listener_loop,
)


@pytest.mark.anyio
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


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_fubon_ws_listener_broadcasts_quote_and_books_messages():
    messages = []
    stored_quotes = []

    async def broadcast_to_ticker(ticker, payload):
        messages.append((ticker, payload))

    async def store_quote_to_db(payload):
        stored_quotes.append(payload)
        return payload

    class FakeFubonManager:
        def __init__(self):
            self.connected = True
            self.handler = None
            self.unregistered = None
            self.start_stock_calls = 0
            self.start_futopt_calls = 0

        def register_message_handler(self, handler):
            self.handler = handler

        def unregister_message_handler(self, handler):
            self.unregistered = handler

        def start_ws_stock(self):
            self.start_stock_calls += 1
            return True

        def start_ws_futopt(self):
            self.start_futopt_calls += 1
            return True

    manager = FakeFubonManager()
    task = asyncio.create_task(
        fubon_ws_listener_loop(
            fubon_manager=manager,
            broadcast_to_ticker=broadcast_to_ticker,
            store_quote_to_db=store_quote_to_db,
        )
    )

    await asyncio.sleep(3.1)
    manager.handler(
        {
            "event": "data",
            "market_type": "stock",
            "channel": "aggregates",
            "data": {
                "symbol": "2330",
                "market": "TSE",
                "exchange": "TWSE",
                "name": "台積電",
                "previousClose": 810,
                "openPrice": 815,
                "highPrice": 818,
                "lowPrice": 812,
                "closePrice": 817,
                "change": 7,
                "changePercent": 0.86,
                "bids": [{"price": 816, "size": 21}],
                "asks": [{"price": 817, "size": 15}],
                "total": {"tradeVolume": 12345},
                "lastUpdated": 1712805300000000,
            },
        }
    )
    manager.handler(
        {
            "event": "data",
            "market_type": "stock",
            "channel": "books",
            "data": {
                "symbol": "2330",
                "market": "TSE",
                "bids": [{"price": 816, "size": 21}],
                "asks": [{"price": 817, "size": 15}],
                "time": 1712805300000000,
            },
        }
    )

    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert manager.unregistered is manager.handler
    assert manager.start_stock_calls == 0
    assert manager.start_futopt_calls == 0
    assert stored_quotes[0]["ticker"] == "2330.TW"
    assert stored_quotes[0]["is_delayed"] is False
    assert messages[0][0] == "2330.TW"
    assert messages[0][1]["type"] == "quote"
    assert messages[1][1]["type"] == "books"
