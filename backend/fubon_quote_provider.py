from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from data_fetcher import normalize_ticker
from fubon_symbols import (
    fubon_market_to_ticker,
    is_taiwan_stock_ticker,
    tw_ticker_to_fubon,
)
from quote_provider import QuoteProvider


def fubon_timestamp_to_iso(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    while numeric > 10_000_000_000:
        numeric /= 1000.0
    try:
        return datetime.fromtimestamp(numeric, timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def _normalize_order_levels(levels: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(levels, list):
        return normalized
    for item in levels[:5]:
        if not isinstance(item, dict):
            continue
        price = item.get("price")
        size = item.get("size")
        try:
            normalized.append(
                {
                    "price": float(price) if price is not None else None,
                    "size": int(size) if size is not None else None,
                }
            )
        except (TypeError, ValueError):
            continue
    return normalized


def build_fubon_quote_payload(
    ticker: str,
    payload: Dict[str, Any],
    *,
    source: str = "fubon_neo",
) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None

    normalized_ticker = normalize_ticker(ticker)
    price = payload.get("closePrice")
    if price is None:
        price = payload.get("lastPrice")
    if price is None:
        return None

    bids = _normalize_order_levels(payload.get("bids"))
    asks = _normalize_order_levels(payload.get("asks"))
    total = payload.get("total") if isinstance(payload.get("total"), dict) else {}

    previous_close = payload.get("previousClose")
    change = payload.get("change")
    if change is None and previous_close not in (None, ""):
        try:
            change = float(price) - float(previous_close)
        except (TypeError, ValueError):
            change = None

    return {
        "ticker": normalized_ticker,
        "resolved_symbol": str(payload.get("symbol") or tw_ticker_to_fubon(normalized_ticker) or normalized_ticker),
        "market": payload.get("market"),
        "exchange": payload.get("exchange"),
        "source": source,
        "quote_type": "realtime",
        "is_delayed": False,
        "name": payload.get("name") or normalized_ticker,
        "currency": "TWD",
        "price": float(price),
        "open": payload.get("openPrice"),
        "high": payload.get("highPrice"),
        "low": payload.get("lowPrice"),
        "prev_close": previous_close,
        "change": change,
        "change_pct": payload.get("changePercent"),
        "volume": total.get("tradeVolume"),
        "market_cap": None,
        "bid": bids[0].get("price") if bids else None,
        "ask": asks[0].get("price") if asks else None,
        "bid_size": bids[0].get("size") if bids else None,
        "ask_size": asks[0].get("size") if asks else None,
        "bids": bids,
        "asks": asks,
        "quote_timestamp": fubon_timestamp_to_iso(
            payload.get("lastUpdated")
            or payload.get("closeTime")
            or total.get("time")
            or payload.get("date")
        ),
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
    }


class FubonQuoteProvider(QuoteProvider):
    provider_name = "fubon_neo"
    quote_type = "realtime"
    is_delayed = False

    def __init__(self, manager):
        self._manager = manager

    async def fetch_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        normalized_ticker = normalize_ticker(ticker)
        symbol = tw_ticker_to_fubon(normalized_ticker)
        if not symbol:
            return None

        response = await self._manager.fetch_stock_quote(symbol)
        if not response:
            return None

        market = response.get("market")
        resolved_ticker = (
            fubon_market_to_ticker(response.get("symbol") or symbol, market)
            if market
            else normalized_ticker
        )
        payload = build_fubon_quote_payload(resolved_ticker, response, source=self.provider_name)
        if not payload:
            return None
        payload["ticker"] = normalized_ticker
        payload["resolved_symbol"] = response.get("symbol") or symbol
        return payload


class HybridQuoteProvider(QuoteProvider):
    provider_name = "hybrid"
    quote_type = "mixed"
    is_delayed = True

    def __init__(self, fubon_provider: QuoteProvider, yahoo_provider: QuoteProvider):
        self._fubon = fubon_provider
        self._yahoo = yahoo_provider

    async def fetch_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        normalized_ticker = normalize_ticker(ticker)
        if is_taiwan_stock_ticker(normalized_ticker):
            fubon_quote = await self._fubon.fetch_quote(normalized_ticker)
            if fubon_quote:
                return fubon_quote
        return await self._yahoo.fetch_quote(normalized_ticker)
