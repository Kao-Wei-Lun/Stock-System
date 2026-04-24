import asyncio
import database
import pytest
import fubon_provider
import repositories.fubon_accounts as fubon_accounts_repo

from fubon_provider import FubonSDKManager


class FakeSDK:
    def __init__(self):
        self.calls = []

    def apikey_login(self, *args):
        self.calls.append(("apikey_login", args))
        return {"is_success": True, "message": None}

    def login(self, *args):
        self.calls.append(("login", args))
        return {"is_success": True, "message": None}


def test_login_account_uses_apikey_login_with_positional_args():
    sdk = FakeSDK()

    result = FubonSDKManager._login_account(
        sdk,
        {
            "user_id": "A123456789",
            "password": "unused-password",
            "api_key": "test-api-key",
            "cert_path": "C:\\certs\\fubon.pfx",
            "cert_password": "cert-pass",
        },
    )

    assert result["is_success"] is True
    assert sdk.calls == [
        ("apikey_login", ("A123456789", "test-api-key", "C:\\certs\\fubon.pfx", "cert-pass"))
    ]


def test_login_account_falls_back_to_password_login_when_api_key_is_absent():
    sdk = FakeSDK()

    FubonSDKManager._login_account(
        sdk,
        {
            "user_id": "A123456789",
            "password": "login-password",
            "api_key": "",
            "cert_path": "C:\\certs\\fubon.pfx",
            "cert_password": "",
        },
    )

    assert sdk.calls == [
        ("login", ("A123456789", "login-password", "C:\\certs\\fubon.pfx"))
    ]


def test_login_result_failure_is_detected():
    assert FubonSDKManager._is_login_success({"is_success": False, "message": "bad credentials"}) is False
    assert FubonSDKManager._login_message({"is_success": False, "message": "bad credentials"}) == "bad credentials"


class FakeWebSocket:
    def __init__(self):
        self.handlers = {}
        self.calls = []

    def on(self, event_name, handler):
        self.handlers[event_name] = handler

    def subscribe(self, payload):
        self.calls.append(("subscribe", payload))
        return None

    def unsubscribe(self, payload):
        self.calls.append(("unsubscribe", payload))
        return None


class FakeConnectWebSocket:
    def __init__(self):
        self.connect_calls = 0

    def connect(self):
        self.connect_calls += 1
        if self.connect_calls > 1:
            raise RuntimeError("socket is already opened")


def test_subscription_id_updates_from_subscribed_event():
    manager = FubonSDKManager()
    manager._ws_stock = FakeWebSocket()
    manager.connected = True
    manager._attach_message_handlers()

    placeholder = manager.subscribe_stock("2330", "aggregates")

    assert placeholder == "stock:2330:aggregates"

    manager._dispatch_ws_message(
        "stock",
        {
            "event": "subscribed",
            "data": {"id": "abc123", "channel": "aggregates", "symbol": "2330"},
        },
    )

    assert manager._subscriptions["stock:2330:aggregates"] == "abc123"


def test_subscribe_stock_async_waits_for_subscribed_event():
    manager = FubonSDKManager()
    manager._ws_stock = FakeWebSocket()
    manager.connected = True
    manager._attach_message_handlers()

    async def run():
        task = asyncio.create_task(manager.subscribe_stock_async("2330", "aggregates", timeout=1.0))
        await asyncio.sleep(0)
        manager._dispatch_ws_message(
            "stock",
            {
                "event": "subscribed",
                "data": {"id": "async-123", "channel": "aggregates", "symbol": "2330"},
            },
        )
        return await task

    assert asyncio.run(run()) == "async-123"


def test_subscribe_stock_async_raises_on_error_event():
    manager = FubonSDKManager()
    manager._ws_stock = FakeWebSocket()
    manager.connected = True
    manager._attach_message_handlers()

    async def run():
        task = asyncio.create_task(manager.subscribe_stock_async("2330", "aggregates", timeout=1.0))
        await asyncio.sleep(0)
        manager._dispatch_ws_message(
            "stock",
            {
                "event": "error",
                "data": {"message": "subscription limit reached"},
            },
        )
        with pytest.raises(RuntimeError, match="subscription limit reached"):
            await task

    asyncio.run(run())


