"""Market data routes — kline, quote, info, sync, search, stats."""

import logging

from fastapi import APIRouter, HTTPException, Query

from data_fetcher import normalize_ticker
from database import db
from display_name_resolver import resolve_display_name
from providers import fetcher
from schemas import QuoteResponse
from tw_symbol_lookup import search_taiwan_tickers

log = logging.getLogger(__name__)

# These will be injected from main.py on startup
_fetch_and_store_quote_snapshot = None
_sync_tracked_market_data = None
_needs_history_backfill = None
_has_suspicious_daily_rows = None
FULL_HISTORY_PERIODS = {"10y", "max"}
LATEST_DATA_SYNC_PERIOD = "1y"
LATEST_DATA_SYNC_INTERVAL = "1d"

router = APIRouter(prefix="/api", tags=["market_data"])


def configure(
    *,
    fetch_and_store_quote_snapshot,
    sync_tracked_market_data,
    needs_history_backfill,
    has_suspicious_daily_rows,
    full_history_periods,
    latest_data_sync_period,
    latest_data_sync_interval,
):
    """Inject helpers from main.py to avoid circular imports."""
    global _fetch_and_store_quote_snapshot, _sync_tracked_market_data
    global _needs_history_backfill, _has_suspicious_daily_rows
    global FULL_HISTORY_PERIODS, LATEST_DATA_SYNC_PERIOD, LATEST_DATA_SYNC_INTERVAL
    _fetch_and_store_quote_snapshot = fetch_and_store_quote_snapshot
    _sync_tracked_market_data = sync_tracked_market_data
    _needs_history_backfill = needs_history_backfill
    _has_suspicious_daily_rows = has_suspicious_daily_rows
    FULL_HISTORY_PERIODS = full_history_periods
    LATEST_DATA_SYNC_PERIOD = latest_data_sync_period
    LATEST_DATA_SYNC_INTERVAL = latest_data_sync_interval


@router.get("/kline/{ticker}")
async def get_kline(
    ticker: str,
    period: str = Query("1y", description="5d 1mo 3mo 6mo 1y 2y 5y 10y max"),
    interval: str = Query("1d", description="1h 1d 1wk 1mo"),
):
    ticker = normalize_ticker(ticker)
    period = (period or "1y").lower()
    interval = (interval or "1d").lower()
    rows = await db.get_ohlcv(ticker, period=period, interval=interval)

    if _needs_history_backfill(rows, period) or _has_suspicious_daily_rows(ticker, rows, interval):
        fetch_period = "max" if period in FULL_HISTORY_PERIODS else period
        await fetcher.fetch_and_store(ticker, period=fetch_period, interval=interval, include_info=False)
        rows = await db.get_ohlcv(ticker, period=period, interval=interval)

    return {"ticker": ticker, "interval": interval, "data": rows}


@router.get("/quote/{ticker}", response_model=QuoteResponse)
async def get_quote(ticker: str):
    ticker = normalize_ticker(ticker)
    quote = await _fetch_and_store_quote_snapshot(ticker)
    if not quote:
        quote = await db.get_market_quote(ticker)
    if not quote:
        raise HTTPException(404, "Unable to fetch quote")
    return quote


@router.get("/info/{ticker}")
async def get_info(ticker: str):
    ticker = normalize_ticker(ticker)
    info = await db.get_stock_info(ticker)
    if not info:
        info = await fetcher.fetch_and_store_info(ticker)
    return info or {}


@router.post("/sync/{ticker}")
async def sync_ticker(
    ticker: str,
    period: str = Query("max", description="5d 1mo 3mo 6mo 1y 2y 5y 10y max"),
    interval: str = Query("1d", description="1h 1d 1wk 1mo"),
):
    ticker = normalize_ticker(ticker)
    period = (period or "max").lower()
    interval = (interval or "1d").lower()
    count = await fetcher.fetch_and_store(ticker, period=period, interval=interval, include_info=False)
    return {"ticker": ticker, "synced": count, "period": period, "interval": interval}


@router.post("/sync/all")
async def sync_all_tracked(
    period: str = Query(LATEST_DATA_SYNC_PERIOD, description="1mo 3mo 6mo 1y 2y 5y 10y max"),
    interval: str = Query(LATEST_DATA_SYNC_INTERVAL, description="1d 1wk 1mo"),
):
    return await _sync_tracked_market_data(period=period, interval=interval, reason="manual-all")


@router.get("/search")
async def search(q: str = Query(..., min_length=1)):
    results = []
    seen = set()

    for row in await db.search_tickers(q.upper()):
        ticker = normalize_ticker(row.get("ticker", ""))
        if not ticker or ticker in seen:
            continue
        results.append(
            {
                "ticker": ticker,
                "name": resolve_display_name(ticker, row),
            }
        )
        seen.add(ticker)

    for row in search_taiwan_tickers(q):
        ticker = normalize_ticker(row.get("ticker", ""))
        if not ticker or ticker in seen:
            continue
        results.append(
            {
                "ticker": ticker,
                "name": row.get("name") or ticker,
            }
        )
        seen.add(ticker)
        if len(results) >= 20:
            break

    return results[:20]


@router.get("/db/stats")
async def db_stats():
    return await db.get_stats()
