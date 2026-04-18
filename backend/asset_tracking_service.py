from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Iterable, List


BASE_CURRENCY = "TWD"
_POSITIVE_CASH_FLOW_TYPES = {"deposit", "dividend", "interest", "transfer_in"}
_NEGATIVE_CASH_FLOW_TYPES = {"withdraw", "fee", "tax", "fx_fee", "transfer_out"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_currency(value: Any, default: str = BASE_CURRENCY) -> str:
    text = str(value or "").strip().upper()
    return text or default


def _normalize_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    if len(text) == 10:
        text = f"{text}T00:00:00+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _currency_fx_map(
    cash_entries: Iterable[Dict[str, Any]],
    trade_entries: Iterable[Dict[str, Any]],
    base_currency: str,
) -> Dict[str, float]:
    fx_map: Dict[str, tuple[datetime, float]] = {
        _normalize_currency(base_currency): (datetime.max.replace(tzinfo=timezone.utc), 1.0),
    }

    def collect(rows: Iterable[Dict[str, Any]], dt_key: str) -> None:
        for row in rows:
            currency = _normalize_currency(row.get("currency"), base_currency)
            if currency == _normalize_currency(base_currency):
                fx_map[currency] = (datetime.max.replace(tzinfo=timezone.utc), 1.0)
                continue
            fx_rate = _safe_float(row.get("fx_rate_to_base"), 0.0)
            if fx_rate <= 0:
                continue
            row_dt = _normalize_datetime(row.get(dt_key))
            previous = fx_map.get(currency)
            if previous is None or row_dt >= previous[0]:
                fx_map[currency] = (row_dt, fx_rate)

    collect(cash_entries, "flow_date")
    collect(trade_entries, "trade_date")
    return {key: value for key, (_, value) in fx_map.items()}


def _resolve_fx_rate(currency: str, fx_map: Dict[str, float], base_currency: str) -> float:
    normalized = _normalize_currency(currency, base_currency)
    if normalized == _normalize_currency(base_currency):
        return 1.0
    return _safe_float(fx_map.get(normalized), 0.0)


def _cash_flow_signed_amount(entry: Dict[str, Any]) -> float:
    flow_type = str(entry.get("flow_type") or "").strip().lower()
    amount = _safe_float(entry.get("amount"))
    if flow_type in _POSITIVE_CASH_FLOW_TYPES:
        return abs(amount)
    if flow_type in _NEGATIVE_CASH_FLOW_TYPES:
        return -abs(amount)
    return amount


def _account_sort_key(item: Dict[str, Any]) -> tuple[int, int]:
    return (_safe_int(item.get("sort_order")), _safe_int(item.get("id")))


