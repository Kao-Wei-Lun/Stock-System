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


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _coerce_positive_float(value: Any) -> Optional[float]:
    numeric = _coerce_float(value)
    return numeric if numeric is not None and numeric > 0 else None


def _normalize_order_levels(levels: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(levels, list):
        return normalized
    for item in levels[:5]:
        if not isinstance(item, dict):
            continue
        price = _coerce_positive_float(item.get("price"))
        size = item.get("size")
        if price is None:
            continue
        try:
            normalized.append(
                {
                    "price": price,
                    "size": int(size) if size is not None else None,
                }
            )
        except (TypeError, ValueError):
            continue
    return normalized


def _normalize_scalar_book_level(price: Any, size: Any = None) -> list[dict[str, Any]]:
    normalized_price = _coerce_positive_float(price)
    if normalized_price is None:
        return []
    try:
        return [
            {
                "price": normalized_price,
                "size": int(size) if size not in (None, "") else None,
            }
        ]
    except (TypeError, ValueError):
        return []


def build_fubon_quote_payload(
    ticker: str,
    payload: Dict[str, Any],
    *,
    source: str = "fubon_neo",
) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None

    normalized_ticker = normalize_ticker(ticker)
    price = _coerce_positive_float(payload.get("closePrice"))
    if price is None:
        price = _coerce_positive_float(payload.get("lastPrice"))
    if price is None:
        price = _coerce_positive_float(payload.get("price"))
    if price is None and isinstance(payload.get("lastTrade"), dict):
        price = _coerce_positive_float(payload["lastTrade"].get("price"))
    if price is None and isinstance(payload.get("trades"), list) and payload["trades"]:
        price = _coerce_positive_float(payload["trades"][0].get("price"))
    if price is None:
        return None

    latest_trade = payload["trades"][0] if isinstance(payload.get("trades"), list) and payload["trades"] else {}
    bids = _normalize_order_levels(payload.get("bids"))
    asks = _normalize_order_levels(payload.get("asks"))
    if not bids:
        bids = _normalize_scalar_book_level(payload.get("bid") or latest_trade.get("bid"))
    if not asks:
        asks = _normalize_scalar_book_level(payload.get("ask") or latest_trade.get("ask"))
    total = payload.get("total") if isinstance(payload.get("total"), dict) else {}

    previous_close = _coerce_positive_float(payload.get("previousClose"))
    change = _coerce_float(payload.get("change"))
    if change is None and previous_close not in (None, ""):
        try:
            change = price - previous_close
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
        "price": price,
        "open": _coerce_positive_float(payload.get("openPrice")),
        "high": _coerce_positive_float(payload.get("highPrice")),
        "low": _coerce_positive_float(payload.get("lowPrice")),
        "prev_close": previous_close,
        "change": change,
        "change_pct": _coerce_float(payload.get("changePercent")),
        "volume": payload.get("volume") or total.get("tradeVolume"),
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
            or payload.get("time")
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
            return fubon_quote
        return await self._yahoo.fetch_quote(normalized_ticker)
