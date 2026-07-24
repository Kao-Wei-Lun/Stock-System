"""Read-side asset valuation queries."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict

from asset_tracking_service import build_asset_performance_report, build_asset_portfolio_snapshot


class InvalidAllocationGroup(ValueError):
    """Raised when an unsupported allocation projection is requested."""


def build_allocation(snapshot: Dict[str, Any], group_by: str) -> Dict[str, Any]:
    normalized_group_by = str(group_by or "account").strip().lower()
    if normalized_group_by == "account":
        return snapshot.get("allocation") or {"group_by": "account", "items": []}
    if normalized_group_by != "market":
        raise InvalidAllocationGroup("Allocation group_by must be account or market")

    grouped: Dict[str, float] = defaultdict(float)
    for holding in snapshot.get("holdings") or []:
        market_key = str(holding.get("market") or "UNKNOWN").strip().upper() or "UNKNOWN"
        grouped[market_key] += float(holding.get("market_value_base") or 0.0)
    total_value = sum(grouped.values()) or 0.0
    items = [
        {
            "key": key,
            "value_base": round(value, 6),
            "weight_pct": round(value / total_value * 100, 4) if total_value else 0.0,
        }
        for key, value in sorted(grouped.items(), key=lambda item: item[1], reverse=True)
    ]
    return {"group_by": "market", "items": items}


def build_contributors(snapshot: Dict[str, Any], limit: int) -> Dict[str, Any]:
    clean_limit = max(1, min(int(limit or 10), 50))
    holdings = list(snapshot.get("holdings") or [])
    return {
        "top_gainers": sorted(
            holdings,
            key=lambda item: float(item.get("unrealized_pnl_base") or 0.0),
            reverse=True,
        )[:clean_limit],
        "top_losers": sorted(
            holdings,
            key=lambda item: float(item.get("unrealized_pnl_base") or 0.0),
        )[:clean_limit],
    }


def resolve_performance_start(range_name: str, *, today: date | None = None) -> str:
    normalized = str(range_name or "1y").strip().lower()
    current = today or datetime.now(timezone.utc).date()
    if normalized in {"all", "max"}:
        return "1900-01-01"
    if normalized == "ytd":
        return date(current.year, 1, 1).isoformat()
    if normalized.endswith("d") and normalized[:-1].isdigit():
        return (current - timedelta(days=int(normalized[:-1]))).isoformat()
    if normalized.endswith("y") and normalized[:-1].isdigit():
        return (current - timedelta(days=int(normalized[:-1]) * 365)).isoformat()
    days = {"30d": 30, "90d": 90, "180d": 180, "1y": 365, "2y": 730, "3y": 1095}.get(
        normalized,
        365,
    )
    return (current - timedelta(days=days)).isoformat()


class AssetValuationQueries:
    """Coordinates valuation reads using injected persistence/provider callbacks."""

    def __init__(self, *, load_inputs, fetch_quote, persist_snapshot, get_price_history) -> None:
        self.load_inputs = load_inputs
        self.fetch_quote = fetch_quote
        self.persist_snapshot = persist_snapshot
        self.get_price_history = get_price_history

    async def build_snapshot(self, *, refresh: bool = True) -> Dict[str, Any]:
        (
            accounts,
            cash_entries,
            trade_entries,
            adjustment_entries,
            price_overrides,
            fx_rates,
            reconciliation_snapshots,
        ) = await self.load_inputs(refresh_public_fx=refresh)
        snapshot = await build_asset_portfolio_snapshot(
            accounts,
            cash_entries,
            trade_entries,
            adjustment_entries=adjustment_entries,
            price_overrides=price_overrides,
            fx_rate_entries=fx_rates,
            reconciliation_snapshots=reconciliation_snapshots,
            fetch_quote=lambda ticker: self.fetch_quote(ticker, refresh=refresh),
        )
        await self.persist_snapshot(snapshot)
        return snapshot

    async def build_performance(self, range_name: str, *, refresh: bool = True) -> Dict[str, Any]:
        (
            accounts,
            cash_entries,
            trade_entries,
            adjustment_entries,
            price_overrides,
            fx_rates,
            _,
        ) = await self.load_inputs(refresh_public_fx=refresh)
        report = await build_asset_performance_report(
            accounts,
            cash_entries,
            trade_entries,
            start_at=resolve_performance_start(range_name),
            end_at=datetime.now(timezone.utc).isoformat(),
            adjustment_entries=adjustment_entries,
            price_overrides=price_overrides,
            fx_rate_entries=fx_rates,
            get_price_history=self.get_price_history,
            fetch_quote=lambda ticker: self.fetch_quote(ticker, refresh=refresh),
        )
        report["range"] = str(range_name or "1y").strip().lower() or "1y"
        return report
