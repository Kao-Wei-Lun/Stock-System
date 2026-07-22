from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from security_sanitizer import redact_sensitive_text, secret_values_from_account


log = logging.getLogger(__name__)


class FubonMarketdataAuthenticationError(RuntimeError):
    """Raised when Fubon/Fugle marketdata credentials remain invalid after retry."""


def _is_marketdata_auth_error(exc: Exception) -> bool:
    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status", None) or getattr(response, "status_code", None)
    text = " ".join(
        str(part or "")
        for part in (
            exc,
            status,
            response_status,
            getattr(exc, "message", None),
            getattr(exc, "error", None),
        )
    ).lower()
    return (
        status == 401
        or response_status == 401
        or "status: 401" in text
        or "statuscode\":401" in text.replace(" ", "")
        or "token expired" in text
        or "invalid authentication credentials" in text
        or "unauthorized" in text
    )


def _normalize_futopt_session(session: str | None) -> Optional[str]:
    raw = str(session or "").strip().lower()
    if raw in {"afterhours", "night", "night_session"}:
        return "afterhours"
    return None


def _object_field(value: Any, *names: str) -> Any:
    if isinstance(value, dict):
        for name in names:
            if name in value:
                return value.get(name)
        return None
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return None


def _build_futopt_estimate_margin_order(
    symbol: str,
    *,
    price: float,
    lot: int = 1,
    session: str | None = "REGULAR",
):
    try:
        from fubon_neo.constant import (
            BSAction,
            FutOptMarketType,
            FutOptOrderType,
            FutOptPriceType,
            TimeInForce,
        )
        from fubon_neo.sdk import FutOptOrder
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "fubon_neo SDK is not installed. Install docs/fubon_neo-2.2.8-cp37-abi3-win_amd64.whl first."
        ) from exc

    numeric_price = float(price)
    price_text = str(int(numeric_price)) if numeric_price.is_integer() else str(numeric_price)
    market_type = (
        FutOptMarketType.FutureNight
        if _normalize_futopt_session(session) == "afterhours"
        else FutOptMarketType.Future
    )
    return FutOptOrder(
        buy_sell=BSAction.Buy,
        symbol=str(symbol).strip().upper(),
        price=price_text,
        lot=max(1, int(lot or 1)),
        market_type=market_type,
        price_type=FutOptPriceType.Limit,
        time_in_force=TimeInForce.ROD,
        order_type=FutOptOrderType.New,
        user_def="QVMargin",
    )


