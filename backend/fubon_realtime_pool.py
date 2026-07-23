from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from data_fetcher import normalize_ticker
from futopt_session import is_futopt_after_hours
from fubon_quote_provider import build_fubon_quote_payload
from fubon_symbols import (
    is_exact_futopt_contract,
    supports_fubon_stock_realtime_ticker,
    tw_ticker_to_fubon,
)
from fubon_provider import FubonSDKManager


log = logging.getLogger(__name__)

WATCHLIST_SOURCE = "watchlist"
WS_SOURCE = "ws"


@dataclass(slots=True)
class RealtimeAssignment:
    requested_ticker: str
    resolved_ticker: str
    market_type: str
    symbol: str
    channels: tuple[str, ...]
    account_id: int
    after_hours: bool = False


class FubonRealtimeSubscriptionPool:
    def __init__(
        self,
        primary_manager: FubonSDKManager,
        *,
        resolve_futopt_contract: Optional[Callable[[str], Awaitable[Optional[dict]]]] = None,
        store_quote: Optional[Callable[[dict], Awaitable[Any]]] = None,
        notification_ttl_seconds: float = 600.0,
        subscription_timeout_seconds: float = 2.5,
        full_quote_stale_seconds: float = 20.0,
        utcnow: Optional[Callable[[], datetime]] = None,
    ):
        self._primary_manager = primary_manager
        self._resolve_futopt_contract = resolve_futopt_contract
        self._store_quote = store_quote
        self._notification_ttl_seconds = notification_ttl_seconds
        self._subscription_timeout_seconds = subscription_timeout_seconds
        self._full_quote_stale_seconds = max(1.0, float(full_quote_stale_seconds))
        self._utcnow = utcnow or (lambda: datetime.now(timezone.utc))
        self._db = None
        self._managers: Dict[int, FubonSDKManager] = {}
        self._manager_bridge_handlers: Dict[int, Callable[[dict], None]] = {}
        self._message_handlers: list[Callable[[dict], None]] = []
        self._source_tickers: dict[str, set[str]] = defaultdict(set)
        self._assignments: dict[str, RealtimeAssignment] = {}
        # Multiple user-facing aliases may resolve to one physical contract. Keep
        # one SDK subscription per account/contract/channel set and reference-count it.
        self._physical_subscriptions: dict[tuple, int] = {}
        self._resolved_to_requested: dict[str, set[str]] = defaultdict(set)
        self._assignment_lock = asyncio.Lock()
        self._pending_tasks: dict[str, asyncio.Task] = {}
        self._last_shortage_notifications: dict[str, float] = {}
        self._ws_diagnostics: dict[str, dict[str, Any]] = {}
        self._recovery_lock = asyncio.Lock()
        self._reload_lock = asyncio.Lock()
        self._warmup_task: asyncio.Task | None = None
        self._warmup_state = "idle"
        self._warmup_started_at: str | None = None
        self._warmup_completed_at: str | None = None
        self._warmup_error: str | None = None

    @property
    def connected(self) -> bool:
        return any(manager.connected for manager in self._managers.values())

    @property
    def active_account_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self._managers.keys()))

    def register_message_handler(self, handler: Callable[[dict], None]) -> None:
        if handler in self._message_handlers:
            return
        self._message_handlers.append(handler)

    def unregister_message_handler(self, handler: Callable[[dict], None]) -> None:
        self._message_handlers = [item for item in self._message_handlers if item is not handler]

    def configure_store_quote(self, handler: Optional[Callable[[dict], Awaitable[Any]]]) -> None:
        self._store_quote = handler

    def get_warmup_status(self) -> dict[str, Any]:
        configured_count = len(self._managers)
        connected_count = sum(1 for manager in self._managers.values() if manager.connected)
        return {
            "state": self._warmup_state,
            "started_at": self._warmup_started_at,
            "completed_at": self._warmup_completed_at,
            "error": self._warmup_error,
            "configured_account_count": configured_count,
            "connected_account_count": connected_count,
            "connected": connected_count > 0,
            "complete": self._warmup_state in {"ready", "failed", "cancelled", "stopped"},
        }

    def start_background_warmup(self, db) -> asyncio.Task:
        """Start provider initialization without blocking FastAPI readiness."""
        self._db = db
        task = self._warmup_task
        if task is not None and not task.done():
            return task
        self._warmup_state = "scheduled"
        self._warmup_started_at = None
        self._warmup_completed_at = None
        self._warmup_error = None
        self._warmup_task = asyncio.create_task(
            self._run_background_warmup(db),
            name="fubon-provider-warmup",
        )
        return self._warmup_task

    async def _run_background_warmup(self, db) -> bool:
        self._warmup_state = "running"
        self._warmup_started_at = self._utcnow().isoformat()
        try:
            connected = await self.init_from_db(db)
            await self.sync_watchlist_from_db(db)
        except asyncio.CancelledError:
            self._warmup_state = "cancelled"
            self._warmup_completed_at = self._utcnow().isoformat()
            raise
        except Exception as exc:
            self._warmup_state = "failed"
            self._warmup_error = str(exc)[:300]
            self._warmup_completed_at = self._utcnow().isoformat()
            log.exception("Fubon provider background warmup failed: %s", exc)
            return False
        self._warmup_state = "ready"
        self._warmup_completed_at = self._utcnow().isoformat()
        return bool(connected)

    async def wait_for_warmup(self, timeout: float | None = None) -> bool:
        task = self._warmup_task
        if task is None:
            return bool(self.connected)
        try:
            if timeout is None:
                return bool(await asyncio.shield(task))
            return bool(await asyncio.wait_for(asyncio.shield(task), timeout=max(0.0, float(timeout))))
        except asyncio.TimeoutError:
            return False
        except asyncio.CancelledError:
            if task.cancelled():
                return False
            raise

    async def init_from_db(self, db) -> bool:
        self._db = db
        return await self.reload_from_db(db)

    async def reload_from_db(self, db=None) -> bool:
        async with self._reload_lock:
            return await self._reload_from_db_locked(db)

    async def _reload_from_db_locked(self, db=None) -> bool:
        from repositories.fubon_accounts import FubonAccountRepository

        self._db = db or self._db
        if self._db is None:
            return False

        repo = FubonAccountRepository(self._db)
        accounts = await repo.list_enabled_accounts_with_secrets()
        accounts_by_id = {int(account["id"]): account for account in accounts if account.get("id") is not None}
        desired_ids = set(accounts_by_id.keys())

        primary_account = next((account for account in accounts if account.get("is_active")), None)
        if primary_account is None and accounts:
            primary_account = accounts[0]
        primary_id = int(primary_account["id"]) if primary_account and primary_account.get("id") is not None else None

        if primary_account and primary_id is not None:
            self._managers[primary_id] = self._primary_manager
            self._attach_bridge_handler(primary_id, self._primary_manager)
            try:
                initialized = await self._primary_manager._init_with_account(primary_account, repo)
                if initialized:
                    self._primary_manager.start_ws_stock()
                    self._primary_manager.start_ws_futopt()
            except Exception as exc:
                log.warning("Fubon primary account %s warmup failed: %s", primary_id, exc)

        removed_ids = [account_id for account_id in list(self._managers.keys()) if account_id not in desired_ids]
        for account_id in removed_ids:
            manager = self._managers.pop(account_id, None)
            handler = self._manager_bridge_handlers.pop(account_id, None)
            if manager and handler:
                manager.unregister_message_handler(handler)
            if manager and (manager is not self._primary_manager or account_id not in desired_ids):
                manager.shutdown()

        for account in accounts:
            account_id = int(account["id"])
            if primary_id is not None and account_id == primary_id:
                continue
            manager = self._managers.get(account_id)
            if manager is None:
                manager = FubonSDKManager()
                self._managers[account_id] = manager
                self._attach_bridge_handler(account_id, manager)
            try:
                initialized = await manager._init_with_account(account, repo)
                if initialized:
                    manager.start_ws_stock()
                    manager.start_ws_futopt()
            except Exception as exc:
                log.warning("Fubon account %s warmup failed: %s", account_id, exc)

        await self._rebalance_assignments()
        return self.connected

    async def shutdown_async(self, *, shutdown_primary: bool = False) -> None:
        task = self._warmup_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self.shutdown(shutdown_primary=shutdown_primary)
        self._warmup_state = "stopped"
        self._warmup_completed_at = self._utcnow().isoformat()

    def shutdown(self, *, shutdown_primary: bool = False) -> None:
        for task in list(self._pending_tasks.values()):
            if not task.done():
                task.cancel()
        self._pending_tasks.clear()

        for account_id, manager in list(self._managers.items()):
            handler = self._manager_bridge_handlers.pop(account_id, None)
            if handler:
                manager.unregister_message_handler(handler)
            if manager is self._primary_manager and not shutdown_primary:
                continue
            manager.shutdown()
        if shutdown_primary:
            self._managers.clear()
        else:
            self._managers = {
                account_id: manager for account_id, manager in self._managers.items() if manager is self._primary_manager
            }
        self._assignments.clear()
        self._physical_subscriptions.clear()
        self._resolved_to_requested.clear()
        self._source_tickers.clear()
        self._ws_diagnostics.clear()

    async def sync_watchlist_from_db(self, db=None) -> None:
        database = db or self._db
        if database is None:
            return
        try:
            groups = await database.get_watchlist_groups()
        except Exception as exc:
            log.warning("Realtime watchlist sync skipped: %s", exc)
            return
        tickers = []
        for group in groups:
            for item in group.get("items", []):
                ticker = normalize_ticker(item.get("ticker"))
                if ticker:
                    tickers.append(ticker)
        await self.set_source_tickers(WATCHLIST_SOURCE, tickers, wait_for_assignments=False)

    async def set_source_tickers(
        self,
        source: str,
        tickers: list[str] | set[str] | tuple[str, ...],
        *,
        wait_for_assignments: bool = True,
    ) -> None:
        normalized_source = str(source or "").strip().lower() or WATCHLIST_SOURCE
        desired = {normalize_ticker(ticker) for ticker in tickers if normalize_ticker(ticker)}
        current = set(self._source_tickers.get(normalized_source, set()))
        self._source_tickers[normalized_source] = desired

        removed = current - desired
        added = desired - current

        for ticker in sorted(removed):
            if wait_for_assignments:
                await self._refresh_ticker_assignment(ticker)
            else:
                self._schedule_task(ticker, self._refresh_ticker_assignment(ticker))
        for ticker in sorted(added):
            if wait_for_assignments:
                await self._ensure_assignment(ticker)
            else:
                self._schedule_task(ticker, self._ensure_assignment(ticker))

    def track_ticker(self, ticker: str, *, source: str = WS_SOURCE) -> None:
        normalized = normalize_ticker(ticker)
        if not normalized:
            return
        normalized_source = str(source or "").strip().lower() or WS_SOURCE
        if normalized in self._source_tickers[normalized_source]:
            return
        self._source_tickers[normalized_source].add(normalized)
        self._schedule_task(normalized, self._ensure_assignment(normalized))

    def untrack_ticker(self, ticker: str, *, source: str = WS_SOURCE) -> None:
        normalized = normalize_ticker(ticker)
        if not normalized:
            return
        normalized_source = str(source or "").strip().lower() or WS_SOURCE
        self._source_tickers.get(normalized_source, set()).discard(normalized)
        self._schedule_task(normalized, self._refresh_ticker_assignment(normalized))

    def resolve_broadcast_tickers(self, ticker: str) -> tuple[str, ...]:
        normalized = normalize_ticker(ticker)
        requested = set(self._resolved_to_requested.get(normalized, set()))
        requested.add(normalized)
        return tuple(sorted(requested))

    def record_ws_message(
        self,
        ticker: str,
        channel: str,
        *,
        market_type: str | None = None,
        account_id: int | None = None,
        target_tickers: tuple[str, ...] | list[str] | set[str] = (),
    ) -> None:
        normalized = normalize_ticker(ticker)
        normalized_channel = str(channel or "").strip().lower()
        if not normalized or not normalized_channel:
            return

        now = self._utcnow().isoformat()
        keys = {normalized}
        for item in target_tickers:
            target = normalize_ticker(item)
            if target:
                keys.add(target)

        for key in keys:
            diagnostic = self._ws_diagnostics.setdefault(
                key,
                {
                    "ticker": key,
                    "last_seen_at": None,
                    "last_channel": None,
                    "channels": {},
                },
            )
            channel_state = diagnostic["channels"].setdefault(
                normalized_channel,
                {
                    "count": 0,
                    "last_seen_at": None,
                    "market_type": None,
                    "account_id": None,
                    "source_ticker": None,
                },
            )
            channel_state["count"] += 1
            channel_state["last_seen_at"] = now
            channel_state["market_type"] = market_type
            channel_state["account_id"] = account_id
            channel_state["source_ticker"] = normalized
            diagnostic["last_seen_at"] = now
            diagnostic["last_channel"] = normalized_channel

    def get_ws_diagnostics(self) -> dict[str, dict[str, Any]]:
        now = self._utcnow()
        result: dict[str, dict[str, Any]] = {}
        for ticker, payload in sorted(self._ws_diagnostics.items()):
            channels: dict[str, dict[str, Any]] = {}
            for channel, channel_payload in sorted(payload.get("channels", {}).items()):
                age_seconds = self._age_seconds(channel_payload.get("last_seen_at"), now)
                channels[channel] = {
                    **channel_payload,
                    "age_seconds": age_seconds,
                    "is_fresh": age_seconds is not None and age_seconds <= self._full_quote_stale_seconds,
                }
            last_seen_age_seconds = self._age_seconds(payload.get("last_seen_at"), now)
            result[ticker] = {
                **payload,
                "age_seconds": last_seen_age_seconds,
                "is_fresh": last_seen_age_seconds is not None
                and last_seen_age_seconds <= self._full_quote_stale_seconds,
                "channels": channels,
            }
        return result

    @staticmethod
    def _age_seconds(value: Any, now: datetime) -> float | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (now - parsed.astimezone(timezone.utc)).total_seconds())

    def _has_fresh_quote_channel(self, ticker: str) -> bool:
        diagnostic = self._ws_diagnostics.get(normalize_ticker(ticker)) or {}
        quote_state = (diagnostic.get("channels") or {}).get("quote") or {}
        age_seconds = self._age_seconds(quote_state.get("last_seen_at"), self._utcnow())
        return age_seconds is not None and age_seconds <= self._full_quote_stale_seconds

    def supports_full_ws_quotes_for_ticker(self, ticker: str) -> bool:
        assignment = self._assignments.get(normalize_ticker(ticker))
        if not assignment:
            return False
        manager = self._managers.get(assignment.account_id)
        return bool(
            manager
            and manager.connected
            and manager.ws_mode == "Normal"
            and self._has_fresh_quote_channel(ticker)
        )

    def get_account_runtime_statuses(self) -> dict[int, dict[str, Any]]:
        assigned_by_account: dict[int, list[RealtimeAssignment]] = defaultdict(list)
        for assignment in self._assignments.values():
            assigned_by_account[assignment.account_id].append(assignment)

        result: dict[int, dict[str, Any]] = {}
        for account_id, manager in self._managers.items():
            assignments = sorted(
                assigned_by_account.get(account_id, []),
                key=lambda item: (item.requested_ticker, item.resolved_ticker),
            )
            result[account_id] = {
                "realtime_assigned_count": len(assignments),
                "realtime_physical_subscription_count": sum(
                    1
                    for key, reference_count in self._physical_subscriptions.items()
                    if key[0] == account_id and reference_count > 0
                ),
                "realtime_assigned_tickers": [item.requested_ticker for item in assignments],
                "realtime_resolved_tickers": sorted({item.resolved_ticker for item in assignments}),
                "realtime_afterhours_tickers": [
                    item.requested_ticker
                    for item in assignments
                    if item.market_type == "futopt" and item.after_hours
                ],
                "realtime_ws_mode": manager.ws_mode,
                "realtime_connected": bool(manager.connected),
                "realtime_reconnect": manager.get_reconnect_status()
                if hasattr(manager, "get_reconnect_status")
                else {},
            }
        return result

    async def reconnect_account(self, account_id: int, market_type: str | None = None) -> dict[str, Any]:
        """Recover one configured account without restarting the FastAPI process."""
        from repositories.fubon_accounts import FubonAccountRepository

        normalized_market = str(market_type or "").strip().lower() or None
        if normalized_market not in {None, "stock", "futopt"}:
            raise ValueError("market_type must be stock or futopt")
        if self._db is None:
            return {"success": False, "account_id": account_id, "message": "database is not configured"}

        async with self._recovery_lock:
            manager = self._managers.get(int(account_id))
            if normalized_market and manager and manager.connected:
                success = bool(manager.force_reconnect_ws(normalized_market))
                return {
                    "success": success,
                    "account_id": int(account_id),
                    "market_type": normalized_market,
                    "message": "websocket reconnect started" if success else "websocket reconnect failed",
                }

            repo = FubonAccountRepository(self._db)
            account = await repo.get_account_with_secrets(int(account_id))
            if not account:
                return {"success": False, "account_id": int(account_id), "message": "account not found"}
            if not account.get("is_enabled"):
                return {"success": False, "account_id": int(account_id), "message": "account is disabled"}

            if manager is None:
                manager = self._primary_manager if account.get("is_active") else FubonSDKManager()
                self._managers[int(account_id)] = manager

            bridge = self._manager_bridge_handlers.pop(int(account_id), None)
            if bridge:
                manager.unregister_message_handler(bridge)
            manager.shutdown()

            success = await manager._init_with_account(account, repo)
            self._managers[int(account_id)] = manager
            self._attach_bridge_handler(int(account_id), manager)
            if success:
                manager.start_ws_stock()
                manager.start_ws_futopt()
            await self._rebalance_assignments()
            return {
                "success": bool(success),
                "account_id": int(account_id),
                "market_type": "all",
                "message": "account reconnected" if success else "account reconnect failed",
            }

    async def refresh_session_assignments(self) -> None:
        """Re-subscribe futures/options streams when TAIFEX switches day/night sessions."""
        disconnected_ids = [
            account_id for account_id, manager in list(self._managers.items()) if not manager.connected
        ]
        for account_id in disconnected_ids:
            log.warning("Fubon account %s is disconnected; attempting isolated recovery", account_id)
            try:
                await self.reconnect_account(account_id)
            except Exception as exc:
                log.warning("Fubon account %s recovery failed: %s", account_id, exc)

        desired_after_hours = is_futopt_after_hours()
        stale_tickers = [
            ticker
            for ticker, assignment in list(self._assignments.items())
            if assignment.market_type == "futopt"
            and assignment.after_hours != desired_after_hours
            and self._has_any_source(ticker)
        ]
        for ticker in stale_tickers:
            await self._ensure_assignment(ticker)

    def _attach_bridge_handler(self, account_id: int, manager: FubonSDKManager) -> None:
        existing = self._manager_bridge_handlers.get(account_id)
        if existing:
            manager.unregister_message_handler(existing)

        def _bridge(message: dict, aid: int = account_id) -> None:
            payload = dict(message or {})
            payload.setdefault("account_id", aid)
            for handler in list(self._message_handlers):
                try:
                    handler(payload)
                except Exception as exc:
                    log.warning("Fubon realtime pool handler failed: %s", exc)

        self._manager_bridge_handlers[account_id] = _bridge
        manager.register_message_handler(_bridge)

    async def _rebalance_assignments(self) -> None:
        desired = set()
        for items in self._source_tickers.values():
            desired.update(items)

        for ticker in list(self._assignments.keys()):
            await self._remove_assignment(ticker)
        for ticker in sorted(desired):
            await self._ensure_assignment(ticker)

    def _schedule_task(self, ticker: str, coroutine) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        existing = self._pending_tasks.get(ticker)
        if existing and not existing.done():
            existing.cancel()
        task = loop.create_task(coroutine, name=f"fubon-realtime:{ticker}")
        self._pending_tasks[ticker] = task

        def _cleanup(_task: asyncio.Task, key: str = ticker) -> None:
            if self._pending_tasks.get(key) is _task:
                self._pending_tasks.pop(key, None)

        task.add_done_callback(_cleanup)

    def _has_any_source(self, ticker: str) -> bool:
        return any(ticker in items for items in self._source_tickers.values())

    async def _release_ticker_if_unused(self, ticker: str) -> None:
        normalized = normalize_ticker(ticker)
        if not normalized or self._has_any_source(normalized):
            return
        await self._remove_assignment(normalized)

    async def _refresh_ticker_assignment(self, ticker: str) -> None:
        normalized = normalize_ticker(ticker)
        if not normalized:
            return
        if not self._has_any_source(normalized):
            await self._remove_assignment(normalized)
            return
        await self._ensure_assignment(normalized)

    async def _remove_assignment(self, ticker: str) -> None:
        normalized = normalize_ticker(ticker)
        if not normalized:
            return
        async with self._assignment_lock:
            self._remove_assignment_locked(normalized)

    async def _ensure_assignment(self, ticker: str) -> None:
        normalized = normalize_ticker(ticker)
        if not normalized or not self._has_any_source(normalized):
            return

        created_assignment: tuple[FubonSDKManager, RealtimeAssignment] | None = None
        async with self._assignment_lock:
            existing = self._assignments.get(normalized)
            if existing:
                manager = self._managers.get(existing.account_id)
                if manager and manager.connected and self._assignment_satisfies_preference(normalized, existing):
                    return
                self._remove_assignment_locked(normalized)

            target = await self._resolve_target(normalized)
            if not target:
                return

            errors: list[str] = []
            for account_id, manager in self._candidate_managers(normalized, target=target):
                try:
                    channels = await self._subscribe_target_on_manager(account_id, manager, target)
                except Exception as exc:
                    log.warning("Fubon realtime subscribe failed for %s via account %s: %s", normalized, account_id, exc)
                    errors.append(f"{account_id}:{exc}")
                    continue

                assignment = RealtimeAssignment(
                    requested_ticker=normalized,
                    resolved_ticker=target["resolved_ticker"],
                    market_type=target["market_type"],
                    symbol=target["symbol"],
                    channels=channels,
                    account_id=account_id,
                    after_hours=bool(target.get("after_hours")),
                )
                self._assignments[normalized] = assignment
                self._resolved_to_requested[target["resolved_ticker"]].add(normalized)
                created_assignment = (manager, assignment)
                break

        if created_assignment:
            await self._prime_assignment_quote(*created_assignment)
            return
        await self._notify_shortage(normalized, errors)

    async def _prime_assignment_quote(
        self,
        manager: FubonSDKManager,
        assignment: RealtimeAssignment,
    ) -> None:
        if assignment.market_type != "stock" or not callable(self._store_quote):
            return

        try:
            response = await manager.fetch_stock_quote(assignment.symbol)
            payload = build_fubon_quote_payload(
                assignment.requested_ticker,
                response or {},
                source="fubon_neo",
            )
            if payload:
                await self._store_quote(payload)
        except Exception as exc:
            log.debug(
                "Fubon realtime prime quote failed for %s via account %s: %s",
                assignment.requested_ticker,
                assignment.account_id,
                exc,
            )

    async def _resolve_target(self, ticker: str) -> Optional[dict[str, str]]:
        normalized = normalize_ticker(ticker)
        if supports_fubon_stock_realtime_ticker(normalized):
            symbol = tw_ticker_to_fubon(normalized)
            if not symbol:
                return None
            return {
                "requested_ticker": normalized,
                "resolved_ticker": normalized,
                "market_type": "stock",
                "symbol": symbol,
            }

        if is_exact_futopt_contract(normalized):
            return {
                "requested_ticker": normalized,
                "resolved_ticker": normalized,
                "market_type": "futopt",
                "symbol": normalized,
                "after_hours": is_futopt_after_hours(),
            }

        if not callable(self._resolve_futopt_contract):
            return None

        resolved = await self._resolve_futopt_contract(normalized)
        resolved_symbol = str((resolved or {}).get("resolved_symbol") or "").strip().upper()
        if not resolved_symbol:
            return None
        return {
            "requested_ticker": normalized,
            "resolved_ticker": resolved_symbol,
            "market_type": "futopt",
            "symbol": resolved_symbol,
            "after_hours": is_futopt_after_hours(),
        }

    def _preferred_ws_modes_for_ticker(self, ticker: str) -> tuple[str, ...]:
        active_sources = {
            source
            for source, items in self._source_tickers.items()
            if ticker in items
        }
        # Any active source beyond the passive watchlist should prefer Normal mode,
        # because downstream consumers may require candle/aggregate channels.
        if active_sources - {WATCHLIST_SOURCE}:
            return ("Normal", "Speed")
        if WATCHLIST_SOURCE in active_sources:
            return ("Speed", "Normal")
        return ("Speed", "Normal")

    @staticmethod
    def _mode_priority(ws_mode: str | None, preferred_modes: tuple[str, ...]) -> int:
        normalized = str(ws_mode or "").strip()
        try:
            return preferred_modes.index(normalized)
        except ValueError:
            return len(preferred_modes) + 1

    def _assignment_satisfies_preference(self, ticker: str, assignment: RealtimeAssignment) -> bool:
        manager = self._managers.get(assignment.account_id)
        if not manager or not manager.connected:
            return False
        if assignment.market_type == "futopt" and assignment.after_hours != is_futopt_after_hours():
            return False

        candidates = self._candidate_managers(ticker)
        if not candidates:
            return False

        preferred_modes = self._preferred_ws_modes_for_ticker(ticker)
        current_priority = self._mode_priority(manager.ws_mode, preferred_modes)
        best_priority = min(
            self._mode_priority(candidate_manager.ws_mode, preferred_modes)
            for _, candidate_manager in candidates
        )
        return current_priority == best_priority

    def _candidate_managers(
        self,
        ticker: str,
        *,
        target: dict[str, str] | None = None,
    ) -> list[tuple[int, FubonSDKManager]]:
        loads = defaultdict(int)
        for key, reference_count in self._physical_subscriptions.items():
            if reference_count > 0:
                loads[key[0]] += 1

        primary_id = self._primary_manager.active_account_id
        preferred_modes = self._preferred_ws_modes_for_ticker(ticker)
        candidates = [
            (account_id, manager)
            for account_id, manager in self._managers.items()
            if manager and manager.connected
        ]
        return sorted(
            candidates,
            key=lambda item: (
                self._mode_priority(item[1].ws_mode, preferred_modes),
                0 if target and self._target_is_subscribed_on_manager(item[0], item[1], target) else 1,
                loads[item[0]],
                0 if primary_id is not None and item[0] == primary_id else 1,
                item[0],
            ),
        )

    def _target_is_subscribed_on_manager(
        self,
        account_id: int,
        manager: FubonSDKManager,
        target: dict[str, str],
    ) -> bool:
        channels = self._channels_for(manager, target["market_type"])
        key = self._physical_subscription_key(
            account_id,
            target["market_type"],
            target["symbol"],
            bool(target.get("after_hours")),
            channels,
        )
        return self._physical_subscriptions.get(key, 0) > 0

    @staticmethod
    def _channels_for(manager: FubonSDKManager, market_type: str) -> tuple[str, ...]:
        if market_type == "stock":
            return ("aggregates", "books", "candles") if manager.ws_mode == "Normal" else ("trades", "books")
        return ("aggregates", "books", "candles") if manager.ws_mode == "Normal" else ("trades", "books")

    @staticmethod
    def _physical_subscription_key(
        account_id: int,
        market_type: str,
        symbol: str,
        after_hours: bool,
        channels: tuple[str, ...],
    ) -> tuple:
        return (account_id, market_type, symbol, after_hours, channels)

    async def _subscribe_target_on_manager(
        self,
        account_id: int,
        manager: FubonSDKManager,
        target: dict[str, str],
    ) -> tuple[str, ...]:
        channels = self._channels_for(manager, target["market_type"])
        subscribed: list[str] = []
        after_hours = bool(target.get("after_hours"))
        subscription_key = self._physical_subscription_key(
            account_id,
            target["market_type"],
            target["symbol"],
            after_hours,
            channels,
        )
        reference_count = self._physical_subscriptions.get(subscription_key, 0)
        if reference_count > 0:
            self._physical_subscriptions[subscription_key] = reference_count + 1
            return channels

        try:
            for channel in channels:
                if target["market_type"] == "stock":
                    await manager.subscribe_stock_async(
                        target["symbol"],
                        channel,
                        timeout=self._subscription_timeout_seconds,
                    )
                else:
                    await manager.subscribe_futopt_async(
                        target["symbol"],
                        channel,
                        after_hours=after_hours,
                        timeout=self._subscription_timeout_seconds,
                    )
                subscribed.append(channel)
        except Exception:
            for channel in subscribed:
                if target["market_type"] == "stock":
                    manager.unsubscribe_stock(target["symbol"], channel)
                else:
                    manager.unsubscribe_futopt(target["symbol"], channel, after_hours=after_hours)
            raise

        self._physical_subscriptions[subscription_key] = 1
        return channels

    async def _notify_shortage(self, ticker: str, errors: list[str]) -> None:
        if self._db is None:
            return
        normalized = normalize_ticker(ticker)
        reason_key = "no_connected_accounts" if not any(manager.connected for manager in self._managers.values()) else normalized
        now = time.monotonic()
        last_sent = self._last_shortage_notifications.get(reason_key, 0.0)
        if now - last_sent < self._notification_ttl_seconds:
            return

        message = (
            f"{normalized} 無法再分配到可用的富邦即時行情帳號。"
            " 請檢查現有 API KEY 連線狀態，必要時新增可用的 API KEY。"
        )
        if errors:
            message = f"{message} 最後錯誤：{errors[-1]}"

        try:
            await self._db.create_notification(
                {
                    "category": "system",
                    "level": "warning",
                    "title": "即時行情訂閱容量不足",
                    "message": message,
                    "payload": {
                        "ticker": normalized,
                        "reason": "realtime_subscription_exhausted",
                        "errors": errors,
                    },
                }
            )
            self._last_shortage_notifications[reason_key] = now
        except Exception as exc:
            log.warning("Failed to persist realtime shortage notification for %s: %s", normalized, exc)

    def _remove_assignment_locked(self, ticker: str) -> None:
        assignment = self._assignments.pop(ticker, None)
        if not assignment:
            return
        self._resolved_to_requested.get(assignment.resolved_ticker, set()).discard(assignment.requested_ticker)
        if not self._resolved_to_requested.get(assignment.resolved_ticker):
            self._resolved_to_requested.pop(assignment.resolved_ticker, None)
        manager = self._managers.get(assignment.account_id)
        subscription_key = self._physical_subscription_key(
            assignment.account_id,
            assignment.market_type,
            assignment.symbol,
            assignment.after_hours,
            assignment.channels,
        )
        reference_count = self._physical_subscriptions.get(subscription_key, 0)
        if reference_count > 1:
            self._physical_subscriptions[subscription_key] = reference_count - 1
            return
        self._physical_subscriptions.pop(subscription_key, None)
        if not manager:
            return
        for channel in assignment.channels:
            if assignment.market_type == "stock":
                manager.unsubscribe_stock(assignment.symbol, channel)
            else:
                manager.unsubscribe_futopt(assignment.symbol, channel, after_hours=assignment.after_hours)
