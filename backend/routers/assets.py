"""Asset tracking routes."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from asset_tracking_service import (
    build_asset_alerts,
    build_asset_performance_report,
    build_asset_portfolio_snapshot,
)
from data_fetcher import normalize_ticker
from database import DEFAULT_OWNER_ID, db
from database.helpers import (
    _normalize_asset_cash_ledger_payload,
    _normalize_asset_trade_payload,
    _parse_datetime_value,
)
from schemas import (
    AssetAccountCreatePayload,
    AssetAccountUpdatePayload,
    AssetCashLedgerCreatePayload,
    AssetCashLedgerUpdatePayload,
    AssetCsvImportPayload,
    AssetFxRateCreatePayload,
    AssetFxRateUpdatePayload,
    AssetJournalImportPayload,
    AssetPositionAdjustmentCreatePayload,
    AssetPositionAdjustmentUpdatePayload,
    AssetPriceOverrideCreatePayload,
    AssetPriceOverrideUpdatePayload,
    AssetRecomputePayload,
    AssetReconciliationCreatePayload,
    AssetTradeCreatePayload,
    AssetTradeUpdatePayload,
)

router = APIRouter(prefix="/api/assets", tags=["assets"])

_fetch_and_store_quote_snapshot = None
_latest_public_fx_provider = None
_SNAPSHOT_LIMIT = 5000
_LEDGER_PAGE_SIZE = 1000
_AUTO_TRADE_SETTLEMENT_SOURCE = "trade_settlement_auto"


def configure(*, fetch_and_store_quote_snapshot, latest_public_fx_provider=None) -> None:
    global _fetch_and_store_quote_snapshot, _latest_public_fx_provider
    _fetch_and_store_quote_snapshot = fetch_and_store_quote_snapshot
    _latest_public_fx_provider = latest_public_fx_provider


async def _ensure_account_exists(account_id: int | None) -> Dict[str, Any] | None:
    if account_id is None:
        return None
    account = await db.get_asset_account(account_id, owner_id=DEFAULT_OWNER_ID)
    if not account:
        raise HTTPException(400, f"Asset account {account_id} does not exist")
    return account


def _build_trade_settlement_note(trade_entry: Dict[str, Any], broker_account: Dict[str, Any], settlement_account: Dict[str, Any]) -> str:
    ticker = str(trade_entry.get("ticker") or "").strip().upper() or "UNKNOWN"
    side = str(trade_entry.get("side") or "").strip().lower()
    action = "buy" if side == "buy" else "sell"
    return (
        f"Auto settlement sync for trade #{trade_entry.get('id')} {ticker} {action} "
        f"between {settlement_account.get('name') or settlement_account.get('id')} "
        f"and {broker_account.get('name') or broker_account.get('id')}."
    )


def _build_trade_settlement_payloads(
    trade_entry: Dict[str, Any],
    broker_account: Dict[str, Any],
    settlement_account: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    amount = abs(float(trade_entry.get("net_amount") or 0.0))
    if amount <= 0:
        return {}

    trade_date = trade_entry.get("trade_date")
    currency = trade_entry.get("currency") or broker_account.get("base_currency") or "TWD"
    fx_rate_to_base = float(trade_entry.get("fx_rate_to_base") or 1.0)
    side = str(trade_entry.get("side") or "").strip().lower()
    note = _build_trade_settlement_note(trade_entry, broker_account, settlement_account)

    common = {
        "flow_date": trade_date,
        "amount": amount,
        "currency": currency,
        "fx_rate_to_base": fx_rate_to_base,
        "is_initial_balance": False,
        "source": _AUTO_TRADE_SETTLEMENT_SOURCE,
        "linked_trade_id": trade_entry.get("id"),
        "note": note,
    }
    if side == "buy":
        return {
            "settlement_out": {
                **common,
                "account_id": settlement_account.get("id"),
                "flow_type": "transfer_out",
                "linked_trade_role": "settlement_out",
                "counterparty": broker_account.get("name"),
            },
            "broker_in": {
                **common,
                "account_id": broker_account.get("id"),
                "flow_type": "transfer_in",
                "linked_trade_role": "broker_in",
                "counterparty": settlement_account.get("name"),
            },
        }
    if side == "sell":
        return {
            "broker_out": {
                **common,
                "account_id": broker_account.get("id"),
                "flow_type": "transfer_out",
                "linked_trade_role": "broker_out",
                "counterparty": settlement_account.get("name"),
            },
            "settlement_in": {
                **common,
                "account_id": settlement_account.get("id"),
                "flow_type": "transfer_in",
                "linked_trade_role": "settlement_in",
                "counterparty": broker_account.get("name"),
            },
        }
    return {}


async def _validate_account_settlement_config(payload: Dict[str, Any], *, account_id: int | None = None) -> None:
    settlement_account_id = payload.get("settlement_account_id")
    if settlement_account_id in ("", 0):
        settlement_account_id = None
    if settlement_account_id is not None:
        settlement_account_id = int(settlement_account_id)
        if account_id is not None and settlement_account_id == int(account_id):
            raise HTTPException(400, "Settlement account cannot point to the same asset account")
        await _ensure_account_exists(settlement_account_id)
    if payload.get("auto_sync_trade_settlement") and settlement_account_id is None:
        raise HTTPException(400, "Settlement account is required when auto trade settlement sync is enabled")


async def _delete_trade_linked_cash_entries(trade_id: int) -> None:
    linked_entries = await db.list_asset_cash_ledger_entries_by_linked_trade(trade_id, owner_id=DEFAULT_OWNER_ID)
    for entry in linked_entries:
        await db.delete_asset_cash_ledger_entry(int(entry.get("id")), owner_id=DEFAULT_OWNER_ID)


async def _sync_trade_linked_cash_entries(trade_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    linked_entries = await db.list_asset_cash_ledger_entries_by_linked_trade(
        int(trade_entry.get("id") or 0),
        owner_id=DEFAULT_OWNER_ID,
    )
    broker_account = await _ensure_account_exists(int(trade_entry.get("account_id")))
    auto_enabled = bool(broker_account and broker_account.get("auto_sync_trade_settlement"))
    settlement_account_id = int((broker_account or {}).get("settlement_account_id") or 0)
    is_initial_balance = bool(trade_entry.get("is_initial_balance"))

    if not auto_enabled or not settlement_account_id or is_initial_balance:
        for entry in linked_entries:
            await db.delete_asset_cash_ledger_entry(int(entry.get("id")), owner_id=DEFAULT_OWNER_ID)
        return []

    settlement_account = await _ensure_account_exists(settlement_account_id)
    if int(settlement_account.get("id") or 0) == int(broker_account.get("id") or 0):
        raise HTTPException(400, "Settlement account cannot point to the same brokerage account")

    payloads = _build_trade_settlement_payloads(trade_entry, broker_account, settlement_account)
    expected_roles = set(payloads)
    existing_by_role = {str(item.get("linked_trade_role") or ""): item for item in linked_entries}
    synced_entries: List[Dict[str, Any]] = []

    for role, payload in payloads.items():
        existing = existing_by_role.get(role)
        if existing:
            synced = await db.update_asset_cash_ledger_entry(int(existing.get("id")), payload, owner_id=DEFAULT_OWNER_ID)
        else:
            synced = await db.create_asset_cash_ledger_entry(payload, owner_id=DEFAULT_OWNER_ID)
        synced_entries.append(synced)

    for entry in linked_entries:
        if str(entry.get("linked_trade_role") or "") not in expected_roles:
            await db.delete_asset_cash_ledger_entry(int(entry.get("id")), owner_id=DEFAULT_OWNER_ID)

    return synced_entries


async def _create_trade_entry_with_settlement_sync(payload: Dict[str, Any]) -> Dict[str, Any]:
    trade_entry = await db.create_asset_trade_entry(payload, owner_id=DEFAULT_OWNER_ID)
    try:
        await _sync_trade_linked_cash_entries(trade_entry)
    except Exception:  # noqa: BLE001 - best-effort rollback to avoid half-created trade state
        await db.delete_asset_trade_entry(int(trade_entry.get("id")), owner_id=DEFAULT_OWNER_ID)
        raise
    return trade_entry


def _is_public_auto_fx_source(source: str | None) -> bool:
    normalized = str(source or "").strip().lower()
    return normalized in {"taifex_daily_reference", "public_auto"}


async def _load_all_asset_rows(fetcher, **kwargs) -> List[Dict[str, Any]]:
    """Read a complete ledger in stable pages so long histories are never truncated."""
    rows: List[Dict[str, Any]] = []
    offset = 0
    while True:
        page = await fetcher(
            owner_id=DEFAULT_OWNER_ID,
            limit=_LEDGER_PAGE_SIZE,
            offset=offset,
            **kwargs,
        )
        rows.extend(page)
        if len(page) < _LEDGER_PAGE_SIZE:
            return rows
        offset += len(page)


async def _sync_latest_public_fx_rates() -> List[Dict[str, Any]]:
    if _latest_public_fx_provider is None:
        return await _load_all_asset_rows(db.list_asset_fx_rates)

    try:
        payload = await asyncio.to_thread(_latest_public_fx_provider.fetch_latest_rates)
    except Exception:  # noqa: BLE001 - keep asset snapshot resilient to public FX fetch issues
        return await _load_all_asset_rows(db.list_asset_fx_rates)

    snapshot_date = payload.get("snapshot_date")
    candidate_rates = payload.get("rates") or []
    if not snapshot_date or not candidate_rates:
        return await _load_all_asset_rows(db.list_asset_fx_rates)

    existing_rows = await db.list_asset_fx_rates(
        owner_id=DEFAULT_OWNER_ID,
        date_from=snapshot_date,
        date_to=snapshot_date,
        limit=_SNAPSHOT_LIMIT,
    )
    existing_map = {
        (str(item.get("from_currency") or "").upper(), str(item.get("to_currency") or "").upper()): item
        for item in existing_rows
    }

    for item in candidate_rates:
        from_currency = str(item.get("from_currency") or "").strip().upper()
        to_currency = str(item.get("to_currency") or "").strip().upper()
        if not from_currency or not to_currency:
            continue
        existing = existing_map.get((from_currency, to_currency))
        if existing and not _is_public_auto_fx_source(existing.get("source")):
            continue
        await db.create_asset_fx_rate(
            {
                "snapshot_date": snapshot_date,
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": item.get("rate"),
                "source": item.get("source") or payload.get("source") or "public_auto",
                "note": item.get("note"),
            },
            owner_id=DEFAULT_OWNER_ID,
        )

    return await _load_all_asset_rows(db.list_asset_fx_rates)


async def _load_asset_inputs(*, refresh_public_fx: bool = False) -> tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    fx_loader = _sync_latest_public_fx_rates() if refresh_public_fx else _load_all_asset_rows(db.list_asset_fx_rates)
    (
        accounts,
        cash_entries,
        trade_entries,
        adjustment_entries,
        price_overrides,
        fx_rates,
        reconciliation_snapshots,
    ) = await asyncio.gather(
        db.list_asset_accounts(owner_id=DEFAULT_OWNER_ID),
        _load_all_asset_rows(db.list_asset_cash_ledger_entries),
        _load_all_asset_rows(db.list_asset_trade_entries),
        _load_all_asset_rows(db.list_asset_position_adjustments),
        _load_all_asset_rows(db.list_asset_price_overrides),
        fx_loader,
        _load_all_asset_rows(db.list_asset_reconciliation_snapshots),
    )
    return (
        accounts,
        cash_entries,
        trade_entries,
        adjustment_entries,
        price_overrides,
        fx_rates,
        reconciliation_snapshots,
    )


async def _fetch_latest_quote(ticker: str, *, refresh: bool = True) -> Dict[str, Any] | None:
    normalized = normalize_ticker(ticker)
    quote = None
    if refresh and _fetch_and_store_quote_snapshot:
        quote = await _fetch_and_store_quote_snapshot(normalized)
    if not quote:
        quote = await db.get_market_quote(normalized)
    return quote


async def _persist_snapshot(snapshot: Dict[str, Any]) -> None:
    await db.replace_asset_positions_current(DEFAULT_OWNER_ID, snapshot.get("holdings") or [])
    await db.replace_asset_valuations_current(DEFAULT_OWNER_ID, snapshot.get("holdings") or [])


def _build_reconciliation_positions_payload(snapshot: Dict[str, Any], account_id: int) -> List[Dict[str, Any]]:
    return [
        {
            "ticker": item.get("ticker"),
            "display_name": item.get("display_name"),
            "quantity": item.get("quantity"),
            "last_price": item.get("last_price"),
            "market_value_base": item.get("market_value_base"),
            "quote_timestamp": item.get("quote_timestamp"),
            "quote_source": item.get("quote_source"),
            "manual_price_override_id": item.get("manual_price_override_id"),
        }
        for item in snapshot.get("holdings") or []
        if int(item.get("account_id") or 0) == int(account_id)
    ]


def _build_allocation(snapshot: Dict[str, Any], group_by: str) -> Dict[str, Any]:
    normalized_group_by = str(group_by or "account").strip().lower()
    if normalized_group_by == "account":
        return snapshot.get("allocation") or {"group_by": "account", "items": []}

    if normalized_group_by != "market":
        raise HTTPException(400, "Allocation group_by must be account or market")

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


def _build_contributors(snapshot: Dict[str, Any], limit: int) -> Dict[str, Any]:
    clean_limit = max(1, min(int(limit or 10), 50))
    holdings = list(snapshot.get("holdings") or [])
    top_gainers = sorted(
        holdings,
        key=lambda item: float(item.get("unrealized_pnl_base") or 0.0),
        reverse=True,
    )[:clean_limit]
    top_losers = sorted(
        holdings,
        key=lambda item: float(item.get("unrealized_pnl_base") or 0.0),
    )[:clean_limit]
    return {"top_gainers": top_gainers, "top_losers": top_losers}


async def _build_snapshot(*, refresh: bool = True) -> Dict[str, Any]:
    (
        accounts,
        cash_entries,
        trade_entries,
        adjustment_entries,
        price_overrides,
        fx_rates,
        reconciliation_snapshots,
    ) = await _load_asset_inputs(refresh_public_fx=refresh)
    snapshot = await build_asset_portfolio_snapshot(
        accounts,
        cash_entries,
        trade_entries,
        adjustment_entries=adjustment_entries,
        price_overrides=price_overrides,
        fx_rate_entries=fx_rates,
        reconciliation_snapshots=reconciliation_snapshots,
        fetch_quote=(lambda ticker: _fetch_latest_quote(ticker, refresh=refresh)),
    )
    await _persist_snapshot(snapshot)
    return snapshot


def _resolve_performance_start(range_name: str) -> str:
    normalized = str(range_name or "1y").strip().lower()
    today = datetime.now(timezone.utc).date()
    if normalized in {"all", "max"}:
        return "1900-01-01"
    if normalized == "ytd":
        return date(today.year, 1, 1).isoformat()
    if normalized.endswith("d") and normalized[:-1].isdigit():
        return (today - timedelta(days=int(normalized[:-1]))).isoformat()
    if normalized.endswith("y") and normalized[:-1].isdigit():
        return (today - timedelta(days=int(normalized[:-1]) * 365)).isoformat()
    mapping = {
        "30d": 30,
        "90d": 90,
        "180d": 180,
        "1y": 365,
        "2y": 730,
        "3y": 1095,
    }
    days = mapping.get(normalized, 365)
    return (today - timedelta(days=days)).isoformat()


async def _build_performance(range_name: str, *, refresh: bool = True) -> Dict[str, Any]:
    (
        accounts,
        cash_entries,
        trade_entries,
        adjustment_entries,
        price_overrides,
        fx_rates,
        _,
    ) = await _load_asset_inputs(refresh_public_fx=refresh)
    start_at = _resolve_performance_start(range_name)
    report = await build_asset_performance_report(
        accounts,
        cash_entries,
        trade_entries,
        start_at=start_at,
        end_at=datetime.now(timezone.utc).isoformat(),
        adjustment_entries=adjustment_entries,
        price_overrides=price_overrides,
        fx_rate_entries=fx_rates,
        get_price_history=lambda ticker, start_date, end_date: db.get_ohlcv_range(ticker, start_date, end_date, "1d"),
        fetch_quote=(lambda ticker: _fetch_latest_quote(ticker, refresh=refresh)),
    )
    report["range"] = str(range_name or "1y").strip().lower() or "1y"
    return report


def _normalize_csv_text(value: str) -> str:
    return str(value or "").replace("\ufeff", "").strip()


def _normalize_csv_row(row: Dict[str, Any]) -> Dict[str, str]:
    normalized = {}
    for key, value in (row or {}).items():
        normalized_key = str(key or "").strip().lower()
        if not normalized_key:
            continue
        normalized[normalized_key] = str(value or "").strip()
    return normalized


def _csv_import_error_message(exc: Exception) -> str:
    message = str(exc)
    if message.startswith("Asset account ") and message.endswith(" does not exist"):
        account_id = message.removeprefix("Asset account ").removesuffix(" does not exist")
        return f"資產帳戶 {account_id} 不存在"
    translations = (
        ("Asset trade quantity must be greater than 0", "交易數量必須大於 0"),
        ("Asset trade price must be greater than 0", "交易價格必須大於 0"),
        ("Asset trade side must be buy or sell", "交易方向必須為 buy 或 sell"),
        ("Asset trade ticker is required", "交易商品代號不可空白"),
        ("Asset trade trade_date is required", "交易日期不可空白"),
        ("Asset cash ledger amount is required", "現金金額不可空白"),
        ("Asset cash ledger flow_type is required", "現金流向類型不可空白"),
        ("Asset cash ledger flow_date is required", "現金日期不可空白"),
        ("Unable to parse trade_date", "無法解析交易日期"),
        ("Unable to parse flow_date", "無法解析現金日期"),
        ("Unable to parse account_id", "無法解析帳戶代號"),
        (
            "CSV row is missing account_id/account_name and no default_account_id was provided",
            "CSV 列缺少 account_id/account_name，且未選擇預設帳戶",
        ),
        ("Unable to resolve account_name", "無法依帳戶名稱找到資產帳戶"),
    )
    for source, translated in translations:
        if source in message:
            suffix = message.split(source, 1)[1]
            return f"{translated}{suffix}"
    return f"資料格式錯誤：{message}"


def _build_account_lookups(accounts: List[Dict[str, Any]]) -> tuple[Dict[int, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    by_id = {int(account["id"]): account for account in accounts if account.get("id") is not None}
    by_name = {str(account.get("name") or "").strip().lower(): account for account in accounts if account.get("name")}
    return by_id, by_name


def _resolve_account_id_from_csv(
    row: Dict[str, str],
    *,
    default_account_id: int | None,
    accounts_by_id: Dict[int, Dict[str, Any]],
    accounts_by_name: Dict[str, Dict[str, Any]],
) -> int:
    raw_account_id = row.get("account_id") or row.get("account")
    if raw_account_id:
        try:
            account_id = int(raw_account_id)
        except ValueError as exc:
            raise ValueError(f"Unable to parse account_id {raw_account_id!r}") from exc
        if account_id not in accounts_by_id:
            raise ValueError(f"Asset account {account_id} does not exist")
        return account_id

    raw_account_name = (row.get("account_name") or row.get("account") or "").strip().lower()
    if raw_account_name:
        account = accounts_by_name.get(raw_account_name)
        if not account:
            raise ValueError(f"Unable to resolve account_name {raw_account_name!r}")
        return int(account["id"])

    if default_account_id is None:
        raise ValueError("CSV row is missing account_id/account_name and no default_account_id was provided")
    if default_account_id not in accounts_by_id:
        raise ValueError(f"Asset account {default_account_id} does not exist")
    return int(default_account_id)


def _resolve_trade_currency_for_market(market: str) -> str:
    return "USD" if str(market or "").strip().upper() == "US" else "TWD"


def _infer_trade_market(raw_ticker: str) -> str:
    normalized = normalize_ticker(raw_ticker)
    if normalized.endswith(".TW") or normalized.endswith(".TWO"):
        return "TW"
    if normalized.endswith(".HK"):
        return "HK"
    return "US"


def _parse_trade_csv_payload(
    row: Dict[str, str],
    *,
    default_account_id: int | None,
    accounts_by_id: Dict[int, Dict[str, Any]],
    accounts_by_name: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    account_id = _resolve_account_id_from_csv(
        row,
        default_account_id=default_account_id,
        accounts_by_id=accounts_by_id,
        accounts_by_name=accounts_by_name,
    )
    raw_ticker = row.get("ticker") or row.get("symbol")
    market = row.get("market") or _infer_trade_market(raw_ticker or "")
    payload = {
        "account_id": account_id,
        "trade_date": row.get("trade_date") or row.get("date") or row.get("datetime"),
        "ticker": normalize_ticker(raw_ticker or ""),
        "display_name": row.get("display_name") or row.get("name") or None,
        "market": market,
        "asset_type": row.get("asset_type") or "stock",
        "currency": (row.get("currency") or _resolve_trade_currency_for_market(market)).upper(),
        "side": (row.get("side") or row.get("direction") or "").lower(),
        "quantity": row.get("quantity") or row.get("size"),
        "price": row.get("price") or row.get("trade_price"),
        "fee_amount": row.get("fee_amount") or row.get("fee") or 0,
        "tax_amount": row.get("tax_amount") or row.get("tax") or 0,
        "fx_rate_to_base": row.get("fx_rate_to_base") or row.get("fx_rate") or 1,
        "source": row.get("source") or "csv_import",
        "note": row.get("note") or None,
    }
    return payload


def _parse_cash_csv_payload(
    row: Dict[str, str],
    *,
    default_account_id: int | None,
    accounts_by_id: Dict[int, Dict[str, Any]],
    accounts_by_name: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    account_id = _resolve_account_id_from_csv(
        row,
        default_account_id=default_account_id,
        accounts_by_id=accounts_by_id,
        accounts_by_name=accounts_by_name,
    )
    account = accounts_by_id[account_id]
    payload = {
        "account_id": account_id,
        "flow_date": row.get("flow_date") or row.get("date") or row.get("datetime"),
        "flow_type": (row.get("flow_type") or row.get("type") or "").lower(),
        "amount": row.get("amount"),
        "currency": (row.get("currency") or account.get("base_currency") or "TWD").upper(),
        "fx_rate_to_base": row.get("fx_rate_to_base") or row.get("fx_rate") or 1,
        "counterparty": row.get("counterparty") or row.get("from_to") or None,
        "note": row.get("note") or None,
    }
    return payload


def _run_csv_import(
    csv_text: str,
    *,
    default_account_id: int | None,
    accounts: List[Dict[str, Any]],
    parser,
    item_type: str,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    normalized_csv = _normalize_csv_text(csv_text)
    if not normalized_csv:
        raise ValueError("CSV text is required")

    reader = csv.DictReader(io.StringIO(normalized_csv))
    if not reader.fieldnames:
        raise ValueError("CSV must include a header row")

    accounts_by_id, accounts_by_name = _build_account_lookups(accounts)
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for index, raw_row in enumerate(reader, start=2):
        row = _normalize_csv_row(raw_row)
        if not any(row.values()):
            continue
        try:
            parsed = parser(
                row,
                default_account_id=default_account_id,
                accounts_by_id=accounts_by_id,
                accounts_by_name=accounts_by_name,
            )
            normalized = (
                _normalize_asset_trade_payload(parsed)
                if item_type == "trade"
                else _normalize_asset_cash_ledger_payload(parsed)
            )
            date_field = "trade_date" if item_type == "trade" else "flow_date"
            if _parse_datetime_value(normalized.get(date_field)) is None:
                raise ValueError(f"Unable to parse {date_field} {normalized.get(date_field)!r}")
            reference = next(
                (
                    row.get(key)
                    for key in ("external_id", "transaction_id", "trade_id", "order_id", "reference_id")
                    if row.get(key)
                ),
                None,
            )
            normalized["import_key"] = _build_asset_import_key(item_type, normalized, reference=reference)
            normalized["import_row"] = index
            normalized["import_reference"] = reference
            normalized["import_status"] = "importable"
            items.append(normalized)
        except Exception as exc:  # noqa: BLE001 - collect row-level import issues
            errors.append({"row": index, "message": _csv_import_error_message(exc), "payload": row})
    seen_rows: Dict[str, int] = {}
    for item in items:
        import_key = str(item.get("import_key") or "")
        if import_key in seen_rows:
            item["import_status"] = "duplicate_in_file"
            item["duplicate_of_row"] = seen_rows[import_key]
        else:
            seen_rows[import_key] = int(item["import_row"])
    return items, errors


def _canonical_import_number(value: Any) -> str:
    return format(float(value or 0), ".12g")


def _canonical_import_datetime(value: Any) -> str:
    parsed = _parse_datetime_value(value)
    if parsed is None:
        return ""
    return parsed.isoformat(timespec="microseconds")


def _build_asset_import_key(item_type: str, item: Dict[str, Any], *, reference: str | None = None) -> str:
    if reference:
        identity: Dict[str, Any] = {
            "type": item_type,
            "account_id": int(item.get("account_id") or 0),
            "reference": str(reference).strip(),
        }
    elif item_type == "trade":
        identity = {
            "type": "trade",
            "account_id": int(item.get("account_id") or 0),
            "date": _canonical_import_datetime(item.get("trade_date")),
            "ticker": str(item.get("ticker") or "").strip().upper(),
            "side": str(item.get("side") or "").strip().lower(),
            "quantity": _canonical_import_number(item.get("quantity")),
            "price": _canonical_import_number(item.get("price")),
            "fee": _canonical_import_number(item.get("fee_amount")),
            "tax": _canonical_import_number(item.get("tax_amount")),
            "currency": str(item.get("currency") or "").strip().upper(),
        }
    else:
        identity = {
            "type": "cash",
            "account_id": int(item.get("account_id") or 0),
            "date": _canonical_import_datetime(item.get("flow_date")),
            "flow_type": str(item.get("flow_type") or "").strip().lower(),
            "amount": _canonical_import_number(item.get("amount")),
            "currency": str(item.get("currency") or "").strip().upper(),
            "counterparty": str(item.get("counterparty") or "").strip().lower(),
        }
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mark_database_duplicates(
    items: List[Dict[str, Any]],
    existing_items: List[Dict[str, Any]],
    *,
    item_type: str,
    stored_import_keys: Dict[str, int] | None = None,
) -> None:
    existing_keys: Dict[str, Any] = dict(stored_import_keys or {})
    for existing in existing_items:
        import_key = str(existing.get("import_key") or "") or _build_asset_import_key(item_type, existing)
        existing_keys.setdefault(import_key, existing.get("id"))
    for item in items:
        if item.get("import_status") != "importable":
            continue
        existing_id = existing_keys.get(str(item.get("import_key") or ""))
        if existing_id is not None:
            item["import_status"] = "duplicate_in_database"
            item["existing_id"] = existing_id


def _csv_import_summary(items: List[Dict[str, Any]], errors: List[Dict[str, Any]], **extra: Any) -> Dict[str, Any]:
    file_duplicates = sum(1 for item in items if item.get("import_status") == "duplicate_in_file")
    database_duplicates = sum(1 for item in items if item.get("import_status") == "duplicate_in_database")
    importable_count = sum(1 for item in items if item.get("import_status") == "importable")
    return {
        "input_count": len(items) + len(errors),
        "row_count": len(items),
        "valid_count": len(items),
        "importable_count": importable_count,
        "duplicate_count": file_duplicates + database_duplicates,
        "file_duplicate_count": file_duplicates,
        "database_duplicate_count": database_duplicates,
        "error_count": len(errors),
        **extra,
    }


def _asset_import_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in item.items()
        if key not in {"import_row", "import_reference", "import_status", "duplicate_of_row", "existing_id"}
    }


def _map_journal_entry_to_asset_trades(entry: Dict[str, Any], account_id: int) -> Dict[str, Any]:
    direction = str(entry.get("direction") or "long").strip().lower()
    if direction != "long":
        return {"entry_id": entry.get("id"), "importable": False, "reason": "Only long journal trades can be imported."}

    normalized_ticker = normalize_ticker(entry.get("ticker"))
    market = entry.get("market") or _infer_trade_market(normalized_ticker)
    currency = _resolve_trade_currency_for_market(market)
    base_note = f"Imported from journal #{entry.get('id')}"
    payloads = [
        {
            "account_id": account_id,
            "trade_date": entry.get("entry_time"),
            "ticker": normalized_ticker,
            "display_name": entry.get("ticker"),
            "market": market,
            "asset_type": "stock",
            "currency": currency,
            "side": "buy",
            "quantity": entry.get("size"),
            "price": entry.get("entry_price"),
            "fee_amount": 0,
            "tax_amount": 0,
            "fx_rate_to_base": 1 if currency == "TWD" else 1,
            "source": f"journal:{entry.get('id')}:entry",
            "note": base_note,
        }
    ]
    if entry.get("exit_time") and entry.get("exit_price"):
        payloads.append(
            {
                "account_id": account_id,
                "trade_date": entry.get("exit_time"),
                "ticker": normalized_ticker,
                "display_name": entry.get("ticker"),
                "market": market,
                "asset_type": "stock",
                "currency": currency,
                "side": "sell",
                "quantity": entry.get("size"),
                "price": entry.get("exit_price"),
                "fee_amount": 0,
                "tax_amount": 0,
                "fx_rate_to_base": 1 if currency == "TWD" else 1,
                "source": f"journal:{entry.get('id')}:exit",
                "note": base_note,
            }
        )
    return {"entry_id": entry.get("id"), "importable": True, "payloads": payloads, "entry": entry}


async def _build_journal_import_preview(payload: AssetJournalImportPayload) -> Dict[str, Any]:
    await _ensure_account_exists(payload.account_id)
    journal_entries = await db.list_trade_journal_entries(
        owner_id=DEFAULT_OWNER_ID,
        ticker=normalize_ticker(payload.ticker) if payload.ticker else None,
        market=payload.market,
        strategy_code=payload.strategy_code,
        tag=payload.tag,
        search=payload.search,
        limit=payload.limit,
    )
    asset_trades = await _load_all_asset_rows(db.list_asset_trade_entries)
    existing_sources = {str(item.get("source") or "") for item in asset_trades}

    items = []
    importable_count = 0
    skipped_count = 0
    for entry in journal_entries:
        mapped = _map_journal_entry_to_asset_trades(entry, payload.account_id)
        if not mapped.get("importable"):
            skipped_count += 1
            items.append(
                {
                    "entry_id": entry.get("id"),
                    "ticker": entry.get("ticker"),
                    "entry_time": entry.get("entry_time"),
                    "exit_time": entry.get("exit_time"),
                    "importable": False,
                    "reason": mapped.get("reason"),
                    "payloads": [],
                }
            )
            continue

        payloads = mapped["payloads"]
        missing_payloads = [item for item in payloads if item["source"] not in existing_sources]
        importable = bool(missing_payloads)
        if importable:
            importable_count += 1
        else:
            skipped_count += 1
        items.append(
            {
                "entry_id": entry.get("id"),
                "ticker": entry.get("ticker"),
                "entry_time": entry.get("entry_time"),
                "exit_time": entry.get("exit_time"),
                "importable": importable,
                "reason": None if importable else "Already imported",
                "payloads": missing_payloads,
            }
        )

    return {
        "account_id": payload.account_id,
        "items": items,
        "summary": {
            "entry_count": len(items),
            "importable_count": importable_count,
            "skipped_count": skipped_count,
        },
    }


@router.get("/accounts")
async def list_asset_accounts():
    return {"items": await db.list_asset_accounts(owner_id=DEFAULT_OWNER_ID)}


@router.post("/accounts")
async def create_asset_account(payload: AssetAccountCreatePayload):
    data = payload.model_dump()
    await _validate_account_settlement_config(data)
    try:
        return await db.create_asset_account(data, owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/accounts/{account_id}")
async def get_asset_account(account_id: int):
    account = await db.get_asset_account(account_id, owner_id=DEFAULT_OWNER_ID)
    if not account:
        raise HTTPException(404, "Asset account not found")
    return account


@router.patch("/accounts/{account_id}")
async def update_asset_account(account_id: int, payload: AssetAccountUpdatePayload):
    existing = await db.get_asset_account(account_id, owner_id=DEFAULT_OWNER_ID)
    if not existing:
        raise HTTPException(404, "Asset account not found")
    data = payload.model_dump(exclude_unset=True)
    merged = dict(existing)
    merged.update(data)
    await _validate_account_settlement_config(merged, account_id=account_id)
    try:
        account = await db.update_asset_account(account_id, data, owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not account:
        raise HTTPException(404, "Asset account not found")
    return account


@router.delete("/accounts/{account_id}")
async def delete_asset_account(account_id: int):
    for account in await db.list_asset_accounts(owner_id=DEFAULT_OWNER_ID):
        if int(account.get("settlement_account_id") or 0) != int(account_id):
            continue
        await db.update_asset_account(
            int(account.get("id")),
            {"settlement_account_id": None, "auto_sync_trade_settlement": False},
            owner_id=DEFAULT_OWNER_ID,
        )
    deleted = await db.delete_asset_account(account_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Asset account not found")
    return {"ok": True, "account_id": account_id}


@router.get("/cash-ledger")
async def list_asset_cash_ledger(
    account_id: int | None = Query(None),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    limit: int = Query(200, ge=1, le=5000),
):
    return {
        "items": await db.list_asset_cash_ledger_entries(
            owner_id=DEFAULT_OWNER_ID,
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    }


@router.post("/cash-ledger")
async def create_asset_cash_ledger_entry(payload: AssetCashLedgerCreatePayload):
    await _ensure_account_exists(payload.account_id)
    try:
        return await db.create_asset_cash_ledger_entry(payload.model_dump(), owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/cash-ledger/{entry_id}")
async def get_asset_cash_ledger_entry(entry_id: int):
    entry = await db.get_asset_cash_ledger_entry(entry_id, owner_id=DEFAULT_OWNER_ID)
    if not entry:
        raise HTTPException(404, "Asset cash ledger entry not found")
    return entry


@router.patch("/cash-ledger/{entry_id}")
async def update_asset_cash_ledger_entry(entry_id: int, payload: AssetCashLedgerUpdatePayload):
    data = payload.model_dump(exclude_unset=True)
    if "account_id" in data:
        await _ensure_account_exists(int(data["account_id"]))
    try:
        entry = await db.update_asset_cash_ledger_entry(entry_id, data, owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not entry:
        raise HTTPException(404, "Asset cash ledger entry not found")
    return entry


@router.delete("/cash-ledger/{entry_id}")
async def delete_asset_cash_ledger_entry(entry_id: int):
    deleted = await db.delete_asset_cash_ledger_entry(entry_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Asset cash ledger entry not found")
    return {"ok": True, "entry_id": entry_id}


@router.get("/trades")
async def list_asset_trade_entries(
    account_id: int | None = Query(None),
    ticker: str | None = Query(None),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    limit: int = Query(200, ge=1, le=5000),
):
    normalized_ticker = normalize_ticker(ticker) if ticker else None
    return {
        "items": await db.list_asset_trade_entries(
            owner_id=DEFAULT_OWNER_ID,
            account_id=account_id,
            ticker=normalized_ticker,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    }


@router.post("/trades")
async def create_asset_trade_entry(payload: AssetTradeCreatePayload):
    await _ensure_account_exists(payload.account_id)
    data = payload.model_dump()
    data["ticker"] = normalize_ticker(data["ticker"])
    try:
        return await _create_trade_entry_with_settlement_sync(data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/trades/{entry_id}")
async def get_asset_trade_entry(entry_id: int):
    entry = await db.get_asset_trade_entry(entry_id, owner_id=DEFAULT_OWNER_ID)
    if not entry:
        raise HTTPException(404, "Asset trade entry not found")
    return entry


@router.patch("/trades/{entry_id}")
async def update_asset_trade_entry(entry_id: int, payload: AssetTradeUpdatePayload):
    data = payload.model_dump(exclude_unset=True)
    if "account_id" in data:
        await _ensure_account_exists(int(data["account_id"]))
    if "ticker" in data:
        data["ticker"] = normalize_ticker(data["ticker"])
    try:
        entry = await db.update_asset_trade_entry(entry_id, data, owner_id=DEFAULT_OWNER_ID)
        if entry:
            await _sync_trade_linked_cash_entries(entry)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not entry:
        raise HTTPException(404, "Asset trade entry not found")
    return entry


@router.delete("/trades/{entry_id}")
async def delete_asset_trade_entry(entry_id: int):
    existing = await db.get_asset_trade_entry(entry_id, owner_id=DEFAULT_OWNER_ID)
    if not existing:
        raise HTTPException(404, "Asset trade entry not found")
    await _delete_trade_linked_cash_entries(entry_id)
    deleted = await db.delete_asset_trade_entry(entry_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Asset trade entry not found")
    return {"ok": True, "entry_id": entry_id}


@router.get("/adjustments")
async def list_asset_position_adjustments(
    account_id: int | None = Query(None),
    ticker: str | None = Query(None),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    limit: int = Query(200, ge=1, le=5000),
):
    return {
        "items": await db.list_asset_position_adjustments(
            owner_id=DEFAULT_OWNER_ID,
            account_id=account_id,
            ticker=normalize_ticker(ticker) if ticker else None,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    }


@router.post("/adjustments")
async def create_asset_position_adjustment(payload: AssetPositionAdjustmentCreatePayload):
    await _ensure_account_exists(payload.account_id)
    data = payload.model_dump()
    data["ticker"] = normalize_ticker(data["ticker"])
    if data.get("target_ticker"):
        data["target_ticker"] = normalize_ticker(data["target_ticker"])
    try:
        return await db.create_asset_position_adjustment(data, owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/adjustments/{adjustment_id}")
async def update_asset_position_adjustment(adjustment_id: int, payload: AssetPositionAdjustmentUpdatePayload):
    data = payload.model_dump(exclude_unset=True)
    if "account_id" in data:
        await _ensure_account_exists(int(data["account_id"]))
    if "ticker" in data:
        data["ticker"] = normalize_ticker(data["ticker"])
    if "target_ticker" in data and data["target_ticker"]:
        data["target_ticker"] = normalize_ticker(data["target_ticker"])
    try:
        adjustment = await db.update_asset_position_adjustment(adjustment_id, data, owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not adjustment:
        raise HTTPException(404, "Asset position adjustment not found")
    return adjustment


@router.delete("/adjustments/{adjustment_id}")
async def delete_asset_position_adjustment(adjustment_id: int):
    deleted = await db.delete_asset_position_adjustment(adjustment_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Asset position adjustment not found")
    return {"ok": True, "adjustment_id": adjustment_id}


@router.get("/price-overrides")
async def list_asset_price_overrides(
    account_id: int | None = Query(None),
    ticker: str | None = Query(None),
    limit: int = Query(200, ge=1, le=5000),
):
    return {
        "items": await db.list_asset_price_overrides(
            owner_id=DEFAULT_OWNER_ID,
            account_id=account_id,
            ticker=normalize_ticker(ticker) if ticker else None,
            limit=limit,
        )
    }


@router.post("/price-overrides")
async def create_asset_price_override(payload: AssetPriceOverrideCreatePayload):
    if payload.account_id is not None:
        await _ensure_account_exists(payload.account_id)
    data = payload.model_dump()
    data["ticker"] = normalize_ticker(data["ticker"])
    try:
        return await db.create_asset_price_override(data, owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/price-overrides/{override_id}")
async def update_asset_price_override(override_id: int, payload: AssetPriceOverrideUpdatePayload):
    data = payload.model_dump(exclude_unset=True)
    if "account_id" in data and data["account_id"] is not None:
        await _ensure_account_exists(int(data["account_id"]))
    if "ticker" in data:
        data["ticker"] = normalize_ticker(data["ticker"])
    try:
        override = await db.update_asset_price_override(override_id, data, owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not override:
        raise HTTPException(404, "Asset price override not found")
    return override


@router.delete("/price-overrides/{override_id}")
async def delete_asset_price_override(override_id: int):
    deleted = await db.delete_asset_price_override(override_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Asset price override not found")
    return {"ok": True, "override_id": override_id}


@router.get("/fx-rates")
async def list_asset_fx_rates(
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    from_currency: str | None = Query(None),
    to_currency: str | None = Query(None),
    limit: int = Query(365, ge=1, le=5000),
    refresh_public: bool = Query(False),
):
    if refresh_public:
        await _sync_latest_public_fx_rates()
    return {
        "items": await db.list_asset_fx_rates(
            owner_id=DEFAULT_OWNER_ID,
            date_from=date_from,
            date_to=date_to,
            from_currency=from_currency,
            to_currency=to_currency,
            limit=limit,
        )
    }


@router.post("/fx-rates")
async def create_asset_fx_rate(payload: AssetFxRateCreatePayload):
    try:
        return await db.create_asset_fx_rate(payload.model_dump(), owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/fx-rates/{fx_rate_id}")
async def update_asset_fx_rate(fx_rate_id: int, payload: AssetFxRateUpdatePayload):
    try:
        item = await db.update_asset_fx_rate(fx_rate_id, payload.model_dump(exclude_unset=True), owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not item:
        raise HTTPException(404, "Asset FX rate not found")
    return item


@router.delete("/fx-rates/{fx_rate_id}")
async def delete_asset_fx_rate(fx_rate_id: int):
    deleted = await db.delete_asset_fx_rate(fx_rate_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Asset FX rate not found")
    return {"ok": True, "fx_rate_id": fx_rate_id}


@router.get("/reconciliation")
async def list_asset_reconciliation_snapshots(
    account_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=5000),
):
    return {
        "items": await db.list_asset_reconciliation_snapshots(
            owner_id=DEFAULT_OWNER_ID,
            account_id=account_id,
            limit=limit,
        )
    }


@router.post("/reconciliation")
async def create_asset_reconciliation_snapshot(payload: AssetReconciliationCreatePayload, refresh: bool = Query(True)):
    await _ensure_account_exists(payload.account_id)
    snapshot = await _build_snapshot(refresh=refresh)
    account_summary = next(
        (item for item in snapshot.get("accounts") or [] if int(item.get("account_id") or 0) == int(payload.account_id)),
        None,
    )
    if not account_summary:
        raise HTTPException(400, f"Unable to build system snapshot for asset account {payload.account_id}")

    data = payload.model_dump()
    if not data.get("positions_payload"):
        data["positions_payload"] = _build_reconciliation_positions_payload(snapshot, payload.account_id)
    data["cash_system"] = account_summary.get("cash_total_base")
    data["market_value_system"] = account_summary.get("market_value_base")
    try:
        return await db.create_asset_reconciliation_snapshot(data, owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/reconciliation/{snapshot_id}")
async def get_asset_reconciliation_snapshot(snapshot_id: int):
    snapshot = await db.get_asset_reconciliation_snapshot(snapshot_id, owner_id=DEFAULT_OWNER_ID)
    if not snapshot:
        raise HTTPException(404, "Asset reconciliation snapshot not found")
    return snapshot


@router.delete("/reconciliation/{snapshot_id}")
async def delete_asset_reconciliation_snapshot(snapshot_id: int):
    deleted = await db.delete_asset_reconciliation_snapshot(snapshot_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Asset reconciliation snapshot not found")
    return {"ok": True, "snapshot_id": snapshot_id}


@router.post("/import/trades-csv")
async def import_asset_trades_csv(payload: AssetCsvImportPayload):
    accounts, existing_trades = await asyncio.gather(
        db.list_asset_accounts(owner_id=DEFAULT_OWNER_ID),
        _load_all_asset_rows(db.list_asset_trade_entries),
    )
    try:
        items, errors = _run_csv_import(
            payload.csv_text,
            default_account_id=payload.default_account_id,
            accounts=accounts,
            parser=_parse_trade_csv_payload,
            item_type="trade",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    stored_import_keys = await db.find_asset_trade_import_keys(
        [str(item.get("import_key") or "") for item in items],
        owner_id=DEFAULT_OWNER_ID,
    )
    _mark_database_duplicates(
        items,
        existing_trades,
        item_type="trade",
        stored_import_keys=stored_import_keys,
    )
    duplicates = [item for item in items if item.get("import_status") != "importable"]
    if payload.dry_run:
        return {
            "dry_run": True,
            "summary": _csv_import_summary(items, errors),
            "items": items,
            "duplicates": duplicates,
            "errors": errors,
        }

    created = []
    row_errors = list(errors)
    for item in items:
        if item.get("import_status") != "importable":
            continue
        try:
            created.append(await _create_trade_entry_with_settlement_sync(_asset_import_payload(item)))
        except Exception as exc:  # noqa: BLE001
            row_errors.append({"row": item.get("import_row"), "message": str(exc), "payload": item})
    return {
        "dry_run": False,
        "summary": _csv_import_summary(
            items,
            errors,
            created_count=len(created),
            skipped_count=len(duplicates),
            error_count=len(row_errors),
        ),
        "items": created,
        "duplicates": duplicates,
        "errors": row_errors,
    }


@router.post("/import/cash-csv")
async def import_asset_cash_csv(payload: AssetCsvImportPayload):
    accounts, existing_cash = await asyncio.gather(
        db.list_asset_accounts(owner_id=DEFAULT_OWNER_ID),
        _load_all_asset_rows(db.list_asset_cash_ledger_entries),
    )
    try:
        items, errors = _run_csv_import(
            payload.csv_text,
            default_account_id=payload.default_account_id,
            accounts=accounts,
            parser=_parse_cash_csv_payload,
            item_type="cash",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    stored_import_keys = await db.find_asset_cash_import_keys(
        [str(item.get("import_key") or "") for item in items],
        owner_id=DEFAULT_OWNER_ID,
    )
    _mark_database_duplicates(
        items,
        existing_cash,
        item_type="cash",
        stored_import_keys=stored_import_keys,
    )
    duplicates = [item for item in items if item.get("import_status") != "importable"]
    if payload.dry_run:
        return {
            "dry_run": True,
            "summary": _csv_import_summary(items, errors),
            "items": items,
            "duplicates": duplicates,
            "errors": errors,
        }

    created = []
    row_errors = list(errors)
    for item in items:
        if item.get("import_status") != "importable":
            continue
        try:
            created.append(await db.create_asset_cash_ledger_entry(_asset_import_payload(item), owner_id=DEFAULT_OWNER_ID))
        except Exception as exc:  # noqa: BLE001
            row_errors.append({"row": item.get("import_row"), "message": str(exc), "payload": item})
    return {
        "dry_run": False,
        "summary": _csv_import_summary(
            items,
            errors,
            created_count=len(created),
            skipped_count=len(duplicates),
            error_count=len(row_errors),
        ),
        "items": created,
        "duplicates": duplicates,
        "errors": row_errors,
    }


@router.post("/journal-import/preview")
async def preview_asset_journal_import(payload: AssetJournalImportPayload):
    return await _build_journal_import_preview(payload)


@router.post("/journal-import")
async def import_asset_journal_entries(payload: AssetJournalImportPayload):
    preview = await _build_journal_import_preview(payload)
    created = []
    errors = []
    for item in preview.get("items") or []:
        if not item.get("importable"):
            continue
        for trade_payload in item.get("payloads") or []:
            try:
                created.append(await _create_trade_entry_with_settlement_sync(trade_payload))
            except Exception as exc:  # noqa: BLE001
                errors.append({"entry_id": item.get("entry_id"), "source": trade_payload.get("source"), "message": str(exc)})
    return {
        "summary": {
            "entry_count": preview.get("summary", {}).get("entry_count", 0),
            "created_count": len(created),
            "error_count": len(errors),
        },
        "items": created,
        "errors": errors,
    }


@router.post("/recompute")
async def recompute_asset_tracking(payload: AssetRecomputePayload):
    snapshot = await _build_snapshot(refresh=payload.refresh)
    performance = await _build_performance(payload.performance_range, refresh=payload.refresh)
    alerts = build_asset_alerts(snapshot, performance)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_summary": snapshot.get("summary") or {},
        "performance_summary": performance.get("summary") or {},
        "alerts": alerts,
    }


@router.get("/alerts/current")
async def get_asset_alerts_current(
    refresh: bool = Query(True),
    performance_range: str = Query("1y"),
):
    snapshot = await _build_snapshot(refresh=refresh)
    performance = await _build_performance(performance_range, refresh=refresh)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_currency": snapshot.get("base_currency"),
        "items": build_asset_alerts(snapshot, performance),
    }


@router.get("/performance")
async def get_asset_performance(
    range_name: str = Query("1y", alias="range"),
    refresh: bool = Query(True),
):
    return await _build_performance(range_name, refresh=refresh)


@router.get("/portfolio/current")
async def get_asset_portfolio_snapshot(refresh: bool = Query(True), allocation_group_by: str = Query("account")):
    snapshot = await _build_snapshot(refresh=refresh)
    snapshot["allocation"] = _build_allocation(snapshot, allocation_group_by)
    return snapshot


@router.get("/holdings/current")
async def get_asset_holdings_current(refresh: bool = Query(True)):
    snapshot = await _build_snapshot(refresh=refresh)
    return {
        "generated_at": snapshot.get("generated_at"),
        "base_currency": snapshot.get("base_currency"),
        "warnings": snapshot.get("warnings") or [],
        "quote_gaps": snapshot.get("quote_gaps") or [],
        "items": snapshot.get("holdings") or [],
    }


@router.get("/summary/current")
async def get_asset_summary_current(refresh: bool = Query(True)):
    snapshot = await _build_snapshot(refresh=refresh)
    return {
        "generated_at": snapshot.get("generated_at"),
        "base_currency": snapshot.get("base_currency"),
        "warnings": snapshot.get("warnings") or [],
        "quote_gaps": snapshot.get("quote_gaps") or [],
        "accounts": snapshot.get("accounts") or [],
        "reconciliation": snapshot.get("reconciliation") or {"items": [], "summary": {}},
        "summary": snapshot.get("summary") or {},
    }


@router.get("/allocation/current")
async def get_asset_allocation_current(refresh: bool = Query(True), group_by: str = Query("account")):
    snapshot = await _build_snapshot(refresh=refresh)
    return {
        "generated_at": snapshot.get("generated_at"),
        "base_currency": snapshot.get("base_currency"),
        "allocation": _build_allocation(snapshot, group_by),
    }


@router.get("/contributors/current")
async def get_asset_contributors_current(refresh: bool = Query(True), limit: int = Query(10, ge=1, le=50)):
    snapshot = await _build_snapshot(refresh=refresh)
    return {
        "generated_at": snapshot.get("generated_at"),
        "base_currency": snapshot.get("base_currency"),
        **_build_contributors(snapshot, limit),
    }
