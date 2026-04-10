"""
QuantVision Pro backend API server.

Refactored: routes are in backend/routers/*, schemas in backend/schemas.py.
This file retains app creation, middleware, lifespan, and scheduler wiring.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, time as time_of_day, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from background_tasks import BackgroundTaskService
from database import db, init_db
from env_validation import (
    read_bool_env,
    read_hhmm_env,
    read_int_env,
    read_text_env,
    read_timezone_env,
    read_url_env,
    validate_runtime_environment,
)
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
from scheduler import BackgroundScheduler, SchedulerDependencies, SchedulerSettings
from taifex_fetcher import taifex_fetcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

load_dotenv()

# ─── Configuration ───────────────────────────────────────────

STARTUP_DOWNLOAD_DELAY_SECONDS = 2.5
APP_PORT = read_int_env("APP_PORT", "8001", minimum=1, maximum=65535)
FRONTEND_DEV_URL = read_url_env("FRONTEND_DEV_URL", "http://localhost:5173")
STARTUP_DOWNLOAD_ENABLED = read_bool_env("STARTUP_DOWNLOAD_ENABLED", False)
INSTITUTIONAL_AUTO_SYNC_ENABLED = read_bool_env("INSTITUTIONAL_AUTO_SYNC_ENABLED", True)
LATEST_DATA_SYNC_PERIOD = read_text_env("LATEST_DATA_SYNC_PERIOD", "1y").strip().lower() or "1y"
LATEST_DATA_SYNC_INTERVAL = read_text_env("LATEST_DATA_SYNC_INTERVAL", "1d").strip().lower() or "1d"
LATEST_DATA_SYNC_ON_STARTUP = read_bool_env("LATEST_DATA_SYNC_ON_STARTUP", True)
ALERT_EVALUATOR_ENABLED = read_bool_env("ALERT_EVALUATOR_ENABLED", True)
ALERT_POLL_INTERVAL_SECONDS = read_int_env("ALERT_POLL_INTERVAL_SECONDS", "30", minimum=10)
MARKET_INTELLIGENCE_SYNC_ENABLED = read_bool_env("MARKET_INTELLIGENCE_SYNC_ENABLED", True)
MARKET_INTELLIGENCE_STARTUP_SYNC = read_bool_env("MARKET_INTELLIGENCE_STARTUP_SYNC", True)
APP_TIMEZONE = read_timezone_env("APP_TIMEZONE", "Asia/Taipei")
DAILY_LATEST_SYNC_TIME_RAW = read_hhmm_env("DAILY_LATEST_SYNC_TIME", "18:10")
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

background_tasks = BackgroundTaskService(
    db=db,
    fetcher=fetcher,
    quote_provider=quote_provider,
    macro_snapshot_provider=macro_snapshot_provider,
    market_event_provider=market_event_provider,
    news_provider=news_provider,
    startup_download_tickers=STARTUP_DOWNLOAD_TICKERS,
    startup_download_delay_seconds=STARTUP_DOWNLOAD_DELAY_SECONDS,
    latest_data_sync_period=LATEST_DATA_SYNC_PERIOD,
    latest_data_sync_interval=LATEST_DATA_SYNC_INTERVAL,
    logger=log,
)

get_tracked_sync_tickers = background_tasks.get_tracked_sync_tickers
sync_tracked_market_data = background_tasks.sync_tracked_market_data
fetch_and_store_quote_snapshot = background_tasks.fetch_and_store_quote_snapshot
sync_market_intelligence_snapshot = background_tasks.sync_market_intelligence_snapshot
fetch_startup_history_for_ticker = background_tasks.fetch_startup_history_for_ticker


background_scheduler = BackgroundScheduler(
    settings=SchedulerSettings(
        startup_download_enabled=STARTUP_DOWNLOAD_ENABLED,
        institutional_auto_sync_enabled=INSTITUTIONAL_AUTO_SYNC_ENABLED,
        latest_data_sync_on_startup=LATEST_DATA_SYNC_ON_STARTUP,
        alert_evaluator_enabled=ALERT_EVALUATOR_ENABLED,
        market_intelligence_sync_enabled=MARKET_INTELLIGENCE_SYNC_ENABLED,
        market_intelligence_startup_sync=MARKET_INTELLIGENCE_STARTUP_SYNC,
        alert_poll_interval_seconds=ALERT_POLL_INTERVAL_SECONDS,
        app_tz=APP_TZ,
        daily_latest_sync_time=DAILY_LATEST_SYNC_TIME,
        startup_download_delay_seconds=STARTUP_DOWNLOAD_DELAY_SECONDS,
    ),
    dependencies=SchedulerDependencies(
        startup_download_tickers=STARTUP_DOWNLOAD_TICKERS,
        fetch_history_for_ticker=fetch_startup_history_for_ticker,
        sync_institutional_snapshot=taifex_fetcher.ensure_daily_snapshot,
        sync_tracked_market_data=sync_tracked_market_data,
        fetch_and_store_quote_snapshot=fetch_and_store_quote_snapshot,
        evaluate_active_alerts=alert_engine.evaluate_active_alerts,
        sync_market_intelligence_snapshot=sync_market_intelligence_snapshot,
        get_subscribed_tickers=ws_manager.get_subscribed_tickers,
        broadcast_to_ticker=ws_manager.broadcast_to_ticker,
    ),
    logger=log,
)


# ─── App lifecycle ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("QuantVision Pro backend starting...")

    validate_runtime_environment()
    await init_db()
    await db.ensure_default_watchlist(DEFAULT_WATCHLIST, DEFAULT_WATCH_GROUP_NAME)
    await db.ensure_watchlist_group_items(
        MARKET_OVERVIEW_GROUP_NAME, MARKET_OVERVIEW_TICKERS, sort_order=999,
    )
    background_scheduler.start()
    yield
    await background_scheduler.shutdown()
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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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
    scheduler=background_scheduler,
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
    validate_runtime_environment()
    uvicorn.run("main:app", host="0.0.0.0", port=APP_PORT, reload=False, log_level="info")
