"""Asset tracking routes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from asset_tracking_service import build_asset_portfolio_snapshot
from data_fetcher import normalize_ticker
from database import DEFAULT_OWNER_ID, db
from schemas import (
    AssetAccountCreatePayload,
    AssetAccountUpdatePayload,
    AssetCashLedgerCreatePayload,
    AssetCashLedgerUpdatePayload,
    AssetTradeCreatePayload,
    AssetTradeUpdatePayload,
)

router = APIRouter(prefix="/api/assets", tags=["assets"])

_fetch_and_store_quote_snapshot = None
_SNAPSHOT_LIMIT = 5000


def configure(*, fetch_and_store_quote_snapshot) -> None:
    global _fetch_and_store_quote_snapshot
    _fetch_and_store_quote_snapshot = fetch_and_store_quote_snapshot


async def _ensure_account_exists(account_id: int) -> Dict[str, Any]:
    account = await db.get_asset_account(account_id, owner_id=DEFAULT_OWNER_ID)
    if not account:
        raise HTTPException(400, f"Asset account {account_id} does not exist")
    return account


async def _load_asset_inputs() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    accounts = await db.list_asset_accounts(owner_id=DEFAULT_OWNER_ID)
    cash_entries = await db.list_asset_cash_ledger_entries(
        owner_id=DEFAULT_OWNER_ID,
        limit=_SNAPSHOT_LIMIT,
    )
    trade_entries = await db.list_asset_trade_entries(
        owner_id=DEFAULT_OWNER_ID,
        limit=_SNAPSHOT_LIMIT,
    )
    return accounts, cash_entries, trade_entries


async def _fetch_latest_quote(ticker: str, *, refresh: bool = True) -> Dict[str, Any] | None:
    normalized = normalize_ticker(ticker)
    quote = None
    if refresh and _fetch_and_store_quote_snapshot:
        quote = await _fetch_and_store_quote_snapshot(normalized)
    if not quote:
        quote = await db.get_market_quote(normalized)
    return quote


async def _persist_snapshot(snapshot: Dict[str, Any]) -> None:
    await db.replace_asset_positions_current(
        DEFAULT_OWNER_ID,
        snapshot.get("holdings") or [],
    )
    await db.replace_asset_valuations_current(
        DEFAULT_OWNER_ID,
        snapshot.get("holdings") or [],
    )


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
    return {
        "group_by": "market",
        "items": items,
    }


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
    return {
        "top_gainers": top_gainers,
        "top_losers": top_losers,
    }


async def _build_snapshot(*, refresh: bool = True) -> Dict[str, Any]:
    accounts, cash_entries, trade_entries = await _load_asset_inputs()
    snapshot = await build_asset_portfolio_snapshot(
        accounts,
        cash_entries,
        trade_entries,
        fetch_quote=(lambda ticker: _fetch_latest_quote(ticker, refresh=refresh)),
    )
    await _persist_snapshot(snapshot)
    return snapshot


@router.get("/accounts")
async def list_asset_accounts():
    return {"items": await db.list_asset_accounts(owner_id=DEFAULT_OWNER_ID)}


@router.post("/accounts")
async def create_asset_account(payload: AssetAccountCreatePayload):
    try:
        return await db.create_asset_account(payload.model_dump(), owner_id=DEFAULT_OWNER_ID)
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
    try:
        account = await db.update_asset_account(
            account_id,
            payload.model_dump(exclude_unset=True),
            owner_id=DEFAULT_OWNER_ID,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not account:
        raise HTTPException(404, "Asset account not found")
    return account


@router.delete("/accounts/{account_id}")
async def delete_asset_account(account_id: int):
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
        entry = await db.update_asset_cash_ledger_entry(
            entry_id,
            data,
            owner_id=DEFAULT_OWNER_ID,
        )
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
        return await db.create_asset_trade_entry(data, owner_id=DEFAULT_OWNER_ID)
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
        entry = await db.update_asset_trade_entry(
            entry_id,
            data,
            owner_id=DEFAULT_OWNER_ID,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not entry:
        raise HTTPException(404, "Asset trade entry not found")
    return entry


@router.delete("/trades/{entry_id}")
async def delete_asset_trade_entry(entry_id: int):
    deleted = await db.delete_asset_trade_entry(entry_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Asset trade entry not found")
    return {"ok": True, "entry_id": entry_id}


@router.get("/portfolio/current")
async def get_asset_portfolio_snapshot(
    refresh: bool = Query(True),
    allocation_group_by: str = Query("account"),
):
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
        "summary": snapshot.get("summary") or {},
    }


@router.get("/allocation/current")
async def get_asset_allocation_current(
    refresh: bool = Query(True),
    group_by: str = Query("account"),
):
    snapshot = await _build_snapshot(refresh=refresh)
    return {
        "generated_at": snapshot.get("generated_at"),
        "base_currency": snapshot.get("base_currency"),
        "allocation": _build_allocation(snapshot, group_by),
    }


@router.get("/contributors/current")
async def get_asset_contributors_current(
    refresh: bool = Query(True),
    limit: int = Query(10, ge=1, le=50),
):
    snapshot = await _build_snapshot(refresh=refresh)
    return {
        "generated_at": snapshot.get("generated_at"),
        "base_currency": snapshot.get("base_currency"),
        **_build_contributors(snapshot, limit),
    }
