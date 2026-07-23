import asyncio

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import fubon_realtime_pool as realtime_pool_module
from fubon_realtime_pool import FubonRealtimeSubscriptionPool
import repositories.fubon_accounts as fubon_accounts_repository


class FakeManager:
    def __init__(self, account_id, ws_mode="Normal"):
        self.active_account_id = account_id
        self.connected = True
        self.ws_mode = ws_mode
        self.subscribed = []
        self.unsubscribed = []
        self.handlers = []
        self.quote_requests = []

    def register_message_handler(self, handler):
        self.handlers.append(handler)

    def unregister_message_handler(self, handler):
        self.handlers = [item for item in self.handlers if item is not handler]

    async def subscribe_stock_async(self, symbol, channel, timeout=2.5):
        self.subscribed.append(("stock", symbol, channel, timeout))
        return f"{symbol}-{channel}"

    async def subscribe_futopt_async(self, symbol, channel, after_hours=False, timeout=2.5):
        self.subscribed.append(("futopt", symbol, channel, after_hours, timeout))
        return f"{symbol}-{channel}"

    def unsubscribe_stock(self, symbol, channel):
        self.unsubscribed.append(("stock", symbol, channel))

    def unsubscribe_futopt(self, symbol, channel, after_hours=False):
        self.unsubscribed.append(("futopt", symbol, channel, after_hours))

    def shutdown(self):
        self.connected = False

    async def fetch_stock_quote(self, symbol):
        self.quote_requests.append(symbol)
        return {
            "symbol": symbol,
            "market": "TSE",
            "exchange": "TWSE",
            "price": 817,
            "bid": 816,
            "ask": 817,
            "volume": 12345,
            "time": 1685338200000000,
        }


class FakeDb:
    def __init__(self):
        self.notifications = []

    async def create_notification(self, payload):
        self.notifications.append(payload)
        return payload


class WarmupManager(FakeManager):
    def __init__(self, account_id, *, release=None, fail=False):
        super().__init__(account_id)
        self.connected = False
        self.release = release
        self.fail = fail
        self.init_calls = []
        self.stock_started = 0
        self.futopt_started = 0

    async def _init_with_account(self, account, _repo):
        self.init_calls.append(account["id"])
        if self.release is not None:
            await self.release.wait()
        if self.fail:
            raise RuntimeError("account login failed")
        self.connected = True
        return True

    def start_ws_stock(self):
        self.stock_started += 1

    def start_ws_futopt(self):
        self.futopt_started += 1


class WarmupDb(FakeDb):
    async def get_watchlist_groups(self):
        return []


class WarmupRepo:
    accounts = []

    def __init__(self, _db):
        pass

    async def list_enabled_accounts_with_secrets(self):
        return list(self.accounts)


@pytest.mark.anyio
async def test_background_warmup_does_not_block_application_readiness(monkeypatch):
    release = asyncio.Event()
    primary = WarmupManager(1, release=release)
    pool = FubonRealtimeSubscriptionPool(primary)
    WarmupRepo.accounts = [{"id": 1, "is_active": True, "is_enabled": True}]
    monkeypatch.setattr(fubon_accounts_repository, "FubonAccountRepository", WarmupRepo)

    task = pool.start_background_warmup(WarmupDb())
    assert pool.get_warmup_status()["state"] == "scheduled"
    await asyncio.sleep(0)
    assert pool.get_warmup_status()["state"] == "running"
    assert task.done() is False

    release.set()
    assert await task is True
    status = pool.get_warmup_status()
    assert status["state"] == "ready"
    assert status["connected_account_count"] == 1
    assert primary.stock_started == 1
    assert primary.futopt_started == 1


