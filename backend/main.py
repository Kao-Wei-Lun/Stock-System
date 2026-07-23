"""
QuantVision Pro backend API server.

Refactored: routes are in backend/routers/*, schemas in backend/schemas.py.
This file retains app creation, middleware, lifespan, and scheduler wiring.
"""

import asyncio
import logging
import sys
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, time as time_of_day, timedelta, timezone
from pathlib import Path
from types import MethodType
from zoneinfo import ZoneInfo

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from background_tasks import BackgroundTaskService
from data_quality_service import DataQualityService
from database import DEFAULT_OWNER_ID, db, init_db
from env_validation import (
    read_bool_env,
    read_float_env,
    read_hhmm_env,
    read_int_env,
    read_text_env,
    read_timezone_env,
    read_url_env,
    validate_runtime_environment,
)
from futopt_history_service import FutoptCandleRecorder, FutoptRefreshCoordinator
from frontend_static import SPAStaticFiles
from logging_config import configure_logging
from local_access import LocalAccessMiddleware, split_csv
from performance_timing import RequestTimingMiddleware
from realtime_quote_persistence import RealtimeQuotePersistenceBuffer
from macro_regime import build_macro_dashboard_payload
from paper_trading.margin_sync import sync_all_paper_trading_account_margins
from providers import (
    alert_engine,
    fetcher,
    fubon_manager,
    fubon_futopt_provider,
    fubon_realtime_pool,
    fundamentals_provider,
    latest_public_fx_provider,
    macro_snapshot_provider,
    market_event_provider,
    news_provider,
    quote_provider,
    screener_engine,
    taiwan_chip_provider,
    ws_manager,
    fubon_market_snapshot_provider,
)
from routers import alerts, assets, backtest, intelligence, journal, market_data, paper_trading, reports, settings, system, watchlist, workspace
from routers.watchlist import hydrate_watchlist_item
from scheduler import BackgroundScheduler, SchedulerDependencies, SchedulerSettings
from mysql_backup import DEFAULT_BACKUP_DIR, MysqlSettings, create_backup, latest_backup_status, verify_backup
from taifex_fetcher import taifex_fetcher
from taiwan_history_backfill_service import TaiwanHistoryBackfillService, _normalize_intervals
from workload_executor import BoundedWorkloadExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
configure_logging()
log = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────

