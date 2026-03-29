"""
QuantVision Pro backend API server.
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from data_fetcher import DataFetcher, normalize_ticker
from database import db, init_db
from ws_manager import ConnectionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

load_dotenv()

fetcher = DataFetcher()
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
DISPLAY_NAME_OVERRIDES = {
    "^TWII": "台灣加權指數",
    "^TWOII": "櫃買指數",
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ 指數",
    "^SOX": "費城半導體",
    "^DJI": "道瓊工業指數",
    "^N225": "日經 225",
    "^HSI": "恆生指數",
    "000001.SS": "上證綜合指數",
    "^STOXX50E": "Euro Stoxx 50",
    "GC=F": "黃金",
    "SI=F": "白銀",
    "HG=F": "銅",
    "CL=F": "WTI 原油",
    "BZ=F": "布蘭特原油",
    "NG=F": "天然氣",
}
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

FULL_HISTORY_PERIODS = {"10y", "max"}


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
    asyncio.create_task(realtime_polling_loop())
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


async def realtime_polling_loop():
    await asyncio.sleep(5)
    while True:
        subscribed = ws_manager.get_subscribed_tickers()
        if subscribed:
            for ticker in subscribed:
                try:
                    quote = await fetcher.fetch_realtime_quote(ticker)
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


async def hydrate_watchlist_item(ticker: str, group: dict) -> dict:
    row = await db.get_latest_ohlcv(ticker)
    info = await db.get_stock_info(ticker)
    prev = await db.get_prev_close(ticker) if row else None
    chg_pct = ((row["close"] - prev) / prev * 100) if row and prev else 0
    display_name = (
        DISPLAY_NAME_OVERRIDES.get(ticker)
        or (info.get("name") if info else None)
        or ticker
    )

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
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


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


@app.get("/api/quote/{ticker}")
async def get_quote(ticker: str):
    ticker = normalize_ticker(ticker)
    quote = await fetcher.fetch_realtime_quote(ticker)
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


@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    return await db.search_tickers(q.upper())


@app.get("/api/db/stats")
async def db_stats():
    return await db.get_stats()


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
    if ticker.endswith(".TW"):
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
