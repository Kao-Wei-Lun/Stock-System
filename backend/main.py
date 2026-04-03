"""
QuantVision Pro backend API server.

Refactored: routes are in backend/routers/*, schemas in backend/schemas.py.
This file retains app creation, middleware, lifespan, and background tasks.
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, time as time_of_day, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from data_fetcher import normalize_ticker
from database import db, init_db
from macro_regime import build_macro_dashboard_payload
from providers import (
    alert_engine,
    fetcher,
    fundamentals_provider,
    macro_snapshot_provider,
    market_event_provider,
    news_provider,
    quote_provider,
    screener_engine,
    taiwan_chip_provider,
    ws_manager,
)
from routers import alerts, backtest, intelligence, journal, market_data, system, watchlist, workspace
from routers.watchlist import hydrate_watchlist_item
from taifex_fetcher import taifex_fetcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

load_dotenv()

# ─── Configuration ───────────────────────────────────────────

STARTUP_DOWNLOAD_DELAY_SECONDS = 2.5
APP_PORT = int(os.getenv("APP_PORT", "8001"))
FRONTEND_DEV_URL = os.getenv("FRONTEND_DEV_URL", "http://localhost:5173").rstrip("/")
STARTUP_DOWNLOAD_ENABLED = os.getenv("STARTUP_DOWNLOAD_ENABLED", "false").strip().lower() in {
    "1", "true", "yes", "on",
}
INSTITUTIONAL_AUTO_SYNC_ENABLED = os.getenv("INSTITUTIONAL_AUTO_SYNC_ENABLED", "true").strip().lower() in {
    "1", "true", "yes", "on",
}
LATEST_DATA_SYNC_PERIOD = os.getenv("LATEST_DATA_SYNC_PERIOD", "1y").strip().lower() or "1y"
LATEST_DATA_SYNC_INTERVAL = os.getenv("LATEST_DATA_SYNC_INTERVAL", "1d").strip().lower() or "1d"
LATEST_DATA_SYNC_ON_STARTUP = os.getenv("LATEST_DATA_SYNC_ON_STARTUP", "true").strip().lower() in {
    "1", "true", "yes", "on",
}
ALERT_EVALUATOR_ENABLED = os.getenv("ALERT_EVALUATOR_ENABLED", "true").strip().lower() in {
    "1", "true", "yes", "on",
}
ALERT_POLL_INTERVAL_SECONDS = max(10, int(os.getenv("ALERT_POLL_INTERVAL_SECONDS", "30")))
MARKET_INTELLIGENCE_SYNC_ENABLED = os.getenv("MARKET_INTELLIGENCE_SYNC_ENABLED", "true").strip().lower() in {
    "1", "true", "yes", "on",
}
MARKET_INTELLIGENCE_STARTUP_SYNC = os.getenv("MARKET_INTELLIGENCE_STARTUP_SYNC", "true").strip().lower() in {
    "1", "true", "yes", "on",
}
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Taipei").strip() or "Asia/Taipei"
DAILY_LATEST_SYNC_TIME_RAW = os.getenv("DAILY_LATEST_SYNC_TIME", "18:10").strip() or "18:10"
FRONTEND_DIST_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"

DEFAULT_WATCH_GROUP_NAME = "我的自選"
MARKET_OVERVIEW_GROUP_NAME = "全球大盤"
DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "BRK-B",
    "2330.TW", "2317.TW", "2454.TW", "2382.TW", "2303.TW",
    "0700.HK", "9988.HK",
]
MARKET_OVERVIEW_TICKERS = [
    "^TWII", "^TWOII", "^GSPC", "^IXIC", "^SOX", "^DJI",
    "^N225", "^HSI", "000001.SS", "^STOXX50E",
    "GC=F", "SI=F", "HG=F", "CL=F", "BZ=F", "NG=F",
]
STARTUP_DOWNLOAD_TICKERS = list(dict.fromkeys(DEFAULT_WATCHLIST + MARKET_OVERVIEW_TICKERS))
TAIFEX_SPOT_REFERENCE = [
    {"ticker": "^TWII", "label": "台灣加權指數"},
    {"ticker": "^TWOII", "label": "櫃買指數"},
    {"ticker": "2330.TW", "label": "台積電"},
    {"ticker": "0050.TW", "label": "元大台灣50"},
]

FULL_HISTORY_PERIODS = {"10y", "max"}
APP_TZ = ZoneInfo(APP_TIMEZONE)
TRACKED_SYNC_LOCK = asyncio.Lock()


# ─── Utility helpers ─────────────────────────────────────────

def _period_to_since(period: str):
    period = (period or "").strip().lower()
    if not period or period == "max":
        return None
    mapping = {
        "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180,
        "1y": 365, "2y": 730, "5y": 1825, "10y": 3650,
    }
    days = mapping.get(period)
    if days is None:
        return None
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


def _parse_daily_sync_time(value: str) -> time_of_day:
    try:
        parts = value.split(":")
        return time_of_day(int(parts[0]), int(parts[1]))
    except Exception:
        return time_of_day(18, 10)


DAILY_LATEST_SYNC_TIME = _parse_daily_sync_time(DAILY_LATEST_SYNC_TIME_RAW)


def _row_date_to_datetime(row_date):
    if isinstance(row_date, datetime):
        return row_date
    if isinstance(row_date, str):
        try:
            return datetime.fromisoformat(row_date)
        except ValueError:
            return None
    return None


def _needs_history_backfill(rows, period: str) -> bool:
    if not rows or len(rows) < 5:
        return True
    since = _period_to_since(period)
    if since is None:
        return len(rows) < 100
    earliest = rows[0].get("date", "") if isinstance(rows[0], dict) else ""
    if not earliest:
        return True
    try:
        return earliest > since
    except TypeError:
        return True


def _has_suspicious_daily_rows(ticker: str, rows, interval: str) -> bool:
    if interval not in ("1d", "1wk") or not rows or len(rows) < 2:
        return False
    last_date = _row_date_to_datetime(rows[-1].get("date")) if isinstance(rows[-1], dict) else None
    if last_date is None:
        return False
    now = datetime.now(timezone.utc)
    gap_days = (now - last_date.replace(tzinfo=timezone.utc if last_date.tzinfo is None else last_date.tzinfo)).days
    threshold = 6 if interval == "1d" else 14
    if gap_days > threshold:
        return True
    return False


# ─── Background tasks ────────────────────────────────────────

async def startup_download():
    log.info("Starting history download for %s tickers...", len(STARTUP_DOWNLOAD_TICKERS))
    for ticker in STARTUP_DOWNLOAD_TICKERS:
        try:
            count = await fetcher.fetch_and_store(ticker, period="2y", include_info=False)
            if count:
                log.info("  %s: %s candle rows stored", ticker, count)
            else:
                log.warning("  %s: no history fetched, will retry on demand", ticker)
            await asyncio.sleep(STARTUP_DOWNLOAD_DELAY_SECONDS)
        except Exception as exc:
            log.warning("  %s download failed: %s", ticker, exc)
    log.info("History download finished")


async def startup_institutional_snapshot():
    try:
        payload = await taifex_fetcher.ensure_daily_snapshot()
        log.info(
            "Institutional snapshot ready: query=%s resolved=%s",
            payload.get("query_date"), payload.get("resolved_date"),
        )
    except Exception as exc:
        log.warning("Institutional snapshot sync failed: %s", exc)


async def get_tracked_sync_tickers() -> list[str]:
    groups = await db.get_watchlist_groups()
    tickers = [
        normalize_ticker(item["ticker"])
        for group in groups
        for item in group.get("items", [])
        if item.get("ticker")
    ]
    if not tickers:
        return list(STARTUP_DOWNLOAD_TICKERS)
    return list(dict.fromkeys(tickers))


async def sync_tracked_market_data(
    period: str = LATEST_DATA_SYNC_PERIOD,
    interval: str = LATEST_DATA_SYNC_INTERVAL,
    reason: str = "manual",
) -> dict:
    normalized_period = (period or LATEST_DATA_SYNC_PERIOD).lower()
    normalized_interval = (interval or LATEST_DATA_SYNC_INTERVAL).lower()
    tickers = await get_tracked_sync_tickers()

    async with TRACKED_SYNC_LOCK:
        log.info(
            "Tracked market sync started: reason=%s tickers=%s period=%s interval=%s",
            reason, len(tickers), normalized_period, normalized_interval,
        )
        successes = []
        failures = []
        total_rows = 0
        for index, ticker in enumerate(tickers):
            try:
                synced = await fetcher.fetch_and_store(
                    ticker, period=normalized_period,
                    interval=normalized_interval, include_info=False,
                )
                total_rows += synced
                successes.append({"ticker": ticker, "synced": synced})
                await db.log_sync(ticker, "success", synced, f"{reason}:{normalized_period}/{normalized_interval}")
            except Exception as exc:
                message = str(exc)
                failures.append({"ticker": ticker, "message": message})
                await db.log_sync(ticker, "error", 0, f"{reason}:{message[:500]}")
                log.warning("Tracked sync failed for %s (%s): %s", ticker, reason, exc)
            if index < len(tickers) - 1:
                await asyncio.sleep(STARTUP_DOWNLOAD_DELAY_SECONDS)

        log.info(
            "Tracked market sync finished: reason=%s success=%s failure=%s rows=%s",
            reason, len(successes), len(failures), total_rows,
        )
        return {
            "reason": reason,
            "period": normalized_period, "interval": normalized_interval,
            "tickers": tickers,
            "success_count": len(successes), "failure_count": len(failures),
            "total_rows": total_rows,
            "results": successes, "failures": failures,
        }


async def daily_latest_sync_loop():
    await asyncio.sleep(15)
    if LATEST_DATA_SYNC_ON_STARTUP:
        try:
            await sync_tracked_market_data(reason="startup-latest")
        except Exception as exc:
            log.warning("Startup latest market sync failed: %s", exc)

    while True:
        now = datetime.now(APP_TZ)
        next_run_date = now.date()
        next_run = datetime.combine(next_run_date, DAILY_LATEST_SYNC_TIME, tzinfo=APP_TZ)
        if now >= next_run:
            next_run_date += timedelta(days=1)
            next_run = datetime.combine(next_run_date, DAILY_LATEST_SYNC_TIME, tzinfo=APP_TZ)
        sleep_seconds = max(60, int((next_run - now).total_seconds()))
        await asyncio.sleep(sleep_seconds)
        try:
            await sync_tracked_market_data(reason="daily-latest")
        except Exception as exc:
            log.warning("Daily latest market sync failed: %s", exc)


async def realtime_polling_loop():
    await asyncio.sleep(5)
    while True:
        subscribed = ws_manager.get_subscribed_tickers()
        if subscribed:
            for ticker in subscribed:
                try:
                    quote = await fetch_and_store_quote_snapshot(ticker)
                    if quote:
                        await ws_manager.broadcast_to_ticker(
                            ticker,
                            {
                                "type": "quote", "ticker": ticker,
                                "data": quote, "ts": int(time.time() * 1000),
                            },
                        )
                except Exception as exc:
                    log.debug("quote error %s: %s", ticker, exc)
                await asyncio.sleep(0.2)
        await asyncio.sleep(15)


async def alert_evaluator_loop():
    await asyncio.sleep(10)
    while True:
        try:
            triggered = await alert_engine.evaluate_active_alerts()
            if triggered:
                log.info("Alert evaluator triggered %s alert(s)", triggered)
        except Exception as exc:
            log.warning("Alert evaluator loop failed: %s", exc)
        await asyncio.sleep(ALERT_POLL_INTERVAL_SECONDS)


async def market_intelligence_sync_loop():
    await asyncio.sleep(12)
    if MARKET_INTELLIGENCE_STARTUP_SYNC:
        try:
            summary = await sync_market_intelligence_snapshot(reason="startup-market-intelligence")
            log.info("Market intelligence startup sync finished: %s", summary)
        except Exception as exc:
            log.warning("Market intelligence startup sync failed: %s", exc)
    while True:
        await asyncio.sleep(6 * 60 * 60)
        try:
            summary = await sync_market_intelligence_snapshot(reason="scheduled-market-intelligence")
            log.info("Market intelligence scheduled sync finished: %s", summary)
        except Exception as exc:
            log.warning("Market intelligence scheduled sync failed: %s", exc)


async def fetch_and_store_quote_snapshot(ticker: str) -> dict | None:
    ticker = normalize_ticker(ticker)
    quote = await quote_provider.fetch_quote(ticker)
    if not quote:
        return None
    return await db.upsert_market_quote(quote)


async def sync_market_intelligence_snapshot(reason: str = "manual") -> dict:
    tickers = await get_tracked_sync_tickers()
    macro_items = await macro_snapshot_provider.sync_macro_snapshots()
    event_count = await market_event_provider.sync_events_for_tickers(tickers)
    news_count = 0
    for ticker in tickers[:20]:
        try:
            articles = await news_provider.sync_ticker_news(ticker, limit=6)
            news_count += len(articles)
        except Exception as exc:
            log.debug("news sync failed for %s (%s): %s", ticker, reason, exc)
    return {
        "reason": reason, "macro_count": len(macro_items),
        "event_count": event_count, "news_count": news_count,
        "tracked_tickers": len(tickers),
    }


# ─── App lifecycle ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("QuantVision Pro backend starting...")
    await init_db()
    await db.ensure_default_watchlist(DEFAULT_WATCHLIST, DEFAULT_WATCH_GROUP_NAME)
    await db.ensure_watchlist_group_items(
        MARKET_OVERVIEW_GROUP_NAME, MARKET_OVERVIEW_TICKERS, sort_order=999,
    )
    if STARTUP_DOWNLOAD_ENABLED:
        asyncio.create_task(startup_download())
    else:
        log.info("Startup Yahoo history prefetch skipped (STARTUP_DOWNLOAD_ENABLED=false).")
    if INSTITUTIONAL_AUTO_SYNC_ENABLED:
        asyncio.create_task(startup_institutional_snapshot())
    else:
        log.info("Startup institutional snapshot sync skipped (INSTITUTIONAL_AUTO_SYNC_ENABLED=false).")
    asyncio.create_task(daily_latest_sync_loop())
    asyncio.create_task(realtime_polling_loop())
    if ALERT_EVALUATOR_ENABLED:
        asyncio.create_task(alert_evaluator_loop())
    else:
        log.info("Alert evaluator skipped (ALERT_EVALUATOR_ENABLED=false).")
    if MARKET_INTELLIGENCE_SYNC_ENABLED:
        asyncio.create_task(market_intelligence_sync_loop())
    else:
        log.info("Market intelligence sync skipped (MARKET_INTELLIGENCE_SYNC_ENABLED=false).")
    yield
    await db.close()
    log.info("QuantVision Pro backend stopped")


app = FastAPI(title="QuantVision Pro API", version="1.0.0", lifespan=lifespan)

# ─── CORS ────────────────────────────────────────────────────

local_dev_origin_regex = (
    rf"^https?://("
    rf"localhost|127\.0\.0\.1|0\.0\.0\.0|"
    rf"192\.168\.\d{{1,3}}\.\d{{1,3}}|"
    rf"10\.\d{{1,3}}\.\d{{1,3}}\.\d{{1,3}}|"
    rf"172\.(1[6-9]|2\d|3[0-1])\.\d{{1,3}}\.\d{{1,3}}"
    rf")(:\d{{2,5}})?$"
)

allowed_origins = list(
    {
        FRONTEND_DEV_URL,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        f"http://localhost:{APP_PORT}",
        f"http://127.0.0.1:{APP_PORT}",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=local_dev_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIST_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")

# ─── Configure router deps & include ────────────────────────

market_data.configure(
    fetch_and_store_quote_snapshot=fetch_and_store_quote_snapshot,
    sync_tracked_market_data=sync_tracked_market_data,
    needs_history_backfill=_needs_history_backfill,
    has_suspicious_daily_rows=_has_suspicious_daily_rows,
    full_history_periods=FULL_HISTORY_PERIODS,
    latest_data_sync_period=LATEST_DATA_SYNC_PERIOD,
    latest_data_sync_interval=LATEST_DATA_SYNC_INTERVAL,
)

intelligence.configure(
    sync_market_intelligence_snapshot=sync_market_intelligence_snapshot,
    fetch_and_store_quote_snapshot=fetch_and_store_quote_snapshot,
    app_tz=APP_TZ,
    taifex_spot_reference=TAIFEX_SPOT_REFERENCE,
)
system.configure(
    frontend_dev_url=FRONTEND_DEV_URL,
    frontend_dist_dir=FRONTEND_DIST_DIR,
)

app.include_router(watchlist.router)
app.include_router(workspace.router)
app.include_router(alerts.router)
app.include_router(journal.router)
app.include_router(backtest.router)
app.include_router(market_data.router)
app.include_router(intelligence.router)
app.include_router(system.router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=APP_PORT, reload=False, log_level="info")