STARTUP_DOWNLOAD_DELAY_SECONDS = read_float_env("STARTUP_DOWNLOAD_DELAY_SECONDS", "2.5", minimum=0)
APP_PORT = read_int_env("APP_PORT", "8001", minimum=1, maximum=65535)
APP_BIND_HOST = read_text_env("APP_BIND_HOST", "127.0.0.1").strip() or "127.0.0.1"
FRONTEND_DEV_URL = read_url_env("FRONTEND_DEV_URL", "http://localhost:5173")
ALLOW_LAN_ACCESS = read_bool_env("ALLOW_LAN_ACCESS", False)
LAN_ALLOWED_NETWORKS = read_text_env("LAN_ALLOWED_NETWORKS", "")
LAN_ALLOWED_ORIGINS = split_csv(read_text_env("LAN_ALLOWED_ORIGINS", ""))
STARTUP_DOWNLOAD_ENABLED = read_bool_env("STARTUP_DOWNLOAD_ENABLED", False)
INSTITUTIONAL_AUTO_SYNC_ENABLED = read_bool_env("INSTITUTIONAL_AUTO_SYNC_ENABLED", True)
TAIWAN_CHIP_AUTO_SYNC_ENABLED = read_bool_env("TAIWAN_CHIP_AUTO_SYNC_ENABLED", True)
LATEST_DATA_SYNC_PERIOD = read_text_env("LATEST_DATA_SYNC_PERIOD", "1y").strip().lower() or "1y"
LATEST_DATA_SYNC_INTERVAL = read_text_env("LATEST_DATA_SYNC_INTERVAL", "1d").strip().lower() or "1d"
LATEST_DATA_SYNC_ON_STARTUP = read_bool_env("LATEST_DATA_SYNC_ON_STARTUP", True)
TW_FULL_HISTORY_SYNC_ENABLED = read_bool_env("TW_FULL_HISTORY_SYNC_ENABLED", False)
TW_FULL_HISTORY_SYNC_START_RAW = read_hhmm_env("TW_FULL_HISTORY_SYNC_START", "14:00")
TW_FULL_HISTORY_SYNC_STOP_RAW = read_hhmm_env("TW_FULL_HISTORY_SYNC_STOP", "08:00")
TW_FULL_HISTORY_PERIOD = read_text_env("TW_FULL_HISTORY_PERIOD", "max").strip().lower() or "max"
TW_FULL_HISTORY_INCREMENTAL_PERIOD = read_text_env("TW_FULL_HISTORY_INCREMENTAL_PERIOD", "5d").strip().lower() or "5d"
TW_FULL_HISTORY_INTERVALS = _normalize_intervals(read_text_env("TW_FULL_HISTORY_INTERVALS", "1d,1wk,1mo"))
TW_FULL_HISTORY_DELAY_SECONDS = read_float_env("TW_FULL_HISTORY_DELAY_SECONDS", "0.8", minimum=0)
TW_FULL_HISTORY_TICKER_DELAY_SECONDS = read_float_env("TW_FULL_HISTORY_TICKER_DELAY_SECONDS", "2.0", minimum=0)
TW_FULL_HISTORY_INCLUDE_ETF = read_bool_env("TW_FULL_HISTORY_INCLUDE_ETF", True)
TW_FULL_HISTORY_RETRY_INTERVAL_SECONDS = read_int_env(
    "TW_FULL_HISTORY_RETRY_INTERVAL_SECONDS",
    "1800",
    minimum=0,
)
TW_FULL_HISTORY_RETRY_MIN_LATEST_COVERAGE_PCT = read_float_env(
    "TW_FULL_HISTORY_RETRY_MIN_LATEST_COVERAGE_PCT",
    "80",
    minimum=0,
)
ALERT_EVALUATOR_ENABLED = read_bool_env("ALERT_EVALUATOR_ENABLED", True)
ALERT_POLL_INTERVAL_SECONDS = read_int_env("ALERT_POLL_INTERVAL_SECONDS", "30", minimum=10)
MARKET_INTELLIGENCE_SYNC_ENABLED = read_bool_env("MARKET_INTELLIGENCE_SYNC_ENABLED", True)
MARKET_INTELLIGENCE_STARTUP_SYNC = read_bool_env("MARKET_INTELLIGENCE_STARTUP_SYNC", True)
MARKET_INTELLIGENCE_SYNC_INTERVAL_SECONDS = read_int_env(
    "MARKET_INTELLIGENCE_SYNC_INTERVAL_SECONDS",
    "3600",
    minimum=60,
)
FUTOPT_RECORDER_ENABLED = read_bool_env("FUTOPT_RECORDER_ENABLED", True)
PAPER_MARGIN_AUTO_SYNC_ENABLED = read_bool_env("PAPER_MARGIN_AUTO_SYNC_ENABLED", True)
FUTOPT_RECORDER_SYMBOLS_RAW = read_text_env("FUTOPT_RECORDER_SYMBOLS", "TXF,TMF")
FUTOPT_RECORDER_BACKFILL_INTERVAL_SECONDS = read_int_env(
    "FUTOPT_RECORDER_BACKFILL_INTERVAL_SECONDS",
    "300",
    minimum=60,
)
FUTOPT_RECORDER_POLL_SECONDS = read_int_env("FUTOPT_RECORDER_POLL_SECONDS", "30", minimum=5)
FUTOPT_BACKGROUND_STALE_SECONDS = read_float_env("FUTOPT_BACKGROUND_STALE_SECONDS", "90", minimum=1)
FUTOPT_BACKGROUND_EMPTY_WAIT_SECONDS = read_float_env("FUTOPT_BACKGROUND_EMPTY_WAIT_SECONDS", "8", minimum=0.1)
FUTOPT_BACKGROUND_MAX_CONCURRENT_REFRESHES = read_int_env(
    "FUTOPT_BACKGROUND_MAX_CONCURRENT_REFRESHES",
    "2",
    minimum=1,
    maximum=8,
)
ASSET_QUOTE_REFRESH_TIMEOUT_SECONDS = read_float_env("ASSET_QUOTE_REFRESH_TIMEOUT_SECONDS", "8", minimum=0.1)
ASSET_QUOTE_REFRESH_MAX_CONCURRENCY = read_int_env(
    "ASSET_QUOTE_REFRESH_MAX_CONCURRENCY", "6", minimum=1, maximum=32,
)
ASSET_QUOTE_CACHE_TTL_SECONDS = read_float_env("ASSET_QUOTE_CACHE_TTL_SECONDS", "15", minimum=0)
BACKTEST_EXECUTOR_ENABLED = read_bool_env("BACKTEST_EXECUTOR_ENABLED", True)
BACKTEST_TIMEOUT_SECONDS = read_float_env("BACKTEST_TIMEOUT_SECONDS", "30", minimum=0.1)
APP_TIMEZONE = read_timezone_env("APP_TIMEZONE", "Asia/Taipei")
DAILY_LATEST_SYNC_TIME_RAW = read_hhmm_env("DAILY_LATEST_SYNC_TIME", "18:10")
TRACKED_MARKET_SYNC_TIME_RAW = read_hhmm_env("TRACKED_MARKET_SYNC_TIME", DAILY_LATEST_SYNC_TIME_RAW)
TAIWAN_CHIP_SYNC_TIME_RAW = read_hhmm_env("TAIWAN_CHIP_SYNC_TIME", DAILY_LATEST_SYNC_TIME_RAW)
FUBON_MARKET_SNAPSHOT_SYNC_TIME_RAW = read_hhmm_env(
    "FUBON_MARKET_SNAPSHOT_SYNC_TIME",
    DAILY_LATEST_SYNC_TIME_RAW,
)
INSTITUTIONAL_SYNC_TIME_RAW = read_hhmm_env("INSTITUTIONAL_SYNC_TIME", "19:00")
PAPER_MARGIN_SYNC_TIME_RAW = read_hhmm_env("PAPER_MARGIN_SYNC_TIME", DAILY_LATEST_SYNC_TIME_RAW)
REALTIME_POLL_INTERVAL_SECONDS = read_float_env("REALTIME_POLL_INTERVAL_SECONDS", "15", minimum=1)
REALTIME_PER_TICKER_DELAY_SECONDS = read_float_env("REALTIME_PER_TICKER_DELAY_SECONDS", "0.2", minimum=0)
REALTIME_QUOTE_PERSIST_INTERVAL_MS = read_int_env(
    "REALTIME_QUOTE_PERSIST_INTERVAL_MS",
    "500",
    minimum=250,
    maximum=2000,
)
REALTIME_QUOTE_PERSIST_CAPACITY = read_int_env(
    "REALTIME_QUOTE_PERSIST_CAPACITY",
    "500",
    minimum=1,
    maximum=5000,
)
REALTIME_QUOTE_PERSIST_ASYNC_ENABLED = read_bool_env("REALTIME_QUOTE_PERSIST_ASYNC_ENABLED", True)
FUBON_WS_SESSION_REFRESH_SECONDS = read_float_env("FUBON_WS_SESSION_REFRESH_SECONDS", "30", minimum=1)
LATEST_SYNC_STARTUP_DELAY_SECONDS = read_float_env("LATEST_SYNC_STARTUP_DELAY_SECONDS", "15", minimum=0)
FUBON_MARKET_SNAPSHOT_STARTUP_DELAY_SECONDS = read_float_env(
    "FUBON_MARKET_SNAPSHOT_STARTUP_DELAY_SECONDS",
    "20",
    minimum=0,
)
TW_FULL_HISTORY_STARTUP_DELAY_SECONDS = read_float_env("TW_FULL_HISTORY_STARTUP_DELAY_SECONDS", "35", minimum=0)
PAPER_MARGIN_STARTUP_DELAY_SECONDS = read_float_env("PAPER_MARGIN_STARTUP_DELAY_SECONDS", "25", minimum=0)
REALTIME_POLL_STARTUP_DELAY_SECONDS = read_float_env("REALTIME_POLL_STARTUP_DELAY_SECONDS", "5", minimum=0)
ALERT_STARTUP_DELAY_SECONDS = read_float_env("ALERT_STARTUP_DELAY_SECONDS", "10", minimum=0)
MARKET_INTELLIGENCE_STARTUP_DELAY_SECONDS = read_float_env(
    "MARKET_INTELLIGENCE_STARTUP_DELAY_SECONDS",
    "12",
    minimum=0,
)
AUTO_BACKUP_ENABLED = read_bool_env("AUTO_BACKUP_ENABLED", True)
AUTO_BACKUP_SCOPE = read_text_env("AUTO_BACKUP_SCOPE", "critical").strip().lower() or "critical"
if AUTO_BACKUP_SCOPE not in {"full", "critical", "market-history"}:
    raise RuntimeError("AUTO_BACKUP_SCOPE must be 'full', 'critical', or 'market-history'")