@pytest.mark.anyio
async def test_account_warmup_failure_does_not_cancel_remaining_accounts(monkeypatch):
    primary = WarmupManager(1, fail=True)
    secondary = WarmupManager(2)
    pool = FubonRealtimeSubscriptionPool(primary)
    WarmupRepo.accounts = [
        {"id": 1, "is_active": True, "is_enabled": True},
        {"id": 2, "is_active": False, "is_enabled": True},
    ]
    monkeypatch.setattr(fubon_accounts_repository, "FubonAccountRepository", WarmupRepo)
    monkeypatch.setattr(realtime_pool_module, "FubonSDKManager", lambda: secondary)

    connected = await pool.init_from_db(WarmupDb())

    assert connected is True
    assert primary.connected is False
    assert secondary.connected is True
    assert secondary.stock_started == 1
    assert secondary.futopt_started == 1


@pytest.mark.anyio
async def test_async_shutdown_cancels_incomplete_provider_warmup(monkeypatch):
    release = asyncio.Event()
    primary = WarmupManager(1, release=release)
    pool = FubonRealtimeSubscriptionPool(primary)
    WarmupRepo.accounts = [{"id": 1, "is_active": True, "is_enabled": True}]
    monkeypatch.setattr(fubon_accounts_repository, "FubonAccountRepository", WarmupRepo)

    task = pool.start_background_warmup(WarmupDb())
    await asyncio.sleep(0)
    await pool.shutdown_async()

    assert task.done() is True
    assert pool.get_warmup_status()["state"] == "stopped"


@pytest.mark.anyio
async def test_realtime_pool_distributes_watchlist_tickers_across_connected_accounts():
    primary = FakeManager(1)
    secondary = FakeManager(2)
    pool = FubonRealtimeSubscriptionPool(primary)
    pool._managers = {1: primary, 2: secondary}

    await pool.set_source_tickers("watchlist", ["2330.TW", "2317.TW"])

    runtime = pool.get_account_runtime_statuses()
    assert runtime[1]["realtime_assigned_count"] == 1
    assert runtime[2]["realtime_assigned_count"] == 1


@pytest.mark.anyio
async def test_realtime_pool_prefers_speed_for_watchlist_only_ticker():
    normal = FakeManager(1, ws_mode="Normal")
    speed = FakeManager(2, ws_mode="Speed")
    pool = FubonRealtimeSubscriptionPool(normal)
    pool._managers = {1: normal, 2: speed}

    await pool.set_source_tickers("watchlist", ["2330.TW"])

    runtime = pool.get_account_runtime_statuses()
    assert runtime[1]["realtime_assigned_count"] == 0
    assert runtime[2]["realtime_assigned_tickers"] == ["2330.TW"]


@pytest.mark.anyio
async def test_realtime_pool_promotes_ws_ticker_to_normal_mode_when_available():
    normal = FakeManager(1, ws_mode="Normal")
    speed = FakeManager(2, ws_mode="Speed")
    pool = FubonRealtimeSubscriptionPool(normal)
    pool._managers = {1: normal, 2: speed}

    await pool.set_source_tickers("watchlist", ["2330.TW"])
    assert pool.get_account_runtime_statuses()[2]["realtime_assigned_tickers"] == ["2330.TW"]

    await pool.set_source_tickers("ws", ["2330.TW"])

    runtime = pool.get_account_runtime_statuses()
    assert runtime[1]["realtime_assigned_tickers"] == ["2330.TW"]
    assert runtime[2]["realtime_assigned_count"] == 0
    assert ("stock", "2330", "trades") in [item[:3] for item in speed.unsubscribed]


@pytest.mark.anyio
async def test_realtime_pool_prefers_normal_for_paper_bot_source():
    normal = FakeManager(1, ws_mode="Normal")
    speed = FakeManager(2, ws_mode="Speed")

    async def resolve_contract(_ticker):
        return {"resolved_symbol": "TMFE6"}

    pool = FubonRealtimeSubscriptionPool(normal, resolve_futopt_contract=resolve_contract)
    pool._managers = {1: normal, 2: speed}

    await pool.set_source_tickers("paper_bot_1", ["TMF"])

    runtime = pool.get_account_runtime_statuses()
    assert runtime[1]["realtime_assigned_tickers"] == ["TMF"]
    assert runtime[2]["realtime_assigned_count"] == 0
    assert ("futopt", "TMFE6", "candles") in [item[:3] for item in normal.subscribed]


