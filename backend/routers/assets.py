"""Asset tracking routes."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from asset_tracking_service import build_asset_alerts
from asset_use_cases.account_ledger_commands import (
    AssetAccountLedgerCommands,
    build_trade_settlement_note as _build_trade_settlement_note,
    build_trade_settlement_payloads as _build_trade_settlement_payloads,
)
from asset_use_cases import csv_imports as asset_csv_imports
from asset_use_cases.market_hydration import (
    is_public_auto_fx_source as _is_public_auto_fx_source,
    load_all_asset_rows,
    provider_wait_budget,
    read_fresh_quote_cache,
)
from asset_use_cases.reconciliation import (
    build_reconciliation_positions_payload,
)
from asset_use_cases.valuation_queries import (
    AssetValuationQueries,
    InvalidAllocationGroup,
    build_allocation as query_allocation,
    build_contributors as query_contributors,
    resolve_performance_start,
)
from data_fetcher import normalize_ticker
from database import DEFAULT_OWNER_ID, db
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
log = logging.getLogger(__name__)

_fetch_and_store_quote_snapshot = None
_latest_public_fx_provider = None
_quote_refresh_timeout_seconds = 8.0
_quote_refresh_tasks: Dict[str, asyncio.Task] = {}
_quote_refresh_max_concurrency = 6
_quote_refresh_semaphore = asyncio.Semaphore(_quote_refresh_max_concurrency)
_quote_cache_ttl_seconds = 15.0
_quote_cache: Dict[str, tuple[float, int, Dict[str, Any]]] = {}
_fx_refresh_task: asyncio.Task | None = None
_SNAPSHOT_LIMIT = 5000
_LEDGER_PAGE_SIZE = 1000


def configure(
    *,
    fetch_and_store_quote_snapshot,
    latest_public_fx_provider=None,
    quote_refresh_timeout_seconds=8.0,
    quote_refresh_max_concurrency=6,
    quote_cache_ttl_seconds=15.0,
) -> None:
    global _fetch_and_store_quote_snapshot, _latest_public_fx_provider, _quote_refresh_timeout_seconds
    global _quote_refresh_max_concurrency, _quote_refresh_semaphore, _quote_cache_ttl_seconds
    _fetch_and_store_quote_snapshot = fetch_and_store_quote_snapshot
    _latest_public_fx_provider = latest_public_fx_provider
    _quote_refresh_timeout_seconds = max(0.1, float(quote_refresh_timeout_seconds))
    _quote_refresh_max_concurrency = max(1, int(quote_refresh_max_concurrency))
    _quote_refresh_semaphore = asyncio.Semaphore(_quote_refresh_max_concurrency)
    _quote_cache_ttl_seconds = max(0.0, float(quote_cache_ttl_seconds))
    _quote_cache.clear()


async def shutdown() -> None:
    """Cancel outstanding provider refreshes during application shutdown."""
    global _fx_refresh_task
    pending = [task for task in _quote_refresh_tasks.values() if not task.done()]
    if _fx_refresh_task is not None and not _fx_refresh_task.done():
        pending.append(_fx_refresh_task)
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    _quote_refresh_tasks.clear()
    _fx_refresh_task = None
    _quote_cache.clear()


def performance_status() -> Dict[str, Any]:
    return {
        "max_concurrency": _quote_refresh_max_concurrency,
        "in_flight": sum(1 for task in _quote_refresh_tasks.values() if not task.done()),
        "cache_entries": len(_quote_cache),
        "cache_ttl_seconds": _quote_cache_ttl_seconds,
        "provider_timeout_seconds": _quote_refresh_timeout_seconds,
    }


async def _run_quote_refresh(normalized: str) -> Dict[str, Any] | None:
    async with _quote_refresh_semaphore:
        quote = await _fetch_and_store_quote_snapshot(normalized)
    if quote:
        _quote_cache[normalized] = (
            time.monotonic() + _quote_cache_ttl_seconds,
            id(_fetch_and_store_quote_snapshot),
            quote,
        )
    return quote


def _account_ledger_commands() -> AssetAccountLedgerCommands:
    return AssetAccountLedgerCommands(db, owner_id=DEFAULT_OWNER_ID)


async def _ensure_account_exists(account_id: int | None) -> Dict[str, Any] | None:
    try:
        return await _account_ledger_commands().ensure_account_exists(account_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


async def _validate_account_settlement_config(
    payload: Dict[str, Any],
    *,
    account_id: int | None = None,
) -> None:
    try:
        await _account_ledger_commands().validate_account_settlement_config(
            payload,
            account_id=account_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


async def _delete_trade_linked_cash_entries(trade_id: int) -> None:
    await _account_ledger_commands().delete_trade_linked_cash_entries(trade_id)


async def _sync_trade_linked_cash_entries(trade_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        return await _account_ledger_commands().sync_trade_linked_cash_entries(trade_entry)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


async def _create_trade_entry_with_settlement_sync(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return await _account_ledger_commands().create_trade_entry_with_settlement_sync(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


async def _load_all_asset_rows(fetcher, **kwargs) -> List[Dict[str, Any]]:
    return await load_all_asset_rows(
        fetcher,
        owner_id=DEFAULT_OWNER_ID,
        page_size=_LEDGER_PAGE_SIZE,
        **kwargs,
    )


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


async def _load_asset_fx_rates(*, refresh: bool = False) -> List[Dict[str, Any]]:
    """Return persisted FX rates promptly while deduplicating a public refresh.

    Public providers can be slow or temporarily unreachable. Asset valuation must
    remain usable in that case, so requests with existing rates use a short wait
    budget and let one shared refresh finish in the background.
    """
    global _fx_refresh_task

    stored_rates = await _load_all_asset_rows(db.list_asset_fx_rates)
    if not refresh or _latest_public_fx_provider is None:
        return stored_rates

    task = _fx_refresh_task
    if task is None or task.done():
        task = asyncio.create_task(
            _sync_latest_public_fx_rates(),
            name="asset-public-fx-refresh",
        )
        _fx_refresh_task = task

        def cleanup(done_task: asyncio.Task) -> None:
            global _fx_refresh_task
            if _fx_refresh_task is done_task:
                _fx_refresh_task = None
            if not done_task.cancelled():
                done_task.exception()

        task.add_done_callback(cleanup)

    wait_budget = provider_wait_budget(
        has_persisted_value=bool(stored_rates),
        timeout_seconds=_quote_refresh_timeout_seconds,
    )
    try:
        refreshed_rates = await asyncio.wait_for(asyncio.shield(task), timeout=wait_budget)
        return refreshed_rates or stored_rates
    except TimeoutError:
        log.warning(
            "Public FX refresh is still running after %.1fs; using persisted rates",
            wait_budget,
        )
        return stored_rates
    except Exception as exc:  # noqa: BLE001 - asset valuation should retain persisted FX data
        log.warning("Public FX refresh failed; using persisted rates: %s", exc)
        return stored_rates


async def _load_asset_inputs(*, refresh_public_fx: bool = False) -> tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    fx_loader = _load_asset_fx_rates(refresh=refresh_public_fx)
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
    cached_quote = read_fresh_quote_cache(
        _quote_cache,
        normalized,
        provider_identity=id(_fetch_and_store_quote_snapshot),
    )
    if refresh and cached_quote:
        return cached_quote
    stored_quote = await db.get_market_quote(normalized)
    if not refresh or not _fetch_and_store_quote_snapshot:
        return stored_quote

    task = _quote_refresh_tasks.get(normalized)
    if task is None or task.done():
        task = asyncio.create_task(
            _run_quote_refresh(normalized),
            name=f"asset-quote-refresh:{normalized}",
        )
        _quote_refresh_tasks[normalized] = task

        def cleanup(done_task: asyncio.Task, *, symbol: str = normalized) -> None:
            if _quote_refresh_tasks.get(symbol) is done_task:
                _quote_refresh_tasks.pop(symbol, None)
            if not done_task.cancelled():
                done_task.exception()

        task.add_done_callback(cleanup)

    # When a stored quote exists, keep the request responsive and let a slow
    # provider finish in the background. A later read receives the refreshed row.
    wait_budget = provider_wait_budget(
        has_persisted_value=bool(stored_quote),
        timeout_seconds=_quote_refresh_timeout_seconds,
    )
    try:
        quote = await asyncio.wait_for(asyncio.shield(task), timeout=wait_budget)
        return quote or stored_quote
    except TimeoutError:
        log.warning(
            "Asset quote refresh is still running for %s after %.1fs; using the latest stored quote",
            normalized,
            wait_budget,
        )
        return stored_quote
    except Exception as exc:  # noqa: BLE001 - asset valuation should fall back to persisted data
        log.warning("Asset quote refresh failed for %s; using the latest stored quote: %s", normalized, exc)
        return stored_quote


async def _persist_snapshot(snapshot: Dict[str, Any]) -> None:
    await db.replace_asset_positions_current(DEFAULT_OWNER_ID, snapshot.get("holdings") or [])
    await db.replace_asset_valuations_current(DEFAULT_OWNER_ID, snapshot.get("holdings") or [])


def _build_reconciliation_positions_payload(snapshot: Dict[str, Any], account_id: int) -> List[Dict[str, Any]]:
    return build_reconciliation_positions_payload(snapshot, account_id)


def _build_allocation(snapshot: Dict[str, Any], group_by: str) -> Dict[str, Any]:
    try:
        return query_allocation(snapshot, group_by)
    except InvalidAllocationGroup as exc:
        raise HTTPException(400, str(exc)) from exc


def _build_contributors(snapshot: Dict[str, Any], limit: int) -> Dict[str, Any]:
    return query_contributors(snapshot, limit)


def _valuation_queries() -> AssetValuationQueries:
    return AssetValuationQueries(
        load_inputs=_load_asset_inputs,
        fetch_quote=_fetch_latest_quote,
        persist_snapshot=_persist_snapshot,
        get_price_history=lambda ticker, start_date, end_date: db.get_ohlcv_range(
            ticker,
            start_date,
            end_date,
            "1d",
        ),
    )


async def _build_snapshot(*, refresh: bool = True) -> Dict[str, Any]:
    return await _valuation_queries().build_snapshot(refresh=refresh)


def _resolve_performance_start(range_name: str) -> str:
    return resolve_performance_start(range_name)


async def _build_performance(range_name: str, *, refresh: bool = True) -> Dict[str, Any]:
    return await _valuation_queries().build_performance(range_name, refresh=refresh)


def _normalize_csv_text(value: str) -> str:
    return asset_csv_imports.normalize_csv_text(value)


def _normalize_csv_row(row: Dict[str, Any]) -> Dict[str, str]:
    return asset_csv_imports.normalize_csv_row(row)


def _csv_import_error_message(exc: Exception) -> str:
    return asset_csv_imports.csv_import_error_message(exc)


def _build_account_lookups(accounts: List[Dict[str, Any]]) -> tuple[Dict[int, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    return asset_csv_imports.build_account_lookups(accounts)


def _resolve_account_id_from_csv(
    row: Dict[str, str],
    *,
    default_account_id: int | None,
    accounts_by_id: Dict[int, Dict[str, Any]],
    accounts_by_name: Dict[str, Dict[str, Any]],
) -> int:
    return asset_csv_imports.resolve_account_id_from_csv(
        row,
        default_account_id=default_account_id,
        accounts_by_id=accounts_by_id,
        accounts_by_name=accounts_by_name,
    )


def _resolve_trade_currency_for_market(market: str) -> str:
    return asset_csv_imports.resolve_trade_currency_for_market(market)


def _infer_trade_market(raw_ticker: str) -> str:
    return asset_csv_imports.infer_trade_market(raw_ticker)


def _parse_trade_csv_payload(
    row: Dict[str, str],
    *,
    default_account_id: int | None,
    accounts_by_id: Dict[int, Dict[str, Any]],
    accounts_by_name: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    return asset_csv_imports.parse_trade_csv_payload(
        row,
        default_account_id=default_account_id,
        accounts_by_id=accounts_by_id,
        accounts_by_name=accounts_by_name,
    )


def _parse_cash_csv_payload(
    row: Dict[str, str],
    *,
    default_account_id: int | None,
    accounts_by_id: Dict[int, Dict[str, Any]],
    accounts_by_name: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    return asset_csv_imports.parse_cash_csv_payload(
        row,
        default_account_id=default_account_id,
        accounts_by_id=accounts_by_id,
        accounts_by_name=accounts_by_name,
    )


def _run_csv_import(
    csv_text: str,
    *,
    default_account_id: int | None,
    accounts: List[Dict[str, Any]],
    parser,
    item_type: str,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    return asset_csv_imports.run_csv_import(
        csv_text,
        default_account_id=default_account_id,
        accounts=accounts,
        parser=parser,
        item_type=item_type,
    )


def _canonical_import_number(value: Any) -> str:
    return asset_csv_imports.canonical_import_number(value)


def _canonical_import_datetime(value: Any) -> str:
    return asset_csv_imports.canonical_import_datetime(value)


def _build_asset_import_key(item_type: str, item: Dict[str, Any], *, reference: str | None = None) -> str:
    return asset_csv_imports.build_asset_import_key(item_type, item, reference=reference)


def _mark_database_duplicates(
    items: List[Dict[str, Any]],
    existing_items: List[Dict[str, Any]],
    *,
    item_type: str,
    stored_import_keys: Dict[str, int] | None = None,
) -> None:
    asset_csv_imports.mark_database_duplicates(
        items,
        existing_items,
        item_type=item_type,
        stored_import_keys=stored_import_keys,
    )


def _csv_import_summary(items: List[Dict[str, Any]], errors: List[Dict[str, Any]], **extra: Any) -> Dict[str, Any]:
    return asset_csv_imports.csv_import_summary(items, errors, **extra)


def _asset_import_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    return asset_csv_imports.asset_import_payload(item)


async def _run_atomic_asset_import(
    *,
    import_type: str,
    source_name: str | None,
    items: List[Dict[str, Any]],
    duplicates: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
    create_item,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    return await asset_csv_imports.run_atomic_asset_import(
        repository=db,
        owner_id=DEFAULT_OWNER_ID,
        import_type=import_type,
        source_name=source_name,
        items=items,
        duplicates=duplicates,
        errors=errors,
        create_item=create_item,
    )


def _map_journal_entry_to_asset_trades(entry: Dict[str, Any], account_id: int) -> Dict[str, Any]:
    return asset_csv_imports.map_journal_entry_to_asset_trades(entry, account_id)


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
        await _load_asset_fx_rates(refresh=True)
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


@router.get("/import-batches")
async def list_asset_import_batches(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    items = await db.list_asset_import_batches(
        owner_id=DEFAULT_OWNER_ID,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "count": len(items), "limit": limit, "offset": offset}


@router.post("/import-batches/{batch_id}/rollback")
async def rollback_asset_import_batch(batch_id: int):
    batch = await db.get_asset_import_batch(batch_id, owner_id=DEFAULT_OWNER_ID)
    if not batch:
        raise HTTPException(404, "Asset import batch not found")
    if batch.get("status") == "rolled_back":
        return {"ok": True, "batch": batch, "deleted": {"trade_count": 0, "cash_count": 0}}
    if batch.get("status") != "committed":
        raise HTTPException(409, "Only committed asset import batches can be rolled back")

    async with db.transaction():
        deleted = await db.delete_asset_import_batch_entries(batch_id, owner_id=DEFAULT_OWNER_ID)
        batch = await db.finalize_asset_import_batch(
            batch_id,
            {**batch, "status": "rolled_back"},
            owner_id=DEFAULT_OWNER_ID,
        )
    return {"ok": True, "batch": batch, "deleted": deleted}


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

    async def create_trade(item_payload):
        return await _create_trade_entry_with_settlement_sync(item_payload)

    created, row_errors, batch = await _run_atomic_asset_import(
        import_type="trade_csv",
        source_name=payload.source_name,
        items=items,
        duplicates=duplicates,
        errors=errors,
        create_item=create_trade,
    )
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
        "batch": batch,
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

    async def create_cash(item_payload):
        return await db.create_asset_cash_ledger_entry(item_payload, owner_id=DEFAULT_OWNER_ID)

    created, row_errors, batch = await _run_atomic_asset_import(
        import_type="cash_csv",
        source_name=payload.source_name,
        items=items,
        duplicates=duplicates,
        errors=errors,
        create_item=create_cash,
    )
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
        "batch": batch,
    }


@router.post("/journal-import/preview")
async def preview_asset_journal_import(payload: AssetJournalImportPayload):
    return await _build_journal_import_preview(payload)


@router.post("/journal-import")
async def import_asset_journal_entries(payload: AssetJournalImportPayload):
    preview = await _build_journal_import_preview(payload)
    preview_items = preview.get("items") or []
    trade_items: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    for item in preview_items:
        if not item.get("importable"):
            duplicates.append(item)
            continue
        for trade_payload in item.get("payloads") or []:
            trade_items.append({**trade_payload, "import_status": "importable", "import_row": item.get("entry_id")})

    async def create_trade(item_payload):
        return await _create_trade_entry_with_settlement_sync(item_payload)

    created, errors, batch = await _run_atomic_asset_import(
        import_type="journal",
        source_name=payload.source_name or "trade_journal",
        items=trade_items,
        duplicates=duplicates,
        errors=[],
        create_item=create_trade,
    )
    return {
        "summary": {
            "entry_count": preview.get("summary", {}).get("entry_count", 0),
            "created_count": len(created),
            "error_count": len(errors),
        },
        "items": created,
        "errors": errors,
        "batch": batch,
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