AUTO_BACKUP_INTERVAL_HOURS = read_float_env("AUTO_BACKUP_INTERVAL_HOURS", "24", minimum=1)
AUTO_BACKUP_MAX_AGE_HOURS = read_float_env("AUTO_BACKUP_MAX_AGE_HOURS", "36", minimum=1)
AUTO_BACKUP_INITIAL_DELAY_SECONDS = read_float_env("AUTO_BACKUP_INITIAL_DELAY_SECONDS", "300", minimum=0)
AUTO_BACKUP_TIMEOUT_SECONDS = read_int_env("AUTO_BACKUP_TIMEOUT_SECONDS", "1800", minimum=60)
AUTO_BACKUP_RETENTION_DAYS = read_int_env("AUTO_BACKUP_RETENTION_DAYS", "30", minimum=0)
AUTO_BACKUP_KEEP_MINIMUM = read_int_env("AUTO_BACKUP_KEEP_MINIMUM", "7", minimum=1)
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
FUTOPT_RECORDER_SYMBOLS = [
    symbol.strip().upper()
    for symbol in FUTOPT_RECORDER_SYMBOLS_RAW.split(",")
    if symbol.strip()
] or ["TXF", "TMF"]

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
TRACKED_MARKET_SYNC_TIME = _parse_daily_sync_time(TRACKED_MARKET_SYNC_TIME_RAW)
TAIWAN_CHIP_SYNC_TIME = _parse_daily_sync_time(TAIWAN_CHIP_SYNC_TIME_RAW)
FUBON_MARKET_SNAPSHOT_SYNC_TIME = _parse_daily_sync_time(FUBON_MARKET_SNAPSHOT_SYNC_TIME_RAW)
INSTITUTIONAL_SYNC_TIME = _parse_daily_sync_time(INSTITUTIONAL_SYNC_TIME_RAW)
PAPER_MARGIN_SYNC_TIME = _parse_daily_sync_time(PAPER_MARGIN_SYNC_TIME_RAW)
TW_FULL_HISTORY_SYNC_START_TIME = _parse_daily_sync_time(TW_FULL_HISTORY_SYNC_START_RAW)
TW_FULL_HISTORY_SYNC_STOP_TIME = _parse_daily_sync_time(TW_FULL_HISTORY_SYNC_STOP_RAW)


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
tw_history_backfill_service = TaiwanHistoryBackfillService(
    db=db,
    fetcher=fetcher,
    market_snapshot_provider=fubon_market_snapshot_provider,
    app_tz=APP_TZ,
    history_period=TW_FULL_HISTORY_PERIOD,
    incremental_period=TW_FULL_HISTORY_INCREMENTAL_PERIOD,
    intervals=TW_FULL_HISTORY_INTERVALS,
    request_delay_seconds=TW_FULL_HISTORY_DELAY_SECONDS,
    ticker_delay_seconds=TW_FULL_HISTORY_TICKER_DELAY_SECONDS,
    include_etf=TW_FULL_HISTORY_INCLUDE_ETF,
    logger=log,
)

