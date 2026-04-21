from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Sequence


BASE_CURRENCY = "TWD"
_POSITIVE_CASH_FLOW_TYPES = {"deposit", "dividend", "interest", "transfer_in"}
_NEGATIVE_CASH_FLOW_TYPES = {"withdraw", "fee", "tax", "fx_fee", "transfer_out"}
_RECONCILIATION_DIFF_EPSILON = 0.01
_DEFAULT_ALERT_DRAWNDOWN_THRESHOLD_PCT = 10.0
_DEFAULT_ALERT_CONCENTRATION_THRESHOLD_PCT = 35.0
_DEFAULT_ALERT_HOLDING_LOSS_THRESHOLD_PCT = 15.0


def _safe_float(value: Any, default: float | None = 0.0) -> float | None:
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
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
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


def _normalize_date(value: Any) -> date:
    if isinstance(value, datetime):
        return _normalize_datetime(value).date()
    if isinstance(value, date):
        return value
    if not value:
        return date(1970, 1, 1)
    text = str(value).strip()
    if not text:
        return date(1970, 1, 1)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return date(1970, 1, 1)


def _end_of_day(value: Any) -> datetime:
    day = _normalize_date(value)
    return datetime.combine(day, time.max, tzinfo=timezone.utc)


def _account_sort_key(item: Dict[str, Any]) -> tuple[int, int]:
    return (_safe_int(item.get("sort_order")), _safe_int(item.get("id")))


def _cash_flow_signed_amount(entry: Dict[str, Any]) -> float:
    flow_type = str(entry.get("flow_type") or "").strip().lower()
    amount = _safe_float(entry.get("amount")) or 0.0
    if flow_type in _POSITIVE_CASH_FLOW_TYPES:
        return abs(amount)
    if flow_type in _NEGATIVE_CASH_FLOW_TYPES:
        return -abs(amount)
    return amount


def _normalize_position_key(account_id: int, ticker: str) -> tuple[int, str]:
    return account_id, str(ticker or "").strip().upper()


def _make_position_record(
    *,
    account_id: int,
    account_name: str,
    ticker: str,
    display_name: str | None = None,
    market: str | None = None,
    asset_type: str | None = None,
    currency: str | None = None,
) -> Dict[str, Any]:
    return {
        "account_id": account_id,
        "account_name": account_name,
        "ticker": ticker,
        "display_name": display_name or ticker,
        "market": market,
        "asset_type": asset_type or "stock",
        "currency": currency or BASE_CURRENCY,
        "quantity": 0.0,
        "avg_cost": 0.0,
        "cost_basis": 0.0,
        "realized_pnl": 0.0,
        "trade_count": 0,
        "last_trade_at": None,
    }