def compute_asset_positions(
    accounts: List[Dict[str, Any]],
    cash_entries: List[Dict[str, Any]],
    trade_entries: List[Dict[str, Any]],
    *,
    base_currency: str = BASE_CURRENCY,
) -> Dict[str, Any]:
    normalized_base_currency = _normalize_currency(base_currency)
    sorted_accounts = sorted(accounts or [], key=_account_sort_key)
    account_lookup = {account["id"]: account for account in sorted_accounts if account.get("id") is not None}
    fx_map = _currency_fx_map(cash_entries, trade_entries, normalized_base_currency)

    cash_by_account_currency: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    positions_state: Dict[tuple[int, str], Dict[str, Any]] = {}
    warnings: List[str] = []

    for entry in sorted(cash_entries or [], key=lambda item: (_normalize_datetime(item.get("flow_date")), _safe_int(item.get("id")))):
        account_id = _safe_int(entry.get("account_id"))
        if account_id not in account_lookup:
            warnings.append(f"Cash entry {entry.get('id')} references unknown account {account_id}.")
            continue
        currency = _normalize_currency(entry.get("currency"), account_lookup[account_id].get("base_currency") or normalized_base_currency)
        cash_by_account_currency[account_id][currency] += _cash_flow_signed_amount(entry)

    for entry in sorted(trade_entries or [], key=lambda item: (_normalize_datetime(item.get("trade_date")), _safe_int(item.get("id")))):
        account_id = _safe_int(entry.get("account_id"))
        if account_id not in account_lookup:
            warnings.append(f"Trade entry {entry.get('id')} references unknown account {account_id}.")
            continue

        account = account_lookup[account_id]
        currency = _normalize_currency(entry.get("currency"), account.get("base_currency") or normalized_base_currency)
        ticker = str(entry.get("ticker") or "").strip().upper()
        if not ticker:
            warnings.append(f"Trade entry {entry.get('id')} is missing ticker.")
            continue

        quantity = _safe_float(entry.get("quantity"))
        price = _safe_float(entry.get("price"))
        fee_amount = _safe_float(entry.get("fee_amount"))
        tax_amount = _safe_float(entry.get("tax_amount"))
        if quantity <= 0 or price <= 0:
            warnings.append(f"Trade entry {entry.get('id')} has invalid quantity or price.")
            continue

        key = (account_id, ticker)
        position = positions_state.setdefault(
            key,
            {
                "account_id": account_id,
                "account_name": account.get("name") or f"Account {account_id}",
                "ticker": ticker,
                "display_name": entry.get("display_name") or ticker,
                "market": entry.get("market"),
                "asset_type": entry.get("asset_type") or "stock",
                "currency": currency,
                "quantity": 0.0,
                "avg_cost": 0.0,
                "cost_basis": 0.0,
                "realized_pnl": 0.0,
                "trade_count": 0,
                "last_trade_at": None,
            },
        )

        side = str(entry.get("side") or "").strip().lower()
        gross_amount = quantity * price
        total_cost = gross_amount + fee_amount + tax_amount
        proceeds = gross_amount - fee_amount - tax_amount
        if side == "buy":
            cash_by_account_currency[account_id][currency] -= total_cost
            position["quantity"] += quantity
            position["cost_basis"] += total_cost
            position["avg_cost"] = (
                position["cost_basis"] / position["quantity"] if position["quantity"] > 0 else 0.0
            )
        elif side == "sell":
            if position["quantity"] + 1e-9 < quantity:
                warnings.append(
                    f"Trade entry {entry.get('id')} sells more {ticker} than available in account {account_id}."
                )
                continue
            avg_cost = position["avg_cost"] if position["quantity"] > 0 else 0.0
            removed_cost = avg_cost * quantity
            cash_by_account_currency[account_id][currency] += proceeds
            position["quantity"] -= quantity
            position["cost_basis"] = max(position["cost_basis"] - removed_cost, 0.0)
            position["realized_pnl"] += proceeds - removed_cost
            position["avg_cost"] = (
                position["cost_basis"] / position["quantity"] if position["quantity"] > 0 else 0.0
            )
        else:
            warnings.append(f"Trade entry {entry.get('id')} has unsupported side '{entry.get('side')}'.")
            continue

        position["trade_count"] += 1
        position["last_trade_at"] = entry.get("trade_date")

    account_summaries: List[Dict[str, Any]] = []
    positions: List[Dict[str, Any]] = []
    realized_total_base = 0.0

    for account in sorted_accounts:
        account_id = account["id"]
        cash_breakdown = []
        cash_total_base = 0.0
        for currency, amount in sorted(cash_by_account_currency.get(account_id, {}).items()):
            fx_rate = _resolve_fx_rate(currency, fx_map, normalized_base_currency)
            amount_base = amount * fx_rate if fx_rate > 0 else None
            if amount_base is not None:
                cash_total_base += amount_base
            cash_breakdown.append(
                {
                    "currency": currency,
                    "amount": round(amount, 6),
                    "fx_rate_to_base": fx_rate if fx_rate > 0 else None,
                    "amount_base": round(amount_base, 6) if amount_base is not None else None,
                }
            )

        account_positions: List[Dict[str, Any]] = []
        for position in positions_state.values():
            if position["account_id"] != account_id or position["quantity"] <= 0:
                if position["account_id"] == account_id and position["realized_pnl"]:
                    realized_total_base += position["realized_pnl"] * _resolve_fx_rate(
                        position["currency"],
                        fx_map,
                        normalized_base_currency,
                    )
                continue

            fx_rate = _resolve_fx_rate(position["currency"], fx_map, normalized_base_currency)
            realized_base = position["realized_pnl"] * fx_rate if fx_rate > 0 else None
            if realized_base is not None:
                realized_total_base += realized_base
            normalized_position = {
                **position,
                "quantity": round(position["quantity"], 6),
                "avg_cost": round(position["avg_cost"], 6),
                "cost_basis": round(position["cost_basis"], 6),
                "realized_pnl": round(position["realized_pnl"], 6),
                "fx_rate_to_base": fx_rate if fx_rate > 0 else None,
                "cost_basis_base": round(position["cost_basis"] * fx_rate, 6) if fx_rate > 0 else None,
                "realized_pnl_base": round(realized_base, 6) if realized_base is not None else None,
            }
            positions.append(normalized_position)
            account_positions.append(normalized_position)

        account_summaries.append(
            {
                "account_id": account_id,
                "account_name": account.get("name") or f"Account {account_id}",
                "account_type": account.get("account_type"),
                "base_currency": _normalize_currency(account.get("base_currency"), normalized_base_currency),
                "include_in_total": bool(account.get("include_in_total", True)),
                "cash_breakdown": cash_breakdown,
                "cash_total_base": round(cash_total_base, 6),
                "position_count": len(account_positions),
            }
        )

    return {
        "base_currency": normalized_base_currency,
        "fx_rates": fx_map,
        "account_summaries": account_summaries,
        "positions": sorted(
            positions,
            key=lambda item: (item.get("account_name") or "", item.get("ticker") or ""),
        ),
        "realized_total_base": round(realized_total_base, 6),
        "warnings": list(dict.fromkeys(warnings)),
    }