get_tracked_sync_tickers = background_tasks.get_tracked_sync_tickers
sync_tracked_market_data = background_tasks.sync_tracked_market_data
fetch_and_store_quote_snapshot = background_tasks.fetch_and_store_quote_snapshot
store_realtime_quote = background_tasks.store_realtime_quote
quote_persistence_buffer = RealtimeQuotePersistenceBuffer(
    background_tasks.persist_realtime_quote,
    flush_interval_ms=REALTIME_QUOTE_PERSIST_INTERVAL_MS,
    capacity=REALTIME_QUOTE_PERSIST_CAPACITY,
    logger=log,
)
sync_market_intelligence_snapshot = background_tasks.sync_market_intelligence_snapshot
fetch_startup_history_for_ticker = background_tasks.fetch_startup_history_for_ticker
sync_taiwan_full_history = tw_history_backfill_service.sync_history
fubon_realtime_pool.configure_store_quote(store_realtime_quote)
futopt_candle_recorder = FutoptCandleRecorder(
    provider=fubon_futopt_provider,
    db=db,
    realtime_pool=fubon_realtime_pool,
    symbols=FUTOPT_RECORDER_SYMBOLS,
    logger=log,
)
futopt_refresh_coordinator = FutoptRefreshCoordinator(
    provider=fubon_futopt_provider,
    db=db,
    stale_after_seconds=FUTOPT_BACKGROUND_STALE_SECONDS,
    empty_wait_seconds=FUTOPT_BACKGROUND_EMPTY_WAIT_SECONDS,
    max_concurrent_refreshes=FUTOPT_BACKGROUND_MAX_CONCURRENT_REFRESHES,
    logger=log,
)


