import asyncio
import database
import pytest
import fubon_provider
import repositories.fubon_accounts as fubon_accounts_repo

from fubon_provider import FubonMarketdataAuthenticationError, FubonSDKManager, classify_fubon_error


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


def test_login_accounts_extracts_and_selects_futopt_account():
    stock_account = {"account_type": "stock", "account": "S001"}
    futopt_account = {"account_type": "futopt", "account": "F001"}

    accounts = FubonSDKManager._extract_login_accounts({"data": [stock_account, futopt_account]})

    assert accounts == [stock_account, futopt_account]
    assert FubonSDKManager._select_futopt_account(accounts) == futopt_account


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


class FakeReconnectWebSocket(FakeWebSocket):
    def __init__(self):
        super().__init__()
        self.connect_calls = 0
        self.disconnect_calls = 0

    def connect(self):
        self.connect_calls += 1

    def disconnect(self):
        self.disconnect_calls += 1


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


def test_subscribe_futopt_afterhours_sends_flag_and_matches_plain_ack():
    manager = FubonSDKManager()
    manager._ws_futopt = FakeWebSocket()
    manager.connected = True
    manager._attach_message_handlers()

    async def run():
        task = asyncio.create_task(
            manager.subscribe_futopt_async("TXFE6", "books", after_hours=True, timeout=1.0)
        )
        await asyncio.sleep(0)
        manager._dispatch_ws_message(
            "futopt",
            {
                "event": "subscribed",
                "data": {"id": "night-books", "channel": "books", "symbol": "TXFE6"},
            },
        )
        return await task

    assert asyncio.run(run()) == "night-books"
    assert manager._ws_futopt.calls[0] == (
        "subscribe",
        {"channel": "books", "symbol": "TXFE6", "afterHours": True},
    )
    assert manager._subscriptions["futopt:TXFE6:books:afterhours"] == "night-books"


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


def test_manual_reconnect_reopens_socket_and_restores_desired_subscriptions_without_duplicates():
    manager = FubonSDKManager()
    websocket = FakeReconnectWebSocket()
    manager._ws_stock = websocket
    manager.connected = True
    manager.start_ws_stock()
    manager.subscribe_stock("2330", "books")

    for _minute in range(30):
        assert manager.force_reconnect_ws("stock") is True
        manager._handle_ws_connect("stock")

    status = manager.get_reconnect_status()["stock"]
    assert websocket.disconnect_calls == 30
    assert websocket.connect_calls == 31
    assert status["subscription_count"] == 1
    assert status["desired_subscription_count"] == 1
    assert list(manager._subscriptions) == ["stock:2330:books"]


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


def test_failed_reconnect_is_rescheduled_with_exponential_backoff(monkeypatch):
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
    monkeypatch.setattr(fubon_provider.random, "uniform", lambda _start, _end: 0.0)
    manager._reconnect_ws_target = lambda _market_type: False

    manager._schedule_reconnect_ws_target("stock")
    assert timers[0].interval == 1.0
    timers[0].alive = False
    manager._run_scheduled_reconnect("stock")

    assert manager._ws_reconnect_attempts["stock"] == 1
    assert len(timers) == 2
    assert timers[1].interval == 2.0
    assert manager.get_reconnect_status()["stock"]["pending"] is True


def test_ws_connect_resets_reconnect_state():
    manager = FubonSDKManager()
    manager._ws_reconnect_attempts["futopt"] = 4
    manager._ws_reconnect_last_error["futopt"] = "temporary failure"

    manager._handle_ws_connect("futopt")

    status = manager.get_reconnect_status()["futopt"]
    assert status["attempts"] == 0
    assert status["last_error"] is None
    assert status["last_success_at"] is not None
    assert status["state"] == "connected"
    assert status["next_retry_at"] is None


def test_ws_disconnect_records_transient_state_and_retry_deadline(monkeypatch):
    manager = FubonSDKManager()
    manager.connected = True

    class FakeTimer:
        def __init__(self, interval, callback):
            self.interval = interval
            self.callback = callback
            self.daemon = False

        def start(self):
            pass

        def is_alive(self):
            return True

        def cancel(self):
            pass

    monkeypatch.setattr(fubon_provider.threading, "Timer", FakeTimer)
    monkeypatch.setattr(fubon_provider.random, "uniform", lambda _start, _end: 0.0)

    manager._handle_ws_disconnect("stock", RuntimeError("connection closed"))

    status = manager.get_reconnect_status()["stock"]
    assert status["state"] == "backoff"
    assert status["last_error_category"] == "transient"
    assert status["last_disconnect_at"] is not None
    assert status["next_retry_at"] is not None


@pytest.mark.parametrize(
    "error",
    [
        ConnectionAbortedError(10053, "連線已被您主機上的軟體中止。"),
        RuntimeError("[WinError 10053] connection aborted"),
        "ConnectionAbortedError: local software aborted the connection",
        "連線已被您主機上的軟體中止",
    ],
)
def test_winerror_10053_is_classified_as_transient(error):
    assert classify_fubon_error(error) == "transient"


def test_manager_detects_futures_capability_without_selecting_known_stock_account():
    manager = FubonSDKManager()
    stock = {"account_type": "stock"}
    futures = {"account_type": "futures"}
    manager._login_accounts = [stock, futures]

    assert manager.account_capabilities == ("futures", "stock")
    assert manager._select_futopt_account([stock, futures]) is futures
    assert manager._select_futopt_account([stock]) is None


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


