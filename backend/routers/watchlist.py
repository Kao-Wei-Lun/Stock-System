"""Watchlist routes."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from cache import AsyncTTLCache
from data_fetcher import normalize_ticker
from database import db
from display_name_resolver import resolve_display_name
from market_freshness import is_at_least_as_recent, market_aware_freshness
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
_watchlist_metadata_cache = AsyncTTLCache(ttl_seconds=30, max_entries=4)
_quote_refresh_status_provider = None


def configure(*, quote_refresh_status_provider=None):
    global _quote_refresh_status_provider
    _quote_refresh_status_provider = quote_refresh_status_provider


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


async def hydrate_watchlist_item(
    ticker: str,
    group: dict,
    item: dict | None = None,
    prefetched: dict | None = None,
) -> dict:
    normalized_ticker = str(ticker).strip().upper()
    recent_rows = (prefetched or {}).get("recent_ohlcv", {}).get(normalized_ticker)
    if recent_rows is None:
        row = await db.get_latest_ohlcv(ticker)
    else:
        row = recent_rows[0] if recent_rows else None
    quote = (
        (prefetched or {}).get("quotes", {}).get(normalized_ticker)
        if prefetched is not None
        else await db.get_market_quote(ticker)
    )
    info = (
        (prefetched or {}).get("stock_info", {}).get(normalized_ticker)
        if prefetched is not None
        else await db.get_stock_info(ticker)
    )
    quote_timestamp = (quote or {}).get("quote_timestamp") or (quote or {}).get("synced_at")
    row_timestamp = (row or {}).get("date")
    use_quote = bool(quote) and (
        not row or is_at_least_as_recent(quote_timestamp, row_timestamp)
    )
    snapshot = quote if use_quote else row
    data_timestamp = quote_timestamp if use_quote else row_timestamp
    data_origin = "quote" if use_quote else ("ohlcv" if row else "missing")
    freshness = market_aware_freshness(
        data_timestamp,
        ticker=ticker,
        data_origin=data_origin,
    )
    if callable(_quote_refresh_status_provider):
        refresh_state = _quote_refresh_status_provider(ticker)
        if freshness.get("freshness_status") == "missing":
            freshness["stale_reason"] = "missing_quote"
        elif freshness.get("is_stale") and refresh_state.get("in_backoff"):
            freshness["stale_reason"] = "provider_backoff"
        elif freshness.get("is_stale") and freshness.get("market_is_open"):
            freshness["stale_reason"] = "market_open_quote_expired"
        elif freshness.get("is_stale"):
            freshness["stale_reason"] = "completed_session_missing"
        else:
            freshness["stale_reason"] = None
        freshness.update({
            "refresh_status": refresh_state.get("refresh_status"),
            "next_refresh": refresh_state.get("next_refresh"),
            "backoff_until": refresh_state.get("backoff_until"),
            "last_refresh_error_category": refresh_state.get("last_error_category"),
            "provider_degraded": refresh_state.get("provider_degraded"),
        })
    prev = None
    if use_quote and quote.get("prev_close") not in (None, 0):
        prev = quote.get("prev_close")
    elif row:
        if recent_rows is not None:
            prev = recent_rows[1].get("close") if len(recent_rows) > 1 else None
        else:
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
        "data_origin": data_origin,
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
    tickers = list(dict.fromkeys(
        str(item.get("ticker") or "").strip().upper()
        for group in groups
        for item in group.get("items", [])
        if item.get("ticker")
    ))
    recent_ohlcv, quotes, stock_info = await asyncio.gather(
        db.get_recent_ohlcv_many(tickers, per_ticker_limit=2),
        db.get_market_quotes(tickers),
        db.get_stock_info_many(tickers),
    )
    prefetched = {
        "recent_ohlcv": recent_ohlcv,
        "quotes": quotes,
        "stock_info": stock_info,
    }
    flat_items = []
    for group in groups:
        hydrated_items = []
        for item in group.get("items", []):
            hydrated = await hydrate_watchlist_item(item["ticker"], group, item, prefetched=prefetched)
            hydrated["id"] = item["id"]
            hydrated["sort_order"] = item["sort_order"]
            hydrated_items.append(hydrated)
            flat_items.append(hydrated)
        group["items"] = hydrated_items
    return {"groups": groups, "items": flat_items}


@router.get("/watchlist/metadata")
async def get_watchlist_metadata():
    async def load_metadata():
        groups = await db.get_watchlist_groups()
        tickers = list(dict.fromkeys(
            str(item.get("ticker") or "").strip().upper()
            for group in groups
            for item in group.get("items", [])
            if item.get("ticker")
        ))
        stock_info = await db.get_stock_info_many(tickers)
        flat_items = []
        for group in groups:
            compact_items = []
            for item in group.get("items", []):
                ticker = str(item.get("ticker") or "").strip().upper()
                compact = {
                    "id": item.get("id"),
                    "ticker": ticker,
                    "name": resolve_display_name(ticker, stock_info.get(ticker)),
                    "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
                    "sort_order": item.get("sort_order", 0),
                    "group_id": group.get("id"),
                    "group_name": group.get("name"),
                    "group_color": group.get("color"),
                    "category": categorize(ticker),
                }
                compact_items.append(compact)
                flat_items.append(compact)
            group["items"] = compact_items
        return {"groups": groups, "items": flat_items, "quotes_included": False}

    return await _watchlist_metadata_cache.get_or_load("default", load_metadata)


@router.post("/watchlist/groups")
async def create_watchlist_group(payload: WatchlistGroupCreate):
    try:
        group = await db.create_watchlist_group(payload.name, color=payload.color)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await _watchlist_metadata_cache.clear()
    return {**group, "items": []}


@router.patch("/watchlist/groups/{group_id}")
async def rename_watchlist_group(group_id: int, payload: WatchlistGroupUpdate):
    try:
        group = await db.rename_watchlist_group(group_id, payload.name, color=payload.color)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not group:
        raise HTTPException(404, "Watchlist group not found")
    await _watchlist_metadata_cache.clear()
    return group


@router.delete("/watchlist/groups/{group_id}")
async def delete_watchlist_group(group_id: int):
    deleted = await db.delete_watchlist_group(group_id)
    if not deleted:
        raise HTTPException(404, "Watchlist group not found")
    await _watchlist_metadata_cache.clear()
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
    await _watchlist_metadata_cache.clear()
    hydrated = await hydrate_watchlist_item(ticker, group, item)
    hydrated["id"] = item["id"]
    hydrated["sort_order"] = item["sort_order"]
    return hydrated


@router.delete("/watchlist/items/{item_id}")
async def delete_watchlist_item(item_id: int):
    deleted = await db.delete_watchlist_item(item_id)
    if not deleted:
        raise HTTPException(404, "Watchlist item not found")
    await _watchlist_metadata_cache.clear()
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
    await _watchlist_metadata_cache.clear()
    return {"ok": True, "group_id": group_id, "item_ids": payload.item_ids}