async def sync_paper_trading_margins(reason: str = "scheduled") -> dict:
    return await sync_all_paper_trading_account_margins(
        db,
        fubon_futopt_provider,
        owner_id=DEFAULT_OWNER_ID,
        app_tz=APP_TZ,
        reason=reason,
    )


def get_mysql_backup_health() -> dict:
    return latest_backup_status(DEFAULT_BACKUP_DIR, max_age_hours=AUTO_BACKUP_MAX_AGE_HOURS)


def get_scheduled_mysql_backup_health() -> dict:
    return latest_backup_status(
        DEFAULT_BACKUP_DIR,
        max_age_hours=AUTO_BACKUP_MAX_AGE_HOURS,
        scope=AUTO_BACKUP_SCOPE,
    )


def create_scheduled_mysql_backup() -> dict:
    result = create_backup(
        MysqlSettings.from_env(),
        backup_dir=DEFAULT_BACKUP_DIR,
        retention_days=AUTO_BACKUP_RETENTION_DAYS,
        keep_minimum=AUTO_BACKUP_KEEP_MINIMUM,
        scope=AUTO_BACKUP_SCOPE,
        timeout_seconds=AUTO_BACKUP_TIMEOUT_SECONDS,
    )
    verification = verify_backup(Path(result["backup_dir"]) / result["manifest_file"])
    return {**result, "verified": bool(verification.get("valid"))}


