"""
Yahoo Finance data fetcher using the public chart endpoint.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote as urlquote

import requests

from database import db

log = logging.getLogger(__name__)

_quote_cache: Dict[str, tuple] = {}
QUOTE_CACHE_TTL = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
RANGE_MAP = {
    "5d": "5d",
    "1mo": "1mo",
    "3mo": "3mo",
    "6mo": "6mo",
    "1y": "1y",
    "2y": "2y",
    "5y": "5y",
    "10y": "10y",
    "max": "max",
}


def normalize_ticker(ticker: str) -> str:
    raw = (ticker or "").strip().upper()
    if not raw:
        return raw
    if raw.startswith("^") or "." in raw or "-" in raw:
        return raw
    # When the input is not a pure English ticker, default to Taiwan suffix.
    if not raw.isalpha():
        return f"{raw}.TW"
    return raw


class DataFetcher:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(1)

    async def fetch_and_store(
        self,
        ticker: str,
        period: str = "2y",
        interval: str = "1d",
        include_info: bool = False,
    ) -> int:
        ticker = normalize_ticker(ticker)
        async with self._semaphore:
            loop = asyncio.get_event_loop()
            try:
                rows, info = await loop.run_in_executor(
                    None,
                    self._download_sync,
                    ticker,
                    period,
                    interval,
                    include_info,
                )
            except Exception as exc:
                log.warning("download %s failed: %s", ticker, exc)
                await db.log_sync(ticker, "error", 0, str(exc))
                return 0

        count = await db.upsert_ohlcv_batch(ticker, rows, interval)
        if info:
            await db.upsert_stock_info(ticker, info)

        status = "ok" if count else "empty"
        message = "" if count else "No rows returned from Yahoo Finance"
        await db.log_sync(ticker, status, count, message)
        return count

    def _download_sync(
        self,
        ticker: str,
        period: str,
        interval: str,
        include_info: bool,
    ) -> Tuple[List[Dict], Dict]:
        chart = self._fetch_chart_result(ticker, period=period, interval=interval)
        rows = self._rows_from_chart(chart, interval)
        info = self._info_from_chart(ticker, chart) if include_info else {}
        return rows, info

    async def fetch_realtime_quote(self, ticker: str) -> Optional[Dict]:
        ticker = normalize_ticker(ticker)
        now = time.time()
        if ticker in _quote_cache:
            ts, data = _quote_cache[ticker]
            if now - ts < QUOTE_CACHE_TTL:
                return data

        async with self._semaphore:
            loop = asyncio.get_event_loop()
            try:
                data = await loop.run_in_executor(None, self._quote_sync, ticker)
            except Exception as exc:
                log.debug("quote %s: %s", ticker, exc)
                return None

        if data:
            _quote_cache[ticker] = (now, data)
        return data

    def _quote_sync(self, ticker: str) -> Optional[Dict]:
        chart = self._fetch_chart_result(ticker, period="5d", interval="1d")
        rows = self._rows_from_chart(chart, "1d")
        if not rows:
            return None

        meta = chart.get("meta", {})
        last = rows[-1]
        prev = rows[-2] if len(rows) > 1 else None

        price = _as_float(meta.get("regularMarketPrice")) or last["close"]
        prev_close = (
            _as_float(meta.get("previousClose"))
            or _as_float(meta.get("chartPreviousClose"))
            or (prev["close"] if prev else None)
        )
        open_price = _as_float(meta.get("regularMarketOpen")) or last["open"]
        day_high = _as_float(meta.get("regularMarketDayHigh")) or last["high"]
        day_low = _as_float(meta.get("regularMarketDayLow")) or last["low"]
        volume = _as_int(meta.get("regularMarketVolume")) or last["volume"] or 0

        change = round(price - prev_close, 4) if prev_close else 0
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0

        return {
            "ticker": ticker,
            "price": round(float(price), 4),
            "open": round(float(open_price), 4) if open_price is not None else None,
            "high": round(float(day_high), 4) if day_high is not None else None,
            "low": round(float(day_low), 4) if day_low is not None else None,
            "prev_close": round(float(prev_close), 4) if prev_close is not None else None,
            "change": change,
            "change_pct": change_pct,
            "volume": int(volume),
            "market_cap": _as_int(meta.get("marketCap")),
            "name": meta.get("longName") or meta.get("shortName") or ticker,
            "currency": meta.get("currency") or "USD",
            "ts": int(time.time() * 1000),
        }

    async def fetch_and_store_info(self, ticker: str) -> Optional[Dict]:
        ticker = normalize_ticker(ticker)
        async with self._semaphore:
            loop = asyncio.get_event_loop()
            try:
                info = await loop.run_in_executor(None, self._info_sync, ticker)
                if info:
                    await db.upsert_stock_info(ticker, info)
                    return await db.get_stock_info(ticker)
            except Exception as exc:
                log.warning("info %s: %s", ticker, exc)
        return None

    async def incremental_update(self, ticker: str) -> int:
        return await self.fetch_and_store(ticker, period="5d", include_info=False)

    def _info_sync(self, ticker: str) -> Dict:
        chart = self._fetch_chart_result(ticker, period="1mo", interval="1d")
        return self._info_from_chart(ticker, chart)

    def _fetch_chart_result(self, ticker: str, period: str, interval: str) -> Dict:
        params = {
            "range": RANGE_MAP.get(period, period),
            "interval": interval,
            "includePrePost": "false",
            "events": "div,splits",
        }
        response = requests.get(
            CHART_URL.format(ticker=urlquote(ticker)),
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        chart = payload.get("chart", {})
        if chart.get("error"):
            raise RuntimeError(chart["error"].get("description") or str(chart["error"]))
        result = chart.get("result") or []
        if not result:
            raise RuntimeError("Yahoo chart response returned no result")
        return result[0]

    def _rows_from_chart(self, chart: Dict, interval: str) -> List[Dict]:
        timestamps = chart.get("timestamp") or []
        indicators = chart.get("indicators", {})
        quote = (indicators.get("quote") or [{}])[0]
        adjclose = ((indicators.get("adjclose") or [{}])[0]).get("adjclose") or []

        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        rows: List[Dict] = []
        for idx, ts in enumerate(timestamps):
            close_price = _list_float(closes, idx)
            if close_price is None:
                continue

            open_price = _list_float(opens, idx)
            high_price = _list_float(highs, idx)
            low_price = _list_float(lows, idx)
            volume = _list_int(volumes, idx) or 0
            adjusted_close = _list_float(adjclose, idx) or close_price
            dt = datetime.utcfromtimestamp(int(ts))

            rows.append(
                {
                    "date": _format_chart_date(dt, interval),
                    "open": round(open_price if open_price is not None else close_price, 4),
                    "high": round(high_price if high_price is not None else close_price, 4),
                    "low": round(low_price if low_price is not None else close_price, 4),
                    "close": round(close_price, 4),
                    "volume": volume,
                    "adj_close": round(adjusted_close, 4),
                }
            )
        return rows

    def _info_from_chart(self, ticker: str, chart: Dict) -> Dict:
        meta = chart.get("meta", {})
        return {
            "longName": meta.get("longName") or meta.get("shortName") or ticker,
            "shortName": meta.get("shortName") or meta.get("longName") or ticker,
            "marketCap": _as_int(meta.get("marketCap")),
            "currency": meta.get("currency"),
            "exchange": meta.get("exchangeName"),
            "country": meta.get("exchangeTimezoneName"),
        }


def _format_chart_date(dt: datetime, interval: str) -> str:
    if interval.endswith("d") or interval.endswith("wk") or interval.endswith("mo"):
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _list_float(values: List, index: int) -> Optional[float]:
    if index >= len(values):
        return None
    return _as_float(values[index])


def _list_int(values: List, index: int) -> Optional[int]:
    if index >= len(values):
        return None
    return _as_int(values[index])


def _as_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