def test_unsubscribe_uses_resolved_channel_id():
    manager = FubonSDKManager()
    manager._ws_stock = FakeWebSocket()
    manager.connected = True
    manager._subscriptions["stock:2330:aggregates"] = "resolved-id"
    manager._subscription_payloads["stock:2330:aggregates"] = {"channel": "aggregates", "symbol": "2330"}

    manager.unsubscribe_stock("2330", "aggregates")

    assert manager._ws_stock.calls == [("unsubscribe", {"id": "resolved-id"})]


def test_start_ws_stock_is_idempotent_for_already_started_socket():
    manager = FubonSDKManager()
    manager._ws_stock = FakeConnectWebSocket()

    assert manager.start_ws_stock() is True
    assert manager.start_ws_stock() is True
    assert manager._ws_stock.connect_calls == 1


def test_unregister_message_handler_and_shutdown_suppress_dispatch():
    manager = FubonSDKManager()
    received = []

    def handler(message):
        received.append(message)

    manager.register_message_handler(handler)
    manager.unregister_message_handler(handler)
    manager._dispatch_ws_message("stock", {"event": "data", "data": {"symbol": "2330"}})

    assert received == []


def test_disconnect_during_shutdown_does_not_reconnect():
    manager = FubonSDKManager()
    manager.connected = True
    manager._shutting_down = True
    manager._ws_started_targets.add("stock")
    reconnected = []
    manager._reconnect_ws_target = lambda market_type: reconnected.append(market_type)

    manager._handle_ws_disconnect("stock", None, None)

    assert reconnected == []
    assert "stock" not in manager._ws_started_targets


def test_disconnect_schedules_single_reconnect_while_timer_is_active(monkeypatch):
    manager = FubonSDKManager()
    manager.connected = True
    timers = []

    class FakeTimer:
        def __init__(self, interval, callback):
            self.interval = interval
            self.callback = callback
            self.alive = False
            self.daemon = False
            timers.append(self)

        def start(self):
            self.alive = True

        def is_alive(self):
            return self.alive

        def cancel(self):
            self.alive = False

    monkeypatch.setattr(fubon_provider.threading, "Timer", FakeTimer)

    manager._handle_ws_disconnect("futopt", None, None)
    manager._handle_ws_disconnect("futopt", None, None)

    assert len(timers) == 1
    assert "futopt" in manager._ws_reconnect_timers


def test_run_scheduled_reconnect_cleans_timer_and_reconnects():
    manager = FubonSDKManager()
    manager.connected = True
    reconnected = []

    class FakeTimer:
        def __init__(self):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

        def is_alive(self):
            return True

    timer = FakeTimer()
    manager._ws_reconnect_timers["futopt"] = timer
    manager._reconnect_ws_target = lambda market_type: reconnected.append(market_type)

    manager._run_scheduled_reconnect("futopt")

    assert reconnected == ["futopt"]
    assert "futopt" not in manager._ws_reconnect_timers
    assert timer.cancelled is False


class FakeSnapshotApi:
    def __init__(self):
        self.calls = []

    def quotes(self, **kwargs):
        self.calls.append(("quotes", kwargs))
        return {"market": kwargs["market"], "data": []}

    def movers(self, **kwargs):
        self.calls.append(("movers", kwargs))
        return {"market": kwargs["market"], "direction": kwargs["direction"], "data": []}

    def actives(self, **kwargs):
        self.calls.append(("actives", kwargs))
        return {"market": kwargs["market"], "trade": kwargs["trade"], "data": []}


class FakeRestStock:
    def __init__(self, snapshot):
        self.snapshot = snapshot


class FakeFutoptIntradayApi:
    def __init__(self):
        self.calls = []

    def quote(self, **kwargs):
        self.calls.append(("quote", kwargs))
        return {"symbol": kwargs["symbol"]}

    def candles(self, **kwargs):
        self.calls.append(("candles", kwargs))
        return {"symbol": kwargs["symbol"], "data": []}


class FakeRestFutopt:
    def __init__(self, intraday):
        self.intraday = intraday


class FakeRepo:
    def __init__(self, account):
        self.account = account

    async def get_active_account(self):
        return self.account


def test_fetch_stock_snapshot_quotes_calls_sdk_snapshot_quotes():
    manager = FubonSDKManager()
    snapshot = FakeSnapshotApi()
    manager.connected = True
    manager.get_rest_stock = lambda: FakeRestStock(snapshot)

    payload = asyncio.run(manager.fetch_stock_snapshot_quotes(market="TSE"))

    assert payload["market"] == "TSE"
    assert snapshot.calls == [("quotes", {"market": "TSE"})]


