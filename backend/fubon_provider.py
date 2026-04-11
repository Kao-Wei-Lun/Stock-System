from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional


log = logging.getLogger(__name__)


class FubonSDKManager:
    def __init__(self):
        self._sdk = None
        self._active_account_id: Optional[int] = None
        self._ws_stock = None
        self._ws_futopt = None
        self._subscriptions: Dict[str, str] = {}
        self._subscription_payloads: Dict[str, dict] = {}
        self._subscription_id_to_key: Dict[str, str] = {}
        self._message_handlers: list[Callable[[dict], None]] = []
        self._attached_targets: set[str] = set()
        self.connected = False

    @property
    def enabled(self) -> bool:
        return self.connected and self._sdk is not None

    @property
    def active_account_id(self) -> Optional[int]:
        return self._active_account_id

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
        self._message_handlers.append(handler)
        self._attach_message_handlers()

    def subscribe_stock(self, symbol: str, channel: str = "aggregates") -> Optional[str]:
        return self._subscribe(self._ws_stock, "stock", symbol, channel)

    def unsubscribe_stock(self, symbol: str, channel: str = "aggregates") -> None:
        self._unsubscribe(self._ws_stock, "stock", symbol, channel)

    def subscribe_futopt(self, symbol: str, channel: str = "aggregates") -> Optional[str]:
        return self._subscribe(self._ws_futopt, "futopt", symbol, channel)

    def unsubscribe_futopt(self, symbol: str, channel: str = "aggregates") -> None:
        self._unsubscribe(self._ws_futopt, "futopt", symbol, channel)

    def start_ws_stock(self) -> bool:
        if not self._ws_stock:
            return False
        self._attach_message_handlers()
        for method_name in ("connect", "start"):
            method = getattr(self._ws_stock, method_name, None)
            if callable(method):
                try:
                    method()
                    return True
                except Exception as exc:
                    log.warning("Fubon stock websocket %s failed: %s", method_name, exc)
                    return False
        return True

    def start_ws_futopt(self) -> bool:
        if not self._ws_futopt:
            return False
        self._attach_message_handlers()
        for method_name in ("connect", "start"):
            method = getattr(self._ws_futopt, method_name, None)
            if callable(method):
                try:
                    method()
                    return True
                except Exception as exc:
                    log.warning("Fubon futopt websocket %s failed: %s", method_name, exc)
                    return False
        return True

    def get_rest_stock(self):
        if not self.connected or not self._sdk:
            return None
        marketdata = getattr(self._sdk, "marketdata", None)
        rest_client = getattr(marketdata, "rest_client", None)
        return getattr(rest_client, "stock", None)

    async def fetch_stock_quote(self, symbol: str) -> Optional[dict]:
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

    def shutdown(self) -> None:
        self._best_effort_shutdown(self._ws_stock)
        self._best_effort_shutdown(self._ws_futopt)
        self._best_effort_shutdown(self._sdk)
        self._reset_runtime_state()

    def _reset_runtime_state(self) -> None:
        self._sdk = None
        self._active_account_id = None
        self._ws_stock = None
        self._ws_futopt = None
        self._subscriptions = {}
        self._subscription_payloads = {}
        self._subscription_id_to_key = {}
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
        payload = self._normalize_ws_message(market_type, message)
        if not payload:
            return
        self._update_subscription_state(payload)
        for handler in list(self._message_handlers):
            try:
                handler(payload)
            except Exception as exc:
                log.warning("Fubon message handler failed: %s", exc)

    def _handle_ws_connect(self, market_type: str, *args) -> None:
        log.info("Fubon %s websocket connected", market_type)

    def _handle_ws_disconnect(self, market_type: str, *args) -> None:
        log.warning("Fubon %s websocket disconnected: %s", market_type, args or "unknown")
        self._reconnect_ws_target(market_type)

    def _handle_ws_error(self, market_type: str, *args) -> None:
        log.warning("Fubon %s websocket error: %s", market_type, args or "unknown")

    def _reconnect_ws_target(self, market_type: str) -> None:
        if not self.connected:
            return
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