background_scheduler = BackgroundScheduler(
    settings=SchedulerSettings(
        startup_download_enabled=STARTUP_DOWNLOAD_ENABLED,
        institutional_auto_sync_enabled=INSTITUTIONAL_AUTO_SYNC_ENABLED,
        taiwan_chip_auto_sync_enabled=TAIWAN_CHIP_AUTO_SYNC_ENABLED,
        latest_data_sync_on_startup=LATEST_DATA_SYNC_ON_STARTUP,
        alert_evaluator_enabled=ALERT_EVALUATOR_ENABLED,
        market_intelligence_sync_enabled=MARKET_INTELLIGENCE_SYNC_ENABLED,
        market_intelligence_startup_sync=MARKET_INTELLIGENCE_STARTUP_SYNC,
        alert_poll_interval_seconds=ALERT_POLL_INTERVAL_SECONDS,
        app_tz=APP_TZ,
        daily_latest_sync_time=DAILY_LATEST_SYNC_TIME,
        tracked_market_sync_time=TRACKED_MARKET_SYNC_TIME,
        taiwan_chip_sync_time=TAIWAN_CHIP_SYNC_TIME,
        fubon_market_snapshot_sync_time=FUBON_MARKET_SNAPSHOT_SYNC_TIME,
        institutional_sync_time=INSTITUTIONAL_SYNC_TIME,
        paper_margin_sync_time=PAPER_MARGIN_SYNC_TIME,
        market_intelligence_sync_interval_seconds=MARKET_INTELLIGENCE_SYNC_INTERVAL_SECONDS,
        realtime_poll_interval_seconds=REALTIME_POLL_INTERVAL_SECONDS,
        realtime_per_ticker_delay_seconds=REALTIME_PER_TICKER_DELAY_SECONDS,
        fubon_ws_session_refresh_seconds=FUBON_WS_SESSION_REFRESH_SECONDS,
        latest_sync_startup_delay_seconds=LATEST_SYNC_STARTUP_DELAY_SECONDS,
        fubon_market_snapshot_startup_delay_seconds=FUBON_MARKET_SNAPSHOT_STARTUP_DELAY_SECONDS,
        tw_full_history_startup_delay_seconds=TW_FULL_HISTORY_STARTUP_DELAY_SECONDS,
        paper_margin_startup_delay_seconds=PAPER_MARGIN_STARTUP_DELAY_SECONDS,
        realtime_poll_startup_delay_seconds=REALTIME_POLL_STARTUP_DELAY_SECONDS,
        alert_startup_delay_seconds=ALERT_STARTUP_DELAY_SECONDS,
        market_intelligence_startup_delay_seconds=MARKET_INTELLIGENCE_STARTUP_DELAY_SECONDS,
        startup_download_delay_seconds=STARTUP_DOWNLOAD_DELAY_SECONDS,
        futopt_recorder_enabled=FUTOPT_RECORDER_ENABLED,
        futopt_recorder_poll_seconds=FUTOPT_RECORDER_POLL_SECONDS,
        futopt_recorder_backfill_interval_seconds=FUTOPT_RECORDER_BACKFILL_INTERVAL_SECONDS,
        paper_margin_auto_sync_enabled=PAPER_MARGIN_AUTO_SYNC_ENABLED,
        tw_full_history_sync_enabled=TW_FULL_HISTORY_SYNC_ENABLED,
        tw_full_history_sync_start_time=TW_FULL_HISTORY_SYNC_START_TIME,
        tw_full_history_sync_stop_time=TW_FULL_HISTORY_SYNC_STOP_TIME,
        tw_full_history_retry_interval_seconds=TW_FULL_HISTORY_RETRY_INTERVAL_SECONDS,
        tw_full_history_retry_min_latest_coverage_pct=TW_FULL_HISTORY_RETRY_MIN_LATEST_COVERAGE_PCT,
        auto_backup_enabled=AUTO_BACKUP_ENABLED,
        auto_backup_scope=AUTO_BACKUP_SCOPE,
        auto_backup_interval_hours=AUTO_BACKUP_INTERVAL_HOURS,
        auto_backup_max_age_hours=AUTO_BACKUP_MAX_AGE_HOURS,
        auto_backup_initial_delay_seconds=AUTO_BACKUP_INITIAL_DELAY_SECONDS,
    ),
    dependencies=SchedulerDependencies(
        startup_download_tickers=STARTUP_DOWNLOAD_TICKERS,
        fetch_history_for_ticker=fetch_startup_history_for_ticker,
        sync_institutional_snapshot=taifex_fetcher.ensure_daily_snapshot,
        sync_taiwan_chip_snapshot=taiwan_chip_provider.ensure_daily_snapshot,
        sync_tracked_market_data=sync_tracked_market_data,
        fetch_and_store_quote_snapshot=fetch_and_store_quote_snapshot,
        evaluate_active_alerts=alert_engine.evaluate_active_alerts,
        sync_market_intelligence_snapshot=sync_market_intelligence_snapshot,
        get_subscribed_tickers=ws_manager.get_subscribed_tickers,
        broadcast_to_ticker=ws_manager.broadcast_to_ticker,
        store_quote_to_db=(
            quote_persistence_buffer.enqueue
            if REALTIME_QUOTE_PERSIST_ASYNC_ENABLED
            else store_realtime_quote
        ),
        fubon_manager=fubon_realtime_pool,
        skip_poll_for_ticker=lambda ticker: fubon_realtime_pool.supports_full_ws_quotes_for_ticker(ticker),
        archive_fubon_market_snapshot=fubon_market_snapshot_provider.archive_daily_snapshot,
        futopt_candle_recorder=futopt_candle_recorder,
        sync_paper_trading_margins=sync_paper_trading_margins,
        sync_taiwan_full_history=sync_taiwan_full_history,
        get_taiwan_analysis_kline_coverage=db.get_tw_analysis_kline_coverage,
        create_mysql_backup=create_scheduled_mysql_backup,
        get_mysql_backup_status=get_scheduled_mysql_backup_health,
    ),
    logger=log,
)
data_quality_service = DataQualityService(
    db=db,
    scheduler=background_scheduler,
    fubon_pool=fubon_realtime_pool,
    ws_manager=ws_manager,
    futopt_recorder=futopt_candle_recorder,
    futopt_enabled=FUTOPT_RECORDER_ENABLED,
    backup_status_provider=get_mysql_backup_health,
)
backtest_workload_executor = BoundedWorkloadExecutor(
    name="backtest",
    max_workers=1,
    timeout_seconds=BACKTEST_TIMEOUT_SECONDS,
    enabled=BACKTEST_EXECUTOR_ENABLED,
    executor_kind="process",
)


