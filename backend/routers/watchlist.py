"""Watchlist routes."""

import logging

from fastapi import APIRouter, HTTPException

from data_fetcher import normalize_ticker
from database import db
from display_name_resolver import resolve_display_name
from market_freshness import is_at_least_as_recent, market_data_freshness
from providers import fetcher, fubon_realtime_pool
from schemas import (
    WatchlistGroupCreate,
    WatchlistGroupUpdate,
    WatchlistItemCreate,
    WatchlistItemsOrderUpdate,
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
    quote_timestamp = (quote or {}).get("quote_timestamp") or (quote or {}).get("synced_at")
    row_timestamp = (row or {}).get("date")
    use_quote = bool(quote) and (
        not row or is_at_least_as_recent(quote_timestamp, row_timestamp)
    )
    snapshot = quote if use_quote else row
    data_timestamp = quote_timestamp if use_quote else row_timestamp
    freshness = market_data_freshness(data_timestamp)
    prev = None
    if use_quote and quote.get("prev_close") not in (None, 0):
        prev = quote.get("prev_close")
    elif row:
        prev = await db.get_prev_close(ticker)

    latest_price = None
    if use_quote and quote.get("price") is not None:
        latest_price = quote.get("price")
    elif row:
        latest_price = row.get("close")

    chg_pct = ((latest_price - prev) / prev * 100) if latest_price is not None and prev else 0
    display_name = resolve_display_name(ticker, info)

    return {
        "ticker": ticker,
        "name": display_name,
        "close": latest_price,
        "open": snapshot.get("open") if snapshot else None,
        "high": snapshot.get("high") if snapshot else None,
        "low": snapshot.get("low") if snapshot else None,
        "volume": snapshot.get("volume") if snapshot else None,
        "change_pct": round(chg_pct, 2) if latest_price is not None else 0,
        "date": row["date"] if row else None,
        "source": (snapshot or {}).get("source") or "local_cache",
        "quote_type": (quote or {}).get("quote_type") if use_quote else "historical_close",
        "is_delayed": (quote or {}).get("is_delayed", True) if use_quote else True,
        "quote_timestamp": (quote or {}).get("quote_timestamp") if use_quote else None,
        "synced_at": (
            (quote or {}).get("synced_at")
            if use_quote
            else (row or {}).get("updated_at")
        ),
        "data_origin": "quote" if use_quote else ("ohlcv" if row else "missing"),
        **freshness,
        "tags": item.get("tags") if isinstance(item, dict) and isinstance(item.get("tags"), list) else [],
        "category": categorize(ticker),
        "group_id": group["id"],
        "group_name": group["name"],
        "group_color": group.get("color"),
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
        group = await db.create_watchlist_group(payload.name, color=payload.color)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**group, "items": []}


@router.patch("/watchlist/groups/{group_id}")
async def rename_watchlist_group(group_id: int, payload: WatchlistGroupUpdate):
    try:
        group = await db.rename_watchlist_group(group_id, payload.name, color=payload.color)
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
    await fubon_realtime_pool.sync_watchlist_from_db(db)
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

    await fubon_realtime_pool.sync_watchlist_from_db(db)
    hydrated = await hydrate_watchlist_item(ticker, group, item)
    hydrated["id"] = item["id"]
    hydrated["sort_order"] = item["sort_order"]
    return hydrated


@router.delete("/watchlist/items/{item_id}")
async def delete_watchlist_item(item_id: int):
    deleted = await db.delete_watchlist_item(item_id)
    if not deleted:
        raise HTTPException(404, "Watchlist item not found")
    await fubon_realtime_pool.sync_watchlist_from_db(db)
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
