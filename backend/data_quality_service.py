"""Unified operational and market-data quality snapshot."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from market_freshness import is_at_least_as_recent, market_aware_freshness
from security_sanitizer import redact_sensitive_data


STATUS_RANK = {"healthy": 0, "idle": 0, "warning": 1, "error": 2}


def _component(status: str, label: str, **details: Any) -> dict[str, Any]:
    return {"status": status, "label": label, **details}


@dataclass(slots=True)
class DataQualityService:
    db: Any
    scheduler: Any
    fubon_pool: Any
    ws_manager: Any
    futopt_recorder: Any = None
    futopt_enabled: bool = True
    backup_status_provider: Any = None

    async def build_snapshot(self, *, now: datetime | None = None) -> dict[str, Any]:
        reference = now or datetime.now(timezone.utc)
        database_health, migrations, watchlist = await asyncio.gather(
            self._safe_async(self.db.health_check, fallback={"connected": False, "error": "health_check_failed"}),
            self._safe_async(self.db.get_migration_status, fallback={"pending_count": None, "up_to_date": False}),
            self._watchlist_quality(reference),
        )
        components: dict[str, dict[str, Any]] = {}
        issues: list[dict[str, str]] = []

        database_ok = bool(database_health.get("connected"))
        components["database"] = _component(
            "healthy" if database_ok else "error",
            "MySQL 可用" if database_ok else "MySQL 無法查詢",
            **database_health,
        )

        pending_count = migrations.get("pending_count")
        unknown_versions = migrations.get("unknown_applied_versions") or []
        migration_ok = bool(migrations.get("up_to_date")) and not unknown_versions
        components["migrations"] = _component(
            "healthy" if migration_ok else "warning",
            "資料庫版本已同步" if migration_ok else "資料庫 migration 待處理",
            current_version=migrations.get("current_version"),
            applied_versions=migrations.get("applied_versions") or [],
            pending_count=pending_count,
            pending_versions=[item.get("version") for item in migrations.get("pending") or []],
            unknown_applied_versions=unknown_versions,
        )

        scheduler_summary = self._safe_sync(self.scheduler.health_summary, fallback={
            "running": False,
            "task_count": 0,
            "active_count": 0,
            "tasks": [],
        }) if self.scheduler is not None else {
            "running": False,
            "task_count": 0,
            "active_count": 0,
            "tasks": [],
        }
        scheduler_failed = int(scheduler_summary.get("failed_count") or 0)
        scheduler_stopped = int(scheduler_summary.get("unexpected_stopped_count") or 0)
        scheduler_ok = bool(
            scheduler_summary.get("running")
            and scheduler_summary.get("active_count", 0) > 0
            and scheduler_failed == 0
            and scheduler_stopped == 0
        )
        components["scheduler"] = _component(
            "healthy" if scheduler_ok else ("error" if scheduler_failed else "warning"),
            "背景排程運作中" if scheduler_ok else (
                "背景排程有任務異常停止" if scheduler_failed else "背景排程未完整運作"
            ),
            **scheduler_summary,
        )

        if self.backup_status_provider is None:
            components["backups"] = _component(
                "warning",
                "尚未設定資料庫備份健康檢查",
                healthy=False,
            )
        else:
            backup_status = self._safe_sync(
                self.backup_status_provider,
                fallback={"healthy": False, "status": "error", "error": "backup_status_check_failed"},
            )
            backup_healthy = bool(backup_status.get("healthy"))
            backup_error = backup_status.get("error")
            backup_details = {
                key: value for key, value in backup_status.items()
                if key not in {"status", "error"}
            }
            components["backups"] = _component(
                "healthy" if backup_healthy else ("error" if backup_status.get("status") == "error" else "warning"),
                "資料庫備份在有效期限內" if backup_healthy else "資料庫備份需要注意",
                **backup_details,
                error=backup_error,
            )

        ws_status = self._safe_sync(self.ws_manager.get_status, fallback={
            "client_count": 0,
            "subscribed_ticker_count": 0,
            "subscription_count": 0,
            "subscribed_tickers": [],
        }) if self.ws_manager is not None else {
            "client_count": 0,
            "subscribed_ticker_count": 0,
            "subscription_count": 0,
            "subscribed_tickers": [],
        }
        ws_state = "error" if ws_status.get("error") else ("healthy" if ws_status.get("client_count", 0) else "idle")
        components["websocket"] = _component(
            ws_state,
            "WebSocket 狀態無法讀取" if ws_state == "error" else (
                "WebSocket 已連線" if ws_status.get("client_count", 0) else "目前無 WebSocket 用戶端"
            ),
            **ws_status,
        )

        fubon_result = self._safe_sync(
            self.fubon_pool.get_account_runtime_statuses,
            fallback={"status_check_failed": True},
        ) if self.fubon_pool is not None else {}
        fubon_error = fubon_result.get("error") if fubon_result.get("status_check_failed") else None
        fubon_statuses = {} if fubon_error else redact_sensitive_data(fubon_result)
        connected_accounts = sum(1 for item in fubon_statuses.values() if item.get("realtime_connected"))
        reconnect_attempts = sum(
            int(target.get("attempts") or 0)
            for item in fubon_statuses.values()
            for target in (item.get("realtime_reconnect") or {}).values()
        )
        fubon_connection = self._safe_sync(
            lambda: {"connected": bool(getattr(self.fubon_pool, "connected", False))},
            fallback={"connected": False},
        ) if self.fubon_pool is not None else {"connected": False}
        fubon_error = fubon_error or fubon_connection.get("error")
        fubon_connected = bool(fubon_connection.get("connected"))
        warmup = self._safe_sync(
            self.fubon_pool.get_warmup_status,
            fallback={"state": "unknown", "error": "warmup_status_failed"},
        ) if self.fubon_pool is not None and hasattr(self.fubon_pool, "get_warmup_status") else {
            "state": "unconfigured",
            "configured_account_count": len(fubon_statuses),
            "connected_account_count": connected_accounts,
        }
        warmup_state = str(warmup.get("state") or "unknown")
        configured_accounts = int(warmup.get("configured_account_count") or len(fubon_statuses))
        all_configured_connected = configured_accounts > 0 and connected_accounts >= configured_accounts
        if fubon_error:
            fubon_state = "error"
            fubon_label = "富邦行情狀態無法讀取"
        elif warmup_state in {"scheduled", "running"}:
            fubon_state = "warning"
            fubon_label = "富邦行情帳號連線中"
        elif configured_accounts == 0:
            fubon_state = "idle"
            fubon_label = "尚未設定富邦行情帳號"
        elif all_configured_connected:
            fubon_state = "healthy"
            fubon_label = "富邦行情已連線"
        else:
            fubon_state = "warning"
            fubon_label = "富邦行情部分帳號未連線" if fubon_connected else "富邦行情未連線"
        components["fubon"] = _component(
            fubon_state,
            fubon_label,
            connected=fubon_connected,
            account_count=configured_accounts,
            connected_account_count=connected_accounts,
            reconnect_attempts=reconnect_attempts,
            accounts=fubon_statuses,
            warmup=warmup,
            error=fubon_error,
        )

        components["watchlist"] = watchlist
        components["futures_recorder"] = await self._futures_quality(reference)

        for key, item in components.items():
            if item["status"] in {"warning", "error"}:
                issues.append({"component": key, "status": item["status"], "message": item["label"]})
        worst_rank = max((STATUS_RANK.get(item["status"], 1) for item in components.values()), default=0)
        overall_status = "error" if worst_rank >= 2 else ("warning" if worst_rank == 1 else "healthy")
        counts = Counter(item["status"] for item in components.values())
        return {
            "status": overall_status,
            "generated_at": reference.astimezone(timezone.utc).isoformat(),
            "summary": {
                "component_count": len(components),
                "healthy_count": counts["healthy"],
                "idle_count": counts["idle"],
                "warning_count": counts["warning"],
                "error_count": counts["error"],
            },
            "issues": issues,
            "components": components,
        }

    async def _watchlist_quality(self, reference: datetime) -> dict[str, Any]:
        try:
            groups = await self.db.get_watchlist_groups()
            tickers = list(dict.fromkeys(
                str(item.get("ticker") or "").strip().upper()
                for group in groups
                for item in group.get("items", [])
                if item.get("ticker")
            ))
            if hasattr(self.db, "get_market_quotes") and hasattr(self.db, "get_latest_ohlcv_many"):
                quotes, latest_rows = await asyncio.gather(
                    self.db.get_market_quotes(tickers),
                    self.db.get_latest_ohlcv_many(tickers),
                )
            else:
                quote_rows, ohlcv_rows = await asyncio.gather(
                    asyncio.gather(*(self.db.get_market_quote(ticker) for ticker in tickers)),
                    asyncio.gather(*(self.db.get_latest_ohlcv(ticker) for ticker in tickers)),
                )
                quotes = {ticker: row for ticker, row in zip(tickers, quote_rows) if row}
                latest_rows = {ticker: row for ticker, row in zip(tickers, ohlcv_rows) if row}
            items = []
            source_counts: Counter[str] = Counter()
            for ticker in tickers:
                quote = quotes.get(ticker)
                row = latest_rows.get(ticker)
                quote_time = (quote or {}).get("quote_timestamp") or (quote or {}).get("synced_at")
                row_time = (row or {}).get("date")
                use_quote = bool(quote) and (not row or is_at_least_as_recent(quote_time, row_time))
                selected = quote if use_quote else row
                timestamp = quote_time if use_quote else row_time
                data_origin = "quote" if use_quote else ("ohlcv" if row else "missing")
                freshness = market_aware_freshness(
                    timestamp,
                    ticker=ticker,
                    data_origin=data_origin,
                    now=reference,
                )
                source = str((selected or {}).get("source") or "missing")
                source_counts[source] += 1
                items.append({
                    "ticker": ticker,
                    "source": source,
                    "data_origin": data_origin,
                    **freshness,
                })
            stale_items = [item for item in items if item["is_stale"]]
            status = "healthy" if items and not stale_items else "warning"
            label = "觀察池行情皆在有效期限內" if status == "healthy" else "觀察池存在過期或缺少行情"
            return _component(
                status,
                label,
                ticker_count=len(items),
                current_count=len(items) - len(stale_items),
                stale_count=len(stale_items),
                source_counts=dict(source_counts),
                stale_items=stale_items[:50],
            )
        except Exception as exc:
            return _component("error", "無法檢查觀察池行情", error=str(exc)[:300])

    async def _futures_quality(self, reference: datetime) -> dict[str, Any]:
        if not self.futopt_enabled:
            return _component("idle", "期貨 K 線記錄功能目前停用", active=False, enabled=False)
        if self.futopt_recorder is None:
            return _component("warning", "期貨 K 線記錄器未設定", active=False)
        status = self._safe_sync(
            self.futopt_recorder.get_status,
            fallback={"active": False, "last_error": "status_check_failed"},
        )
        records = []
        try:
            for symbol in status.get("symbols") or []:
                row = await self.db.get_latest_ohlcv(symbol, status.get("interval") or "1m")
                freshness = market_aware_freshness(
                    (row or {}).get("date"),
                    ticker=symbol,
                    data_origin="quote",
                    now=reference,
                )
                records.append({"symbol": symbol, **freshness})
        except Exception as exc:
            return _component(
                "error",
                "無法檢查期貨 K 線持久化資料",
                **status,
                error=str(exc)[:300],
            )
        stale_count = sum(1 for item in records if item["is_stale"])
        has_runtime_problem = bool(status.get("last_error") or status.get("dropped_messages") or stale_count)
        if has_runtime_problem:
            component_status = "warning"
            label = "期貨 K 線記錄器需要注意"
        elif status.get("active"):
            component_status = "healthy"
            label = "期貨 K 線記錄器運作中"
        else:
            component_status = "idle"
            label = "期貨 K 線記錄器目前待命"
        return _component(
            component_status,
            label,
            enabled=True,
            **status,
            persisted_records=records,
            stale_symbol_count=stale_count,
        )

    @staticmethod
    async def _safe_async(callable_obj, *, fallback: dict[str, Any]) -> dict[str, Any]:
        try:
            return await callable_obj()
        except Exception as exc:
            return {**fallback, "error": str(exc)[:300]}

    @staticmethod
    def _safe_sync(callable_obj, *, fallback: dict[str, Any]) -> dict[str, Any]:
        try:
            return callable_obj()
        except Exception as exc:
            return {**fallback, "error": str(exc)[:300]}