@pytest.mark.anyio
async def test_realtime_pool_demotes_ws_ticker_back_to_speed_when_focus_is_removed():
    normal = FakeManager(1, ws_mode="Normal")
    speed = FakeManager(2, ws_mode="Speed")
    pool = FubonRealtimeSubscriptionPool(normal)
    pool._managers = {1: normal, 2: speed}

    await pool.set_source_tickers("watchlist", ["2330.TW"])
    await pool.set_source_tickers("ws", ["2330.TW"])
    assert pool.get_account_runtime_statuses()[1]["realtime_assigned_tickers"] == ["2330.TW"]

    await pool.set_source_tickers("ws", [])

    runtime = pool.get_account_runtime_statuses()
    assert runtime[1]["realtime_assigned_count"] == 0
    assert runtime[2]["realtime_assigned_tickers"] == ["2330.TW"]


@pytest.mark.anyio
async def test_realtime_pool_maps_alias_ticker_to_resolved_contract():
    primary = FakeManager(1)

    async def resolve_contract(_ticker):
        return {"resolved_symbol": "TXFE6"}

    pool = FubonRealtimeSubscriptionPool(primary, resolve_futopt_contract=resolve_contract)
    pool._managers = {1: primary}

    await pool.set_source_tickers("watchlist", ["TXF"])

    assert pool.resolve_broadcast_tickers("TXFE6") == ("TXF", "TXFE6")


@pytest.mark.anyio
async def test_realtime_pool_deduplicates_aliases_resolving_to_same_contract():
    primary = FakeManager(1)
    secondary = FakeManager(2)

    async def resolve_contract(_ticker):
        return {"resolved_symbol": "TXFE6"}

    pool = FubonRealtimeSubscriptionPool(primary, resolve_futopt_contract=resolve_contract)
    pool._managers = {1: primary, 2: secondary}

    await pool.set_source_tickers("ws", ["TXF", "*TXFF"])

    assert len(primary.subscribed) == 3
    assert secondary.subscribed == []
    assert pool.resolve_broadcast_tickers("TXFE6") == ("*TXFF", "TXF", "TXFE6")
    assert pool.get_account_runtime_statuses()[1]["realtime_physical_subscription_count"] == 1

    await pool.set_source_tickers("ws", ["*TXFF"])
    assert primary.unsubscribed == []

    await pool.set_source_tickers("ws", [])
    assert len(primary.unsubscribed) == 3


def test_realtime_pool_records_ws_message_diagnostics():
    primary = FakeManager(1)
    pool = FubonRealtimeSubscriptionPool(primary)

    pool.record_ws_message(
        "TMFE6",
        "books",
        market_type="futopt",
        account_id=1,
        target_tickers=("TMF",),
    )
    pool.record_ws_message("TMFE6", "books", market_type="futopt", account_id=1)

    diagnostics = pool.get_ws_diagnostics()
    assert diagnostics["TMFE6"]["last_channel"] == "books"
    assert diagnostics["TMFE6"]["channels"]["books"]["count"] == 2
    assert diagnostics["TMFE6"]["channels"]["books"]["market_type"] == "futopt"
    assert diagnostics["TMFE6"]["channels"]["books"]["account_id"] == 1
    assert diagnostics["TMF"]["channels"]["books"]["count"] == 1


