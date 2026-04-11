"""Market data routes — kline, quote, info, sync, search, stats."""

import logging

from fastapi import APIRouter, HTTPException, Query

from data_fetcher import normalize_ticker
from database import db
from display_name_resolver import resolve_display_name
from providers import fetcher, fubon_futopt_provider, fubon_market_snapshot_provider
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
ALLOWED_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}
ALLOWED_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "1wk", "1mo"}
INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
INTRADAY_DEFAULT_PERIODS = {
    "1m": "1d",
    "2m": "5d",
    "5m": "5d",
    "15m": "1mo",
    "30m": "1mo",
    "60m": "3mo",
    "90m": "3mo",
    "1h": "3mo",
}
INTRADAY_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo"}
FUTOPT_ALLOWED_INTERVALS = {"1m", "5m", "15m", "30m", "60m", "1h"}

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


async def _get_ohlc_payload(
    ticker: str,
    period: str | None,
    interval: str,
):
    ticker = normalize_ticker(ticker)
    period, interval = _normalize_ohlc_query(period, interval)
    rows = await db.get_ohlcv(ticker, period=period, interval=interval)

    if _needs_history_backfill(rows, period) or _has_suspicious_daily_rows(ticker, rows, interval):
        fetch_period = "max" if period in FULL_HISTORY_PERIODS else period
        await fetcher.fetch_and_store(ticker, period=fetch_period, interval=interval, include_info=False)
        rows = await db.get_ohlcv(ticker, period=period, interval=interval)

    return {"ticker": ticker, "period": period, "interval": interval, "data": rows}


def _normalize_futopt_ohlc_query(period: str | None, interval: str | None) -> tuple[str, str]:
    normalized_interval = (interval or "1m").strip().lower()
    if normalized_interval not in FUTOPT_ALLOWED_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported futopt interval '{normalized_interval}'. Use one of: {', '.join(sorted(FUTOPT_ALLOWED_INTERVALS))}",
        )

    normalized_period = (period or "1d").strip().lower()
    if normalized_period not in INTRADAY_PERIODS:
        allowed = ", ".join(sorted(INTRADAY_PERIODS))
        raise HTTPException(
            status_code=400,
            detail=f"Futopt interval '{normalized_interval}' supports period values: {allowed}",
        )
    return normalized_period, normalized_interval


def _normalize_ohlc_query(period: str | None, interval: str | None) -> tuple[str, str]:
    normalized_interval = (interval or "1d").strip().lower()
    if normalized_interval not in ALLOWED_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported interval '{normalized_interval}'. Use one of: {', '.join(sorted(ALLOWED_INTERVALS))}",
        )

    if normalized_interval in INTRADAY_INTERVALS:
        normalized_period = (period or INTRADAY_DEFAULT_PERIODS[normalized_interval]).strip().lower()
        if normalized_period not in INTRADAY_PERIODS:
            allowed = ", ".join(sorted(INTRADAY_PERIODS))
            raise HTTPException(
                status_code=400,
                detail=f"Intraday interval '{normalized_interval}' supports period values: {allowed}",
            )
        return normalized_period, normalized_interval

    normalized_period = (period or "1y").strip().lower()
    if normalized_period not in ALLOWED_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported period '{normalized_period}'. Use one of: {', '.join(sorted(ALLOWED_PERIODS))}",
        )
    return normalized_period, normalized_interval


@router.get("/kline/{ticker}")
async def get_kline(
    ticker: str,
    period: str | None = Query(None, description="1d 5d 1mo 3mo 6mo 1y 2y 5y 10y max"),
    interval: str = Query("1d", description="1m 5m 15m 60m 1h 1d 1wk 1mo"),
):
    return await _get_ohlc_payload(ticker, period, interval)


@router.get("/ohlc/{ticker}")
async def get_ohlc(
    ticker: str,
    period: str | None = Query(None, description="1d 5d 1mo 3mo 6mo 1y 2y 5y 10y max"),
    interval: str = Query("1d", description="1m 5m 15m 60m 1h 1d 1wk 1mo"),
):
    return await _get_ohlc_payload(ticker, period, interval)


@router.get("/ohlc")
async def get_ohlc_query(
    ticker: str = Query(..., min_length=1),
    period: str | None = Query(None, description="1d 5d 1mo 3mo 6mo 1y 2y 5y 10y max"),
    interval: str = Query("1d", description="1m 5m 15m 60m 1h 1d 1wk 1mo"),
):
    return await _get_ohlc_payload(ticker, period, interval)


@router.get("/quote/{ticker}", response_model=QuoteResponse)
async def get_quote(ticker: str):
    ticker = normalize_ticker(ticker)
    quote = await _fetch_and_store_quote_snapshot(ticker)
    if not quote:
        quote = await db.get_market_quote(ticker)
    if not quote:
        raise HTTPException(404, "Unable to fetch quote")
    return quote


@router.get("/futopt/quote/{symbol}", response_model=QuoteResponse)
async def get_futopt_quote(symbol: str):
    quote = await fubon_futopt_provider.fetch_quote(symbol)
    if not quote:
        raise HTTPException(404, "Unable to fetch futopt quote")
    return quote


@router.get("/futopt/ohlc/{symbol}")
async def get_futopt_ohlc(
    symbol: str,
    period: str | None = Query(None, description="1d 5d 1mo 3mo 6mo"),
    interval: str = Query("1m", description="1m 5m 15m 30m 60m 1h"),
):
    period, interval = _normalize_futopt_ohlc_query(period, interval)
    payload = await fubon_futopt_provider.fetch_intraday_ohlc(symbol, period=period, interval=interval)
    if not payload:
        raise HTTPException(404, "Unable to fetch futopt ohlc")
    return payload


@router.get("/fubon/snapshot/{market}")
async def get_fubon_snapshot(
    market: str,
    refresh: bool = Query(False),
):
    try:
        payload = await fubon_market_snapshot_provider.fetch_snapshot(market, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not payload:
        raise HTTPException(404, "Unable to fetch Fubon market snapshot")
    return payload


@router.get("/fubon/movers/{market}")
async def get_fubon_movers(
    market: str,
    direction: str = Query("up", description="up or down"),
    change: str = Query("percent", description="percent or value"),
    limit: int = Query(10, ge=1, le=50),
    refresh: bool = Query(False),
):
    try:
        payload = await fubon_market_snapshot_provider.fetch_movers(
            market,
            direction=direction,
            change=change,
            limit=limit,
            refresh=refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not payload:
        raise HTTPException(404, "Unable to fetch Fubon movers")
    return payload


@router.get("/fubon/actives/{market}")
async def get_fubon_actives(
    market: str,
    trade: str = Query("value", description="value or volume"),
    limit: int = Query(10, ge=1, le=50),
    refresh: bool = Query(False),
):
    try:
        payload = await fubon_market_snapshot_provider.fetch_actives(
            market,
            trade=trade,
            limit=limit,
            refresh=refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not payload:
        raise HTTPException(404, "Unable to fetch Fubon actives")
    return payload


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
    interval: str = Query("1d", description="1m 5m 15m 60m 1h 1d 1wk 1mo"),
):
    ticker = normalize_ticker(ticker)
    period, interval = _normalize_ohlc_query(period, interval)
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