def test_fetch_stock_snapshot_movers_and_actives_call_snapshot_methods():
    manager = FubonSDKManager()
    snapshot = FakeSnapshotApi()
    manager.connected = True
    manager.get_rest_stock = lambda: FakeRestStock(snapshot)

    movers = asyncio.run(manager.fetch_stock_snapshot_movers(market="OTC", direction="down", change="percent"))
    actives = asyncio.run(manager.fetch_stock_snapshot_actives(market="TSE", trade="value"))

    assert movers["direction"] == "down"
    assert actives["trade"] == "value"
    assert snapshot.calls == [
        ("movers", {"market": "OTC", "direction": "down", "change": "percent"}),
        ("actives", {"market": "TSE", "trade": "value"}),
    ]


def test_ensure_marketdata_ready_reinitializes_when_rest_client_is_missing(monkeypatch):
    manager = FubonSDKManager()
    manager.connected = True
    state = {"ready": False}
    calls = []

    manager.get_rest_stock = lambda: object() if state["ready"] else None
    manager.start_ws_stock = lambda: calls.append("start_ws_stock") or True
    manager.start_ws_futopt = lambda: calls.append("start_ws_futopt") or True

    fake_repo = FakeRepo({"id": 2, "label": "Kao"})

    monkeypatch.setattr(database, "db", object())
    monkeypatch.setattr(fubon_accounts_repo, "FubonAccountRepository", lambda _db: fake_repo)

    async def fake_init_with_account(account, repo=None):
        calls.append(("init", account["id"], repo is fake_repo))
        state["ready"] = True
        manager.connected = True
        return True

    monkeypatch.setattr(manager, "_init_with_account", fake_init_with_account)

    assert asyncio.run(manager.ensure_marketdata_ready()) is True
    assert calls == [
        ("init", 2, True),
        "start_ws_stock",
        "start_ws_futopt",
    ]


def test_fetch_stock_snapshot_quotes_self_heals_missing_rest_client(monkeypatch):
    manager = FubonSDKManager()
    manager.connected = True
    snapshot = FakeSnapshotApi()
    state = {"ready": False}

    manager.get_rest_stock = lambda: FakeRestStock(snapshot) if state["ready"] else None
    manager.start_ws_stock = lambda: True
    manager.start_ws_futopt = lambda: True

    fake_repo = FakeRepo({"id": 2, "label": "Kao"})

    monkeypatch.setattr(database, "db", object())
    monkeypatch.setattr(fubon_accounts_repo, "FubonAccountRepository", lambda _db: fake_repo)

    async def fake_init_with_account(account, repo=None):
        state["ready"] = True
        manager.connected = True
        return True

    monkeypatch.setattr(manager, "_init_with_account", fake_init_with_account)

    payload = asyncio.run(manager.fetch_stock_snapshot_quotes(market="TSE"))

    assert payload["market"] == "TSE"
    assert snapshot.calls == [("quotes", {"market": "TSE"})]


def test_fetch_futopt_requests_omit_regular_session_and_keep_afterhours():
    manager = FubonSDKManager()
    intraday = FakeFutoptIntradayApi()
    manager.connected = True
    manager.ensure_marketdata_ready = lambda require_futopt=False: asyncio.sleep(0, result=True)
    manager.get_rest_futopt = lambda: FakeRestFutopt(intraday)

    asyncio.run(manager.fetch_futopt_quote("MXFE6", session="REGULAR"))
    asyncio.run(manager.fetch_futopt_intraday_candles("MXFE6", timeframe="1", session="REGULAR"))
    asyncio.run(manager.fetch_futopt_quote("MXFE6", session="afterhours"))
    asyncio.run(manager.fetch_futopt_intraday_candles("MXFE6", timeframe="1", session="afterhours"))

    assert intraday.calls == [
        ("quote", {"symbol": "MXFE6"}),
        ("candles", {"symbol": "MXFE6", "timeframe": "1"}),
        ("quote", {"symbol": "MXFE6", "session": "afterhours"}),
        ("candles", {"symbol": "MXFE6", "timeframe": "1", "session": "afterhours"}),
    ]