@pytest.mark.anyio
async def test_full_ws_quote_support_requires_recent_quote_message():
    now = datetime(2026, 7, 22, 1, 0, tzinfo=timezone.utc)
    clock = {"now": now}
    primary = FakeManager(1, ws_mode="Normal")
    pool = FubonRealtimeSubscriptionPool(
        primary,
        full_quote_stale_seconds=20,
        utcnow=lambda: clock["now"],
    )
    pool._managers = {1: primary}
    await pool.set_source_tickers("ws", ["2330.TW"])

    assert pool.supports_full_ws_quotes_for_ticker("2330.TW") is False

    pool.record_ws_message(
        "2330.TW",
        "quote",
        market_type="stock",
        account_id=1,
        target_tickers=("2330.TW",),
    )
    assert pool.supports_full_ws_quotes_for_ticker("2330.TW") is True

    clock["now"] = now + timedelta(seconds=21)
    assert pool.supports_full_ws_quotes_for_ticker("2330.TW") is False
    diagnostics = pool.get_ws_diagnostics()
    assert diagnostics["2330.TW"]["channels"]["quote"]["age_seconds"] == 21
    assert diagnostics["2330.TW"]["channels"]["quote"]["is_fresh"] is False


@pytest.mark.anyio
async def test_session_refresh_recovers_each_disconnected_account_without_full_reload():
    primary = FakeManager(1)
    secondary = FakeManager(2)
    secondary.connected = False
    pool = FubonRealtimeSubscriptionPool(primary)
    pool._managers = {1: primary, 2: secondary}
    pool.reconnect_account = AsyncMock(return_value={"success": True})

    await pool.refresh_session_assignments()

    pool.reconnect_account.assert_awaited_once_with(2)


@pytest.mark.anyio
async def test_realtime_pool_subscribes_futopt_afterhours_when_night_session(monkeypatch):
    monkeypatch.setattr(realtime_pool_module, "is_futopt_after_hours", lambda: True)
    primary = FakeManager(1)
    pool = FubonRealtimeSubscriptionPool(primary)
    pool._managers = {1: primary}

    await pool.set_source_tickers("ws", ["TXFE6"])

    assert ("futopt", "TXFE6", "books", True, 2.5) in primary.subscribed
    assert ("futopt", "TXFE6", "candles", True, 2.5) in primary.subscribed
    assert pool.get_account_runtime_statuses()[1]["realtime_afterhours_tickers"] == ["TXFE6"]


@pytest.mark.anyio
async def test_realtime_pool_refreshes_futopt_subscription_on_session_change(monkeypatch):
    state = {"after_hours": False}
    monkeypatch.setattr(realtime_pool_module, "is_futopt_after_hours", lambda: state["after_hours"])
    primary = FakeManager(1)
    pool = FubonRealtimeSubscriptionPool(primary)
    pool._managers = {1: primary}

    await pool.set_source_tickers("ws", ["TXFE6"])
    state["after_hours"] = True
    await pool.refresh_session_assignments()

    assert ("futopt", "TXFE6", "books", False) in primary.unsubscribed
    assert ("futopt", "TXFE6", "books", True, 2.5) in primary.subscribed


@pytest.mark.anyio
async def test_realtime_pool_creates_notification_when_no_connected_account_available():
    primary = FakeManager(1)
    primary.connected = False
    database = FakeDb()
    pool = FubonRealtimeSubscriptionPool(primary)
    pool._db = database
    pool._managers = {1: primary}

    await pool.set_source_tickers("watchlist", ["2330.TW"])

    assert database.notifications
    assert database.notifications[0]["title"] == "即時行情訂閱容量不足"

@pytest.mark.anyio
async def test_realtime_pool_primes_stock_quote_after_assignment():
    primary = FakeManager(1, ws_mode="Speed")
    stored_quotes = []

    async def store_quote(payload):
        stored_quotes.append(payload)
        return payload

    pool = FubonRealtimeSubscriptionPool(primary, store_quote=store_quote)
    pool._managers = {1: primary}

    await pool.set_source_tickers("watchlist", ["2330.TW"])

    assert primary.quote_requests == ["2330"]
    assert stored_quotes
    assert stored_quotes[0]["ticker"] == "2330.TW"
    assert stored_quotes[0]["quote_type"] == "realtime"
