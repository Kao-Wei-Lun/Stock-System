from __future__ import annotations

import asyncio
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
        self._message_handlers: list[Callable[[dict], None]] = []
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
        old_subscriptions = dict(self._subscriptions)

        from database import db as _db
        from repositories.fubon_accounts import FubonAccountRepository

        repo = FubonAccountRepository(_db)
        success = await self._init_with_account(account, repo)
        if not success:
            return False

        for key in old_subscriptions:
            symbol, channel = key.split(":", 1)
            self.subscribe_stock(symbol, channel)
        return True

    def register_message_handler(self, handler: Callable[[dict], None]) -> None:
        self._message_handlers.append(handler)
        self._attach_message_handlers()

    def subscribe_stock(self, symbol: str, channel: str = "aggregates") -> Optional[str]:
        if not self._ws_stock:
            return None
        key = f"{symbol}:{channel}"
        if key in self._subscriptions:
            return self._subscriptions[key]

        result = self._call_ws_method(
            self._ws_stock,
            "subscribe",
            {"channel": channel, "symbol": symbol},
        )
        channel_id = self._extract_subscription_id(result) or key
        self._subscriptions[key] = channel_id
        return channel_id

    def unsubscribe_stock(self, symbol: str, channel: str = "aggregates") -> None:
        key = f"{symbol}:{channel}"
        channel_id = self._subscriptions.pop(key, None)
        if not channel_id or not self._ws_stock:
            return
        self._call_ws_method(self._ws_stock, "unsubscribe", {"id": channel_id})

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
        self.connected = False

    def _attach_message_handlers(self) -> None:
        if not self._ws_stock:
            return

        def dispatch(message):
            for handler in list(self._message_handlers):
                try:
                    handler(message)
                except Exception as exc:
                    log.warning("Fubon message handler failed: %s", exc)

        for event_name in ("message", "data"):
            on_method = getattr(self._ws_stock, "on", None)
            if callable(on_method):
                try:
                    on_method(event_name, dispatch)
                    return
                except Exception:
                    continue

        for attr_name in ("onmessage", "on_message"):
            if hasattr(self._ws_stock, attr_name):
                try:
                    setattr(self._ws_stock, attr_name, dispatch)
                    return
                except Exception:
                    continue

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
