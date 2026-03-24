"""
QuantVision Pro — Backend API Server
Yahoo Finance 資料源 + SQLite 本地資料庫 + WebSocket 即時推送
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import db, init_db
from data_fetcher import DataFetcher
from ws_manager import ConnectionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

fetcher = DataFetcher()
ws_manager = ConnectionManager()

# ── 預設監控清單 ──────────────────────────────────────────────────────────────
DEFAULT_WATCHLIST = [
    # 美股
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "BRK-B",
    # 台股
    "2330.TW", "2317.TW", "2454.TW", "2382.TW", "2303.TW",
    # 港股
    "0700.HK", "9988.HK",
    # ETF
    "SPY", "QQQ", "VTI", "GLD",
    # 加密
    "BTC-USD", "ETH-USD",
    # 大盤指數
    "^GSPC", "^IXIC", "^DJI", "^TWII",
]

# ── Lifespan (startup / shutdown) ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 QuantVision Pro 後端啟動中...")
    await init_db()
    # 背景任務：初始歷史資料下載
    asyncio.create_task(startup_download())
    # 背景任務：即時價格輪詢
    asyncio.create_task(realtime_polling_loop())
    yield
    log.info("🛑 後端關閉")

app = FastAPI(title="QuantVision Pro API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 靜態前端
try:
    app.mount("/app", StaticFiles(directory="../frontend", html=True), name="frontend")
except Exception:
    pass


# ── 啟動時下載歷史資料 ─────────────────────────────────────────────────────────
async def startup_download():
    """首次啟動時，非同步下載所有股票的歷史 K 線資料"""
    log.info(f"📥 開始下載 {len(DEFAULT_WATCHLIST)} 支股票的歷史資料...")
    for ticker in DEFAULT_WATCHLIST:
        try:
            count = await fetcher.fetch_and_store(ticker, period="2y")
            log.info(f"  ✅ {ticker}: {count} 筆 K 線已存入 DB")
            await asyncio.sleep(0.5)  # 避免 rate limit
        except Exception as e:
            log.warning(f"  ⚠️  {ticker} 下載失敗: {e}")
    log.info("✅ 歷史資料下載完成")


# ── 即時輪詢 (每 15 秒) ────────────────────────────────────────────────────────
async def realtime_polling_loop():
    """每 15 秒輪詢一次有訂閱者的股票，並透過 WebSocket 廣播"""
    await asyncio.sleep(5)  # 等待 DB 初始化
    while True:
        subscribed = ws_manager.get_subscribed_tickers()
        if subscribed:
            for ticker in subscribed:
                try:
                    quote = await fetcher.fetch_realtime_quote(ticker)
                    if quote:
                        await ws_manager.broadcast_to_ticker(ticker, {
                            "type": "quote",
                            "ticker": ticker,
                            "data": quote,
                            "ts": int(time.time() * 1000),
                        })
                except Exception as e:
                    log.debug(f"quote error {ticker}: {e}")
                await asyncio.sleep(0.2)
        await asyncio.sleep(15)


# ══════════════════════════════════════════════════════════════════════════════
# REST API Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/api/watchlist")
async def get_watchlist():
    """取得預設自選股清單及最新報價"""
    results = []
    for ticker in DEFAULT_WATCHLIST:
        row = await db.get_latest_ohlcv(ticker)
        info = await db.get_stock_info(ticker)
        if row:
            prev = await db.get_prev_close(ticker)
            chg_pct = ((row["close"] - prev) / prev * 100) if prev else 0
            results.append({
                "ticker": ticker,
                "name": info.get("name", ticker) if info else ticker,
                "close": row["close"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "volume": row["volume"],
                "change_pct": round(chg_pct, 2),
                "date": row["date"],
                "category": categorize(ticker),
            })
    return results


@app.get("/api/kline/{ticker}")
async def get_kline(
    ticker: str,
    period: str = Query("1y", description="1mo 3mo 6mo 1y 2y 5y"),
    interval: str = Query("1d", description="1d 1wk 1mo"),
):
    """取得 K 線資料（優先從 DB，必要時從 Yahoo 補抓）"""
    rows = await db.get_ohlcv(ticker, period=period, interval=interval)
    if not rows:
        # DB 沒有 → 即時從 Yahoo 抓
        count = await fetcher.fetch_and_store(ticker, period="2y")
        rows = await db.get_ohlcv(ticker, period=period, interval=interval)
    return {"ticker": ticker, "interval": interval, "data": rows}


@app.get("/api/quote/{ticker}")
async def get_quote(ticker: str):
    """取得最新報價（快取 30 秒）"""
    quote = await fetcher.fetch_realtime_quote(ticker)
    if not quote:
        raise HTTPException(404, "無法取得報價")
    return quote


@app.get("/api/info/{ticker}")
async def get_info(ticker: str):
    """取得股票基本資訊"""
    info = await db.get_stock_info(ticker)
    if not info:
        info = await fetcher.fetch_and_store_info(ticker)
    return info or {}


@app.post("/api/sync/{ticker}")
async def sync_ticker(ticker: str):
    """手動觸發同步指定股票的最新資料"""
    count = await fetcher.fetch_and_store(ticker, period="3mo")
    return {"ticker": ticker, "synced": count}


@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    """搜尋本地 DB 中的股票"""
    results = await db.search_tickers(q.upper())
    return results


@app.get("/api/db/stats")
async def db_stats():
    """DB 統計資訊"""
    stats = await db.get_stats()
    return stats


# ══════════════════════════════════════════════════════════════════════════════
# WebSocket
# ══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            action = data.get("action")

            if action == "subscribe":
                ticker = data.get("ticker", "").upper()
                ws_manager.subscribe(websocket, ticker)
                # 立即推送最新報價
                quote = await fetcher.fetch_realtime_quote(ticker)
                if quote:
                    await websocket.send_text(json.dumps({
                        "type": "quote", "ticker": ticker, "data": quote,
                        "ts": int(time.time() * 1000),
                    }))

            elif action == "unsubscribe":
                ticker = data.get("ticker", "").upper()
                ws_manager.unsubscribe(websocket, ticker)

            elif action == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        log.error(f"WS error: {e}")
        ws_manager.disconnect(websocket)


# ── Helpers ───────────────────────────────────────────────────────────────────
def categorize(ticker: str) -> str:
    if ticker.endswith(".TW"):  return "台股"
    if ticker.endswith(".HK"):  return "港股"
    if ticker.startswith("^"):  return "指數"
    if ticker.endswith("-USD"): return "加密"
    if ticker in ("SPY", "QQQ", "VTI", "GLD", "IWM"): return "ETF"
    return "美股"


@app.get("/")
async def root():
    return FileResponse("../frontend/index.html")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