# ─── App lifecycle ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("QuantVision Pro backend starting...")

    backtest_workload_executor.startup()
    futopt_refresh_coordinator.startup()
    validate_runtime_environment()
    await init_db()
    await db.ensure_default_watchlist(DEFAULT_WATCHLIST, DEFAULT_WATCH_GROUP_NAME)
    await db.ensure_watchlist_group_items(
        MARKET_OVERVIEW_GROUP_NAME, MARKET_OVERVIEW_TICKERS, sort_order=999,
    )
    if getattr(db, "_pool", None) is not None:
        # Database-backed screens are ready before external providers finish
        # their multi-account login sequence. The pool exposes warmup progress
        # through readiness and settings APIs while initialization continues.
        fubon_realtime_pool.start_background_warmup(db)
    background_scheduler.start()
    try:
        yield
    finally:
        await background_scheduler.shutdown()
        await quote_persistence_buffer.shutdown()
        await futopt_refresh_coordinator.shutdown()
        await assets.shutdown()
        await backtest_workload_executor.shutdown()
        await fubon_realtime_pool.shutdown_async()
        fubon_manager.shutdown()
        await db.close()
        log.info("QuantVision Pro backend stopped")


app = FastAPI(title="QuantVision Pro API", version="1.0.0", lifespan=lifespan)