def _ensure_position(
    positions_state: Dict[tuple[int, str], Dict[str, Any]],
    account: Dict[str, Any],
    account_id: int,
    ticker: str,
    template: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    key = _normalize_position_key(account_id, ticker)
    if key not in positions_state:
        positions_state[key] = _make_position_record(
            account_id=account_id,
            account_name=account.get("name") or f"Account {account_id}",
            ticker=key[1],
            display_name=(template or {}).get("display_name"),
            market=(template or {}).get("market"),
            asset_type=(template or {}).get("asset_type"),
            currency=(template or {}).get("currency") or account.get("base_currency") or BASE_CURRENCY,
        )
    position = positions_state[key]
    if template:
        if template.get("display_name") and position.get("display_name") == position["ticker"]:
            position["display_name"] = template["display_name"]
        if template.get("market") and not position.get("market"):
            position["market"] = template["market"]
        if template.get("asset_type") and not position.get("asset_type"):
            position["asset_type"] = template["asset_type"]
        if template.get("currency") and not position.get("currency"):
            position["currency"] = template["currency"]
    return position


def _currency_fx_map(
    cash_entries: Iterable[Dict[str, Any]],
    trade_entries: Iterable[Dict[str, Any]],
    fx_rate_entries: Iterable[Dict[str, Any]] | None,
    base_currency: str,
) -> Dict[str, float]:
    normalized_base = _normalize_currency(base_currency)
    max_dt = datetime.max.replace(tzinfo=timezone.utc)
    fx_map: Dict[str, tuple[int, datetime, float]] = {
        normalized_base: (99, max_dt, 1.0),
    }

    def update_rate(currency: str, row_dt: datetime, rate: float, *, priority: int) -> None:
        previous = fx_map.get(currency)
        if previous is None or priority > previous[0] or (priority == previous[0] and row_dt >= previous[1]):
            fx_map[currency] = (priority, row_dt, rate)

    def collect_ledger(rows: Iterable[Dict[str, Any]], dt_key: str) -> None:
        for row in rows:
            currency = _normalize_currency(row.get("currency"), normalized_base)
            if currency == normalized_base:
                fx_map[currency] = (99, max_dt, 1.0)
                continue
            fx_rate = _safe_float(row.get("fx_rate_to_base"), 0.0) or 0.0
            if fx_rate <= 0:
                continue
            row_dt = _normalize_datetime(row.get(dt_key))
            update_rate(currency, row_dt, fx_rate, priority=1)

    def collect_fx(rows: Iterable[Dict[str, Any]]) -> None:
        for row in rows:
            rate = _safe_float(row.get("rate"), 0.0) or 0.0
            if rate <= 0:
                continue
            from_currency = _normalize_currency(row.get("from_currency"))
            to_currency = _normalize_currency(row.get("to_currency"))
            row_dt = _normalize_datetime(row.get("snapshot_date"))

            if to_currency == normalized_base:
                currency = from_currency
                mapped_rate = rate
            elif from_currency == normalized_base:
                currency = to_currency
                mapped_rate = 1.0 / rate
            else:
                continue

            if currency == normalized_base:
                fx_map[currency] = (99, max_dt, 1.0)
                continue

            # Explicit FX snapshots are the valuation source of truth and should
            # override transaction-level fallback rates when both are present.
            update_rate(currency, row_dt, mapped_rate, priority=2)

    collect_ledger(cash_entries, "flow_date")
    collect_ledger(trade_entries, "trade_date")
    collect_fx(fx_rate_entries or [])
    return {key: value for key, (_, __, value) in fx_map.items()}


def _resolve_fx_rate(currency: str, fx_map: Dict[str, float], base_currency: str) -> float:
    normalized = _normalize_currency(currency, base_currency)
    if normalized == _normalize_currency(base_currency):
        return 1.0
    return _safe_float(fx_map.get(normalized), 0.0) or 0.0


def compute_asset_positions(
    accounts: List[Dict[str, Any]],
    cash_entries: List[Dict[str, Any]],
    trade_entries: List[Dict[str, Any]],
    *,
    adjustment_entries: List[Dict[str, Any]] | None = None,
    fx_rate_entries: List[Dict[str, Any]] | None = None,
    base_currency: str = BASE_CURRENCY,
) -> Dict[str, Any]:
    normalized_base_currency = _normalize_currency(base_currency)
    sorted_accounts = sorted(accounts or [], key=_account_sort_key)
    account_lookup = {account["id"]: account for account in sorted_accounts if account.get("id") is not None}
    fx_map = _currency_fx_map(cash_entries, trade_entries, fx_rate_entries, normalized_base_currency)

    cash_by_account_currency: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    positions_state: Dict[tuple[int, str], Dict[str, Any]] = {}
    warnings: List[str] = []

    for entry in sorted(
        cash_entries or [],
        key=lambda item: (_normalize_datetime(item.get("flow_date")), _safe_int(item.get("id"))),
    ):
        account_id = _safe_int(entry.get("account_id"))
        if account_id not in account_lookup:
            warnings.append(f"Cash entry {entry.get('id')} references unknown account {account_id}.")
            continue
        currency = _normalize_currency(
            entry.get("currency"),
            account_lookup[account_id].get("base_currency") or normalized_base_currency,
        )
        cash_by_account_currency[account_id][currency] += _cash_flow_signed_amount(entry)

    trade_events = [
        ("trade", _normalize_datetime(item.get("trade_date")), _safe_int(item.get("id")), item)
        for item in (trade_entries or [])
    ]
    adjustment_events = [
        ("adjustment", _normalize_datetime(item.get("event_date")), _safe_int(item.get("id")), item)
        for item in (adjustment_entries or [])
    ]
    events = sorted(trade_events + adjustment_events, key=lambda item: (item[1], item[2], item[0]))

    for event_kind, _, _, entry in events:
        account_id = _safe_int(entry.get("account_id"))
        if account_id not in account_lookup:
            warnings.append(f"{event_kind.title()} entry {entry.get('id')} references unknown account {account_id}.")
            continue
        account = account_lookup[account_id]

        if event_kind == "trade":
            currency = _normalize_currency(entry.get("currency"), account.get("base_currency") or normalized_base_currency)
            ticker = str(entry.get("ticker") or "").strip().upper()
            if not ticker:
                warnings.append(f"Trade entry {entry.get('id')} is missing ticker.")
                continue

            quantity = _safe_float(entry.get("quantity"), 0.0) or 0.0
            price = _safe_float(entry.get("price"), 0.0) or 0.0
            fee_amount = _safe_float(entry.get("fee_amount"), 0.0) or 0.0
            tax_amount = _safe_float(entry.get("tax_amount"), 0.0) or 0.0
            if quantity <= 0 or price <= 0:
                warnings.append(f"Trade entry {entry.get('id')} has invalid quantity or price.")
                continue

            position = _ensure_position(
                positions_state,
                account,
                account_id,
                ticker,
                {
                    "display_name": entry.get("display_name"),
                    "market": entry.get("market"),
                    "asset_type": entry.get("asset_type") or "stock",
                    "currency": currency,
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
                position["avg_cost"] = position["cost_basis"] / position["quantity"] if position["quantity"] > 0 else 0.0
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
                if abs(position["quantity"]) < 1e-9:
                    position["quantity"] = 0.0
                position["cost_basis"] = max(position["cost_basis"] - removed_cost, 0.0)
                position["realized_pnl"] += proceeds - removed_cost
                position["avg_cost"] = position["cost_basis"] / position["quantity"] if position["quantity"] > 0 else 0.0
            else:
                warnings.append(f"Trade entry {entry.get('id')} has unsupported side '{entry.get('side')}'.")
                continue

            position["trade_count"] += 1
            position["last_trade_at"] = entry.get("trade_date")
            continue

        event_type = str(entry.get("event_type") or "adjustment").strip().lower()
        ticker = str(entry.get("ticker") or "").strip().upper()
        if not ticker:
            warnings.append(f"Adjustment entry {entry.get('id')} is missing ticker.")
            continue

        position = _ensure_position(
            positions_state,
            account,
            account_id,
            ticker,
            {
                "currency": entry.get("currency") or account.get("base_currency") or normalized_base_currency,
            },
        )

        if event_type == "split":
            split_ratio = _safe_float(entry.get("split_ratio"), 0.0) or 0.0
            if split_ratio <= 0:
                warnings.append(f"Adjustment entry {entry.get('id')} has invalid split_ratio.")
                continue
            if position["quantity"] <= 0:
                warnings.append(f"Adjustment entry {entry.get('id')} cannot split empty position {ticker}.")
                continue
            position["quantity"] *= split_ratio
            position["avg_cost"] = position["cost_basis"] / position["quantity"] if position["quantity"] > 0 else 0.0
            continue

        if event_type == "symbol_change":
            target_ticker = str(entry.get("target_ticker") or "").strip().upper()
            if not target_ticker:
                warnings.append(f"Adjustment entry {entry.get('id')} is missing target_ticker.")
                continue
            if position["quantity"] <= 0 and position["cost_basis"] <= 0:
                warnings.append(f"Adjustment entry {entry.get('id')} cannot rename empty position {ticker}.")
                continue
            target_position = _ensure_position(
                positions_state,
                account,
                account_id,
                target_ticker,
                {
                    "display_name": entry.get("target_display_name") or position.get("display_name"),
                    "market": entry.get("target_market") or position.get("market"),
                    "asset_type": entry.get("target_asset_type") or position.get("asset_type"),
                    "currency": position.get("currency"),
                },
            )
            target_position["quantity"] += position["quantity"]
            target_position["cost_basis"] += position["cost_basis"]
            target_position["realized_pnl"] += position["realized_pnl"]
            target_position["trade_count"] += position["trade_count"]
            target_position["last_trade_at"] = position.get("last_trade_at") or entry.get("event_date")
            target_position["avg_cost"] = (
                target_position["cost_basis"] / target_position["quantity"] if target_position["quantity"] > 0 else 0.0
            )
            position["quantity"] = 0.0
            position["avg_cost"] = 0.0
            position["cost_basis"] = 0.0
            position["realized_pnl"] = 0.0
            position["trade_count"] = 0
            position["last_trade_at"] = entry.get("event_date")
            continue

        quantity_delta = _safe_float(entry.get("quantity_delta"), 0.0) or 0.0
        cost_basis_delta = _safe_float(entry.get("cost_basis_delta"), 0.0) or 0.0
        cash_delta = _safe_float(entry.get("cash_delta"), 0.0) or 0.0
        adjustment_currency = _normalize_currency(
            entry.get("currency"),
            position.get("currency") or account.get("base_currency") or normalized_base_currency,
        )
        if cash_delta:
            cash_by_account_currency[account_id][adjustment_currency] += cash_delta

        new_quantity = position["quantity"] + quantity_delta
        if new_quantity < -1e-9:
            warnings.append(f"Adjustment entry {entry.get('id')} would make {ticker} quantity negative.")
            continue
        position["quantity"] = 0.0 if abs(new_quantity) < 1e-9 else new_quantity
        position["cost_basis"] = max(position["cost_basis"] + cost_basis_delta, 0.0)
        position["avg_cost"] = position["cost_basis"] / position["quantity"] if position["quantity"] > 0 else 0.0

    account_summaries: List[Dict[str, Any]] = []
    positions: List[Dict[str, Any]] = []
    realized_total_base = 0.0
    account_realized_totals_base: Dict[int, float] = defaultdict(float)

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
            if position["account_id"] != account_id:
                continue

            fx_rate = _resolve_fx_rate(position["currency"], fx_map, normalized_base_currency)
            realized_base = position["realized_pnl"] * fx_rate if fx_rate > 0 else None
            if realized_base is not None:
                realized_total_base += realized_base
                account_realized_totals_base[account_id] += realized_base

            if position["quantity"] <= 0:
                continue

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
        "positions": sorted(positions, key=lambda item: (item.get("account_name") or "", item.get("ticker") or "")),
        "realized_total_base": round(realized_total_base, 6),
        "account_realized_totals_base": {
            account_id: round(total, 6) for account_id, total in account_realized_totals_base.items()
        },
        "warnings": list(dict.fromkeys(warnings)),
    }


def _build_reconciliation_summary(
    account_summaries: Dict[int, Dict[str, Any]],
    reconciliation_snapshots: List[Dict[str, Any]] | None,
) -> tuple[Dict[str, Any], List[str]]:
    latest_by_account: Dict[int, Dict[str, Any]] = {}
    warnings: List[str] = []

    for snapshot in reconciliation_snapshots or []:
        account_id = _safe_int(snapshot.get("account_id"))
        if account_id not in account_summaries:
            warnings.append(
                f"Reconciliation snapshot {snapshot.get('id')} references unknown account {account_id}."
            )
            continue
        snapshot_dt = _normalize_datetime(snapshot.get("snapshot_date"))
        previous = latest_by_account.get(account_id)
        previous_dt = _normalize_datetime(previous.get("snapshot_date")) if previous else None
        if previous is None or snapshot_dt >= previous_dt:
            latest_by_account[account_id] = snapshot

    items: List[Dict[str, Any]] = []
    difference_total_base = 0.0
    included_difference_total_base = 0.0
    gap_account_count = 0
    latest_snapshot_date = None

    for account_id, snapshot in latest_by_account.items():
        account_summary = account_summaries[account_id]
        cash_actual = _safe_float(snapshot.get("cash_actual"), None)
        cash_system = _safe_float(snapshot.get("cash_system"), None)
        market_value_actual = _safe_float(snapshot.get("market_value_actual"), None)
        market_value_system = _safe_float(snapshot.get("market_value_system"), None)

        cash_difference = (
            round(cash_actual - cash_system, 6) if cash_actual is not None and cash_system is not None else None
        )
        market_value_difference = (
            round(market_value_actual - market_value_system, 6)
            if market_value_actual is not None and market_value_system is not None
            else None
        )

        comparable_actual_total = 0.0
        comparable_system_total = 0.0
        comparable_parts = 0
        for actual_value, system_value in ((cash_actual, cash_system), (market_value_actual, market_value_system)):
            if actual_value is None or system_value is None:
                continue
            comparable_actual_total += actual_value
            comparable_system_total += system_value
            comparable_parts += 1

        total_actual = round(comparable_actual_total, 6) if comparable_parts else None
        total_system = round(comparable_system_total, 6) if comparable_parts else None
        total_difference = (
            round(comparable_actual_total - comparable_system_total, 6) if comparable_parts else None
        )
        has_gap = bool(total_difference is not None and abs(total_difference) >= _RECONCILIATION_DIFF_EPSILON)

        item = {
            "snapshot_id": snapshot.get("id"),
            "account_id": account_id,
            "account_name": account_summary.get("account_name") or f"Account {account_id}",
            "include_in_total": bool(account_summary.get("include_in_total", True)),
            "snapshot_date": snapshot.get("snapshot_date"),
            "cash_actual": cash_actual,
            "cash_system": cash_system,
            "cash_difference": cash_difference,
            "market_value_actual": market_value_actual,
            "market_value_system": market_value_system,
            "market_value_difference": market_value_difference,
            "total_actual": total_actual,
            "total_system": total_system,
            "total_difference": total_difference,
            "has_gap": has_gap,
            "note": snapshot.get("note"),
            "positions_payload": snapshot.get("positions_payload") or [],
            "created_at": snapshot.get("created_at"),
        }
        account_summary["reconciliation"] = item
        items.append(item)

        if total_difference is not None:
            difference_total_base += total_difference
            if item["include_in_total"]:
                included_difference_total_base += total_difference
        if has_gap:
            gap_account_count += 1
        if latest_snapshot_date is None or _normalize_datetime(item["snapshot_date"]) >= _normalize_datetime(latest_snapshot_date):
            latest_snapshot_date = item["snapshot_date"]

    items.sort(
        key=lambda item: (abs(_safe_float(item.get("total_difference"), 0.0) or 0.0), _normalize_datetime(item.get("snapshot_date"))),
        reverse=True,
    )

    return {
        "items": items,
        "summary": {
            "account_count": len(items),
            "gap_account_count": gap_account_count,
            "difference_total_base": round(difference_total_base, 6),
            "included_difference_total_base": round(included_difference_total_base, 6),
            "latest_snapshot_date": latest_snapshot_date,
        },
    }, warnings


def _resolve_price_override(
    price_overrides: Sequence[Dict[str, Any]] | None,
    *,
    ticker: str,
    account_id: int,
    as_of: datetime,
) -> Dict[str, Any] | None:
    best_account_override = None
    best_global_override = None
    best_account_dt = None
    best_global_dt = None
    normalized_ticker = str(ticker or "").strip().upper()

    for item in price_overrides or []:
        if str(item.get("ticker") or "").strip().upper() != normalized_ticker:
            continue
        effective_at = _normalize_datetime(item.get("effective_at"))
        if effective_at > as_of:
            continue
        item_account_id = item.get("account_id")
        if item_account_id is not None and int(item_account_id) == int(account_id):
            if best_account_dt is None or effective_at >= best_account_dt:
                best_account_override = item
                best_account_dt = effective_at
        elif item_account_id in (None, ""):
            if best_global_dt is None or effective_at >= best_global_dt:
                best_global_override = item
                best_global_dt = effective_at
    return best_account_override or best_global_override


def _build_override_quote(override: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ticker": override.get("ticker"),
        "source": "manual_override",
        "quote_type": "manual_override",
        "is_delayed": False,
        "currency": _normalize_currency(override.get("currency")),
        "price": _safe_float(override.get("price"), None),
        "quote_timestamp": override.get("effective_at"),
        "fx_rate_to_base": _safe_float(override.get("fx_rate_to_base"), None),
        "override_id": override.get("id"),
        "force_override": bool(override.get("force_override", False)),
        "note": override.get("note"),
    }


def _find_latest_history_row(rows: Sequence[Dict[str, Any]], as_of_date: date) -> Dict[str, Any] | None:
    best = None
    best_date = None
    for row in rows or []:
        row_date = _normalize_date(row.get("date"))
        if row_date > as_of_date:
            continue
        if best_date is None or row_date >= best_date:
            best = row
            best_date = row_date
    return best


def _build_history_quote(
    position: Dict[str, Any],
    as_of_date: date,
    history_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any] | None:
    row = _find_latest_history_row(history_rows, as_of_date)
    if not row:
        return None
    price = _safe_float(row.get("adj_close"), None) or _safe_float(row.get("close"), None)
    if price is None or price <= 0:
        return None
    row_date = _normalize_date(row.get("date"))
    return {
        "ticker": position.get("ticker"),
        "source": row.get("source") or "ohlcv",
        "quote_type": "historical_close",
        "is_delayed": False,
        "currency": _normalize_currency(position.get("currency"), BASE_CURRENCY),
        "price": price,
        "quote_timestamp": datetime.combine(row_date, time.min, tzinfo=timezone.utc).isoformat(),
    }


async def build_asset_portfolio_snapshot(
    accounts: List[Dict[str, Any]],
    cash_entries: List[Dict[str, Any]],
    trade_entries: List[Dict[str, Any]],
    *,
    adjustment_entries: List[Dict[str, Any]] | None = None,
    price_overrides: List[Dict[str, Any]] | None = None,
    fx_rate_entries: List[Dict[str, Any]] | None = None,
    reconciliation_snapshots: List[Dict[str, Any]] | None = None,
    fetch_quote: Callable[[str], Awaitable[Dict[str, Any] | None]] | None = None,
    base_currency: str = BASE_CURRENCY,
) -> Dict[str, Any]:
    state = compute_asset_positions(
        accounts,
        cash_entries,
        trade_entries,
        adjustment_entries=adjustment_entries,
        fx_rate_entries=fx_rate_entries,
        base_currency=base_currency,
    )
    normalized_base_currency = state["base_currency"]
    positions = state["positions"]
    account_summaries = {
        item["account_id"]: {
            **item,
            "market_value_base": 0.0,
            "unrealized_pnl_base": 0.0,
            "realized_pnl_base": _safe_float(
                (state.get("account_realized_totals_base") or {}).get(item["account_id"]),
                0.0,
            ) or 0.0,
        }
        for item in state["account_summaries"]
    }
    included_account_ids = {
        item["account_id"] for item in account_summaries.values() if item.get("include_in_total", True)
    }
    now_dt = datetime.now(timezone.utc)

    if fetch_quote and positions:
        quotes = await asyncio.gather(*(fetch_quote(position["ticker"]) for position in positions), return_exceptions=True)
    else:
        quotes = [None] * len(positions)

    quote_gaps: List[Dict[str, Any]] = []
    valued_positions: List[Dict[str, Any]] = []
    market_value_total_base = 0.0
    unrealized_total_base = 0.0
    manual_override_count = 0

    for position, quote in zip(positions, quotes):
        resolved_quote = quote if isinstance(quote, dict) else None
        override = _resolve_price_override(
            price_overrides,
            ticker=position["ticker"],
            account_id=_safe_int(position.get("account_id")),
            as_of=now_dt,
        )
        if override:
            override_quote = _build_override_quote(override)
            quote_price = _safe_float((resolved_quote or {}).get("price"), 0.0) or 0.0
            if override_quote.get("force_override") or quote_price <= 0:
                resolved_quote = override_quote
                manual_override_count += 1

        last_price = _safe_float((resolved_quote or {}).get("price"), 0.0) or 0.0
        price_currency = _normalize_currency((resolved_quote or {}).get("currency"), position["currency"])
        direct_fx_rate = _safe_float((resolved_quote or {}).get("fx_rate_to_base"), None)
        fx_rate = direct_fx_rate if direct_fx_rate and direct_fx_rate > 0 else _resolve_fx_rate(
            price_currency,
            state["fx_rates"],
            normalized_base_currency,
        )
        market_value = position["quantity"] * last_price if last_price > 0 else None
        unrealized_pnl = (market_value - position["cost_basis"]) if market_value is not None else None
        market_value_base = market_value * fx_rate if (market_value is not None and fx_rate > 0) else None
        unrealized_pnl_base = unrealized_pnl * fx_rate if (unrealized_pnl is not None and fx_rate > 0) else None
        cost_basis_base = _safe_float(position.get("cost_basis_base"), 0.0) or 0.0
        unrealized_pnl_pct = (
            (unrealized_pnl_base / cost_basis_base * 100)
            if (unrealized_pnl_base is not None and cost_basis_base > 0)
            else None
        )

        if market_value_base is not None and position["account_id"] in included_account_ids:
            market_value_total_base += market_value_base
        if unrealized_pnl_base is not None and position["account_id"] in included_account_ids:
            unrealized_total_base += unrealized_pnl_base
        elif market_value_base is None:
            quote_gaps.append(
                {
                    "ticker": position["ticker"],
                    "account_id": position["account_id"],
                    "account_name": position["account_name"],
                    "manual_override_available": bool(override),
                }
            )

        account_summary = account_summaries.get(position["account_id"])
        if account_summary is not None:
            if market_value_base is not None:
                account_summary["market_value_base"] += market_value_base
            if unrealized_pnl_base is not None:
                account_summary["unrealized_pnl_base"] += unrealized_pnl_base

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
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 4) if unrealized_pnl_pct is not None else None,
                "manual_price_override_id": override.get("id") if override and resolved_quote and resolved_quote.get("source") == "manual_override" else None,
            }
        )

    cash_total_base = sum(
        _safe_float(item.get("cash_total_base"), 0.0) or 0.0
        for item in account_summaries.values()
        if item.get("account_id") in included_account_ids
    )
    realized_total_base = sum(
        _safe_float(item.get("realized_pnl_base"), 0.0) or 0.0
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
    allocation_total = sum(_safe_float(item.get("total_value_base"), 0.0) or 0.0 for item in allocation_base) or 0.0
    allocation_items = [
        {
            "key": item["account_name"],
            "account_id": item["account_id"],
            "value_base": item["total_value_base"],
            "weight_pct": round(item["total_value_base"] / allocation_total * 100, 4) if allocation_total else 0.0,
        }
        for item in sorted(allocation_base, key=lambda row: row["total_value_base"], reverse=True)
    ]
    reconciliation, reconciliation_warnings = _build_reconciliation_summary(account_summaries, reconciliation_snapshots)
    warnings = list(dict.fromkeys([*(state["warnings"] or []), *reconciliation_warnings]))

    return {
        "base_currency": normalized_base_currency,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "warnings": warnings,
        "quote_gaps": quote_gaps,
        "accounts": sorted(
            [
                {
                    **item,
                    "cash_total_base": round(_safe_float(item.get("cash_total_base"), 0.0) or 0.0, 6),
                }
                for item in account_summaries.values()
            ],
            key=lambda item: item["account_name"],
        ),
        "holdings": sorted(
            valued_positions,
            key=lambda item: (_safe_float(item.get("market_value_base"), 0.0) or 0.0, item["ticker"]),
            reverse=True,
        ),
        "allocation": {
            "group_by": "account",
            "items": allocation_items,
        },
        "reconciliation": reconciliation,
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
            "manual_override_count": manual_override_count,
            "reconciliation_account_count": reconciliation["summary"]["account_count"],
            "reconciliation_gap_count": reconciliation["summary"]["gap_account_count"],
            "reconciliation_difference_total_base": reconciliation["summary"]["difference_total_base"],
        },
    }


