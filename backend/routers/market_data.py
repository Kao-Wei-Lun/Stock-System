"""Market data routes — kline, quote, info, sync, search, stats."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from cache import AsyncTTLCache
from data_fetcher import normalize_ticker
from database import db
from display_name_resolver import resolve_display_name
from futopt_history_service import load_futopt_ohlc_db_first, sync_futopt_intraday_ohlc
from fubon_provider import FubonMarketdataAuthenticationError
from fubon_symbols import is_dynamic_futopt_alias, looks_like_futopt_search_query
from providers import fetcher, fubon_futopt_provider, fubon_market_snapshot_provider
from schemas import QuoteResponse
from tw_symbol_lookup import search_taiwan_tickers

log = logging.getLogger(__name__)

# These will be injected from main.py on startup
_fetch_and_store_quote_snapshot = None
_sync_tracked_market_data = None
_sync_taiwan_full_history = None
_needs_history_backfill = None
_has_suspicious_daily_rows = None
_futopt_candle_recorder = None
_futopt_refresh_coordinator = None
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
_snapshot_summary_cache = AsyncTTLCache(ttl_seconds=10, max_entries=8)


def _bounded_ohlc_rows(rows: list[dict], *, since: str | None, limit: int | None, warmup: int) -> list[dict]:
    bounded = rows
    if since:
        try:
            threshold = datetime.fromisoformat(since.replace("Z", "+00:00"))

            def is_after(row):
                value = row.get("date")
                candidate = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                if candidate.tzinfo is None and threshold.tzinfo is not None:
                    candidate = candidate.replace(tzinfo=threshold.tzinfo)
                return candidate > threshold

            bounded = [row for row in bounded if is_after(row)]
        except (TypeError, ValueError):
            raise HTTPException(400, "since must be an ISO-8601 date/time")
    if limit is not None:
        effective_limit = max(limit, warmup)
        bounded = bounded[-effective_limit:]
    return bounded


def configure(
    *,
    fetch_and_store_quote_snapshot,
    sync_tracked_market_data,
    needs_history_backfill,
    has_suspicious_daily_rows,
    full_history_periods,
    latest_data_sync_period,
    latest_data_sync_interval,
    sync_taiwan_full_history=None,
    futopt_candle_recorder=None,
    futopt_refresh_coordinator=None,
):
    """Inject helpers from main.py to avoid circular imports."""
    global _fetch_and_store_quote_snapshot, _sync_tracked_market_data, _sync_taiwan_full_history
    global _needs_history_backfill, _has_suspicious_daily_rows
    global _futopt_candle_recorder, _futopt_refresh_coordinator
    global FULL_HISTORY_PERIODS, LATEST_DATA_SYNC_PERIOD, LATEST_DATA_SYNC_INTERVAL
    _fetch_and_store_quote_snapshot = fetch_and_store_quote_snapshot
    _sync_tracked_market_data = sync_tracked_market_data
    _sync_taiwan_full_history = sync_taiwan_full_history
    _needs_history_backfill = needs_history_backfill
    _has_suspicious_daily_rows = has_suspicious_daily_rows
    _futopt_candle_recorder = futopt_candle_recorder
    _futopt_refresh_coordinator = futopt_refresh_coordinator
    FULL_HISTORY_PERIODS = full_history_periods
    LATEST_DATA_SYNC_PERIOD = latest_data_sync_period
    LATEST_DATA_SYNC_INTERVAL = latest_data_sync_interval


async def _get_ohlc_payload(
    ticker: str,
    period: str | None,
    interval: str,
    *,
    limit: int | None = None,
    since: str | None = None,
    warmup: int = 0,
):
    ticker = normalize_ticker(ticker)
    period, interval = _normalize_ohlc_query(period, interval)
    query_options = {}
    if limit is not None or since is not None:
        query_options = {"limit": max(limit or 1, warmup), "since": since}
    rows = await db.get_ohlcv(ticker, period=period, interval=interval, **query_options)

    if since is None and (_needs_history_backfill(rows, period) or _has_suspicious_daily_rows(ticker, rows, interval)):
        fetch_period = "max" if period in FULL_HISTORY_PERIODS else period
        await fetcher.fetch_and_store(ticker, period=fetch_period, interval=interval, include_info=False)
        rows = await db.get_ohlcv(ticker, period=period, interval=interval, **query_options)

    return {
        "ticker": ticker,
        "period": period,
        "interval": interval,
        "data": rows,
        "row_count": len(rows),
        "incremental": since is not None,
    }


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
    limit: int | None = Query(None, ge=1, le=5000),
    since: str | None = Query(None),
    warmup: int = Query(0, ge=0, le=2000),
):
    return await _get_ohlc_payload(ticker, period, interval, limit=limit, since=since, warmup=warmup)


@router.get("/ohlc/{ticker}")
async def get_ohlc(
    ticker: str,
    period: str | None = Query(None, description="1d 5d 1mo 3mo 6mo 1y 2y 5y 10y max"),
    interval: str = Query("1d", description="1m 5m 15m 60m 1h 1d 1wk 1mo"),
    limit: int | None = Query(None, ge=1, le=5000),
    since: str | None = Query(None),
    warmup: int = Query(0, ge=0, le=2000),
):
    return await _get_ohlc_payload(ticker, period, interval, limit=limit, since=since, warmup=warmup)


@router.get("/ohlc")
async def get_ohlc_query(
    ticker: str = Query(..., min_length=1),
    period: str | None = Query(None, description="1d 5d 1mo 3mo 6mo 1y 2y 5y 10y max"),
    interval: str = Query("1d", description="1m 5m 15m 60m 1h 1d 1wk 1mo"),
    limit: int | None = Query(None, ge=1, le=5000),
    since: str | None = Query(None),
    warmup: int = Query(0, ge=0, le=2000),
):
    return await _get_ohlc_payload(ticker, period, interval, limit=limit, since=since, warmup=warmup)


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
async def get_futopt_quote(
    symbol: str,
    session: str | None = Query("AUTO", description="AUTO, REGULAR, or AFTERHOURS"),
):
    try:
        quote = await fubon_futopt_provider.fetch_quote(symbol, session=session)
    except Exception as exc:
        log.warning("futopt quote fetch failed for %s: %s", symbol, exc)
        raise HTTPException(502, f"Unable to fetch futopt quote: {exc}") from exc
    if not quote:
        raise HTTPException(404, "Unable to fetch futopt quote")
    return quote


@router.get("/futopt/ohlc/{symbol}")
async def get_futopt_ohlc(
    symbol: str,
    period: str | None = Query(None, description="1d 5d 1mo 3mo 6mo"),
    interval: str = Query("1m", description="1m 5m 15m 30m 60m 1h"),
    refresh: bool = Query(True, description="Refresh the persisted tail from Fubon before returning"),
    refresh_mode: str | None = Query(None, description="none, background, or blocking"),
    session: str = Query("AUTO", description="Refresh single-flight session key"),
    limit: int | None = Query(None, ge=1, le=5000),
    since: str | None = Query(None),
    warmup: int = Query(0, ge=0, le=2000),
):
    period, interval = _normalize_futopt_ohlc_query(period, interval)
    selected_refresh_mode = str(refresh_mode or ("blocking" if refresh else "none")).strip().lower()
    if selected_refresh_mode not in {"none", "background", "blocking"}:
        raise HTTPException(400, "refresh_mode must be one of: none, background, blocking")
    payload = await load_futopt_ohlc_db_first(
        fubon_futopt_provider,
        db,
        symbol,
        period=period,
        interval=interval,
        refresh=refresh,
        refresh_mode=selected_refresh_mode,
        refresh_coordinator=_futopt_refresh_coordinator,
        session=session,
    )
    if not payload.get("data") and payload.get("sync_error"):
        raise HTTPException(502, f"Unable to refresh futopt ohlc: {payload['sync_error']}")
    if not payload.get("data"):
        raise HTTPException(404, "Unable to fetch futopt ohlc")
    payload["data"] = _bounded_ohlc_rows(payload["data"], since=since, limit=limit, warmup=warmup)
    payload["row_count"] = len(payload["data"])
    payload["incremental"] = since is not None
    return payload


@router.get("/futopt/history/status")
async def get_futopt_history_status():
    if _futopt_candle_recorder is None:
        return {"configured": False, "active": False}
    return {"configured": True, **_futopt_candle_recorder.get_status()}


@router.post("/futopt/sync/{symbol}")
async def sync_futopt_ohlc(
    symbol: str,
    period: str | None = Query(None, description="1d 5d 1mo 3mo 6mo"),
    interval: str = Query("1m", description="1m 5m 15m 30m 60m 1h"),
):
    period, interval = _normalize_futopt_ohlc_query(period, interval)
    try:
        result = await sync_futopt_intraday_ohlc(
            fubon_futopt_provider,
            db,
            symbol,
            period=period,
            interval=interval,
        )
    except Exception as exc:
        log.warning("futopt ohlc sync failed for %s (%s/%s): %s", symbol, period, interval, exc)
        raise HTTPException(502, f"Unable to sync futopt ohlc: {exc}") from exc
    if not result:
        raise HTTPException(404, "Unable to sync futopt ohlc")
    return result


@router.get("/fubon/snapshot/{market}")
async def get_fubon_snapshot(
    market: str,
    refresh: bool = Query(False),
):
    try:
        payload = await fubon_market_snapshot_provider.fetch_snapshot(market, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FubonMarketdataAuthenticationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not payload:
        raise HTTPException(404, "Unable to fetch Fubon market snapshot")
    return payload


@router.get("/fubon/snapshot/{market}/summary")
async def get_fubon_snapshot_summary(market: str, refresh: bool = Query(False)):
    normalized_market = str(market or "").strip().upper()

    async def load_summary():
        payload = await fubon_market_snapshot_provider.fetch_snapshot(normalized_market, refresh=refresh)
        if not payload:
            raise HTTPException(404, "Unable to fetch Fubon market snapshot")
        return {
            "market": payload.get("market") or normalized_market,
            "date": payload.get("date"),
            "time": payload.get("time"),
            "source": payload.get("source") or "fubon_neo",
            "freshness": payload.get("freshness"),
            "summary": payload.get("summary") or {},
        }

    try:
        if refresh:
            result = await load_summary()
            await _snapshot_summary_cache.invalidate(normalized_market)
            return result
        return await _snapshot_summary_cache.get_or_load(normalized_market, load_summary)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FubonMarketdataAuthenticationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
    except FubonMarketdataAuthenticationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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
    except FubonMarketdataAuthenticationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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


@router.get("/tw/universe")
async def list_taiwan_universe(
    active_only: bool = Query(True),
    include_etf: bool = Query(True),
    limit: int = Query(200, ge=1, le=5000),
):
    return {
        "source": "fubon_neo",
        "items": await db.list_tw_equity_universe(
            active_only=active_only,
            include_etf=include_etf,
            limit=limit,
        ),
    }


@router.get("/tw/universe/coverage")
async def get_taiwan_universe_coverage(
    interval: str = Query("1d", description="1d 1wk 1mo"),
):
    normalized_interval = interval.strip().lower()
    if normalized_interval not in {"1d", "1wk", "1mo"}:
        raise HTTPException(400, "interval must be one of: 1d, 1wk, 1mo")
    return await db.get_tw_universe_coverage(normalized_interval)


@router.get("/tw/universe/analysis-coverage")
async def get_taiwan_analysis_kline_coverage(
    interval: str = Query("1d", description="1d 1wk 1mo"),
):
    normalized_interval = interval.strip().lower()
    if normalized_interval not in {"1d", "1wk", "1mo"}:
        raise HTTPException(400, "interval must be one of: 1d, 1wk, 1mo")
    return await db.get_tw_analysis_kline_coverage(normalized_interval)


@router.get("/tw/history/status")
async def list_taiwan_history_status(
    interval: str | None = Query(None, description="1d 1wk 1mo"),
    status: str | None = Query(None, description="pending running success empty failed"),
    limit: int = Query(500, ge=1, le=5000),
):
    normalized_interval = interval.strip().lower() if interval else None
    if normalized_interval and normalized_interval not in {"1d", "1wk", "1mo"}:
        raise HTTPException(400, "interval must be one of: 1d, 1wk, 1mo")
    normalized_status = status.strip().lower() if status else None
    if normalized_status and normalized_status not in {"pending", "running", "success", "empty", "failed"}:
        raise HTTPException(400, "status must be one of: pending, running, success, empty, failed")
    return {
        "source": "fubon_neo",
        "items": await db.list_tw_history_sync_status(
            interval=normalized_interval,
            status=normalized_status,
            limit=limit,
        ),
    }


async def _run_taiwan_history_sync(*, max_tickers: int | None, force_universe: bool, force_full: bool):
    if not callable(_sync_taiwan_full_history):
        raise HTTPException(503, "Taiwan full history sync service is not configured")
    return await _sync_taiwan_full_history(
        reason="manual-tw-full-history",
        force_universe=force_universe,
        force_full=force_full,
        max_tickers=max_tickers,
    )


@router.post("/tw/history/sync")
async def sync_taiwan_full_history(
    max_tickers: int | None = Query(None, ge=1, le=5000),
    force_universe: bool = Query(True),
    force_full: bool = Query(False),
):
    return await _run_taiwan_history_sync(
        max_tickers=max_tickers,
        force_universe=force_universe,
        force_full=force_full,
    )


@router.post("/tw/history/backfill/full")
async def backfill_taiwan_full_history(
    max_tickers: int | None = Query(None, ge=1, le=5000),
    force_universe: bool = Query(True),
):
    return await _run_taiwan_history_sync(
        max_tickers=max_tickers,
        force_universe=force_universe,
        force_full=True,
    )


@router.post("/tw/history/backfill/missing")
async def backfill_missing_taiwan_history(
    max_tickers: int | None = Query(None, ge=1, le=5000),
    force_universe: bool = Query(True),
):
    return await _run_taiwan_history_sync(
        max_tickers=max_tickers,
        force_universe=force_universe,
        force_full=False,
    )


@router.get("/search")
async def search(q: str = Query(..., min_length=1)):
    results = []
    seen = set()
    normalized_query = q.strip().upper()

    for row in await db.search_tickers(normalized_query):
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

    if is_dynamic_futopt_alias(normalized_query) and normalized_query not in seen:
        try:
            resolution = await fubon_futopt_provider.resolve_contract(normalized_query)
        except Exception as exc:
            log.warning("Dynamic futures alias resolution failed for %s: %s", normalized_query, exc)
            resolution = None
        resolved_symbol = str((resolution or {}).get("resolved_symbol") or "").strip().upper()
        alias_name = {
            "*TXFF": "臺股期貨連續近月",
            "*TMFF": "微型臺指期貨連續近月",
        }.get(normalized_query, normalized_query)
        results.append(
            {
                "ticker": normalized_query,
                "name": f"{alias_name}（目前 {resolved_symbol}）" if resolved_symbol else alias_name,
                "asset_class": "futopt",
                "instrument_type": "future",
                "exchange": "TAIFEX",
                "market": "FUTOPT",
                "source": "fubon_dynamic_alias",
                "resolved_symbol": resolved_symbol or None,
            }
        )
        seen.add(normalized_query)

    if looks_like_futopt_search_query(normalized_query):
        for row in await fubon_futopt_provider.search_contracts(normalized_query, limit=20):
            ticker = normalize_ticker(row.get("ticker", ""))
            if not ticker or ticker in seen:
                continue
            results.append(
                {
                    "ticker": ticker,
                    "name": row.get("name") or ticker,
                    "asset_class": row.get("asset_class") or "futopt",
                    "instrument_type": row.get("instrument_type") or "future",
                    "exchange": row.get("exchange") or "TAIFEX",
                    "market": row.get("market") or "FUTOPT",
                    "source": row.get("source") or "fubon_neo",
                }
            )
            seen.add(ticker)
            if len(results) >= 20:
                break

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
