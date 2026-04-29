from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from database import db
from data_fetcher import DataFetcher, normalize_ticker
from fubon_quote_provider import build_fubon_quote_payload
from fubon_symbols import is_taiwan_stock_ticker, tw_ticker_to_fubon

log = logging.getLogger(__name__)

FUBON_INTRADAY_INTERVALS = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "60m": "60",
    "1h": "60",
}
FUBON_HISTORY_INTERVALS = {
    "1d": "D",
    "1wk": "W",
    "1mo": "M",
}
FUBON_HISTORY_START = date(2010, 1, 1)
FUBON_HISTORY_MAX_RANGE_DAYS = 364


def _coerce_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _history_start_from_period(period: str) -> str:
    normalized = str(period or "1y").strip().lower()
    today = date.today()
    if normalized == "max":
        return FUBON_HISTORY_START.isoformat()
    if normalized.endswith("d") and normalized[:-1].isdigit():
        offset_days = int(normalized[:-1]) + 2
        if offset_days > FUBON_HISTORY_MAX_RANGE_DAYS:
            offset_days = FUBON_HISTORY_MAX_RANGE_DAYS
        start = today - timedelta(days=offset_days)
        return start.isoformat()
    if normalized.endswith("mo") and normalized[:-2].isdigit():
        start = today - timedelta(days=int(normalized[:-2]) * 31)
        return start.isoformat()
    if normalized.endswith("y") and normalized[:-1].isdigit():
        years = int(normalized[:-1])
        if years <= 1:
            start = today - timedelta(days=FUBON_HISTORY_MAX_RANGE_DAYS)
        else:
            start = today - timedelta(days=years * 365)
        return start.isoformat()
    return (today - timedelta(days=FUBON_HISTORY_MAX_RANGE_DAYS)).isoformat()


def _merge_unique_rows(rows: list[dict]) -> list[dict]:
    by_date: dict[str, dict] = {}
    for row in rows:
        row_date = str(row.get("date") or "")
        if not row_date:
            continue
        by_date[row_date] = row
    return [by_date[key] for key in sorted(by_date)]


def _rows_from_fubon_candles(payload: Optional[dict]) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    rows: List[Dict[str, Any]] = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        close_price = _coerce_float(item.get("close"))
        if close_price is None:
            continue
        open_price = _coerce_float(item.get("open"))
        high_price = _coerce_float(item.get("high"))
        low_price = _coerce_float(item.get("low"))
        rows.append(
            {
                "date": str(item.get("date")),
                "open": round(open_price if open_price is not None else close_price, 4),
                "high": round(high_price if high_price is not None else close_price, 4),
                "low": round(low_price if low_price is not None else close_price, 4),
                "close": round(close_price, 4),
                "volume": _coerce_int(item.get("volume")),
                "adj_close": round(close_price, 4),
                "source": "fubon_neo",
            }
        )
    return rows


