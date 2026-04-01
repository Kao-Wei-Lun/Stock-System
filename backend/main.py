"""
QuantVision Pro backend API server.
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, time as time_of_day, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from alert_engine import AlertEngine
from backtest_engine import list_backtest_strategies, run_backtest
from data_fetcher import DataFetcher, normalize_ticker
from database import DEFAULT_OWNER_ID, db, init_db
from display_name_resolver import resolve_display_name
from quote_provider import YahooFinanceQuoteProvider
from taifex_fetcher import taifex_fetcher
from tw_symbol_lookup import search_taiwan_tickers
from ws_manager import ConnectionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

load_dotenv()

fetcher = DataFetcher()
quote_provider = YahooFinanceQuoteProvider(fetcher)
alert_engine = AlertEngine(db, quote_provider)
ws_manager = ConnectionManager()

STARTUP_DOWNLOAD_DELAY_SECONDS = 2.5
APP_PORT = int(os.getenv("APP_PORT", "8001"))
FRONTEND_DEV_URL = os.getenv("FRONTEND_DEV_URL", "http://localhost:5173").rstrip("/")
STARTUP_DOWNLOAD_ENABLED = os.getenv("STARTUP_DOWNLOAD_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
INSTITUTIONAL_AUTO_SYNC_ENABLED = os.getenv("INSTITUTIONAL_AUTO_SYNC_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
LATEST_DATA_SYNC_PERIOD = os.getenv("LATEST_DATA_SYNC_PERIOD", "1y").strip().lower() or "1y"
LATEST_DATA_SYNC_INTERVAL = os.getenv("LATEST_DATA_SYNC_INTERVAL", "1d").strip().lower() or "1d"
LATEST_DATA_SYNC_ON_STARTUP = os.getenv("LATEST_DATA_SYNC_ON_STARTUP", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ALERT_EVALUATOR_ENABLED = os.getenv("ALERT_EVALUATOR_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ALERT_POLL_INTERVAL_SECONDS = max(10, int(os.getenv("ALERT_POLL_INTERVAL_SECONDS", "30")))
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Taipei").strip() or "Asia/Taipei"
DAILY_LATEST_SYNC_TIME_RAW = os.getenv("DAILY_LATEST_SYNC_TIME", "18:10").strip() or "18:10"
FRONTEND_DIST_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"

DEFAULT_WATCH_GROUP_NAME = "我的自選"
MARKET_OVERVIEW_GROUP_NAME = "全球大盤"
DEFAULT_WATCHLIST = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "META",
    "AMZN",
    "TSLA",
    "BRK-B",
    "2330.TW",
    "2317.TW",
    "2454.TW",
    "2382.TW",
    "2303.TW",
    "0700.HK",
    "9988.HK",
]
MARKET_OVERVIEW_TICKERS = [
    "^TWII",
    "^TWOII",
    "^GSPC",
    "^IXIC",
    "^SOX",
    "^DJI",
    "^N225",
    "^HSI",
    "000001.SS",
    "^STOXX50E",
    "GC=F",
    "SI=F",
    "HG=F",
    "CL=F",
    "BZ=F",
    "NG=F",
]
STARTUP_DOWNLOAD_TICKERS = list(dict.fromkeys(DEFAULT_WATCHLIST + MARKET_OVERVIEW_TICKERS))
CATEGORY_OVERRIDES = {
    "^TWII": "台灣指數",
    "^TWOII": "台灣指數",
    "^GSPC": "美股指數",
    "^IXIC": "美股指數",
    "^SOX": "美股指數",
    "^DJI": "美股指數",
    "^N225": "亞洲指數",
    "^HSI": "亞洲指數",
    "000001.SS": "亞洲指數",
    "^STOXX50E": "歐洲指數",
    "GC=F": "原物料",
    "SI=F": "原物料",
    "HG=F": "原物料",
    "CL=F": "原物料",
    "BZ=F": "原物料",
    "NG=F": "原物料",
}
TAIFEX_SPOT_REFERENCE = [
    {"ticker": "^TWII", "label": "台灣加權指數"},
    {"ticker": "^TWOII", "label": "櫃買指數"},
    {"ticker": "2330.TW", "label": "台積電"},
    {"ticker": "0050.TW", "label": "元大台灣50"},
]

FULL_HISTORY_PERIODS = {"10y", "max"}
APP_TZ = ZoneInfo(APP_TIMEZONE)
TRACKED_SYNC_LOCK = asyncio.Lock()


def _period_to_since(period: str):
    period = (period or "").strip().lower()
    if not period or period == "max":
        return None
    if period.endswith("mo") and period[:-2].isdigit():
        return datetime.utcnow() - timedelta(days=int(period[:-2]) * 30)
    if period.endswith("wk") and period[:-2].isdigit():
        return datetime.utcnow() - timedelta(days=int(period[:-2]) * 7)
    if period.endswith("y") and period[:-1].isdigit():
        return datetime.utcnow() - timedelta(days=int(period[:-1]) * 365)
    if period.endswith("d") and period[:-1].isdigit():
        return datetime.utcnow() - timedelta(days=int(period[:-1]))
    return datetime.utcnow() - timedelta(days=365)


def _parse_daily_sync_time(value: str) -> time_of_day:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time_of_day(hour=hour, minute=minute)
    except (TypeError, ValueError):
        pass
    log.warning("Invalid DAILY_LATEST_SYNC_TIME=%s, fallback to 18:10", value)
    return time_of_day(hour=18, minute=10)


DAILY_LATEST_SYNC_TIME = _parse_daily_sync_time(DAILY_LATEST_SYNC_TIME_RAW)


def _row_date_to_datetime(row_date):
    if isinstance(row_date, datetime):
        return row_date
    if not row_date:
        return None
    try:
        return datetime.fromisoformat(str(row_date))
    except ValueError:
        return None


def _needs_history_backfill(rows, period: str) -> bool:
    if not rows:
        return True
    if period in FULL_HISTORY_PERIODS:
        return True

    expected_since = _period_to_since(period)
    oldest = _row_date_to_datetime(rows[0].get("date"))
    if not expected_since or not oldest:
        return False

    grace_days = 5 if period.endswith("d") else 21
    return oldest > expected_since + timedelta(days=grace_days)


def _has_suspicious_daily_rows(ticker: str, rows, interval: str) -> bool:
    if interval != "1d" or not rows or ticker.endswith("-USD"):
        return False
    prev_date = None
    for row in rows:
        row_date = _row_date_to_datetime(row.get("date"))
        if row_date and row_date.weekday() >= 5:
            return True
        if prev_date and row_date and (row_date - prev_date).days > 20:
            return True
        if row_date:
            prev_date = row_date
    return False


class WatchlistGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)


class WatchlistGroupUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)


class WatchlistItemCreate(BaseModel):
    group_id: int
    ticker: str = Field(..., min_length=1, max_length=32)


class WatchlistItemsOrderUpdate(BaseModel):
    item_ids: list[int] = Field(..., min_length=1)


class WorkspacePresetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    chart_layout: str = Field("single", max_length=32)
    active_ticker: str | None = Field(None, max_length=32)
    current_period: str = Field("1y", max_length=16)
    current_interval: str = Field("1d", max_length=16)
    workspace_tab: str = Field("chart", max_length=32)
    comparison_mode: str = Field("percent", max_length=32)
    payload: dict = Field(default_factory=dict)
    is_default: bool = False


class WorkspacePresetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    chart_layout: str | None = Field(None, max_length=32)
    active_ticker: str | None = Field(None, max_length=32)
    current_period: str | None = Field(None, max_length=16)
    current_interval: str | None = Field(None, max_length=16)
    workspace_tab: str | None = Field(None, max_length=32)
    comparison_mode: str | None = Field(None, max_length=32)
    payload: dict | None = None
    is_default: bool | None = None


class AlertCreatePayload(BaseModel):
    name: str | None = Field(None, max_length=128)
    ticker: str = Field(..., min_length=1, max_length=32)
    type: str = Field(..., min_length=1, max_length=32)
    condition: str = Field(..., min_length=1, max_length=32)
    value: float | None = None
    value2: float | None = None
    timeframe: str = Field("1d", max_length=16)
    condition_payload: dict = Field(default_factory=dict)
    notification_title: str | None = Field(None, max_length=255)
    note: str | None = None
    active: bool = True
    triggered: bool = False
    triggered_at: str | None = None
    last_evaluated_at: str | None = None


class AlertUpdatePayload(BaseModel):
    name: str | None = Field(None, max_length=128)
    ticker: str | None = Field(None, min_length=1, max_length=32)
    type: str | None = Field(None, min_length=1, max_length=32)
    condition: str | None = Field(None, min_length=1, max_length=32)
    value: float | None = None
    value2: float | None = None
    timeframe: str | None = Field(None, max_length=16)
    condition_payload: dict | None = None
    notification_title: str | None = Field(None, max_length=255)
    note: str | None = None
    active: bool | None = None
    triggered: bool | None = None
    triggered_at: str | None = None
    last_evaluated_at: str | None = None


class QuoteResponse(BaseModel):
    ticker: str
    source: str
    quote_type: str
    is_delayed: bool
    quote_timestamp: str | None = None
    synced_at: str | None = None
    name: str | None = None
    currency: str | None = None
    price: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: int | None = None
    market_cap: int | None = None
    ts: int | None = None


class BacktestRunCreatePayload(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=32)
    strategy: str = Field(..., min_length=1, max_length=128)
    start: str = Field(..., min_length=10, max_length=32)
    end: str = Field(..., min_length=10, max_length=32)
    interval: str = Field("1d", max_length=16)
    capital: float = Field(..., gt=0)
    fee: float = Field(0.0, ge=0, le=100)
    slippage: float = Field(0.0, ge=0, le=100)
    sl: float | None = Field(None, ge=0, le=100)
    tp: float | None = Field(None, ge=0, le=100)
    position_sizing: str = Field("full_equity", max_length=32)


class NotificationReadStatePayload(BaseModel):
    read: bool = True


class TradeJournalAttachmentPayload(BaseModel):
    file_path: str = Field(..., min_length=1, max_length=512)
    file_type: str | None = Field(None, max_length=64)


class TradeJournalEntryCreatePayload(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=32)
    market: str | None = Field(None, max_length=32)
    direction: str = Field("long", max_length=16)
    strategy_code: str | None = Field(None, max_length=64)
    entry_time: str = Field(..., min_length=10, max_length=64)
    entry_price: float = Field(..., gt=0)
    exit_time: str | None = Field(None, max_length=64)
    exit_price: float | None = None
    size: float = Field(..., gt=0)
    stop_loss: float | None = None
    take_profit: float | None = None
    entry_reason: str | None = None
    exit_reason: str | None = None
    emotion_tag: str | None = Field(None, max_length=64)
    review_notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    attachments: list[TradeJournalAttachmentPayload] = Field(default_factory=list)
    result: dict = Field(default_factory=dict)


class TradeJournalEntryUpdatePayload(BaseModel):
    ticker: str | None = Field(None, min_length=1, max_length=32)
    market: str | None = Field(None, max_length=32)
    direction: str | None = Field(None, max_length=16)
    strategy_code: str | None = Field(None, max_length=64)
    entry_time: str | None = Field(None, min_length=10, max_length=64)
    entry_price: float | None = Field(None, gt=0)
    exit_time: str | None = Field(None, max_length=64)
    exit_price: float | None = None
    size: float | None = Field(None, gt=0)
    stop_loss: float | None = None
    take_profit: float | None = None
    entry_reason: str | None = None
    exit_reason: str | None = None
    emotion_tag: str | None = Field(None, max_length=64)
    review_notes: str | None = None
    tags: list[str] | None = None
    attachments: list[TradeJournalAttachmentPayload] | None = None
    result: dict | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("QuantVision Pro backend starting...")
    await init_db()
    await db.ensure_default_watchlist(DEFAULT_WATCHLIST, DEFAULT_WATCH_GROUP_NAME)
    await db.ensure_watchlist_group_items(
        MARKET_OVERVIEW_GROUP_NAME,
        MARKET_OVERVIEW_TICKERS,
        sort_order=999,
    )
    if STARTUP_DOWNLOAD_ENABLED:
        asyncio.create_task(startup_download())
    else:
        log.info(
            "Startup Yahoo history prefetch skipped "
            "(STARTUP_DOWNLOAD_ENABLED=false)."
        )
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
    yield
    await db.close()
    log.info("QuantVision Pro backend stopped")


app = FastAPI(title="QuantVision Pro API", version="1.0.0", lifespan=lifespan)

local_dev_origin_regex = (
    rf"^https?://("
    rf"localhost|127\.0\.0\.1|0\.0\.0\.0|"
    rf"192\.168\.\d{{1,3}}\.\d{{1,3}}|"
    rf"10\.\d{{1,3}}\.\d{{1,3}}\.\d{{1,3}}|"
    rf"172\.(1[6-9]|2\d|3[0-1])\.\d{{1,3}}\.\d{{1,3}}"
    rf"):(5173|{APP_PORT})$"
)

allowed_origins = sorted(
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


async def startup_download():
    log.info("Starting history download for %s tickers...", len(STARTUP_DOWNLOAD_TICKERS))
    for ticker in STARTUP_DOWNLOAD_TICKERS:
        try:
            count = await fetcher.fetch_and_store(
                ticker,
                period="2y",
                include_info=False,
            )
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
            payload.get("query_date"),
            payload.get("resolved_date"),
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
            reason,
            len(tickers),
            normalized_period,
            normalized_interval,
        )
        successes = []
        failures = []
        total_rows = 0
        for index, ticker in enumerate(tickers):
            try:
                synced = await fetcher.fetch_and_store(
                    ticker,
                    period=normalized_period,
                    interval=normalized_interval,
                    include_info=False,
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
            reason,
            len(successes),
            len(failures),
            total_rows,
        )
        return {
            "reason": reason,
            "period": normalized_period,
            "interval": normalized_interval,
            "tickers": tickers,
            "success_count": len(successes),
            "failure_count": len(failures),
            "total_rows": total_rows,
            "results": successes,
            "failures": failures,
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
                                "type": "quote",
                                "ticker": ticker,
                                "data": quote,
                                "ts": int(time.time() * 1000),
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


async def fetch_and_store_quote_snapshot(ticker: str) -> dict | None:
    ticker = normalize_ticker(ticker)
    quote = await quote_provider.fetch_quote(ticker)
    if not quote:
        return None
    return await db.upsert_market_quote(quote)


async def hydrate_watchlist_item(ticker: str, group: dict) -> dict:
    row = await db.get_latest_ohlcv(ticker)
    info = await db.get_stock_info(ticker)
    prev = await db.get_prev_close(ticker) if row else None
    chg_pct = ((row["close"] - prev) / prev * 100) if row and prev else 0
    display_name = resolve_display_name(ticker, info)

    return {
        "ticker": ticker,
        "name": display_name,
        "close": row["close"] if row else None,
        "open": row["open"] if row else None,
        "high": row["high"] if row else None,
        "low": row["low"] if row else None,
        "volume": row["volume"] if row else None,
        "change_pct": round(chg_pct, 2) if row else 0,
        "date": row["date"] if row else None,
        "category": categorize(ticker),
        "group_id": group["id"],
        "group_name": group["name"],
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/watchlist")
async def get_watchlist():
    groups = await db.get_watchlist_groups()
    flat_items = []

    for group in groups:
        hydrated_items = []
        for item in group.get("items", []):
            hydrated = await hydrate_watchlist_item(item["ticker"], group)
            hydrated["id"] = item["id"]
            hydrated["sort_order"] = item["sort_order"]
            hydrated_items.append(hydrated)
            flat_items.append(hydrated)
        group["items"] = hydrated_items

    return {"groups": groups, "items": flat_items}


@app.post("/api/watchlist/groups")
async def create_watchlist_group(payload: WatchlistGroupCreate):
    try:
        group = await db.create_watchlist_group(payload.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**group, "items": []}


@app.patch("/api/watchlist/groups/{group_id}")
async def rename_watchlist_group(group_id: int, payload: WatchlistGroupUpdate):
    try:
        group = await db.rename_watchlist_group(group_id, payload.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not group:
        raise HTTPException(404, "Watchlist group not found")
    return group


@app.delete("/api/watchlist/groups/{group_id}")
async def delete_watchlist_group(group_id: int):
    deleted = await db.delete_watchlist_group(group_id)
    if not deleted:
        raise HTTPException(404, "Watchlist group not found")
    return {"ok": True, "group_id": group_id}


@app.post("/api/watchlist/items")
async def add_watchlist_item(payload: WatchlistItemCreate):
    group = await db.get_watchlist_group(payload.group_id)
    if not group:
        raise HTTPException(404, "Watchlist group not found")

    ticker = normalize_ticker(payload.ticker)
    try:
        item = await db.add_watchlist_item(payload.group_id, ticker)
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

    hydrated = await hydrate_watchlist_item(ticker, group)
    hydrated["id"] = item["id"]
    hydrated["sort_order"] = item["sort_order"]
    return hydrated


@app.delete("/api/watchlist/items/{item_id}")
async def delete_watchlist_item(item_id: int):
    deleted = await db.delete_watchlist_item(item_id)
    if not deleted:
        raise HTTPException(404, "Watchlist item not found")
    return {"ok": True, "item_id": item_id}


@app.put("/api/watchlist/groups/{group_id}/items/order")
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


@app.get("/api/workspaces")
async def list_workspaces():
    return {"items": await db.list_workspace_presets(owner_id=DEFAULT_OWNER_ID)}


@app.post("/api/workspaces")
async def create_workspace(payload: WorkspacePresetCreate):
    try:
        return await db.create_workspace_preset(payload.model_dump(), owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/workspaces/{workspace_id}")
async def get_workspace(workspace_id: int):
    workspace = await db.get_workspace_preset(workspace_id, owner_id=DEFAULT_OWNER_ID)
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    return workspace


@app.put("/api/workspaces/{workspace_id}")
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


@app.delete("/api/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: int):
    deleted = await db.delete_workspace_preset(workspace_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Workspace not found")
    return {"ok": True, "workspace_id": workspace_id}


@app.get("/api/alerts")
async def list_alerts():
    return {"items": await db.list_alerts(owner_id=DEFAULT_OWNER_ID)}


@app.post("/api/alerts")
async def create_alert(payload: AlertCreatePayload):
    try:
        return await db.create_alert(payload.model_dump(), owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.patch("/api/alerts/{alert_id}")
async def update_alert(alert_id: int, payload: AlertUpdatePayload):
    try:
        alert = await db.update_alert(
            alert_id,
            payload.model_dump(exclude_unset=True),
            owner_id=DEFAULT_OWNER_ID,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not alert:
        raise HTTPException(404, "Alert not found")
    return alert


@app.get("/api/alerts/{alert_id}/triggers")
async def get_alert_trigger_logs(alert_id: int, limit: int = Query(20, ge=1, le=200)):
    alert = await db.get_alert(alert_id, owner_id=DEFAULT_OWNER_ID)
    if not alert:
        raise HTTPException(404, "Alert not found")
    return {"items": await db.list_alert_trigger_logs(alert_id, owner_id=DEFAULT_OWNER_ID, limit=limit)}


@app.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id: int):
    deleted = await db.delete_alert(alert_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Alert not found")
    return {"ok": True, "alert_id": alert_id}


@app.get("/api/notifications")
async def list_notifications(
    unread_only: bool = Query(False, description="Only unread notifications"),
    limit: int = Query(50, ge=1, le=200),
):
    return {
        "items": await db.list_notifications(
            owner_id=DEFAULT_OWNER_ID,
            unread_only=unread_only,
            limit=limit,
        )
    }


@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int):
    notification = await db.mark_notification_read(notification_id, owner_id=DEFAULT_OWNER_ID)
    if not notification:
        raise HTTPException(404, "Notification not found")
    return notification


@app.patch("/api/notifications/{notification_id}/read")
async def patch_notification_read_state(notification_id: int, payload: NotificationReadStatePayload):
    notification = await db.set_notification_read_state(notification_id, payload.read, owner_id=DEFAULT_OWNER_ID)
    if not notification:
        raise HTTPException(404, "Notification not found")
    return notification


@app.get("/api/journal/trades")
async def list_trade_journal_entries(
    ticker: str | None = Query(None),
    market: str | None = Query(None),
    strategy_code: str | None = Query(None),
    tag: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    normalized_ticker = normalize_ticker(ticker) if ticker else None
    return {
        "items": await db.list_trade_journal_entries(
            owner_id=DEFAULT_OWNER_ID,
            ticker=normalized_ticker,
            market=market.strip() if market else None,
            strategy_code=strategy_code.strip() if strategy_code else None,
            tag=tag.strip() if tag else None,
            search=search.strip() if search else None,
            limit=limit,
        )
    }


@app.get("/api/journal/trades/stats")
async def get_trade_journal_stats(
    ticker: str | None = Query(None),
    market: str | None = Query(None),
    strategy_code: str | None = Query(None),
    tag: str | None = Query(None),
    search: str | None = Query(None),
):
    normalized_ticker = normalize_ticker(ticker) if ticker else None
    return await db.get_trade_journal_stats(
        owner_id=DEFAULT_OWNER_ID,
        ticker=normalized_ticker,
        market=market.strip() if market else None,
        strategy_code=strategy_code.strip() if strategy_code else None,
        tag=tag.strip() if tag else None,
        search=search.strip() if search else None,
    )


@app.post("/api/journal/trades")
async def create_trade_journal_entry(payload: TradeJournalEntryCreatePayload):
    try:
        return await db.create_trade_journal_entry(payload.model_dump(), owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/journal/trades/{entry_id}")
async def get_trade_journal_entry(entry_id: int):
    entry = await db.get_trade_journal_entry(entry_id, owner_id=DEFAULT_OWNER_ID)
    if not entry:
        raise HTTPException(404, "Trade journal entry not found")
    return entry


@app.patch("/api/journal/trades/{entry_id}")
async def update_trade_journal_entry(entry_id: int, payload: TradeJournalEntryUpdatePayload):
    try:
        entry = await db.update_trade_journal_entry(
            entry_id,
            payload.model_dump(exclude_unset=True),
            owner_id=DEFAULT_OWNER_ID,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not entry:
        raise HTTPException(404, "Trade journal entry not found")
    return entry


@app.delete("/api/journal/trades/{entry_id}")
async def delete_trade_journal_entry(entry_id: int):
    deleted = await db.delete_trade_journal_entry(entry_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Trade journal entry not found")
    return {"ok": True, "entry_id": entry_id}


@app.get("/api/backtests/strategies")
async def get_backtest_strategies():
    return {"items": list_backtest_strategies()}


@app.get("/api/backtests/runs")
async def list_backtest_runs(
    ticker: str | None = Query(None, description="Optional ticker filter"),
    limit: int = Query(20, ge=1, le=200),
):
    normalized_ticker = normalize_ticker(ticker) if ticker else None
    return {
        "items": await db.list_backtest_runs(
            owner_id=DEFAULT_OWNER_ID,
            ticker=normalized_ticker,
            limit=limit,
        )
    }


@app.get("/api/backtests/runs/{run_id}")
async def get_backtest_run(run_id: int):
    run = await db.get_backtest_run(run_id, owner_id=DEFAULT_OWNER_ID)
    if not run:
        raise HTTPException(404, "Backtest run not found")
    return run


@app.post("/api/backtests/runs")
async def create_backtest_run(payload: BacktestRunCreatePayload):
    ticker = normalize_ticker(payload.ticker)
    start = payload.start.strip()
    end = payload.end.strip()
    if start > end:
        raise HTTPException(400, "Backtest start date must be earlier than end date")

    rows = await db.get_ohlcv_range(
        ticker,
        start_date=start,
        end_date=end,
        interval=payload.interval,
    )
    if len(rows) < 30:
        await fetcher.fetch_and_store(ticker, period="max", interval=payload.interval, include_info=False)
        rows = await db.get_ohlcv_range(
            ticker,
            start_date=start,
            end_date=end,
            interval=payload.interval,
        )

    try:
        result = run_backtest(
            rows,
            {
                "ticker": ticker,
                "strategy": payload.strategy,
                "start": start,
                "end": end,
                "interval": payload.interval,
                "capital": payload.capital,
                "fee_rate": payload.fee / 100,
                "slippage_rate": payload.slippage / 100,
                "stop_loss_pct": (payload.sl / 100) if payload.sl not in (None, "") else None,
                "take_profit_pct": (payload.tp / 100) if payload.tp not in (None, "") else None,
                "position_sizing": payload.position_sizing,
            },
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    persisted = await db.create_backtest_run(
        {
            "ticker": ticker,
            "strategy_key": result["strategy_key"],
            "strategy_name": result["strategy"],
            "interval": result["interval"],
            "start_date": result["start"],
            "end_date": result["end"],
            "initial_capital": result["capital"],
            "final_equity": result["finalEquity"],
            "total_return_pct": result["totalReturn"],
            "max_drawdown_pct": result["maxDrawdown"],
            "sharpe_ratio": result["sharpe"],
            "trade_count": result["sellTrades"],
            "win_rate_pct": result["winRate"],
            "bars_count": result["bars"],
            "fee_rate": result["feeRate"],
            "slippage_rate": result["slippageRate"],
            "stop_loss_pct": result["stopLoss"],
            "take_profit_pct": result["takeProfit"],
            "position_sizing": result["positionSizing"],
            "summary": {
                key: value
                for key, value in result.items()
                if key not in {"trades", "equity_curve"}
            },
        },
        result["trades"],
        result["equity_curve"],
        owner_id=DEFAULT_OWNER_ID,
    )
    return persisted


@app.get("/api/kline/{ticker}")
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


@app.get("/api/quote/{ticker}", response_model=QuoteResponse)
async def get_quote(ticker: str):
    ticker = normalize_ticker(ticker)
    quote = await fetch_and_store_quote_snapshot(ticker)
    if not quote:
        quote = await db.get_market_quote(ticker)
    if not quote:
        raise HTTPException(404, "Unable to fetch quote")
    return quote


@app.get("/api/info/{ticker}")
async def get_info(ticker: str):
    ticker = normalize_ticker(ticker)
    info = await db.get_stock_info(ticker)
    if not info:
        info = await fetcher.fetch_and_store_info(ticker)
    return info or {}


@app.post("/api/sync/{ticker}")
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


@app.post("/api/sync/all")
async def sync_all_tracked(
    period: str = Query(LATEST_DATA_SYNC_PERIOD, description="1mo 3mo 6mo 1y 2y 5y 10y max"),
    interval: str = Query(LATEST_DATA_SYNC_INTERVAL, description="1d 1wk 1mo"),
):
    return await sync_tracked_market_data(period=period, interval=interval, reason="manual-all")


@app.get("/api/search")
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


@app.get("/api/db/stats")
async def db_stats():
    return await db.get_stats()


@app.get("/api/taifex/institutional")
async def get_taifex_institutional(
    date: str | None = Query(None, description="YYYY-MM-DD"),
    refresh: bool = Query(False, description="Force refresh from remote sources"),
):
    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(400, "date must use YYYY-MM-DD") from exc

    payload = await taifex_fetcher.fetch_dashboard(target_date, force_refresh=refresh)

    spot_cards = []
    for item in TAIFEX_SPOT_REFERENCE:
        quote = await fetch_and_store_quote_snapshot(item["ticker"])
        if not quote:
            quote = await db.get_market_quote(item["ticker"])
        if not quote:
            continue
        spot_cards.append(
            {
                "ticker": item["ticker"],
                "label": item["label"],
                "price": quote.get("price"),
                "change": quote.get("change"),
                "change_pct": quote.get("change_pct"),
                "open": quote.get("open"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "volume": quote.get("volume"),
            }
        )

    payload["spot_reference"] = spot_cards
    return payload


@app.get("/api/taifex/institutional/insights")
async def get_taifex_institutional_insights(
    date: str | None = Query(None, description="YYYY-MM-DD"),
    futures_commodity: str | None = Query(None, description="期貨商品名稱"),
    options_commodity: str | None = Query(None, description="選擇權商品名稱"),
    days: int = Query(30, description="10 20 30 60 90"),
    refresh: bool = Query(False, description="Force refresh from remote sources"),
):
    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(400, "date must use YYYY-MM-DD") from exc

    return await taifex_fetcher.fetch_insights(
        target_date,
        futures_commodity.strip() if futures_commodity else None,
        options_commodity.strip() if options_commodity else None,
        days,
        force_refresh=refresh,
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            action = data.get("action")

            if action == "subscribe":
                ticker = normalize_ticker(data.get("ticker", ""))
                ws_manager.subscribe(websocket, ticker)
            elif action == "unsubscribe":
                ticker = normalize_ticker(data.get("ticker", ""))
                ws_manager.unsubscribe(websocket, ticker)
            elif action == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        log.error("WS error: %s", exc)
        ws_manager.disconnect(websocket)


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


@app.get("/")
async def root():
    if FRONTEND_DIST_DIR.exists():
        return RedirectResponse(url="/app/", status_code=307)
    return RedirectResponse(url=FRONTEND_DEV_URL, status_code=307)


@app.get("/app")
async def frontend_entry():
    if FRONTEND_DIST_DIR.exists():
        return RedirectResponse(url="/app/", status_code=307)
    return RedirectResponse(url=FRONTEND_DEV_URL, status_code=307)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=APP_PORT, reload=False, log_level="info")
