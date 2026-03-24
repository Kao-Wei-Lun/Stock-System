"""
Yahoo Finance 資料抓取器
使用 yfinance 庫：歷史 K 線 + 即時報價 + 股票資訊
"""

import asyncio
import logging
import time
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional

import yfinance as yf

from database import db

log = logging.getLogger(__name__)

# 即時報價快取 (ticker -> (timestamp, data))
_quote_cache: Dict[str, tuple] = {}
QUOTE_CACHE_TTL = 15  # 秒


class DataFetcher:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(3)  # 最多同時 3 個 Yahoo 請求

    # ── 歷史 K 線 ─────────────────────────────────────────────────────────────

    async def fetch_and_store(self, ticker: str, period: str = "2y", interval: str = "1d") -> int:
        """
        從 Yahoo Finance 抓取歷史 K 線，存入 SQLite
        回傳存入的筆數
        """
        async with self._semaphore:
            loop = asyncio.get_event_loop()
            try:
                rows, info = await loop.run_in_executor(
                    None, self._download_sync, ticker, period, interval
                )
            except Exception as e:
                log.warning(f"下載 {ticker} 失敗: {e}")
                await db.log_sync(ticker, "error", 0, str(e))
                return 0

        count = await db.upsert_ohlcv_batch(ticker, rows, interval)
        if info:
            await db.upsert_stock_info(ticker, info)
        await db.log_sync(ticker, "ok", count)
        return count

    def _download_sync(self, ticker: str, period: str, interval: str):
        """同步下載（在 executor 中執行）"""
        yf_ticker = yf.Ticker(ticker)

        # 歷史資料
        hist = yf_ticker.history(period=period, interval=interval, auto_adjust=True)
        rows = []
        for ts, row in hist.iterrows():
            date_str = ts.strftime("%Y-%m-%d") if interval == "1d" else ts.strftime("%Y-%m-%d %H:%M:%S")
            rows.append({
                "date":      date_str,
                "open":      round(float(row["Open"]),   4),
                "high":      round(float(row["High"]),   4),
                "low":       round(float(row["Low"]),    4),
                "close":     round(float(row["Close"]),  4),
                "volume":    int(row.get("Volume", 0)),
                "adj_close": round(float(row["Close"]),  4),
            })

        # 股票基本資訊（可能失敗，不阻斷）
        info = {}
        try:
            info = yf_ticker.info or {}
        except Exception:
            pass

        return rows, info

    # ── 即時報價 ──────────────────────────────────────────────────────────────

    async def fetch_realtime_quote(self, ticker: str) -> Optional[Dict]:
        """
        取得即時（延遲 15 分鐘）報價
        有本地快取，15 秒內不重複請求
        """
        now = time.time()
        if ticker in _quote_cache:
            ts, data = _quote_cache[ticker]
            if now - ts < QUOTE_CACHE_TTL:
                return data

        async with self._semaphore:
            loop = asyncio.get_event_loop()
            try:
                data = await loop.run_in_executor(None, self._quote_sync, ticker)
            except Exception as e:
                log.debug(f"quote {ticker}: {e}")
                return None

        if data:
            _quote_cache[ticker] = (now, data)
        return data

    def _quote_sync(self, ticker: str) -> Optional[Dict]:
        """同步取得報價"""
        try:
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info or {}

            # 優先用 fast_info（較快）
            fi = yf_ticker.fast_info
            price = getattr(fi, "last_price", None) or info.get("regularMarketPrice") or info.get("currentPrice")
            prev_close = getattr(fi, "previous_close", None) or info.get("previousClose") or info.get("regularMarketPreviousClose")
            open_price = getattr(fi, "open", None) or info.get("open") or info.get("regularMarketOpen")
            day_high = getattr(fi, "day_high", None) or info.get("dayHigh") or info.get("regularMarketDayHigh")
            day_low = getattr(fi, "day_low", None) or info.get("dayLow") or info.get("regularMarketDayLow")
            volume = getattr(fi, "last_volume", None) or info.get("volume") or info.get("regularMarketVolume") or 0

            if not price:
                return None

            change = round(price - prev_close, 4) if prev_close else 0
            change_pct = round(change / prev_close * 100, 2) if prev_close else 0

            return {
                "ticker":      ticker,
                "price":       round(float(price), 4),
                "open":        round(float(open_price), 4) if open_price else None,
                "high":        round(float(day_high), 4)   if day_high   else None,
                "low":         round(float(day_low), 4)    if day_low    else None,
                "prev_close":  round(float(prev_close), 4) if prev_close else None,
                "change":      change,
                "change_pct":  change_pct,
                "volume":      int(volume),
                "market_cap":  info.get("marketCap"),
                "name":        info.get("longName") or info.get("shortName") or ticker,
                "currency":    info.get("currency", "USD"),
                "ts":          int(time.time() * 1000),
            }
        except Exception as e:
            log.debug(f"_quote_sync {ticker}: {e}")
            return None

    # ── 股票資訊 ──────────────────────────────────────────────────────────────

    async def fetch_and_store_info(self, ticker: str) -> Optional[Dict]:
        """抓取並存入股票基本資訊"""
        loop = asyncio.get_event_loop()
        try:
            info = await loop.run_in_executor(None, lambda: yf.Ticker(ticker).info)
            if info:
                await db.upsert_stock_info(ticker, info)
                return await db.get_stock_info(ticker)
        except Exception as e:
            log.warning(f"info {ticker}: {e}")
        return None

    # ── 增量更新 ─────────────────────────────────────────────────────────────

    async def incremental_update(self, ticker: str) -> int:
        """只抓最近 5 天資料（增量更新用）"""
        return await self.fetch_and_store(ticker, period="5d")
