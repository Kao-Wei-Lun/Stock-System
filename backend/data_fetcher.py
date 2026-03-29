"""
Yahoo Finance data fetcher using the public chart endpoint.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote as urlquote

import requests
import urllib3

from database import db

log = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_quote_cache: Dict[str, tuple] = {}
QUOTE_CACHE_TTL = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
FINMIND_DATA_URL = "https://api.finmindtrade.com/api/v4/data"
FULL_HISTORY_START = datetime(1970, 1, 1, tzinfo=timezone.utc)
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

        if interval == "1d" and rows:
            sorted_rows = sorted(rows, key=lambda item: item["date"])
            await db.delete_ohlcv_range(
                ticker,
                interval=interval,
                start_date=sorted_rows[0]["date"],
                end_date=sorted_rows[-1]["date"],
            )
            rows = sorted_rows
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
        if interval == "1d":
            period1, period2 = self._resolve_period_bounds(period)
            chart = self._fetch_chart_result(
                ticker,
                interval=interval,
                period1=period1,
                period2=period2,
            )
            rows = self._rows_from_chart(chart, interval)
            if self._has_large_daily_gap(rows):
                fallback_rows = self._merge_daily_rows(
                    rows,
                    self._fetch_finmind_daily_rows(ticker, period1, period2),
                )
                if self._has_large_daily_gap(fallback_rows):
                    fallback_rows = self._merge_daily_rows(
                        fallback_rows,
                        self._fetch_twse_daily_rows(ticker, period1, period2),
                    )
                if self._has_large_daily_gap(fallback_rows):
                    fallback_rows = self._merge_daily_rows(
                        fallback_rows,
                        self._fetch_chunked_daily_rows(ticker, period1, period2),
                    )
                rows = fallback_rows
        else:
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

    def _fetch_chart_result(
        self,
        ticker: str,
        period: Optional[str] = None,
        interval: str = "1d",
        period1: Optional[int] = None,
        period2: Optional[int] = None,
    ) -> Dict:
        params = {
            "interval": interval,
            "includePrePost": "false",
            "events": "div,splits",
        }
        if period1 is not None and period2 is not None:
            params["period1"] = int(period1)
            params["period2"] = int(period2)
        else:
            params["range"] = RANGE_MAP.get(period or "1y", period or "1y")
        response = requests.get(
            CHART_URL.format(ticker=urlquote(ticker)),
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        payload = response.json()
        if response.status_code >= 400:
            chart_error = payload.get("chart", {}).get("error")
            if chart_error:
                raise RuntimeError(chart_error.get("description") or str(chart_error))
            response.raise_for_status()
        chart = payload.get("chart", {})
        if chart.get("error"):
            raise RuntimeError(chart["error"].get("description") or str(chart["error"]))
        result = chart.get("result") or []
        if not result:
            raise RuntimeError("Yahoo chart response returned no result")
        return result[0]

    def _fetch_chunked_daily_rows(self, ticker: str, period1: int, period2: int) -> List[Dict]:
        total_days = max(1, int((period2 - period1) / 86400))
        if total_days <= 730:
            rows = self._fetch_monthly_daily_rows(ticker, period1, period2)
            if not self._has_large_daily_gap(rows):
                return rows

        if total_days <= 730:
            chunk_days = 90
        elif total_days <= 3650:
            chunk_days = 120
        else:
            chunk_days = 180

        rows = self._fetch_chunked_daily_rows_with_size(ticker, period1, period2, chunk_days)
        if self._has_large_daily_gap(rows) and chunk_days > 45:
            rows = self._fetch_chunked_daily_rows_with_size(
                ticker,
                period1,
                period2,
                max(45, chunk_days // 2),
            )
        return rows

    def _fetch_monthly_daily_rows(self, ticker: str, period1: int, period2: int) -> List[Dict]:
        start_dt = datetime.fromtimestamp(period1, timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt = datetime.fromtimestamp(period2, timezone.utc)
        cursor = start_dt
        merged_rows: Dict[str, Dict] = {}
        last_error: Optional[Exception] = None

        while cursor < end_dt:
            if cursor.month == 12:
                next_month = cursor.replace(year=cursor.year + 1, month=1, day=1)
            else:
                next_month = cursor.replace(month=cursor.month + 1, day=1)

            chunk_start = max(period1, int(cursor.timestamp()))
            chunk_end = min(period2, int(next_month.timestamp()))

            try:
                chart = self._fetch_chart_result(
                    ticker,
                    interval="1d",
                    period1=chunk_start,
                    period2=chunk_end,
                )
                for row in self._rows_from_chart(chart, "1d"):
                    merged_rows[row["date"]] = row
            except Exception as exc:
                if not self._is_empty_history_error(exc):
                    last_error = exc

            cursor = next_month

        if merged_rows:
            return [merged_rows[date] for date in sorted(merged_rows)]
        if last_error:
            raise last_error
        raise RuntimeError("Yahoo chart response returned no rows across monthly daily fetches")

    def _fetch_twse_daily_rows(self, ticker: str, period1: int, period2: int) -> List[Dict]:
        if not ticker.endswith(".TW"):
            return []

        stock_no = ticker[:-3]
        start_dt = datetime.fromtimestamp(period1, timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt = datetime.fromtimestamp(period2, timezone.utc)
        cursor = start_dt
        merged_rows: Dict[str, Dict] = {}

        while cursor < end_dt:
            params = {
                "date": cursor.strftime("%Y%m01"),
                "stockNo": stock_no,
                "response": "json",
            }
            try:
                response = requests.get(
                    TWSE_STOCK_DAY_URL,
                    params=params,
                    headers={"User-Agent": USER_AGENT},
                    timeout=20,
                    verify=False,
                )
                payload = response.json()
            except Exception as exc:
                log.debug("TWSE daily fallback %s %s failed: %s", ticker, params["date"], exc)
                payload = {}

            if payload.get("stat") == "OK":
                for raw_row in payload.get("data") or []:
                    row = self._row_from_twse(raw_row)
                    if not row:
                        continue
                    row_date = datetime.strptime(row["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    if row_date < datetime.fromtimestamp(period1, timezone.utc) or row_date >= datetime.fromtimestamp(period2, timezone.utc):
                        continue
                    merged_rows[row["date"]] = row

            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1, day=1)

        return [merged_rows[date] for date in sorted(merged_rows)]

    def _fetch_finmind_daily_rows(self, ticker: str, period1: int, period2: int) -> List[Dict]:
        if not ticker.endswith(".TW"):
            return []

        stock_no = ticker[:-3]
        start_dt = datetime.fromtimestamp(period1, timezone.utc)
        end_dt = datetime.fromtimestamp(period2, timezone.utc)

        try:
            response = requests.get(
                FINMIND_DATA_URL,
                params={
                    "dataset": "TaiwanStockPrice",
                    "data_id": stock_no,
                    "start_date": start_dt.strftime("%Y-%m-%d"),
                    "end_date": end_dt.strftime("%Y-%m-%d"),
                },
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            payload = response.json()
        except Exception as exc:
            log.debug("FinMind daily fallback %s failed: %s", ticker, exc)
            return []

        data = payload.get("data") or []
        rows: List[Dict] = []
        for raw_row in data:
            date_value = raw_row.get("date")
            close_price = _as_float(raw_row.get("close"))
            if not date_value or close_price is None:
                continue
            rows.append(
                {
                    "date": str(date_value),
                    "open": round(_as_float(raw_row.get("open")) or close_price, 4),
                    "high": round(_as_float(raw_row.get("max")) or close_price, 4),
                    "low": round(_as_float(raw_row.get("min")) or close_price, 4),
                    "close": round(close_price, 4),
                    "volume": _as_int(raw_row.get("Trading_Volume")) or 0,
                    "adj_close": round(close_price, 4),
                }
            )
        return rows

    def _fetch_chunked_daily_rows_with_size(
        self,
        ticker: str,
        period1: int,
        period2: int,
        chunk_days: int,
    ) -> List[Dict]:

        overlap_days = 7
        cursor = period1
        merged_rows: Dict[str, Dict] = {}
        last_error: Optional[Exception] = None

        while cursor < period2:
            chunk_end = min(period2, cursor + chunk_days * 86400)
            try:
                chart = self._fetch_chart_result(
                    ticker,
                    interval="1d",
                    period1=cursor,
                    period2=chunk_end,
                )
                for row in self._rows_from_chart(chart, "1d"):
                    merged_rows[row["date"]] = row
            except Exception as exc:
                if not self._is_empty_history_error(exc):
                    last_error = exc

            if chunk_end >= period2:
                break
            cursor = chunk_end - overlap_days * 86400

        if merged_rows:
            return [merged_rows[date] for date in sorted(merged_rows)]
        if last_error:
            raise last_error
        raise RuntimeError("Yahoo chart response returned no rows across chunked fetches")

    def _merge_daily_rows(self, primary_rows: List[Dict], fallback_rows: List[Dict]) -> List[Dict]:
        if not primary_rows:
            return list(fallback_rows or [])
        if not fallback_rows:
            return list(primary_rows)

        merged: Dict[str, Dict] = {row["date"]: row for row in primary_rows if row.get("date")}
        for row in fallback_rows:
            row_date = row.get("date")
            if not row_date:
                continue
            merged[row_date] = row
        return [merged[row_date] for row_date in sorted(merged)]

    def _resolve_period_bounds(self, period: str) -> Tuple[int, int]:
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        end = today + timedelta(days=1)
        normalized = (period or "1y").strip().lower()

        if normalized == "max":
            start = FULL_HISTORY_START
        elif normalized.endswith("mo") and normalized[:-2].isdigit():
            start = today - timedelta(days=int(normalized[:-2]) * 31)
        elif normalized.endswith("wk") and normalized[:-2].isdigit():
            start = today - timedelta(days=int(normalized[:-2]) * 7)
        elif normalized.endswith("y") and normalized[:-1].isdigit():
            start = today - timedelta(days=int(normalized[:-1]) * 366)
        elif normalized.endswith("d") and normalized[:-1].isdigit():
            start = today - timedelta(days=int(normalized[:-1]) + 2)
        else:
            start = today - timedelta(days=366)

        if start < FULL_HISTORY_START:
            start = FULL_HISTORY_START
        return int(start.timestamp()), int(end.timestamp())

    def _has_large_daily_gap(self, rows: List[Dict], max_gap_days: int = 20) -> bool:
        if len(rows) < 2:
            return False

        prev_date: Optional[datetime] = None
        for row in rows:
            try:
                current_date = datetime.strptime(row["date"], "%Y-%m-%d")
            except (KeyError, TypeError, ValueError):
                continue
            if prev_date and (current_date - prev_date).days > max_gap_days:
                return True
            prev_date = current_date
        return False

    def _is_empty_history_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "data doesn't exist" in message
            or "no data found" in message
            or "returned no result" in message
        )

    def _row_from_twse(self, raw_row) -> Optional[Dict]:
        if not isinstance(raw_row, list) or len(raw_row) < 7:
            return None
        date_text = str(raw_row[0]).strip()
        if not date_text or "/" not in date_text:
            return None

        try:
            roc_year, month, day = [int(part) for part in date_text.split("/")]
            date_value = f"{roc_year + 1911:04d}-{month:02d}-{day:02d}"
        except ValueError:
            return None

        open_price = _as_float(_strip_numeric(raw_row[3]))
        high_price = _as_float(_strip_numeric(raw_row[4]))
        low_price = _as_float(_strip_numeric(raw_row[5]))
        close_price = _as_float(_strip_numeric(raw_row[6]))
        if close_price is None:
            return None

        volume = _as_int(_strip_numeric(raw_row[1])) or 0
        return {
            "date": date_value,
            "open": round(open_price if open_price is not None else close_price, 4),
            "high": round(high_price if high_price is not None else close_price, 4),
            "low": round(low_price if low_price is not None else close_price, 4),
            "close": round(close_price, 4),
            "volume": volume,
            "adj_close": round(close_price, 4),
        }

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


def _strip_numeric(value):
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("X", "").replace("--", "").strip()
        return cleaned or None
    return value