def _filter_rows_as_of(rows: Sequence[Dict[str, Any]], dt_key: str, as_of: datetime) -> List[Dict[str, Any]]:
    return [row for row in rows if _normalize_datetime(row.get(dt_key)) <= as_of]


def _external_cash_flow_base(
    cash_entries: Sequence[Dict[str, Any]],
    account_lookup: Dict[int, Dict[str, Any]],
    included_account_ids: set[int],
    base_currency: str,
    *,
    start_dt: datetime | None = None,
    end_dt: datetime | None = None,
) -> float:
    total = 0.0
    normalized_base = _normalize_currency(base_currency)
    for entry in cash_entries:
        account_id = _safe_int(entry.get("account_id"))
        if account_id not in included_account_ids or account_id not in account_lookup:
            continue
        flow_dt = _normalize_datetime(entry.get("flow_date"))
        if start_dt and flow_dt <= start_dt:
            continue
        if end_dt and flow_dt > end_dt:
            continue
        currency = _normalize_currency(entry.get("currency"), account_lookup[account_id].get("base_currency") or normalized_base)
        rate = _safe_float(entry.get("fx_rate_to_base"), None)
        if currency == normalized_base:
            rate = 1.0
        if not rate or rate <= 0:
            rate = 1.0 if currency == normalized_base else 0.0
        total += _cash_flow_signed_amount(entry) * rate
    return total


