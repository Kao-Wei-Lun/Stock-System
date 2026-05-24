from __future__ import annotations

import logging
import asyncio
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from database import db
from data_fetcher import DataFetcher, normalize_ticker
from env_validation import read_float_env, read_int_env, read_text_env
from fubon_quote_provider import build_fubon_quote_payload
from fubon_symbols import (
    fubon_index_ticker_to_symbol,
    is_taiwan_market_index_ticker,
    is_taiwan_stock_ticker,
    tw_ticker_to_fubon,
)

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
FUBON_HISTORY_MAX_RANGE_DAYS = read_int_env("FUBON_HISTORY_MAX_RANGE_DAYS", "364", minimum=1)
FUBON_HISTORY_CHUNK_DELAY_SECONDS = read_float_env("FUBON_HISTORY_CHUNK_DELAY_SECONDS", "0.3", minimum=0)


def _read_retry_delays() -> tuple[float, ...]:
    raw = read_text_env("FUBON_RATE_LIMIT_RETRY_DELAYS_SECONDS", "5,15,30")
    delays: list[float] = []
    for item in raw.split(","):
        text = item.strip()
        if not text:
            continue
        try:
            delay = float(text)
        except ValueError:
            log.warning("Ignoring invalid FUBON_RATE_LIMIT_RETRY_DELAYS_SECONDS value: %s", text)
            continue
        if delay >= 0:
            delays.append(delay)
    return tuple(delays or [5.0, 15.0, 30.0])


FUBON_RATE_LIMIT_RETRY_DELAYS_SECONDS = _read_retry_delays()


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


def _is_fubon_not_found_error(exc: Exception) -> bool:
    message = str(exc)
    return "Resource Not Found" in message or "Status: 404" in message or "statusCode\":404" in message


def _is_fubon_rate_limit_error(exc: Exception) -> bool:
    message = str(exc)
    return "Rate limit exceeded" in message or "Status: 429" in message or "statusCode\":429" in message


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
        raise_on_error: bool = False,
    ) -> int:
        normalized_ticker = normalize_ticker(ticker)
        if is_taiwan_stock_ticker(normalized_ticker):
            if not self._should_use_fubon_stock_history(normalized_ticker, interval):
                message = "Taiwan stock history is restricted to Fubon API and this interval is unsupported or Fubon is disconnected"
                log.warning("%s: %s (%s)", message, normalized_ticker, interval)
                await db.log_sync(normalized_ticker, "error", 0, message)
                if raise_on_error:
                    raise RuntimeError(message)
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
                if raise_on_error:
                    raise
                return 0
        return await self._yahoo.fetch_and_store(
            normalized_ticker,
            period=period,
            interval=interval,
            include_info=include_info,
        )

    async def fetch_realtime_quote(self, ticker: str) -> Optional[Dict]:
        normalized_ticker = normalize_ticker(ticker)
        if is_taiwan_stock_ticker(normalized_ticker) or is_taiwan_market_index_ticker(normalized_ticker):
            if not self._fubon_manager.connected:
                log.warning(
                    "Fubon realtime quote unavailable for %s; Yahoo fallback is disabled for Taiwan stocks/indexes",
                    normalized_ticker,
                )
                return None
            symbol = fubon_index_ticker_to_symbol(normalized_ticker) or tw_ticker_to_fubon(normalized_ticker)
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
            response = await self._fetch_fubon_historical_candle_chunk(
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
            if cursor <= end and FUBON_HISTORY_CHUNK_DELAY_SECONDS > 0:
                await asyncio.sleep(FUBON_HISTORY_CHUNK_DELAY_SECONDS)
        return {"symbol": symbol, "data": rows}

    async def _fetch_fubon_historical_candle_chunk(
        self,
        symbol: str,
        *,
        from_date: str,
        to_date: str,
        timeframe: str,
        adjusted: bool,
        sort: str,
    ) -> Optional[dict]:
        attempt = 0
        while True:
            try:
                return await self._fubon_manager.fetch_stock_historical_candles(
                    symbol,
                    from_date=from_date,
                    to_date=to_date,
                    timeframe=timeframe,
                    adjusted=adjusted,
                    sort=sort,
                )
            except Exception as exc:
                if _is_fubon_not_found_error(exc):
                    log.debug(
                        "Fubon historical candle chunk returned 404 for %s %s-%s; continuing",
                        symbol,
                        from_date,
                        to_date,
                    )
                    return None
                if _is_fubon_rate_limit_error(exc) and attempt < len(FUBON_RATE_LIMIT_RETRY_DELAYS_SECONDS):
                    delay_seconds = FUBON_RATE_LIMIT_RETRY_DELAYS_SECONDS[attempt]
                    attempt += 1
                    log.warning(
                        "Fubon historical candle chunk rate-limited for %s %s-%s; retrying in %.1fs",
                        symbol,
                        from_date,
                        to_date,
                        delay_seconds,
                    )
                    if delay_seconds > 0:
                        await asyncio.sleep(delay_seconds)
                    continue
                raise