class FubonSDKManager:
    _RECONNECT_DELAY_SECONDS = 1.0
    _RECONNECT_MAX_DELAY_SECONDS = 30.0

    def __init__(self):
        self._sdk = None
        self._active_account_id: Optional[int] = None
        self._ws_mode = "Speed"
        self._ws_stock = None
        self._ws_futopt = None
        self._login_accounts: list[Any] = []
        self._active_futopt_account = None
        self._ws_started_targets: set[str] = set()
        self._subscriptions: Dict[str, str] = {}
        self._subscription_payloads: Dict[str, dict] = {}
        self._subscription_id_to_key: Dict[str, str] = {}
        self._message_handlers: list[Callable[[dict], None]] = []
        self._attached_targets: set[str] = set()
        self._reinit_lock = asyncio.Lock()
        self._shutting_down = False
        self._pending_subscription_acks: Dict[str, list[asyncio.Future[str]]] = {}
        self._ws_reconnect_timers: Dict[str, threading.Timer] = {}
        self._ws_reconnect_lock = threading.Lock()
        self._ws_reconnect_attempts: Dict[str, int] = {"stock": 0, "futopt": 0}
        self._ws_reconnect_last_error: Dict[str, str | None] = {"stock": None, "futopt": None}
        self._ws_reconnect_last_success_at: Dict[str, str | None] = {"stock": None, "futopt": None}
        self.connected = False

    @property
    def enabled(self) -> bool:
        return self.connected and self._sdk is not None

    @property
    def active_account_id(self) -> Optional[int]:
        return self._active_account_id

    @property
    def ws_mode(self) -> str:
        return self._ws_mode

    @property
    def supports_full_ws_quotes(self) -> bool:
        return self._ws_mode == "Normal"

    async def init_from_db(self, db) -> bool:
        from repositories.fubon_accounts import FubonAccountRepository

        repo = FubonAccountRepository(db)
        account = await repo.get_active_account()
        if not account:
            log.info("No active Fubon account configured; SDK initialization skipped")
            return False
        return await self._init_with_account(account, repo)

    async def _init_with_account(self, account: dict, repo=None) -> bool:
        account_id = account.get("id")
        if repo and account_id:
            await repo.update_connection_status(account_id, "connecting")

        self._shutting_down = False
        old_targets = (self._ws_stock, self._ws_futopt, self._sdk)
        self._reset_runtime_state()

        try:
            sdk, ws_stock, ws_futopt, login_accounts = await asyncio.to_thread(self._login_sync, account)
        except Exception as exc:
            safe_error = redact_sensitive_text(exc, secrets=secret_values_from_account(account))
            for target in old_targets:
                self._best_effort_shutdown(target)
            self.connected = False
            if repo and account_id:
                await repo.update_connection_status(account_id, "error", safe_error)
            log.error("Fubon SDK initialization failed: %s", safe_error)
            return False

        for target in old_targets:
            self._best_effort_shutdown(target)
        self._sdk = sdk
        self._active_account_id = account_id
        self._ws_mode = str(account.get("ws_mode") or "Speed")
        self._ws_stock = ws_stock
        self._ws_futopt = ws_futopt
        self._login_accounts = login_accounts
        self._active_futopt_account = self._select_futopt_account(login_accounts)
        self.connected = True
        self._attach_message_handlers()

        if repo and account_id:
            await repo.update_connection_status(account_id, "connected")
        log.info("Fubon SDK initialized with account %s", account.get("label") or account_id)
        return True

    def _login_sync(self, account: dict):
        try:
            from fubon_neo.sdk import FubonSDK, Mode
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "fubon_neo SDK is not installed. Install docs/fubon_neo-2.2.8-cp37-abi3-win_amd64.whl first."
            ) from exc

        sdk = FubonSDK()
        login_result = self._login_account(sdk, account)
        if not self._is_login_success(login_result):
            raise RuntimeError(self._login_message(login_result) or "Fubon login failed")

        mode = Mode.Normal if account.get("ws_mode") == "Normal" else Mode.Speed
        try:
            sdk.init_realtime(mode)
        except TypeError:
            sdk.init_realtime()

        websocket_client = getattr(getattr(sdk, "marketdata", None), "websocket_client", None)
        ws_stock = getattr(websocket_client, "stock", None)
        ws_futopt = getattr(websocket_client, "futopt", None)
        return sdk, ws_stock, ws_futopt, self._extract_login_accounts(login_result)

    @staticmethod
    def _login_account(sdk, account: dict):
        cert_path = account.get("cert_path") or ""
        cert_password = account.get("cert_password") or ""
        login_args = [account["user_id"]]

        if account.get("api_key"):
            login_args.append(account["api_key"])
            login_args.append(cert_path)
            if cert_password:
                login_args.append(cert_password)
            return sdk.apikey_login(*login_args)

        login_args.append(account["password"])
        login_args.append(cert_path)
        if cert_password:
            login_args.append(cert_password)
        return sdk.login(*login_args)

    @staticmethod
    def _is_login_success(login_result) -> bool:
        if login_result is None:
            return True
        if isinstance(login_result, dict) and "is_success" in login_result:
            return bool(login_result.get("is_success"))
        if hasattr(login_result, "is_success"):
            return bool(getattr(login_result, "is_success"))
        return True

    @staticmethod
    def _login_message(login_result) -> str:
        if isinstance(login_result, dict):
            return str(login_result.get("message") or "")
        if hasattr(login_result, "message"):
            return str(getattr(login_result, "message") or "")
        return ""

    @staticmethod
    def _extract_login_accounts(login_result) -> list[Any]:
        if login_result is None:
            return []
        if isinstance(login_result, (list, tuple)):
            return list(login_result)
        data = _object_field(login_result, "data", "accounts")
        if isinstance(data, (list, tuple)):
            return list(data)
        if data is not None:
            return [data]
        return []

    @staticmethod
    def _select_futopt_account(login_accounts: list[Any]):
        fallback = login_accounts[0] if login_accounts else None
        for account in login_accounts:
            account_type = str(_object_field(account, "account_type", "accountType", "type") or "").lower()
            if any(token in account_type for token in ("futopt", "future", "futures", "option", "期貨")):
                return account
        return fallback

    async def hot_switch(self, account: dict) -> bool:
        old_subscriptions = dict(self._subscription_payloads)

        from database import db as _db
        from repositories.fubon_accounts import FubonAccountRepository

        repo = FubonAccountRepository(_db)
        success = await self._init_with_account(account, repo)
        if not success:
            return False

        self.start_ws_stock()
        self.start_ws_futopt()
        self._restore_ws_subscriptions(old_subscriptions)
        return True

    def register_message_handler(self, handler: Callable[[dict], None]) -> None:
        if handler in self._message_handlers:
            return
        self._message_handlers.append(handler)
        self._attach_message_handlers()

    def unregister_message_handler(self, handler: Callable[[dict], None]) -> None:
        self._message_handlers = [item for item in self._message_handlers if item is not handler]

    def subscribe_stock(self, symbol: str, channel: str = "aggregates") -> Optional[str]:
        return self._subscribe(self._ws_stock, "stock", symbol, channel)

    async def subscribe_stock_async(
        self,
        symbol: str,
        channel: str = "aggregates",
        *,
        timeout: float = 2.5,
    ) -> Optional[str]:
        return await self._subscribe_async(self._ws_stock, "stock", symbol, channel, timeout=timeout)

    def unsubscribe_stock(self, symbol: str, channel: str = "aggregates") -> None:
        self._unsubscribe(self._ws_stock, "stock", symbol, channel)

    def subscribe_futopt(
        self,
        symbol: str,
        channel: str = "aggregates",
        *,
        after_hours: bool = False,
    ) -> Optional[str]:
        return self._subscribe(self._ws_futopt, "futopt", symbol, channel, after_hours=after_hours)

    async def subscribe_futopt_async(
        self,
        symbol: str,
        channel: str = "aggregates",
        *,
        after_hours: bool = False,
        timeout: float = 2.5,
    ) -> Optional[str]:
        return await self._subscribe_async(
            self._ws_futopt,
            "futopt",
            symbol,
            channel,
            after_hours=after_hours,
            timeout=timeout,
        )

    def unsubscribe_futopt(
        self,
        symbol: str,
        channel: str = "aggregates",
        *,
        after_hours: bool = False,
    ) -> None:
        self._unsubscribe(self._ws_futopt, "futopt", symbol, channel, after_hours=after_hours)

    def start_ws_stock(self) -> bool:
        return self._start_ws_target(self._ws_stock, "stock")

    def start_ws_futopt(self) -> bool:
        return self._start_ws_target(self._ws_futopt, "futopt")

    def get_rest_stock(self):
        if not self.connected or not self._sdk:
            return None
        marketdata = getattr(self._sdk, "marketdata", None)
        rest_client = getattr(marketdata, "rest_client", None)
        return getattr(rest_client, "stock", None)

    def get_rest_futopt(self):
        if not self.connected or not self._sdk:
            return None
        marketdata = getattr(self._sdk, "marketdata", None)
        rest_client = getattr(marketdata, "rest_client", None)
        return getattr(rest_client, "futopt", None)

    async def ensure_marketdata_ready(self, *, require_futopt: bool = False) -> bool:
        if self._shutting_down:
            return False
        if self._has_marketdata_ready(require_futopt=require_futopt):
            return True

        async with self._reinit_lock:
            if self._has_marketdata_ready(require_futopt=require_futopt):
                return True

            from database import db as _db
            from repositories.fubon_accounts import FubonAccountRepository

            repo = FubonAccountRepository(_db)
            account = await repo.get_active_account()
            if not account:
                self.connected = False
                log.info("No active Fubon account configured; marketdata reinitialization skipped")
                return False

            log.warning(
                "Fubon marketdata client unavailable in memory; reinitializing active account %s",
                account.get("label") or account.get("id"),
            )
            success = await self._init_with_account(account, repo)
            if not success:
                return False

            self.start_ws_stock()
            self.start_ws_futopt()
            return self._has_marketdata_ready(require_futopt=require_futopt)

    async def ensure_trading_ready(self) -> bool:
        if self._shutting_down:
            return False
        if self.connected and self._sdk and self._active_futopt_account is not None:
            return True

        async with self._reinit_lock:
            if self.connected and self._sdk and self._active_futopt_account is not None:
                return True

            from database import db as _db
            from repositories.fubon_accounts import FubonAccountRepository

            repo = FubonAccountRepository(_db)
            account = await repo.get_active_account()
            if not account:
                self.connected = False
                log.info("No active Fubon account configured; trading reinitialization skipped")
                return False

            log.warning(
                "Fubon trading client unavailable in memory; reinitializing active account %s",
                account.get("label") or account.get("id"),
            )
            success = await self._init_with_account(account, repo)
            if not success:
                return False

            self.start_ws_stock()
            self.start_ws_futopt()
            return bool(self.connected and self._sdk and self._active_futopt_account is not None)

    async def _recover_marketdata_session(
        self,
        exc: Exception,
        *,
        require_futopt: bool = False,
    ) -> bool:
        if self._shutting_down or not _is_marketdata_auth_error(exc):
            return False

        old_subscriptions = dict(self._subscription_payloads)
        self.connected = False

        async with self._reinit_lock:
            from database import db as _db
            from repositories.fubon_accounts import FubonAccountRepository

            repo = FubonAccountRepository(_db)
            account = await repo.get_active_account()
            if not account:
                log.warning("Fubon marketdata authentication failed and no active account is configured")
                return False

            log.warning(
                "Fubon marketdata authentication failed; reinitializing active account %s",
                account.get("label") or account.get("id"),
            )
            success = await self._init_with_account(account, repo)
            if not success:
                return False

            self.start_ws_stock()
            self.start_ws_futopt()
            self._restore_ws_subscriptions(old_subscriptions)
            return self._has_marketdata_ready(require_futopt=require_futopt)

    async def _call_marketdata_rest(
        self,
        client_getter: Callable[[], Any],
        request: Callable[[Any], Any],
        *,
        require_futopt: bool = False,
        operation: str = "marketdata request",
    ) -> Optional[dict]:
        last_auth_error: Exception | None = None
        for attempt in range(2):
            await self.ensure_marketdata_ready(require_futopt=require_futopt)
            client = client_getter()
            if not client:
                return None

            try:
                return await asyncio.to_thread(lambda: request(client))
            except Exception as exc:
                if not _is_marketdata_auth_error(exc):
                    raise

                last_auth_error = exc
                if attempt == 0 and await self._recover_marketdata_session(exc, require_futopt=require_futopt):
                    continue
                raise FubonMarketdataAuthenticationError(
                    f"Fubon {operation} failed because marketdata authentication is invalid or expired"
                ) from exc

        if last_auth_error:
            raise FubonMarketdataAuthenticationError(
                f"Fubon {operation} failed because marketdata authentication is invalid or expired"
            ) from last_auth_error
        return None

    def _has_marketdata_ready(self, *, require_futopt: bool = False) -> bool:
        if not self.connected:
            return False
        if self.get_rest_stock() is None:
            return False
        if require_futopt and self.get_rest_futopt() is None:
            return False
        return True

    def get_futopt_account(self):
        if self._active_futopt_account is not None:
            return self._active_futopt_account
        self._active_futopt_account = self._select_futopt_account(self._login_accounts)
        return self._active_futopt_account

    async def query_futopt_estimate_margin(
        self,
        symbol: str,
        *,
        price: float,
        lot: int = 1,
        session: str | None = "REGULAR",
    ):
        if not await self.ensure_trading_ready():
            raise RuntimeError("Fubon trading client is not ready")
        account = self.get_futopt_account()
        if account is None:
            raise RuntimeError("No Fubon futures/options account returned by login")
        futopt_api = getattr(self._sdk, "futopt", None)
        query_estimate_margin = getattr(futopt_api, "query_estimate_margin", None)
        if not callable(query_estimate_margin):
            raise RuntimeError("Fubon futopt query_estimate_margin API is unavailable")
        order = _build_futopt_estimate_margin_order(
            symbol,
            price=price,
            lot=lot,
            session=session,
        )

        def _query_sync():
            return query_estimate_margin(account, order)

        return await asyncio.to_thread(_query_sync)

    async def fetch_stock_quote(self, symbol: str) -> Optional[dict]:
        def _fetch_sync(rest_stock):
            intraday = getattr(rest_stock, "intraday", None)
            quote = getattr(intraday, "quote", None)
            if not callable(quote):
                return None
            return quote(symbol=symbol)

        return await self._call_marketdata_rest(self.get_rest_stock, _fetch_sync, operation="stock quote")

    async def fetch_stock_intraday_candles(
        self,
        symbol: str,
        *,
        timeframe: str | None = None,
        sort: str | None = None,
    ) -> Optional[dict]:
        def _fetch_sync(rest_stock):
            intraday = getattr(rest_stock, "intraday", None)
            candles = getattr(intraday, "candles", None)
            if not callable(candles):
                return None
            kwargs = {"symbol": symbol}
            if timeframe:
                kwargs["timeframe"] = str(timeframe)
            if sort:
                kwargs["sort"] = str(sort)
            return candles(**kwargs)

        return await self._call_marketdata_rest(
            self.get_rest_stock,
            _fetch_sync,
            operation="stock intraday candles",
        )

    async def fetch_stock_historical_candles(
        self,
        symbol: str,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        timeframe: str | None = None,
        adjusted: bool | None = None,
        sort: str | None = None,
    ) -> Optional[dict]:
        def _fetch_sync(rest_stock):
            historical = getattr(rest_stock, "historical", None) or getattr(rest_stock, "history", None)
            candles = getattr(historical, "candles", None)
            if not callable(candles):
                return None
            kwargs = {"symbol": symbol}
            if from_date:
                kwargs["from"] = from_date
            if to_date:
                kwargs["to"] = to_date
            if timeframe:
                kwargs["timeframe"] = str(timeframe)
            if adjusted is not None:
                kwargs["adjusted"] = "true" if adjusted else "false"
            if sort:
                kwargs["sort"] = str(sort)
            return candles(**kwargs)

        return await self._call_marketdata_rest(
            self.get_rest_stock,
            _fetch_sync,
            operation="stock historical candles",
        )

    async def fetch_stock_snapshot_quotes(
        self,
        *,
        market: str = "TSE",
    ) -> Optional[dict]:
        def _fetch_sync(rest_stock):
            snapshot = getattr(rest_stock, "snapshot", None)
            quotes = getattr(snapshot, "quotes", None)
            if not callable(quotes):
                return None
            return quotes(market=market)

        return await self._call_marketdata_rest(self.get_rest_stock, _fetch_sync, operation="stock snapshot quotes")

    async def fetch_stock_snapshot_movers(
        self,
        *,
        market: str = "TSE",
        direction: str = "up",
        change: str = "percent",
    ) -> Optional[dict]:
        def _fetch_sync(rest_stock):
            snapshot = getattr(rest_stock, "snapshot", None)
            movers = getattr(snapshot, "movers", None)
            if not callable(movers):
                return None
            return movers(market=market, direction=direction, change=change)

        return await self._call_marketdata_rest(self.get_rest_stock, _fetch_sync, operation="stock snapshot movers")

    async def fetch_stock_snapshot_actives(
        self,
        *,
        market: str = "TSE",
        trade: str = "value",
    ) -> Optional[dict]:
        def _fetch_sync(rest_stock):
            snapshot = getattr(rest_stock, "snapshot", None)
            actives = getattr(snapshot, "actives", None)
            if not callable(actives):
                return None
            return actives(market=market, trade=trade)

        return await self._call_marketdata_rest(self.get_rest_stock, _fetch_sync, operation="stock snapshot actives")

    async def fetch_futopt_products(
        self,
        *,
        type: str = "FUTURE",
        exchange: str = "TAIFEX",
        session: str = "REGULAR",
        contractType: str = "I",
    ) -> Optional[dict]:
        def _fetch_sync(rest_futopt):
            intraday = getattr(rest_futopt, "intraday", None)
            products = getattr(intraday, "products", None)
            if not callable(products):
                return None
            return products(
                type=type,
                exchange=exchange,
                session=session,
                contractType=contractType,
            )

        return await self._call_marketdata_rest(
            self.get_rest_futopt,
            _fetch_sync,
            require_futopt=True,
            operation="futopt products",
        )

    async def fetch_futopt_quote(
        self,
        symbol: str,
        *,
        session: str | None = None,
    ) -> Optional[dict]:
        def _fetch_sync(rest_futopt):
            intraday = getattr(rest_futopt, "intraday", None)
            quote = getattr(intraday, "quote", None)
            if not callable(quote):
                return None
            kwargs = {"symbol": symbol}
            normalized_session = _normalize_futopt_session(session)
            if normalized_session:
                kwargs["session"] = normalized_session
            return quote(**kwargs)

        return await self._call_marketdata_rest(
            self.get_rest_futopt,
            _fetch_sync,
            require_futopt=True,
            operation="futopt quote",
        )

    async def fetch_futopt_tickers(
        self,
        *,
        type: str = "FUTURE",
        exchange: str = "TAIFEX",
        session: str = "REGULAR",
        contractType: str = "I",
        product: str | None = None,
    ) -> Optional[dict]:
        def _fetch_sync(rest_futopt):
            intraday = getattr(rest_futopt, "intraday", None)
            tickers = getattr(intraday, "tickers", None)
            if not callable(tickers):
                return None
            kwargs = dict(
                type=type,
                exchange=exchange,
                session=session,
                contractType=contractType,
            )
            if product:
                kwargs["product"] = str(product)
            return tickers(**kwargs)

        return await self._call_marketdata_rest(
            self.get_rest_futopt,
            _fetch_sync,
            require_futopt=True,
            operation="futopt tickers",
        )

    async def fetch_futopt_intraday_candles(
        self,
        symbol: str,
        *,
        timeframe: str | None = None,
        session: str | None = None,
    ) -> Optional[dict]:
        def _fetch_sync(rest_futopt):
            intraday = getattr(rest_futopt, "intraday", None)
            candles = getattr(intraday, "candles", None)
            if not callable(candles):
                return None
            kwargs = {"symbol": symbol}
            if timeframe:
                kwargs["timeframe"] = str(timeframe)
            normalized_session = _normalize_futopt_session(session)
            if normalized_session:
                kwargs["session"] = normalized_session
            return candles(**kwargs)

        return await self._call_marketdata_rest(
            self.get_rest_futopt,
            _fetch_sync,
            require_futopt=True,
            operation="futopt intraday candles",
        )

    def shutdown(self) -> None:
        self._shutting_down = True
        self.connected = False
        self._cancel_all_reconnect_timers()
        self._message_handlers.clear()
        self._best_effort_shutdown(self._ws_stock)
        self._best_effort_shutdown(self._ws_futopt)
        self._best_effort_shutdown(self._sdk)
        self._reset_runtime_state()

    def _reset_runtime_state(self) -> None:
        self._sdk = None
        self._active_account_id = None
        self._ws_mode = "Speed"
        self._ws_stock = None
        self._ws_futopt = None
        self._login_accounts = []
        self._active_futopt_account = None
        self._ws_started_targets = set()
        self._subscriptions = {}
        self._subscription_payloads = {}
        self._subscription_id_to_key = {}
        self._pending_subscription_acks = {}
        self._cancel_all_reconnect_timers()
        self._ws_reconnect_attempts = {"stock": 0, "futopt": 0}
        self._ws_reconnect_last_error = {"stock": None, "futopt": None}
        self._ws_reconnect_last_success_at = {"stock": None, "futopt": None}
        self._attached_targets = set()
        self.connected = False

    def _attach_message_handlers(self) -> None:
        self._attach_target_handlers(self._ws_stock, "stock")
        self._attach_target_handlers(self._ws_futopt, "futopt")

    def _attach_target_handlers(self, target, market_type: str) -> None:
        if not target or market_type in self._attached_targets:
            return

        on_method = getattr(target, "on", None)
        if callable(on_method):
            for event_name in ("message", "data"):
                try:
                    on_method(event_name, lambda message, mt=market_type: self._dispatch_ws_message(mt, message))
                    break
                except Exception:
                    continue
            for event_name, callback in (
                ("connect", lambda *args, mt=market_type: self._handle_ws_connect(mt, *args)),
                ("disconnect", lambda *args, mt=market_type: self._handle_ws_disconnect(mt, *args)),
                ("error", lambda *args, mt=market_type: self._handle_ws_error(mt, *args)),
            ):
                try:
                    on_method(event_name, callback)
                except Exception:
                    continue
            self._attached_targets.add(market_type)
            return

        for attr_name in ("onmessage", "on_message"):
            if hasattr(target, attr_name):
                try:
                    setattr(target, attr_name, lambda message, mt=market_type: self._dispatch_ws_message(mt, message))
                    self._attached_targets.add(market_type)
                    return
                except Exception:
                    continue

    def _dispatch_ws_message(self, market_type: str, message: Any) -> None:
        if self._shutting_down:
            return
        payload = self._normalize_ws_message(market_type, message)
        if not payload:
            return
        self._update_subscription_state(payload)
        self._update_pending_subscription_acks(payload)
        for handler in list(self._message_handlers):
            try:
                handler(payload)
            except Exception as exc:
                log.warning("Fubon message handler failed: %s", exc)

    def _handle_ws_connect(self, market_type: str, *args) -> None:
        if self._shutting_down:
            return
        self._cancel_reconnect_timer(market_type)
        self._ws_reconnect_attempts[market_type] = 0
        self._ws_reconnect_last_error[market_type] = None
        self._ws_reconnect_last_success_at[market_type] = datetime.now(timezone.utc).isoformat()
        self._ws_started_targets.add(market_type)
        log.info("Fubon %s websocket connected", market_type)

    def _handle_ws_disconnect(self, market_type: str, *args) -> None:
        self._ws_started_targets.discard(market_type)
        if self._shutting_down or not self.connected:
            log.info("Fubon %s websocket closed during shutdown", market_type)
            return
        log.warning("Fubon %s websocket disconnected: %s", market_type, args or "unknown")
        self._ws_reconnect_last_error[market_type] = redact_sensitive_text(args or "disconnected")
        self._schedule_reconnect_ws_target(market_type)

    def _handle_ws_error(self, market_type: str, *args) -> None:
        if self._shutting_down:
            return
        log.warning("Fubon %s websocket error: %s", market_type, args or "unknown")
        if any(_is_marketdata_auth_error(arg) for arg in args if isinstance(arg, Exception) or arg is not None):
            self._invalidate_marketdata_session(
                f"Fubon {market_type} websocket authentication failed: {args or 'unknown'}"
            )
            return
        self._ws_reconnect_last_error[market_type] = redact_sensitive_text(args or "websocket error")
        self._schedule_reconnect_ws_target(market_type)

    def _reconnect_ws_target(self, market_type: str) -> bool:
        if not self.connected:
            return False
        target = self._ws_stock if market_type == "stock" else self._ws_futopt
        self._best_effort_shutdown(target)
        started = self.start_ws_stock() if market_type == "stock" else self.start_ws_futopt()
        if not started:
            return False
        self._restore_ws_subscriptions(
            {
                key: payload
                for key, payload in self._subscription_payloads.items()
                if key.startswith(f"{market_type}:")
            }
        )
        return True

    def force_reconnect_ws(self, market_type: str) -> bool:
        normalized = str(market_type or "").strip().lower()
        if normalized not in {"stock", "futopt"}:
            raise ValueError("market_type must be stock or futopt")
        self._cancel_reconnect_timer(normalized)
        try:
            return self._reconnect_ws_target(normalized)
        except Exception as exc:
            safe_error = redact_sensitive_text(exc)
            self._ws_reconnect_last_error[normalized] = safe_error
            log.warning("Fubon %s manual websocket reconnect failed: %s", normalized, safe_error)
            self._schedule_reconnect_ws_target(normalized)
            return False

    def get_reconnect_status(self) -> dict[str, dict[str, Any]]:
        with self._ws_reconnect_lock:
            pending = {
                market_type: bool(timer and timer.is_alive())
                for market_type, timer in self._ws_reconnect_timers.items()
            }
        return {
            market_type: {
                "attempts": int(self._ws_reconnect_attempts.get(market_type, 0)),
                "pending": bool(pending.get(market_type)),
                "last_error": self._ws_reconnect_last_error.get(market_type),
                "last_success_at": self._ws_reconnect_last_success_at.get(market_type),
            }
            for market_type in ("stock", "futopt")
        }

    def _schedule_reconnect_ws_target(self, market_type: str) -> None:
        if not self.connected or self._shutting_down:
            return

        with self._ws_reconnect_lock:
            existing = self._ws_reconnect_timers.get(market_type)
            if existing and existing.is_alive():
                return

            attempts = max(0, int(self._ws_reconnect_attempts.get(market_type, 0)))
            delay_seconds = min(
                self._RECONNECT_MAX_DELAY_SECONDS,
                self._RECONNECT_DELAY_SECONDS * (2 ** min(attempts, 8)),
            )
            timer = threading.Timer(
                delay_seconds,
                lambda mt=market_type: self._run_scheduled_reconnect(mt),
            )
            timer.daemon = True
            self._ws_reconnect_timers[market_type] = timer
            timer.start()

    def _run_scheduled_reconnect(self, market_type: str) -> None:
        self._cancel_reconnect_timer(market_type, cancel_active=False)
        if self._shutting_down or not self.connected:
            return
        self._ws_reconnect_attempts[market_type] = self._ws_reconnect_attempts.get(market_type, 0) + 1
        try:
            started = self._reconnect_ws_target(market_type)
            if started is False:
                self._schedule_reconnect_ws_target(market_type)
        except Exception as exc:
            safe_error = redact_sensitive_text(exc)
            self._ws_reconnect_last_error[market_type] = safe_error
            log.warning("Fubon %s websocket reconnect failed: %s", market_type, safe_error)
            self._schedule_reconnect_ws_target(market_type)

    def _cancel_reconnect_timer(self, market_type: str, *, cancel_active: bool = True) -> None:
        with self._ws_reconnect_lock:
            timer = self._ws_reconnect_timers.pop(market_type, None)
        if timer and cancel_active:
            try:
                timer.cancel()
            except Exception:
                pass

    def _cancel_all_reconnect_timers(self) -> None:
        with self._ws_reconnect_lock:
            timers = list(self._ws_reconnect_timers.values())
            self._ws_reconnect_timers = {}
        for timer in timers:
            try:
                timer.cancel()
            except Exception:
                pass

    def _invalidate_marketdata_session(self, reason: str) -> None:
        if self._shutting_down:
            return
        log.warning("%s; marking Fubon marketdata session for reinitialization", reason)
        self.connected = False
        self._ws_started_targets.clear()
        self._attached_targets.clear()
        self._cancel_all_reconnect_timers()
        self._best_effort_shutdown(self._ws_stock)
        self._best_effort_shutdown(self._ws_futopt)

    def _restore_ws_subscriptions(self, payloads: Dict[str, dict]) -> None:
        for key, payload in payloads.items():
            market_type, _, _, _ = self._split_subscription_key(key)
            symbol = payload.get("symbol")
            channel = payload.get("channel")
            if not symbol or not channel:
                continue
            after_hours = self._coerce_bool(payload.get("afterHours"))
            if market_type == "stock":
                self._subscribe(self._ws_stock, "stock", symbol, channel, force=True)
            elif market_type == "futopt":
                self._subscribe(
                    self._ws_futopt,
                    "futopt",
                    symbol,
                    channel,
                    force=True,
                    after_hours=after_hours,
                )

    def _subscribe(
        self,
        target,
        market_type: str,
        symbol: str,
        channel: str,
        *,
        force: bool = False,
        after_hours: bool = False,
    ) -> Optional[str]:
        if not target:
            return None
        key = self._subscription_key(market_type, symbol, channel, after_hours=after_hours)
        if key in self._subscriptions and not force:
            return self._subscriptions[key]
        if force:
            previous_id = self._subscriptions.get(key)
            if previous_id:
                self._subscription_id_to_key.pop(previous_id, None)

        payload = {"channel": channel, "symbol": symbol}
        if market_type == "futopt" and after_hours:
            payload["afterHours"] = True
        result = self._call_ws_method(target, "subscribe", payload)
        channel_id = self._extract_subscription_id(result) or key
        self._subscription_payloads[key] = payload
        self._subscriptions[key] = channel_id
        if channel_id != key:
            self._subscription_id_to_key[channel_id] = key
        return channel_id

    async def _subscribe_async(
        self,
        target,
        market_type: str,
        symbol: str,
        channel: str,
        *,
        force: bool = False,
        after_hours: bool = False,
        timeout: float = 2.5,
    ) -> Optional[str]:
        if not target:
            return None
        key = self._subscription_key(market_type, symbol, channel, after_hours=after_hours)
        if key in self._subscriptions and not force:
            return self._subscriptions[key]

        loop = asyncio.get_running_loop()
        ack_future: asyncio.Future[str] = loop.create_future()
        pending = self._pending_subscription_acks.setdefault(key, [])
        pending.append(ack_future)

        channel_id = None
        try:
            channel_id = self._subscribe(
                target,
                market_type,
                symbol,
                channel,
                force=force,
                after_hours=after_hours,
            )
            if channel_id and channel_id != key:
                if not ack_future.done():
                    ack_future.set_result(channel_id)
            return await asyncio.wait_for(ack_future, timeout=max(float(timeout or 0), 0.1))
        except Exception:
            if channel_id:
                self._unsubscribe(target, market_type, symbol, channel, after_hours=after_hours)
            raise
        finally:
            self._discard_pending_subscription_ack(key, ack_future)

    def _unsubscribe(
        self,
        target,
        market_type: str,
        symbol: str,
        channel: str,
        *,
        after_hours: bool = False,
    ) -> None:
        key = self._subscription_key(market_type, symbol, channel, after_hours=after_hours)
        channel_id = self._subscriptions.pop(key, None)
        self._subscription_payloads.pop(key, None)
        if channel_id:
            self._subscription_id_to_key.pop(channel_id, None)
        if not channel_id or not target or channel_id == key:
            return
        self._call_ws_method(target, "unsubscribe", {"id": channel_id})

    def _update_subscription_state(self, message: dict) -> None:
        event = str(message.get("event") or "").strip().lower()
        if event not in {"subscribed", "unsubscribed"}:
            return
        market_type = str(message.get("market_type") or "stock")
        data = message.get("data")
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            channel = item.get("channel")
            channel_id = self._extract_subscription_id(item)
            if not symbol or not channel:
                continue
            key = self._resolve_subscription_key_for_ack(market_type, str(symbol), str(channel), item)
            if event == "subscribed":
                self._subscription_payloads.setdefault(key, {"channel": channel, "symbol": symbol})
                if key.endswith(":afterhours"):
                    self._subscription_payloads[key]["afterHours"] = True
                if channel_id:
                    self._subscriptions[key] = channel_id
                    self._subscription_id_to_key[channel_id] = key
                else:
                    self._subscriptions.setdefault(key, key)
                continue

            resolved_key = self._subscription_id_to_key.pop(channel_id, None) if channel_id else None
            self._subscriptions.pop(resolved_key or key, None)
            self._subscription_payloads.pop(resolved_key or key, None)

    def _update_pending_subscription_acks(self, message: dict) -> None:
        event = str(message.get("event") or "").strip().lower()
        if event == "subscribed":
            market_type = str(message.get("market_type") or "stock")
            data = message.get("data")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                symbol = item.get("symbol")
                channel = item.get("channel")
                channel_id = self._extract_subscription_id(item)
                if not symbol or not channel:
                    continue
                key = self._resolve_subscription_key_for_ack(market_type, str(symbol), str(channel), item)
                for future in list(self._pending_subscription_acks.get(key, [])):
                    if not future.done():
                        future.set_result(str(channel_id or key))
                continue
            return

        if event != "error":
            return

        data = message.get("data")
        message_text = ""
        if isinstance(data, dict):
            message_text = str(data.get("message") or data.get("detail") or "").strip()
        error = RuntimeError(message_text or "Fubon realtime subscription failed")
        for futures in self._pending_subscription_acks.values():
            for future in list(futures):
                if not future.done():
                    future.set_exception(error)

    def _discard_pending_subscription_ack(self, key: str, future: asyncio.Future[str]) -> None:
        futures = self._pending_subscription_acks.get(key)
        if not futures:
            return
        self._pending_subscription_acks[key] = [item for item in futures if item is not future and not item.done()]
        if not self._pending_subscription_acks[key]:
            self._pending_subscription_acks.pop(key, None)

    @staticmethod
    def _normalize_ws_message(market_type: str, message: Any) -> Optional[dict]:
        payload = message
        if isinstance(message, str):
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                payload = {"event": "message", "data": {"raw": message}}
        if not isinstance(payload, dict):
            return None
        normalized = dict(payload)
        normalized.setdefault("market_type", market_type)
        return normalized

    @staticmethod
    def _subscription_key(market_type: str, symbol: str, channel: str, *, after_hours: bool = False) -> str:
        suffix = ":afterhours" if market_type == "futopt" and after_hours else ""
        return f"{market_type}:{symbol}:{channel}{suffix}"

    def _subscription_key_candidates(
        self,
        market_type: str,
        symbol: str,
        channel: str,
        *,
        after_hours: bool | None = None,
    ) -> list[str]:
        if market_type != "futopt":
            return [self._subscription_key(market_type, symbol, channel)]
        if after_hours is not None:
            return [self._subscription_key(market_type, symbol, channel, after_hours=after_hours)]
        return [
            self._subscription_key(market_type, symbol, channel),
            self._subscription_key(market_type, symbol, channel, after_hours=True),
        ]

    def _resolve_subscription_key_for_ack(self, market_type: str, symbol: str, channel: str, item: dict) -> str:
        raw_after_hours = item.get("afterHours")
        explicit_after_hours = None if raw_after_hours is None else self._coerce_bool(raw_after_hours)
        candidates = self._subscription_key_candidates(
            market_type,
            symbol,
            channel,
            after_hours=explicit_after_hours,
        )
        for key in candidates:
            if key in self._pending_subscription_acks:
                return key
        for key in candidates:
            if key in self._subscriptions or key in self._subscription_payloads:
                return key
        return candidates[0]

    @staticmethod
    def _split_subscription_key(key: str) -> tuple[str, str, str, bool]:
        parts = str(key).split(":")
        if len(parts) < 3:
            return "stock", "", "", False
        return parts[0], parts[1], parts[2], len(parts) > 3 and parts[3] == "afterhours"

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)

    @staticmethod
    def _call_ws_method(target, method_name: str, payload: dict):
        method = getattr(target, method_name, None)
        if not callable(method):
            return None
        return method(payload)

    @staticmethod
    def _extract_subscription_id(result: Any) -> Optional[str]:
        if isinstance(result, dict):
            value = result.get("id") or result.get("channel_id")
            return str(value) if value else None
        if result:
            return str(result)
        return None

    def _start_ws_target(self, target, market_type: str) -> bool:
        if self._shutting_down or not target:
            return False
        self._attach_message_handlers()
        if market_type in self._ws_started_targets:
            return True

        for method_name in ("connect", "start"):
            method = getattr(target, method_name, None)
            if not callable(method):
                continue
            self._ws_started_targets.add(market_type)
            try:
                method()
                return True
            except Exception as exc:
                message = str(exc).strip().lower()
                if "socket is already opened" in message:
                    log.info("Fubon %s websocket already running", market_type)
                    return True
                self._ws_started_targets.discard(market_type)
                log.warning(
                    "Fubon %s websocket %s failed: %s",
                    market_type,
                    method_name,
                    redact_sensitive_text(exc),
                )
                return False
        self._ws_started_targets.add(market_type)
        return True

    @staticmethod
    def _best_effort_shutdown(target) -> None:
        if target is None:
            return
        for method_name in ("disconnect", "close", "stop", "logout"):
            method = getattr(target, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception:
                    pass


async def test_fubon_login(account: dict) -> dict:
    manager = FubonSDKManager()
    targets = ()
    try:
        targets = await asyncio.to_thread(manager._login_sync, account)
        return {"success": True, "message": "連線測試成功"}
    except Exception as exc:
        return {
            "success": False,
            "message": redact_sensitive_text(exc, secrets=secret_values_from_account(account)),
        }
    finally:
        for target in targets:
            manager._best_effort_shutdown(target)
        manager.shutdown()