def _cash_flow_breakdown_base(
    cash_entries: Sequence[Dict[str, Any]],
    account_lookup: Dict[int, Dict[str, Any]],
    included_account_ids: set[int],
    base_currency: str,
    *,
    start_dt: datetime | None = None,
    end_dt: datetime | None = None,
) -> Dict[str, float]:
    totals = {
        "deposit_base": 0.0,
        "withdraw_base": 0.0,
        "dividend_interest_base": 0.0,
        "fee_tax_base": 0.0,
        "transfer_in_base": 0.0,
        "transfer_out_base": 0.0,
        "other_flow_base": 0.0,
        "net_flow_base": 0.0,
    }
    normalized_base = _normalize_currency(base_currency)
    for entry in cash_entries:
        account_id = _safe_int(entry.get("account_id"))
        if account_id not in included_account_ids or account_id not in account_lookup:
            continue
        flow_dt = _normalize_datetime(entry.get("flow_date"))
        if start_dt and flow_dt <= start_dt:
            continue
        if end_dt and flow_dt > end_dt:
            continue
        currency = _normalize_currency(entry.get("currency"), account_lookup[account_id].get("base_currency") or normalized_base)
        rate = _safe_float(entry.get("fx_rate_to_base"), None)
        if currency == normalized_base:
            rate = 1.0
        if not rate or rate <= 0:
            rate = 1.0 if currency == normalized_base else 0.0
        if rate <= 0:
            continue

        flow_type = str(entry.get("flow_type") or "").strip().lower()
        amount_base = abs(_safe_float(entry.get("amount"), 0.0) or 0.0) * rate
        signed_base = _cash_flow_signed_amount(entry) * rate

        if flow_type == "deposit":
            totals["deposit_base"] += amount_base
        elif flow_type == "withdraw":
            totals["withdraw_base"] += amount_base
        elif flow_type in {"dividend", "interest"}:
            totals["dividend_interest_base"] += amount_base
        elif flow_type in {"fee", "tax", "fx_fee"}:
            totals["fee_tax_base"] += amount_base
        elif flow_type == "transfer_in":
            totals["transfer_in_base"] += amount_base
        elif flow_type == "transfer_out":
            totals["transfer_out_base"] += amount_base
        else:
            totals["other_flow_base"] += signed_base

    totals["net_flow_base"] = (
        totals["deposit_base"]
        - totals["withdraw_base"]
        + totals["dividend_interest_base"]
        - totals["fee_tax_base"]
        + totals["transfer_in_base"]
        - totals["transfer_out_base"]
        + totals["other_flow_base"]
    )
    return {key: round(value, 6) for key, value in totals.items()}