class HybridDataFetcher:
    def __init__(self, yahoo_fetcher: DataFetcher, fubon_manager):
        self._yahoo = yahoo_fetcher
        self._fubon_manager = fubon_manager

    async def fetch_and_store(
        self,
        ticker: str,
        period: str = "2y",
        interval: str = "1d",
        include_info: bool = False,
    ) -> int:
        normalized_ticker = normalize_ticker(ticker)
        if is_taiwan_stock_ticker(normalized_ticker):
            if not self._should_use_fubon_stock_history(normalized_ticker, interval):
                message = "Taiwan stock history is restricted to Fubon API and this interval is unsupported or Fubon is disconnected"
                log.warning("%s: %s (%s)", message, normalized_ticker, interval)
                await db.log_sync(normalized_ticker, "error", 0, message)
                return 0
            try:
                count = await self._fetch_and_store_fubon_stock(
                    normalized_ticker,
                    period=period,
                    interval=interval,
                    include_info=include_info,
                )
                return count
            except Exception as exc:
                message = f"Fubon stock candle fetch failed: {exc}"
                log.warning(
                    "Fubon stock candle fetch failed for %s (%s/%s); Yahoo fallback is disabled for Taiwan stocks: %s",
                    normalized_ticker,
                    period,
                    interval,
                    exc,
                )
                await db.log_sync(normalized_ticker, "error", 0, message)
                return 0
        return await self._yahoo.fetch_and_store(
            normalized_ticker,
            period=period,
            interval=interval,
            include_info=include_info,
        )

    async def fetch_realtime_quote(self, ticker: str) -> Optional[Dict]:
        normalized_ticker = normalize_ticker(ticker)
        if is_taiwan_stock_ticker(normalized_ticker):
            if not self._fubon_manager.connected:
                log.warning(
                    "Fubon realtime quote unavailable for %s; Yahoo fallback is disabled for Taiwan stocks",
                    normalized_ticker,
                )
                return None
            symbol = tw_ticker_to_fubon(normalized_ticker)
            if not symbol:
                return None
            response = await self._fubon_manager.fetch_stock_quote(symbol)
            payload = build_fubon_quote_payload(normalized_ticker, response or {}, source="fubon_neo")
            return payload
        return await self._yahoo.fetch_realtime_quote(normalized_ticker)

    async def fetch_and_store_info(self, ticker: str) -> Optional[Dict]:
        normalized_ticker = normalize_ticker(ticker)
        if is_taiwan_stock_ticker(normalized_ticker):
            log.info("Skipping Yahoo stock info fetch for Taiwan ticker %s", normalized_ticker)
            return None
        return await self._yahoo.fetch_and_store_info(normalized_ticker)

    async def incremental_update(self, ticker: str) -> int:
        return await self.fetch_and_store(ticker, period="5d", include_info=False)

    def _should_use_fubon_stock_history(self, ticker: str, interval: str) -> bool:
        if not self._fubon_manager.connected:
            return False
        if not is_taiwan_stock_ticker(ticker):
            return False
        normalized_interval = str(interval or "1d").strip().lower()
        return normalized_interval in FUBON_INTRADAY_INTERVALS or normalized_interval in FUBON_HISTORY_INTERVALS

    async def _fetch_and_store_fubon_stock(
        self,
        ticker: str,
        *,
        period: str,
        interval: str,
        include_info: bool,
    ) -> int:
        symbol = tw_ticker_to_fubon(ticker)
        if not symbol:
            return 0

        normalized_interval = str(interval or "1d").strip().lower()
        if normalized_interval in FUBON_INTRADAY_INTERVALS:
            response = await self._fubon_manager.fetch_stock_intraday_candles(
                symbol,
                timeframe=FUBON_INTRADAY_INTERVALS[normalized_interval],
                sort="asc",
            )
        else:
            response = await self._fetch_fubon_historical_candles_chunked(
                symbol,
                from_date=_history_start_from_period(period),
                to_date=date.today().isoformat(),
                timeframe=FUBON_HISTORY_INTERVALS[normalized_interval],
                adjusted=True,
                sort="asc",
            )

        rows = _merge_unique_rows(_rows_from_fubon_candles(response))
        if normalized_interval == "1d" and rows:
            await db.delete_ohlcv_range(
                ticker,
                interval=normalized_interval,
                start_date=rows[0]["date"],
                end_date=rows[-1]["date"],
            )

        count = await db.upsert_ohlcv_batch(ticker, rows, normalized_interval)
        if include_info:
            log.info("Skipping Yahoo stock info fetch for Taiwan ticker %s", ticker)

        status = "ok" if count else "empty"
        message = "" if count else "No rows returned from Fubon historical candles"
        await db.log_sync(ticker, status, count, message)
        return count

    async def _fetch_fubon_historical_candles_chunked(
        self,
        symbol: str,
        *,
        from_date: str,
        to_date: str,
        timeframe: str,
        adjusted: bool,
        sort: str,
    ) -> dict:
        start = date.fromisoformat(from_date)
        end = date.fromisoformat(to_date)
        rows: list[dict] = []
        cursor = start
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=FUBON_HISTORY_MAX_RANGE_DAYS), end)
            response = await self._fubon_manager.fetch_stock_historical_candles(
                symbol,
                from_date=cursor.isoformat(),
                to_date=chunk_end.isoformat(),
                timeframe=timeframe,
                adjusted=adjusted,
                sort=sort,
            )
            if isinstance(response, dict):
                rows.extend(response.get("data") or [])
            cursor = chunk_end + timedelta(days=1)
        return {"symbol": symbol, "data": rows}