async def build_asset_portfolio_snapshot(
    accounts: List[Dict[str, Any]],
    cash_entries: List[Dict[str, Any]],
    trade_entries: List[Dict[str, Any]],
    *,
    fetch_quote: Callable[[str], Awaitable[Dict[str, Any] | None]] | None = None,
    base_currency: str = BASE_CURRENCY,
) -> Dict[str, Any]:
    state = compute_asset_positions(
        accounts,
        cash_entries,
        trade_entries,
        base_currency=base_currency,
    )
    normalized_base_currency = state["base_currency"]
    positions = state["positions"]
    account_summaries = {
        item["account_id"]: {
            **item,
            "market_value_base": 0.0,
            "unrealized_pnl_base": 0.0,
            "realized_pnl_base": 0.0,
        }
        for item in state["account_summaries"]
    }
    included_account_ids = {
        item["account_id"]
        for item in account_summaries.values()
        if item.get("include_in_total", True)
    }

    if fetch_quote and positions:
        quotes = await asyncio.gather(
            *(fetch_quote(position["ticker"]) for position in positions),
            return_exceptions=True,
        )
    else:
        quotes = [None] * len(positions)

    quote_gaps: List[Dict[str, Any]] = []
    valued_positions: List[Dict[str, Any]] = []
    market_value_total_base = 0.0
    unrealized_total_base = 0.0

    for position, quote in zip(positions, quotes):
        resolved_quote = quote if isinstance(quote, dict) else None
        last_price = _safe_float((resolved_quote or {}).get("price"), 0.0)
        price_currency = _normalize_currency((resolved_quote or {}).get("currency"), position["currency"])
        fx_rate = _resolve_fx_rate(price_currency, state["fx_rates"], normalized_base_currency)
        market_value = position["quantity"] * last_price if last_price > 0 else None
        unrealized_pnl = (market_value - position["cost_basis"]) if market_value is not None else None
        market_value_base = market_value * fx_rate if (market_value is not None and fx_rate > 0) else None
        unrealized_pnl_base = unrealized_pnl * fx_rate if (unrealized_pnl is not None and fx_rate > 0) else None

        if market_value_base is not None and position["account_id"] in included_account_ids:
            market_value_total_base += market_value_base
        if unrealized_pnl_base is not None and position["account_id"] in included_account_ids:
            unrealized_total_base += unrealized_pnl_base
        else:
            quote_gaps.append(
                {
                    "ticker": position["ticker"],
                    "account_id": position["account_id"],
                    "account_name": position["account_name"],
                }
            )

        account_summary = account_summaries.get(position["account_id"])
        if account_summary is not None:
            if market_value_base is not None:
                account_summary["market_value_base"] += market_value_base
            if unrealized_pnl_base is not None:
                account_summary["unrealized_pnl_base"] += unrealized_pnl_base
            account_summary["realized_pnl_base"] += _safe_float(position.get("realized_pnl_base"))

        valued_positions.append(
            {
                **position,
                "quote_source": (resolved_quote or {}).get("source"),
                "quote_type": (resolved_quote or {}).get("quote_type"),
                "is_delayed": (resolved_quote or {}).get("is_delayed"),
                "quote_timestamp": (resolved_quote or {}).get("quote_timestamp"),
                "last_price": round(last_price, 6) if last_price > 0 else None,
                "last_price_currency": price_currency if last_price > 0 else None,
                "market_value": round(market_value, 6) if market_value is not None else None,
                "market_value_base": round(market_value_base, 6) if market_value_base is not None else None,
                "unrealized_pnl": round(unrealized_pnl, 6) if unrealized_pnl is not None else None,
                "unrealized_pnl_base": round(unrealized_pnl_base, 6) if unrealized_pnl_base is not None else None,
            }
        )

    cash_total_base = sum(
        _safe_float(item.get("cash_total_base"))
        for item in account_summaries.values()
        if item.get("account_id") in included_account_ids
    )
    realized_total_base = sum(
        _safe_float(item.get("realized_pnl_base"))
        for item in account_summaries.values()
        if item.get("account_id") in included_account_ids
    )
    total_asset_value_base = cash_total_base + market_value_total_base
    total_pnl_base = realized_total_base + unrealized_total_base

    allocation_base = [
        {
            **item,
            "market_value_base": round(item["market_value_base"], 6),
            "unrealized_pnl_base": round(item["unrealized_pnl_base"], 6),
            "realized_pnl_base": round(item["realized_pnl_base"], 6),
            "total_value_base": round(item["cash_total_base"] + item["market_value_base"], 6),
        }
        for item in account_summaries.values()
        if item.get("include_in_total", True)
    ]
    allocation_total = sum(_safe_float(item.get("total_value_base")) for item in allocation_base) or 0.0
    allocation_items = [
        {
            "key": item["account_name"],
            "account_id": item["account_id"],
            "value_base": item["total_value_base"],
            "weight_pct": round(item["total_value_base"] / allocation_total * 100, 4) if allocation_total else 0.0,
        }
        for item in sorted(allocation_base, key=lambda row: row["total_value_base"], reverse=True)
    ]

    return {
        "base_currency": normalized_base_currency,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "warnings": state["warnings"],
        "quote_gaps": quote_gaps,
        "accounts": sorted(
            [
                {
                    **item,
                    "cash_total_base": round(_safe_float(item.get("cash_total_base")), 6),
                }
                for item in account_summaries.values()
            ],
            key=lambda item: item["account_name"],
        ),
        "holdings": sorted(
            valued_positions,
            key=lambda item: (_safe_float(item.get("market_value_base")), item["ticker"]),
            reverse=True,
        ),
        "allocation": {
            "group_by": "account",
            "items": allocation_items,
        },
        "summary": {
            "cash_total_base": round(cash_total_base, 6),
            "market_value_total_base": round(market_value_total_base, 6),
            "total_asset_value_base": round(total_asset_value_base, 6),
            "realized_total_base": round(realized_total_base, 6),
            "unrealized_total_base": round(unrealized_total_base, 6),
            "total_pnl_base": round(total_pnl_base, 6),
            "holding_count": len(valued_positions),
            "account_count": len(account_summaries),
            "quote_gap_count": len(quote_gaps),
        },
    }
