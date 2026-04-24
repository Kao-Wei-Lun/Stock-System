from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, Callable, Dict, Optional


log = logging.getLogger(__name__)


def _normalize_futopt_session(session: str | None) -> Optional[str]:
    raw = str(session or "").strip().lower()
    if raw in {"afterhours", "night", "night_session"}:
        return "afterhours"
    return None


class FubonSDKManager:
    _RECONNECT_DELAY_SECONDS = 1.0

    def __init__(self):
        self._sdk = None
        self._active_account_id: Optional[int] = None
        self._ws_mode = "Speed"
        self._ws_stock = None
        self._ws_futopt = None
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
            sdk, ws_stock, ws_futopt = await asyncio.to_thread(self._login_sync, account)
        except Exception as exc:
            for target in old_targets:
                self._best_effort_shutdown(target)
            self.connected = False
            if repo and account_id:
                await repo.update_connection_status(account_id, "error", str(exc))
            log.error("Fubon SDK initialization failed: %s", exc)
            return False

        for target in old_targets:
            self._best_effort_shutdown(target)
        self._sdk = sdk
        self._active_account_id = account_id
        self._ws_mode = str(account.get("ws_mode") or "Speed")
        self._ws_stock = ws_stock
        self._ws_futopt = ws_futopt
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
        return sdk, ws_stock, ws_futopt

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

    def subscribe_futopt(self, symbol: str, channel: str = "aggregates") -> Optional[str]:
        return self._subscribe(self._ws_futopt, "futopt", symbol, channel)

    async def subscribe_futopt_async(
        self,
        symbol: str,
        channel: str = "aggregates",
        *,
        timeout: float = 2.5,
    ) -> Optional[str]:
        return await self._subscribe_async(self._ws_futopt, "futopt", symbol, channel, timeout=timeout)

    def unsubscribe_futopt(self, symbol: str, channel: str = "aggregates") -> None:
        self._unsubscribe(self._ws_futopt, "futopt", symbol, channel)

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

    def _has_marketdata_ready(self, *, require_futopt: bool = False) -> bool:
        if not self.connected:
            return False
        if self.get_rest_stock() is None:
            return False
        if require_futopt and self.get_rest_futopt() is None:
            return False
        return True

    async def fetch_stock_quote(self, symbol: str) -> Optional[dict]:
        await self.ensure_marketdata_ready()
        rest_stock = self.get_rest_stock()
        if not rest_stock:
            return None

        def _fetch_sync():
            intraday = getattr(rest_stock, "intraday", None)
            quote = getattr(intraday, "quote", None)
            if not callable(quote):
                return None
            return quote(symbol=symbol)

        return await asyncio.to_thread(_fetch_sync)

    async def fetch_stock_intraday_candles(
        self,
        symbol: str,
        *,
        timeframe: str | None = None,
        sort: str | None = None,
    ) -> Optional[dict]:
        await self.ensure_marketdata_ready()
        rest_stock = self.get_rest_stock()
        if not rest_stock:
            return None

        def _fetch_sync():
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

        return await asyncio.to_thread(_fetch_sync)

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
        await self.ensure_marketdata_ready()
        rest_stock = self.get_rest_stock()
        if not rest_stock:
            return None

        def _fetch_sync():
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

        return await asyncio.to_thread(_fetch_sync)

    async def fetch_stock_snapshot_quotes(
        self,
        *,
        market: str = "TSE",
    ) -> Optional[dict]:
        await self.ensure_marketdata_ready()
        rest_stock = self.get_rest_stock()
        if not rest_stock:
            return None

        def _fetch_sync():
            snapshot = getattr(rest_stock, "snapshot", None)
            quotes = getattr(snapshot, "quotes", None)
            if not callable(quotes):
                return None
            return quotes(market=market)

        return await asyncio.to_thread(_fetch_sync)

    async def fetch_stock_snapshot_movers(
        self,
        *,
        market: str = "TSE",
        direction: str = "up",
        change: str = "percent",
    ) -> Optional[dict]:
        await self.ensure_marketdata_ready()
        rest_stock = self.get_rest_stock()
        if not rest_stock:
            return None

        def _fetch_sync():
            snapshot = getattr(rest_stock, "snapshot", None)
            movers = getattr(snapshot, "movers", None)
            if not callable(movers):
                return None
            return movers(market=market, direction=direction, change=change)

        return await asyncio.to_thread(_fetch_sync)

    async def fetch_stock_snapshot_actives(
        self,
        *,
        market: str = "TSE",
        trade: str = "value",
    ) -> Optional[dict]:
        await self.ensure_marketdata_ready()
        rest_stock = self.get_rest_stock()
        if not rest_stock:
            return None

        def _fetch_sync():
            snapshot = getattr(rest_stock, "snapshot", None)
            actives = getattr(snapshot, "actives", None)
            if not callable(actives):
                return None
            return actives(market=market, trade=trade)

        return await asyncio.to_thread(_fetch_sync)

    async def fetch_futopt_products(
        self,
        *,
        type: str = "FUTURE",
        exchange: str = "TAIFEX",
        session: str = "REGULAR",
        contractType: str = "I",
    ) -> Optional[dict]:
        await self.ensure_marketdata_ready(require_futopt=True)
        rest_futopt = self.get_rest_futopt()
        if not rest_futopt:
            return None

        def _fetch_sync():
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

        return await asyncio.to_thread(_fetch_sync)

    async def fetch_futopt_quote(
        self,
        symbol: str,
        *,
        session: str | None = None,
    ) -> Optional[dict]:
        await self.ensure_marketdata_ready(require_futopt=True)
        rest_futopt = self.get_rest_futopt()
        if not rest_futopt:
            return None

        def _fetch_sync():
            intraday = getattr(rest_futopt, "intraday", None)
            quote = getattr(intraday, "quote", None)
            if not callable(quote):
                return None
            kwargs = {"symbol": symbol}
            normalized_session = _normalize_futopt_session(session)
            if normalized_session:
                kwargs["session"] = normalized_session
            return quote(**kwargs)

        return await asyncio.to_thread(_fetch_sync)

    async def fetch_futopt_tickers(
        self,
        *,
        type: str = "FUTURE",
        exchange: str = "TAIFEX",
        session: str = "REGULAR",
        contractType: str = "I",
        product: str | None = None,
    ) -> Optional[dict]:
        await self.ensure_marketdata_ready(require_futopt=True)
        rest_futopt = self.get_rest_futopt()
        if not rest_futopt:
            return None

        def _fetch_sync():
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

        return await asyncio.to_thread(_fetch_sync)

    async def fetch_futopt_intraday_candles(
        self,
        symbol: str,
        *,
        timeframe: str | None = None,
        session: str | None = None,
    ) -> Optional[dict]:
        await self.ensure_marketdata_ready(require_futopt=True)
        rest_futopt = self.get_rest_futopt()
        if not rest_futopt:
            return None

        def _fetch_sync():
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

        return await asyncio.to_thread(_fetch_sync)

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
        self._ws_started_targets = set()
        self._subscriptions = {}
        self._subscription_payloads = {}
        self._subscription_id_to_key = {}
        self._pending_subscription_acks = {}
        self._cancel_all_reconnect_timers()
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
        self._ws_started_targets.add(market_type)
        log.info("Fubon %s websocket connected", market_type)

    def _handle_ws_disconnect(self, market_type: str, *args) -> None:
        self._ws_started_targets.discard(market_type)
        if self._shutting_down or not self.connected:
            log.info("Fubon %s websocket closed during shutdown", market_type)
            return
        log.warning("Fubon %s websocket disconnected: %s", market_type, args or "unknown")
        self._schedule_reconnect_ws_target(market_type)

    def _handle_ws_error(self, market_type: str, *args) -> None:
        if self._shutting_down:
            return
        log.warning("Fubon %s websocket error: %s", market_type, args or "unknown")

    def _reconnect_ws_target(self, market_type: str) -> None:
        if not self.connected:
            return
        target = self._ws_stock if market_type == "stock" else self._ws_futopt
        self._best_effort_shutdown(target)
        started = self.start_ws_stock() if market_type == "stock" else self.start_ws_futopt()
        if not started:
            return
        self._restore_ws_subscriptions(
            {
                key: payload
                for key, payload in self._subscription_payloads.items()
                if key.startswith(f"{market_type}:")
            }
        )

    def _schedule_reconnect_ws_target(self, market_type: str) -> None:
        if not self.connected or self._shutting_down:
            return

        with self._ws_reconnect_lock:
            existing = self._ws_reconnect_timers.get(market_type)
            if existing and existing.is_alive():
                return

            timer = threading.Timer(
                self._RECONNECT_DELAY_SECONDS,
                lambda mt=market_type: self._run_scheduled_reconnect(mt),
            )
            timer.daemon = True
            self._ws_reconnect_timers[market_type] = timer
            timer.start()

    def _run_scheduled_reconnect(self, market_type: str) -> None:
        self._cancel_reconnect_timer(market_type, cancel_active=False)
        if self._shutting_down or not self.connected:
            return
        try:
            self._reconnect_ws_target(market_type)
        except Exception as exc:
            log.warning("Fubon %s websocket reconnect failed: %s", market_type, exc)

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

    def _restore_ws_subscriptions(self, payloads: Dict[str, dict]) -> None:
        for key, payload in payloads.items():
            market_type, _, _ = self._split_subscription_key(key)
            symbol = payload.get("symbol")
            channel = payload.get("channel")
            if not symbol or not channel:
                continue
            if market_type == "stock":
                self._subscribe(self._ws_stock, "stock", symbol, channel, force=True)
            elif market_type == "futopt":
                self._subscribe(self._ws_futopt, "futopt", symbol, channel, force=True)

    def _subscribe(
        self,
        target,
        market_type: str,
        symbol: str,
        channel: str,
        *,
        force: bool = False,
    ) -> Optional[str]:
        if not target:
            return None
        key = self._subscription_key(market_type, symbol, channel)
        if key in self._subscriptions and not force:
            return self._subscriptions[key]
        if force:
            previous_id = self._subscriptions.get(key)
            if previous_id:
                self._subscription_id_to_key.pop(previous_id, None)

        payload = {"channel": channel, "symbol": symbol}
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
        timeout: float = 2.5,
    ) -> Optional[str]:
        if not target:
            return None
        key = self._subscription_key(market_type, symbol, channel)
        if key in self._subscriptions and not force:
            return self._subscriptions[key]

        loop = asyncio.get_running_loop()
        ack_future: asyncio.Future[str] = loop.create_future()
        pending = self._pending_subscription_acks.setdefault(key, [])
        pending.append(ack_future)

        channel_id = None
        try:
            channel_id = self._subscribe(target, market_type, symbol, channel, force=force)
            if channel_id and channel_id != key:
                if not ack_future.done():
                    ack_future.set_result(channel_id)
            return await asyncio.wait_for(ack_future, timeout=max(float(timeout or 0), 0.1))
        except Exception:
            if channel_id:
                self._unsubscribe(target, market_type, symbol, channel)
            raise
        finally:
            self._discard_pending_subscription_ack(key, ack_future)

    def _unsubscribe(self, target, market_type: str, symbol: str, channel: str) -> None:
        key = self._subscription_key(market_type, symbol, channel)
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
            key = self._subscription_key(market_type, str(symbol), str(channel))
            if event == "subscribed":
                self._subscription_payloads.setdefault(key, {"channel": channel, "symbol": symbol})
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
                key = self._subscription_key(market_type, str(symbol), str(channel))
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
    def _subscription_key(market_type: str, symbol: str, channel: str) -> str:
        return f"{market_type}:{symbol}:{channel}"

    @staticmethod
    def _split_subscription_key(key: str) -> tuple[str, str, str]:
        parts = str(key).split(":", 2)
        if len(parts) != 3:
            return "stock", "", ""
        return parts[0], parts[1], parts[2]

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
                log.warning("Fubon %s websocket %s failed: %s", market_type, method_name, exc)
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
        return {"success": False, "message": str(exc)}
    finally:
        for target in targets:
            manager._best_effort_shutdown(target)
        manager.shutdown()
