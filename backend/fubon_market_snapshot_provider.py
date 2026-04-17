from __future__ import annotations

import asyncio
import copy
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from fubon_quote_provider import fubon_timestamp_to_iso
from fubon_symbols import fubon_market_to_ticker
from tw_symbol_lookup import get_taiwan_ticker_industry

SNAPSHOT_CACHE_TTL_SECONDS = 60
SUPPORTED_MARKETS = {"TSE", "OTC"}
SUPPORTED_DIRECTIONS = {"up", "down"}
SUPPORTED_CHANGE_TYPES = {"percent", "value"}
SUPPORTED_ACTIVE_TRADES = {"value", "volume"}


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    try:
        return int(float(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _normalize_market(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in SUPPORTED_MARKETS:
        raise ValueError(f"Unsupported market '{value}'. Use one of: {', '.join(sorted(SUPPORTED_MARKETS))}")
    return normalized


def _normalize_direction(value: str) -> str:
    normalized = str(value or "up").strip().lower()
    if normalized not in SUPPORTED_DIRECTIONS:
        raise ValueError(
            f"Unsupported movers direction '{value}'. Use one of: {', '.join(sorted(SUPPORTED_DIRECTIONS))}"
        )
    return normalized


def _normalize_change(value: str) -> str:
    normalized = str(value or "percent").strip().lower()
    if normalized not in SUPPORTED_CHANGE_TYPES:
        raise ValueError(
            f"Unsupported movers change mode '{value}'. Use one of: {', '.join(sorted(SUPPORTED_CHANGE_TYPES))}"
        )
    return normalized


def _normalize_trade(value: str) -> str:
    normalized = str(value or "value").strip().lower()
    if normalized not in SUPPORTED_ACTIVE_TRADES:
        raise ValueError(
            f"Unsupported actives trade mode '{value}'. Use one of: {', '.join(sorted(SUPPORTED_ACTIVE_TRADES))}"
        )
    return normalized


def _normalize_snapshot_row(row: Dict[str, Any], market: str) -> Optional[Dict[str, Any]]:
    symbol = str(row.get("symbol") or "").strip().upper()
    if not symbol:
        return None

    resolved_market = str(row.get("market") or market).strip().upper() or market
    ticker = fubon_market_to_ticker(symbol, resolved_market)
    return {
        "ticker": ticker,
        "symbol": symbol,
        "market": resolved_market,
        "type": row.get("type"),
        "name": row.get("name") or symbol,
        "sector": get_taiwan_ticker_industry(ticker) or "未分類",
        "open": _coerce_float(row.get("openPrice")),
        "high": _coerce_float(row.get("highPrice")),
        "low": _coerce_float(row.get("lowPrice")),
        "price": _coerce_float(row.get("closePrice")),
        "change": _coerce_float(row.get("change")),
        "change_pct": _coerce_float(row.get("changePercent")),
        "volume": _coerce_int(row.get("tradeVolume")),
        "trade_value": _coerce_int(row.get("tradeValue")),
        "quote_timestamp": fubon_timestamp_to_iso(row.get("lastUpdated")),
    }


def _normalize_snapshot_payload(payload: Dict[str, Any], market: str) -> Dict[str, Any]:
    rows = [
        normalized
        for normalized in (
            _normalize_snapshot_row(item, market)
            for item in (payload.get("data") if isinstance(payload.get("data"), list) else [])
        )
        if normalized
    ]
    advancers = sum(1 for item in rows if (item.get("change_pct") or item.get("change") or 0) > 0)
    decliners = sum(1 for item in rows if (item.get("change_pct") or item.get("change") or 0) < 0)
    unchanged = max(len(rows) - advancers - decliners, 0)
    total_trade_value = sum(item.get("trade_value") or 0 for item in rows)

    return {
        "market": market,
        "date": payload.get("date"),
        "time": payload.get("time"),
        "summary": {
            "count": len(rows),
            "advancers": advancers,
            "decliners": decliners,
            "unchanged": unchanged,
            "total_trade_value": total_trade_value,
        },
        "data": rows,
    }


class FubonMarketSnapshotProvider:
    def __init__(self, manager, ttl_seconds: int = SNAPSHOT_CACHE_TTL_SECONDS):
        self._manager = manager
        self._ttl_seconds = ttl_seconds
        self._cache: Dict[tuple, tuple[float, Dict[str, Any]]] = {}
        self._locks: Dict[tuple, asyncio.Lock] = {}

    async def fetch_snapshot(self, market: str, *, refresh: bool = False) -> Optional[Dict[str, Any]]:
        normalized_market = _normalize_market(market)
        return await self._get_cached(
            ("snapshot", normalized_market),
            refresh=refresh,
            loader=lambda: self._load_snapshot(normalized_market),
        )

    async def fetch_movers(
        self,
        market: str,
        *,
        direction: str = "up",
        change: str = "percent",
        limit: int = 10,
        refresh: bool = False,
    ) -> Optional[Dict[str, Any]]:
        normalized_market = _normalize_market(market)
        normalized_direction = _normalize_direction(direction)
        normalized_change = _normalize_change(change)
        payload = await self._get_cached(
            ("movers", normalized_market, normalized_direction, normalized_change),
            refresh=refresh,
            loader=lambda: self._load_movers(normalized_market, normalized_direction, normalized_change),
        )
        if not payload:
            return None
        result = copy.deepcopy(payload)
        result["data"] = result.get("data", [])[: max(int(limit or 0), 0)]
        result["summary"] = {"count": len(result["data"])}
        return result

    async def fetch_actives(
        self,
        market: str,
        *,
        trade: str = "value",
        limit: int = 10,
        refresh: bool = False,
    ) -> Optional[Dict[str, Any]]:
        normalized_market = _normalize_market(market)
        normalized_trade = _normalize_trade(trade)
        payload = await self._get_cached(
            ("actives", normalized_market, normalized_trade),
            refresh=refresh,
            loader=lambda: self._load_actives(normalized_market, normalized_trade),
        )
        if not payload:
            return None
        result = copy.deepcopy(payload)
        result["data"] = result.get("data", [])[: max(int(limit or 0), 0)]
        result["summary"] = {"count": len(result["data"])}
        return result

    async def _get_cached(
        self,
        key: tuple,
        *,
        refresh: bool,
        loader: Callable[[], Awaitable[Optional[Dict[str, Any]]]],
    ) -> Optional[Dict[str, Any]]:
        cached = self._cache.get(key)
        if not refresh and cached and (time.monotonic() - cached[0]) < self._ttl_seconds:
            return copy.deepcopy(cached[1])

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self._cache.get(key)
            if not refresh and cached and (time.monotonic() - cached[0]) < self._ttl_seconds:
                return copy.deepcopy(cached[1])

            payload = await loader()
            if not payload:
                return None
            self._cache[key] = (time.monotonic(), payload)
            return copy.deepcopy(payload)

    async def _load_snapshot(self, market: str) -> Optional[Dict[str, Any]]:
        payload = await self._manager.fetch_stock_snapshot_quotes(market=market)
        if not payload:
            return None
        return _normalize_snapshot_payload(payload, market)

    async def _load_movers(self, market: str, direction: str, change: str) -> Optional[Dict[str, Any]]:
        payload = await self._manager.fetch_stock_snapshot_movers(
            market=market,
            direction=direction,
            change=change,
        )
        if not payload:
            return None
        normalized = _normalize_snapshot_payload(payload, market)
        normalized["direction"] = direction
        normalized["change"] = change
        return normalized

    async def _load_actives(self, market: str, trade: str) -> Optional[Dict[str, Any]]:
        payload = await self._manager.fetch_stock_snapshot_actives(market=market, trade=trade)
        if not payload:
            return None
        normalized = _normalize_snapshot_payload(payload, market)
        normalized["trade"] = trade
        return normalized