async def build_asset_performance_report(
    accounts: List[Dict[str, Any]],
    cash_entries: List[Dict[str, Any]],
    trade_entries: List[Dict[str, Any]],
    *,
    start_at: Any,
    end_at: Any | None = None,
    adjustment_entries: List[Dict[str, Any]] | None = None,
    price_overrides: List[Dict[str, Any]] | None = None,
    fx_rate_entries: List[Dict[str, Any]] | None = None,
    get_price_history: Callable[[str, str, str], Awaitable[List[Dict[str, Any]]]] | None = None,
    fetch_quote: Callable[[str], Awaitable[Dict[str, Any] | None]] | None = None,
    base_currency: str = BASE_CURRENCY,
) -> Dict[str, Any]:
    start_dt = _normalize_datetime(start_at)
    end_dt = _normalize_datetime(end_at) if end_at else datetime.now(timezone.utc)
    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt
    baseline_start_dt = _end_of_day(start_dt.date())

    all_trade_entries = _filter_rows_as_of(trade_entries or [], "trade_date", end_dt)
    all_cash_entries = _filter_rows_as_of(cash_entries or [], "flow_date", end_dt)
    all_adjustment_entries = _filter_rows_as_of(adjustment_entries or [], "event_date", end_dt)
    all_fx_rate_entries = [row for row in (fx_rate_entries or []) if _normalize_date(row.get("snapshot_date")) <= end_dt.date()]

    tickers = sorted(
        {
            str(entry.get("ticker") or "").strip().upper()
            for entry in all_trade_entries + all_adjustment_entries
            if str(entry.get("ticker") or "").strip()
        }
        | {
            str(entry.get("target_ticker") or "").strip().upper()
            for entry in all_adjustment_entries
            if str(entry.get("target_ticker") or "").strip()
        }
    )

    fetch_start_date = (start_dt.date() - timedelta(days=32)).isoformat()
    end_date_text = end_dt.date().isoformat()

    if get_price_history and tickers:
        histories = await asyncio.gather(
            *(get_price_history(ticker, fetch_start_date, end_date_text) for ticker in tickers),
            return_exceptions=True,
        )
        price_histories = {
            ticker: history if isinstance(history, list) else []
            for ticker, history in zip(tickers, histories)
        }
    else:
        price_histories = {ticker: [] for ticker in tickers}

    current_quotes: Dict[str, Dict[str, Any] | None] = {}
    if fetch_quote and tickers and end_dt.date() == datetime.now(timezone.utc).date():
        quotes = await asyncio.gather(*(fetch_quote(ticker) for ticker in tickers), return_exceptions=True)
        current_quotes = {
            ticker: quote if isinstance(quote, dict) else None
            for ticker, quote in zip(tickers, quotes)
        }

    point_dates = {start_dt.date(), end_dt.date()}
    point_dates.update(
        _normalize_datetime(entry.get("flow_date")).date()
        for entry in all_cash_entries
        if start_dt.date() <= _normalize_datetime(entry.get("flow_date")).date() <= end_dt.date()
    )
    point_dates.update(
        _normalize_datetime(entry.get("trade_date")).date()
        for entry in all_trade_entries
        if start_dt.date() <= _normalize_datetime(entry.get("trade_date")).date() <= end_dt.date()
    )
    point_dates.update(
        _normalize_datetime(entry.get("event_date")).date()
        for entry in all_adjustment_entries
        if start_dt.date() <= _normalize_datetime(entry.get("event_date")).date() <= end_dt.date()
    )
    for rows in price_histories.values():
        point_dates.update(
            _normalize_date(row.get("date"))
            for row in rows
            if start_dt.date() <= _normalize_date(row.get("date")) <= end_dt.date()
        )
    sorted_point_dates = sorted(point_dates)

    account_lookup = {account["id"]: account for account in accounts or [] if account.get("id") is not None}
    included_account_ids = {
        int(account["id"])
        for account in accounts or []
        if account.get("id") is not None and bool(account.get("include_in_total", True))
    }

    series: List[Dict[str, Any]] = []
    end_warnings: List[str] = []
    end_quote_gaps: List[Dict[str, Any]] = []

    for point_date in sorted_point_dates:
        as_of = _end_of_day(point_date)
        state = compute_asset_positions(
            accounts,
            _filter_rows_as_of(all_cash_entries, "flow_date", as_of),
            _filter_rows_as_of(all_trade_entries, "trade_date", as_of),
            adjustment_entries=_filter_rows_as_of(all_adjustment_entries, "event_date", as_of),
            fx_rate_entries=[row for row in all_fx_rate_entries if _normalize_date(row.get("snapshot_date")) <= point_date],
            base_currency=base_currency,
        )

        market_value_total_base = 0.0
        unrealized_total_base = 0.0
        quote_gaps: List[Dict[str, Any]] = []
        for position in state["positions"]:
            override = _resolve_price_override(
                price_overrides,
                ticker=position["ticker"],
                account_id=_safe_int(position.get("account_id")),
                as_of=as_of,
            )
            quote = None
            if override and bool(override.get("force_override", False)):
                quote = _build_override_quote(override)
            else:
                quote = _build_history_quote(position, point_date, price_histories.get(position["ticker"], []))
                if quote is None and point_date == end_dt.date():
                    current_quote = current_quotes.get(position["ticker"])
                    if current_quote and (_safe_float(current_quote.get("price"), 0.0) or 0.0) > 0:
                        quote = current_quote
                if quote is None and override:
                    quote = _build_override_quote(override)

            last_price = _safe_float((quote or {}).get("price"), 0.0) or 0.0
            price_currency = _normalize_currency((quote or {}).get("currency"), position.get("currency") or base_currency)
            direct_fx_rate = _safe_float((quote or {}).get("fx_rate_to_base"), None)
            fx_rate = direct_fx_rate if direct_fx_rate and direct_fx_rate > 0 else _resolve_fx_rate(
                price_currency,
                state["fx_rates"],
                state["base_currency"],
            )
            if last_price <= 0 or fx_rate <= 0:
                quote_gaps.append(
                    {
                        "ticker": position["ticker"],
                        "account_id": position["account_id"],
                        "account_name": position["account_name"],
                    }
                )
                continue
            market_value_base = position["quantity"] * last_price * fx_rate
            cost_basis_base = _safe_float(position.get("cost_basis_base"), 0.0) or 0.0
            unrealized_total_base += market_value_base - cost_basis_base if position["account_id"] in included_account_ids else 0.0
            if position["account_id"] in included_account_ids:
                market_value_total_base += market_value_base

        cash_total_base = sum(
            _safe_float(item.get("cash_total_base"), 0.0) or 0.0
            for item in state["account_summaries"]
            if int(item.get("account_id") or 0) in included_account_ids
        )
        realized_total_base = sum(
            _safe_float(total, 0.0) or 0.0
            for account_id, total in (state.get("account_realized_totals_base") or {}).items()
            if int(account_id) in included_account_ids
        )
        total_asset_value_base = cash_total_base + market_value_total_base
        cumulative_net_flow_base = _external_cash_flow_base(
            all_cash_entries,
            account_lookup,
            included_account_ids,
            state["base_currency"],
            start_dt=baseline_start_dt,
            end_dt=as_of,
        )
        flow_breakdown = _cash_flow_breakdown_base(
            all_cash_entries,
            account_lookup,
            included_account_ids,
            state["base_currency"],
            start_dt=baseline_start_dt,
            end_dt=as_of,
        )

        point = {
            "date": point_date.isoformat(),
            "cash_total_base": round(cash_total_base, 6),
            "market_value_total_base": round(market_value_total_base, 6),
            "total_asset_value_base": round(total_asset_value_base, 6),
            "realized_total_base": round(realized_total_base, 6),
            "unrealized_total_base": round(unrealized_total_base, 6),
            "net_flow_base": round(cumulative_net_flow_base, 6),
            "flow_breakdown": flow_breakdown,
            "quote_gap_count": len(quote_gaps),
        }
        series.append(point)

        if point_date == end_dt.date():
            end_warnings = state["warnings"]
            end_quote_gaps = quote_gaps

    if not series:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "base_currency": _normalize_currency(base_currency),
            "warnings": [],
            "quote_gaps": [],
            "summary": {
                "start_value_base": 0.0,
                "end_value_base": 0.0,
                "net_flow_base": 0.0,
                "true_performance_base": 0.0,
                "true_return_pct": 0.0,
                "high_water_mark_base": 0.0,
                "max_drawdown_pct": 0.0,
                "point_count": 0,
                "realized_end_base": 0.0,
                "unrealized_end_base": 0.0,
                "flow_breakdown": {
                    "deposit_base": 0.0,
                    "withdraw_base": 0.0,
                    "dividend_interest_base": 0.0,
                    "fee_tax_base": 0.0,
                    "transfer_in_base": 0.0,
                    "transfer_out_base": 0.0,
                    "other_flow_base": 0.0,
                    "net_flow_base": 0.0,
                },
                "performance_breakdown": {
                    "realized_change_base": 0.0,
                    "unrealized_change_base": 0.0,
                    "other_change_base": 0.0,
                    "total_change_base": 0.0,
                },
            },
            "series": [],
            "monthly_heatmap": [],
            "realized_vs_unrealized": [],
        }

    start_value_base = _safe_float(series[0].get("total_asset_value_base"), 0.0) or 0.0
    start_realized_total_base = _safe_float(series[0].get("realized_total_base"), 0.0) or 0.0
    start_unrealized_total_base = _safe_float(series[0].get("unrealized_total_base"), 0.0) or 0.0
    high_water_mark = 0.0
    max_drawdown_pct = 0.0
    for point in series:
        total = _safe_float(point.get("total_asset_value_base"), 0.0) or 0.0
        high_water_mark = max(high_water_mark, total)
        if high_water_mark > 0:
            drawdown_pct = (total - high_water_mark) / high_water_mark * 100
        else:
            drawdown_pct = 0.0
        point["drawdown_pct"] = round(drawdown_pct, 4)
        point["true_performance_base"] = round(
            total - start_value_base - (_safe_float(point.get("net_flow_base"), 0.0) or 0.0),
            6,
        )
        realized_change_base = (_safe_float(point.get("realized_total_base"), 0.0) or 0.0) - start_realized_total_base
        unrealized_change_base = (_safe_float(point.get("unrealized_total_base"), 0.0) or 0.0) - start_unrealized_total_base
        other_change_base = (_safe_float(point.get("true_performance_base"), 0.0) or 0.0) - realized_change_base - unrealized_change_base
        point["performance_breakdown"] = {
            "realized_change_base": round(realized_change_base, 6),
            "unrealized_change_base": round(unrealized_change_base, 6),
            "other_change_base": round(other_change_base, 6),
            "total_change_base": round(_safe_float(point.get("true_performance_base"), 0.0) or 0.0, 6),
        }
        max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)

    end_point = series[-1]
    end_value_base = _safe_float(end_point.get("total_asset_value_base"), 0.0) or 0.0
    end_net_flow_base = _safe_float(end_point.get("net_flow_base"), 0.0) or 0.0
    true_performance_base = end_value_base - start_value_base - end_net_flow_base
    true_return_pct = (true_performance_base / start_value_base * 100) if start_value_base else 0.0

    monthly_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for point in series:
        monthly_groups[point["date"][:7]].append(point)
    monthly_heatmap: List[Dict[str, Any]] = []
    for month, points in sorted(monthly_groups.items()):
        month_start = _normalize_datetime(f"{month}-01T00:00:00+00:00")
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = next_month - timedelta(microseconds=1)
        month_start_value = _safe_float(points[0].get("total_asset_value_base"), 0.0) or 0.0
        month_end_value = _safe_float(points[-1].get("total_asset_value_base"), 0.0) or 0.0
        month_series_start_dt = _end_of_day(points[0].get("date"))
        month_flow = _external_cash_flow_base(
            all_cash_entries,
            account_lookup,
            included_account_ids,
            _normalize_currency(base_currency),
            start_dt=month_series_start_dt,
            end_dt=month_end,
        )
        performance_base = month_end_value - month_start_value - month_flow
        return_pct = (performance_base / month_start_value * 100) if month_start_value else 0.0
        monthly_heatmap.append(
            {
                "month": month,
                "true_performance_base": round(performance_base, 6),
                "return_pct": round(return_pct, 4),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_currency": _normalize_currency(base_currency),
        "warnings": end_warnings,
        "quote_gaps": end_quote_gaps,
        "summary": {
            "start_value_base": round(start_value_base, 6),
            "end_value_base": round(end_value_base, 6),
            "net_flow_base": round(end_net_flow_base, 6),
            "true_performance_base": round(true_performance_base, 6),
            "true_return_pct": round(true_return_pct, 4),
            "high_water_mark_base": round(high_water_mark, 6),
            "max_drawdown_pct": round(max_drawdown_pct, 4),
            "latest_snapshot_date": end_point["date"],
            "point_count": len(series),
            "realized_end_base": round(_safe_float(end_point.get("realized_total_base"), 0.0) or 0.0, 6),
            "unrealized_end_base": round(_safe_float(end_point.get("unrealized_total_base"), 0.0) or 0.0, 6),
            "flow_breakdown": end_point.get("flow_breakdown") or {
                "deposit_base": 0.0,
                "withdraw_base": 0.0,
                "dividend_interest_base": 0.0,
                "fee_tax_base": 0.0,
                "transfer_in_base": 0.0,
                "transfer_out_base": 0.0,
                "other_flow_base": 0.0,
                "net_flow_base": 0.0,
            },
            "performance_breakdown": end_point.get("performance_breakdown") or {
                "realized_change_base": 0.0,
                "unrealized_change_base": 0.0,
                "other_change_base": 0.0,
                "total_change_base": 0.0,
            },
        },
        "series": series,
        "monthly_heatmap": monthly_heatmap,
        "realized_vs_unrealized": [
            {
                "date": point["date"],
                "realized_total_base": point["realized_total_base"],
                "unrealized_total_base": point["unrealized_total_base"],
            }
            for point in series
        ],
    }


def build_asset_alerts(
    snapshot: Dict[str, Any],
    performance_report: Dict[str, Any] | None,
    *,
    drawdown_threshold_pct: float = _DEFAULT_ALERT_DRAWNDOWN_THRESHOLD_PCT,
    concentration_threshold_pct: float = _DEFAULT_ALERT_CONCENTRATION_THRESHOLD_PCT,
    holding_loss_threshold_pct: float = _DEFAULT_ALERT_HOLDING_LOSS_THRESHOLD_PCT,
) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    summary = snapshot.get("summary") or {}
    holdings = snapshot.get("holdings") or []
    base_currency = snapshot.get("base_currency") or BASE_CURRENCY

    if summary.get("quote_gap_count"):
        alerts.append(
            {
                "level": "warning",
                "code": "quote_gap",
                "title": "存在無法估值的持倉",
                "message": f"{summary.get('quote_gap_count', 0)} 檔標的缺少最新價格，請補手動價格覆蓋。",
            }
        )

    if summary.get("reconciliation_gap_count"):
        alerts.append(
            {
                "level": "warning",
                "code": "reconciliation_gap",
                "title": "帳戶對帳仍有差異",
                "message": f"{summary.get('reconciliation_gap_count', 0)} 個帳戶仍有對帳落差，請檢查現金或持倉校正。",
            }
        )

    total_asset_value_base = _safe_float(summary.get("total_asset_value_base"), 0.0) or 0.0
    if total_asset_value_base > 0:
        heaviest = max(holdings, key=lambda item: _safe_float(item.get("market_value_base"), 0.0) or 0.0, default=None)
        if heaviest:
            weight_pct = ((_safe_float(heaviest.get("market_value_base"), 0.0) or 0.0) / total_asset_value_base) * 100
            if weight_pct >= concentration_threshold_pct:
                alerts.append(
                    {
                        "level": "warning",
                        "code": "concentration",
                        "title": "單一持倉比重偏高",
                        "message": f"{heaviest.get('ticker')} 目前占總資產 {weight_pct:.2f}%。",
                    }
                )

    for holding in holdings:
        unrealized_pct = _safe_float(holding.get("unrealized_pnl_pct"), None)
        if unrealized_pct is None:
            continue
        if unrealized_pct <= -abs(holding_loss_threshold_pct):
            alerts.append(
                {
                    "level": "warning",
                    "code": "holding_drawdown",
                    "title": "單一持倉浮虧偏大",
                    "message": f"{holding.get('ticker')} 未實現報酬 {unrealized_pct:.2f}%。",
                }
            )
            break

    performance_summary = (performance_report or {}).get("summary") or {}
    max_drawdown_pct = _safe_float(performance_summary.get("max_drawdown_pct"), 0.0) or 0.0
    if max_drawdown_pct <= -abs(drawdown_threshold_pct):
        alerts.append(
            {
                "level": "warning",
                "code": "portfolio_drawdown",
                "title": "資產曲線回撤超標",
                "message": f"目前區間最大回撤 {max_drawdown_pct:.2f}%。",
            }
        )

    high_water_mark_base = _safe_float(performance_summary.get("high_water_mark_base"), 0.0) or 0.0
    if high_water_mark_base > 0 and abs(high_water_mark_base - total_asset_value_base) < 0.01:
        alerts.append(
            {
                "level": "info",
                "code": "new_high",
                "title": "總資產接近區間新高",
                "message": f"目前總資產約 {base_currency} {total_asset_value_base:,.0f}，接近近期高點。",
            }
        )

    return alerts
