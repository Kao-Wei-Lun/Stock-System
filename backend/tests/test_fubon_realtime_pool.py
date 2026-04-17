import pytest

from fubon_realtime_pool import FubonRealtimeSubscriptionPool


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

    async def subscribe_futopt_async(self, symbol, channel, timeout=2.5):
        self.subscribed.append(("futopt", symbol, channel, timeout))
        return f"{symbol}-{channel}"

    def unsubscribe_stock(self, symbol, channel):
        self.unsubscribed.append(("stock", symbol, channel))

    def unsubscribe_futopt(self, symbol, channel):
        self.unsubscribed.append(("futopt", symbol, channel))

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

    assert pool.resolve_broadcast_tickers("TXFE6") == ("TXF",)


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
