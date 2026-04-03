"""Watchlist & workspace routes."""

import logging

from fastapi import APIRouter, HTTPException

from data_fetcher import normalize_ticker
from database import DEFAULT_OWNER_ID, db
from display_name_resolver import resolve_display_name
from providers import fetcher
from schemas import (
    WatchlistGroupCreate,
    WatchlistGroupUpdate,
    WatchlistItemCreate,
    WatchlistItemsOrderUpdate,
    WorkspacePresetCreate,
    WorkspacePresetUpdate,
)

log = logging.getLogger(__name__)

CATEGORY_OVERRIDES = {
    "^TWII": "台灣指數", "^TWOII": "台灣指數",
    "^GSPC": "美股指數", "^IXIC": "美股指數", "^SOX": "美股指數", "^DJI": "美股指數",
    "^N225": "亞洲指數", "^HSI": "亞洲指數", "000001.SS": "亞洲指數",
    "^STOXX50E": "歐洲指數",
    "GC=F": "原物料", "SI=F": "原物料", "HG=F": "原物料",
    "CL=F": "原物料", "BZ=F": "原物料", "NG=F": "原物料",
}

router = APIRouter(prefix="/api", tags=["watchlist"])


def categorize(ticker: str) -> str:
    if ticker in CATEGORY_OVERRIDES:
        return CATEGORY_OVERRIDES[ticker]
    if ticker.endswith(".TW") or ticker.endswith(".TWO"):
        return "台股"
    if ticker.endswith(".HK"):
        return "港股"
    if ticker.startswith("^"):
        return "指數"
    if ticker.endswith("-USD"):
        return "加密"
    if ticker in ("SPY", "QQQ", "VTI", "GLD", "IWM"):
        return "ETF"
    return "美股"


async def hydrate_watchlist_item(ticker: str, group: dict, item: dict | None = None) -> dict:
    row = await db.get_latest_ohlcv(ticker)
    quote = await db.get_market_quote(ticker)
    info = await db.get_stock_info(ticker)
    prev = None
    if quote and quote.get("prev_close") not in (None, 0):
        prev = quote.get("prev_close")
    elif row:
        prev = await db.get_prev_close(ticker)

    latest_price = None
    if quote and quote.get("price") is not None:
        latest_price = quote.get("price")
    elif row:
        latest_price = row.get("close")

    chg_pct = ((latest_price - prev) / prev * 100) if latest_price is not None and prev else 0
    display_name = resolve_display_name(ticker, info)

    return {
        "ticker": ticker,
        "name": display_name,
        "close": latest_price,
        "open": quote.get("open") if quote and quote.get("open") is not None else (row["open"] if row else None),
        "high": quote.get("high") if quote and quote.get("high") is not None else (row["high"] if row else None),
        "low": quote.get("low") if quote and quote.get("low") is not None else (row["low"] if row else None),
        "volume": quote.get("volume") if quote and quote.get("volume") is not None else (row["volume"] if row else None),
        "change_pct": round(chg_pct, 2) if latest_price is not None else 0,
        "date": row["date"] if row else None,
        "source": (quote or {}).get("source") or (row or {}).get("source") or "local_cache",
        "quote_type": (quote or {}).get("quote_type"),
        "is_delayed": (quote or {}).get("is_delayed", True),
        "quote_timestamp": (quote or {}).get("quote_timestamp"),
        "synced_at": (quote or {}).get("synced_at") or (row.get("updated_at") if row else None),
        "tags": item.get("tags") if isinstance(item, dict) and isinstance(item.get("tags"), list) else [],
        "category": categorize(ticker),
        "group_id": group["id"],
        "group_name": group["name"],
    }


# ─── Watchlist ───────────────────────────────────────────────

@router.get("/watchlist")
async def get_watchlist():
    groups = await db.get_watchlist_groups()
    flat_items = []
    for group in groups:
        hydrated_items = []
        for item in group.get("items", []):
            hydrated = await hydrate_watchlist_item(item["ticker"], group, item)
            hydrated["id"] = item["id"]
            hydrated["sort_order"] = item["sort_order"]
            hydrated_items.append(hydrated)
            flat_items.append(hydrated)
        group["items"] = hydrated_items
    return {"groups": groups, "items": flat_items}


@router.post("/watchlist/groups")
async def create_watchlist_group(payload: WatchlistGroupCreate):
    try:
        group = await db.create_watchlist_group(payload.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**group, "items": []}


@router.patch("/watchlist/groups/{group_id}")
async def rename_watchlist_group(group_id: int, payload: WatchlistGroupUpdate):
    try:
        group = await db.rename_watchlist_group(group_id, payload.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not group:
        raise HTTPException(404, "Watchlist group not found")
    return group


@router.delete("/watchlist/groups/{group_id}")
async def delete_watchlist_group(group_id: int):
    deleted = await db.delete_watchlist_group(group_id)
    if not deleted:
        raise HTTPException(404, "Watchlist group not found")
    return {"ok": True, "group_id": group_id}


@router.post("/watchlist/items")
async def add_watchlist_item(payload: WatchlistItemCreate):
    group = await db.get_watchlist_group(payload.group_id)
    if not group:
        raise HTTPException(404, "Watchlist group not found")

    ticker = normalize_ticker(payload.ticker)
    try:
        item = await db.add_watchlist_item(payload.group_id, ticker, tags=payload.tags)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    try:
        await fetcher.fetch_and_store(ticker, period="max", interval="1d", include_info=False)
    except Exception as exc:
        log.warning("watchlist sync %s failed: %s", ticker, exc)

    try:
        await fetcher.fetch_and_store_info(ticker)
    except Exception as exc:
        log.warning("watchlist info %s failed: %s", ticker, exc)

    hydrated = await hydrate_watchlist_item(ticker, group, item)
    hydrated["id"] = item["id"]
    hydrated["sort_order"] = item["sort_order"]
    return hydrated


@router.delete("/watchlist/items/{item_id}")
async def delete_watchlist_item(item_id: int):
    deleted = await db.delete_watchlist_item(item_id)
    if not deleted:
        raise HTTPException(404, "Watchlist item not found")
    return {"ok": True, "item_id": item_id}


@router.put("/watchlist/groups/{group_id}/items/order")
async def reorder_watchlist_items(group_id: int, payload: WatchlistItemsOrderUpdate):
    group = await db.get_watchlist_group(group_id)
    if not group:
        raise HTTPException(404, "Watchlist group not found")
    try:
        updated = await db.reorder_watchlist_items(group_id, payload.item_ids)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not updated:
        raise HTTPException(404, "Watchlist items not found")
    return {"ok": True, "group_id": group_id, "item_ids": payload.item_ids}


# ─── Workspaces ──────────────────────────────────────────────

@router.get("/workspaces")
async def list_workspaces():
    return {"items": await db.list_workspace_presets(owner_id=DEFAULT_OWNER_ID)}


@router.post("/workspaces")
async def create_workspace(payload: WorkspacePresetCreate):
    try:
        return await db.create_workspace_preset(payload.model_dump(), owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: int):
    workspace = await db.get_workspace_preset(workspace_id, owner_id=DEFAULT_OWNER_ID)
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    return workspace


@router.put("/workspaces/{workspace_id}")
async def update_workspace(workspace_id: int, payload: WorkspacePresetUpdate):
    try:
        workspace = await db.update_workspace_preset(
            workspace_id,
            payload.model_dump(exclude_unset=True),
            owner_id=DEFAULT_OWNER_ID,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    return workspace


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: int):
    deleted = await db.delete_workspace_preset(workspace_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Workspace not found")
    return {"ok": True, "workspace_id": workspace_id}