class FakeAuthExpiredError(Exception):
    status_code = 401

    def __str__(self):
        return "[Fugle API Error] Token expired Status: 401"


class FakeAuthOnceSnapshotApi(FakeSnapshotApi):
    def __init__(self):
        super().__init__()
        self.failed = False

    def quotes(self, **kwargs):
        self.calls.append(("quotes", kwargs))
        if not self.failed:
            self.failed = True
            raise FakeAuthExpiredError()
        return {"market": kwargs["market"], "data": []}


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


class FakeFutoptTradeApi:
    def __init__(self):
        self.calls = []

    def query_estimate_margin(self, account, order):
        self.calls.append((account, order))
        return {"is_success": True, "data": {"estimate_margin": 27100, "currency": "TWD"}}


class FakeTradeSDK:
    def __init__(self, futopt):
        self.futopt = futopt


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


def test_fetch_stock_snapshot_quotes_reinitializes_after_expired_token(monkeypatch):
    manager = FubonSDKManager()
    manager.connected = True
    snapshot = FakeAuthOnceSnapshotApi()
    calls = []

    manager.get_rest_stock = lambda: FakeRestStock(snapshot)
    manager.start_ws_stock = lambda: calls.append("start_ws_stock") or True
    manager.start_ws_futopt = lambda: calls.append("start_ws_futopt") or True

    fake_repo = FakeRepo({"id": 2, "label": "Kao"})

    monkeypatch.setattr(database, "db", object())
    monkeypatch.setattr(fubon_accounts_repo, "FubonAccountRepository", lambda _db: fake_repo)

    async def fake_init_with_account(account, repo=None):
        calls.append(("init", account["id"], repo is fake_repo))
        manager.connected = True
        return True

    monkeypatch.setattr(manager, "_init_with_account", fake_init_with_account)

    payload = asyncio.run(manager.fetch_stock_snapshot_quotes(market="TSE"))

    assert payload["market"] == "TSE"
    assert snapshot.calls == [
        ("quotes", {"market": "TSE"}),
        ("quotes", {"market": "TSE"}),
    ]
    assert calls == [
        ("init", 2, True),
        "start_ws_stock",
        "start_ws_futopt",
    ]


def test_fetch_stock_snapshot_quotes_reports_auth_error_after_failed_reinit(monkeypatch):
    manager = FubonSDKManager()
    manager.connected = True
    snapshot = FakeAuthOnceSnapshotApi()

    manager.get_rest_stock = lambda: FakeRestStock(snapshot)

    fake_repo = FakeRepo({"id": 2, "label": "Kao"})

    monkeypatch.setattr(database, "db", object())
    monkeypatch.setattr(fubon_accounts_repo, "FubonAccountRepository", lambda _db: fake_repo)

    async def fake_init_with_account(account, repo=None):
        manager.connected = False
        return False

    monkeypatch.setattr(manager, "_init_with_account", fake_init_with_account)

    with pytest.raises(FubonMarketdataAuthenticationError):
        asyncio.run(manager.fetch_stock_snapshot_quotes(market="TSE"))


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


def test_query_futopt_estimate_margin_calls_sdk_trade_api(monkeypatch):
    manager = FubonSDKManager()
    futopt_api = FakeFutoptTradeApi()
    account = {"account_type": "futopt", "account": "F001"}
    manager.connected = True
    manager._sdk = FakeTradeSDK(futopt_api)
    manager._active_futopt_account = account
    manager.ensure_trading_ready = lambda: asyncio.sleep(0, result=True)

    monkeypatch.setattr(
        fubon_provider,
        "_build_futopt_estimate_margin_order",
        lambda symbol, **kwargs: {"symbol": symbol, **kwargs},
    )

    payload = asyncio.run(
        manager.query_futopt_estimate_margin("TMFE6", price=40500, lot=1, session="REGULAR")
    )

    assert payload["data"]["estimate_margin"] == 27100
    assert futopt_api.calls == [
        (account, {"symbol": "TMFE6", "price": 40500, "lot": 1, "session": "REGULAR"})
    ]


def test_query_margin_skips_incompatible_login_account_and_uses_futures_account(monkeypatch):
    manager = FubonSDKManager()
    stock_account = {"account_type": "stock", "account": "S001"}
    futures_account = {"account_type": "futures", "account": "F001"}

    class SelectiveFutoptApi(FakeFutoptTradeApi):
        def query_estimate_margin(self, account, order):
            self.calls.append((account, order))
            if account is stock_account:
                return {"is_success": False, "message": "帳號類別錯誤"}
            return {"is_success": True, "data": {"estimate_margin": 27_100}}

    futopt_api = SelectiveFutoptApi()
    manager.connected = True
    manager._sdk = FakeTradeSDK(futopt_api)
    manager._login_accounts = [stock_account, futures_account]
    manager._active_futopt_account = stock_account
    manager.ensure_trading_ready = lambda: asyncio.sleep(0, result=True)
    monkeypatch.setattr(
        fubon_provider,
        "_build_futopt_estimate_margin_order",
        lambda symbol, **kwargs: {"symbol": symbol, **kwargs},
    )

    payload = asyncio.run(
        manager.query_futopt_estimate_margin("TMFE6", price=40500, lot=1)
    )

    assert payload["data"]["estimate_margin"] == 27_100
    assert [account for account, _order in futopt_api.calls] == [futures_account]
    assert manager.get_futopt_account() is futures_account
