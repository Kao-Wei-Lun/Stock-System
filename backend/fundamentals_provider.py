from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote as urlquote

import requests

from data_fetcher import normalize_ticker
from database import db


log = logging.getLogger(__name__)

YAHOO_QUOTE_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 QuantVision/1.0"}


def _raw_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("raw", value.get("fmt"))
    return value


class FundamentalsProvider:
    def __init__(self, session: Optional[requests.Session] = None):
        self._session = session or requests.Session()
        self._session.headers.update(REQUEST_HEADERS)

    async def sync_ticker_fundamentals(self, ticker: str) -> Optional[Dict[str, Any]]:
        normalized = normalize_ticker(ticker)
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, self._fetch_ticker_fundamentals_sync, normalized)
        if info:
            await db.upsert_stock_info(normalized, info)
        return await db.get_stock_info(normalized)

    def _fetch_ticker_fundamentals_sync(self, ticker: str) -> Dict[str, Any]:
        response = self._session.get(
            YAHOO_QUOTE_SUMMARY_URL.format(ticker=urlquote(ticker)),
            params={"modules": "price,summaryDetail,defaultKeyStatistics,assetProfile"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("quoteSummary", {}).get("result") or []
        if not result:
            return {}
        source = result[0]
        price = source.get("price") or {}
        summary_detail = source.get("summaryDetail") or {}
        key_stats = source.get("defaultKeyStatistics") or {}
        profile = source.get("assetProfile") or {}

        return {
            "longName": price.get("longName") or price.get("shortName") or ticker,
            "shortName": price.get("shortName") or price.get("longName") or ticker,
            "sector": profile.get("sector"),
            "industry": profile.get("industry"),
            "marketCap": _raw_value(price.get("marketCap")) or _raw_value(key_stats.get("marketCap")),
            "trailingPE": _raw_value(summary_detail.get("trailingPE")) or _raw_value(key_stats.get("trailingPE")),
            "dividendYield": _raw_value(summary_detail.get("dividendYield")),
            "fiftyTwoWeekHigh": _raw_value(summary_detail.get("fiftyTwoWeekHigh")),
            "fiftyTwoWeekLow": _raw_value(summary_detail.get("fiftyTwoWeekLow")),
            "averageVolume": _raw_value(summary_detail.get("averageVolume")),
            "longBusinessSummary": profile.get("longBusinessSummary"),
            "currency": price.get("currency"),
            "exchange": price.get("exchangeName") or price.get("exchange"),
            "country": profile.get("country") or price.get("exchangeTimezoneName"),
        }


def build_fundamental_summary(info: Optional[Dict[str, Any]], events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if not info:
        return {
            "headline": "尚未同步基本面資料",
            "signals": [],
            "metrics": {},
        }

    signals: List[Dict[str, str]] = []
    metrics = {
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "pe_ratio": info.get("pe_ratio"),
        "dividend_yield": info.get("dividend_yield"),
        "week_52_high": info.get("week_52_high"),
        "week_52_low": info.get("week_52_low"),
        "avg_volume": info.get("avg_volume"),
        "market_cap": info.get("market_cap"),
        "exchange": info.get("exchange"),
        "currency": info.get("currency"),
    }

    pe_ratio = info.get("pe_ratio")
    dividend_yield = info.get("dividend_yield")
    if pe_ratio is not None:
        if pe_ratio <= 18:
            signals.append({"tone": "positive", "label": "評價偏低", "value": f"PE {pe_ratio:.2f}"})
        elif pe_ratio >= 35:
            signals.append({"tone": "caution", "label": "評價偏高", "value": f"PE {pe_ratio:.2f}"})
    if dividend_yield is not None:
        if dividend_yield >= 0.04:
            signals.append({"tone": "positive", "label": "殖利率偏高", "value": f"{dividend_yield * 100:.2f}%"})
        elif dividend_yield <= 0.01:
            signals.append({"tone": "neutral", "label": "成長型標的", "value": f"{dividend_yield * 100:.2f}%"})

    upcoming = sorted(
        [
            item for item in (events or [])
            if item.get("event_type") in {"earnings", "ex_dividend"}
        ],
        key=lambda item: (item.get("event_date") or "", item.get("event_time") or ""),
    )
    if upcoming:
        first = upcoming[0]
        signals.append(
            {
                "tone": "event",
                "label": "近期事件",
                "value": f"{first.get('title') or first.get('event_type')} / {first.get('event_date') or 'N/A'}",
            }
        )

    headline = info.get("name") or info.get("ticker") or "基本面資料"
    if info.get("sector") and info.get("industry"):
        headline = f"{headline} / {info['sector']} / {info['industry']}"

    return {
        "headline": headline,
        "signals": signals[:4],
        "metrics": metrics,
        "description": info.get("description") or "",
        "updated_at": info.get("updated_at"),
    }