def _install_quiet_router_lifespan(app: FastAPI) -> None:
    router = app.router

    async def quiet_lifespan(self, scope, receive, send):
        started = False
        lifespan_app = scope.get("app")
        await receive()
        try:
            async with self.lifespan_context(lifespan_app) as maybe_state:
                if maybe_state is not None:
                    if "state" not in scope:
                        raise RuntimeError('The server does not support "state" in the lifespan scope.')
                    scope["state"].update(maybe_state)
                await send({"type": "lifespan.startup.complete"})
                started = True
                await receive()
        except asyncio.CancelledError:
            if started:
                log.info("Lifespan shutdown cancelled during reload; treating it as a normal shutdown.")
                await send({"type": "lifespan.shutdown.complete"})
                return
            raise
        except BaseException:
            exc_text = traceback.format_exc()
            if started:
                await send({"type": "lifespan.shutdown.failed", "message": exc_text})
            else:
                await send({"type": "lifespan.startup.failed", "message": exc_text})
            raise
        else:
            await send({"type": "lifespan.shutdown.complete"})

    router.lifespan = MethodType(quiet_lifespan, router)


_install_quiet_router_lifespan(app)

# ─── CORS ────────────────────────────────────────────────────

local_origin_hosts = rf"localhost|127\.0\.0\.1|0\.0\.0\.0"
local_dev_origin_regex = rf"^https?://({local_origin_hosts})(:\d{{2,5}})?$"

allowed_origins = list(
    {
        FRONTEND_DEV_URL,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        f"http://localhost:{APP_PORT}",
        f"http://127.0.0.1:{APP_PORT}",
    }
)
if ALLOW_LAN_ACCESS:
    allowed_origins.extend(LAN_ALLOWED_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=local_dev_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["Server-Timing", "X-Request-ID"],
)
app.add_middleware(
    LocalAccessMiddleware,
    allow_lan=ALLOW_LAN_ACCESS,
    allowed_networks=LAN_ALLOWED_NETWORKS,
)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)

if FRONTEND_DIST_DIR.exists():
    app.mount("/app", SPAStaticFiles(directory=FRONTEND_DIST_DIR), name="frontend")

# ─── Configure router deps & include ────────────────────────

market_data.configure(
    fetch_and_store_quote_snapshot=fetch_and_store_quote_snapshot,
    sync_tracked_market_data=sync_tracked_market_data,
    needs_history_backfill=_needs_history_backfill,
    has_suspicious_daily_rows=_has_suspicious_daily_rows,
    full_history_periods=FULL_HISTORY_PERIODS,
    latest_data_sync_period=LATEST_DATA_SYNC_PERIOD,
    latest_data_sync_interval=LATEST_DATA_SYNC_INTERVAL,
    sync_taiwan_full_history=sync_taiwan_full_history,
    futopt_candle_recorder=futopt_candle_recorder,
    futopt_refresh_coordinator=futopt_refresh_coordinator,
)
assets.configure(
    fetch_and_store_quote_snapshot=fetch_and_store_quote_snapshot,
    latest_public_fx_provider=latest_public_fx_provider,
    quote_refresh_timeout_seconds=ASSET_QUOTE_REFRESH_TIMEOUT_SECONDS,
    quote_refresh_max_concurrency=ASSET_QUOTE_REFRESH_MAX_CONCURRENCY,
    quote_cache_ttl_seconds=ASSET_QUOTE_CACHE_TTL_SECONDS,
)
backtest.configure(executor=backtest_workload_executor)

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
    database=db,
    data_quality_service=data_quality_service,
    quote_persistence_buffer=quote_persistence_buffer,
    backtest_workload_executor=backtest_workload_executor,
    asset_quote_status_provider=assets.performance_status,
    provider_warmup_status_provider=fubon_realtime_pool.get_warmup_status,
)

app.include_router(watchlist.router)
app.include_router(workspace.router)
app.include_router(alerts.router)
app.include_router(assets.router)
app.include_router(journal.router)
app.include_router(backtest.router)
app.include_router(market_data.router)
app.include_router(intelligence.router)
app.include_router(settings.router)
app.include_router(system.router)
app.include_router(paper_trading.router)
app.include_router(reports.router)


if __name__ == "__main__":
    validate_runtime_environment()
    uvicorn.run("main:app", host=APP_BIND_HOST, port=APP_PORT, reload=False, log_level="info", use_colors=False)
