from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote as urlquote

import requests

from data_fetcher import DataFetcher, normalize_ticker
from database import db


log = logging.getLogger(__name__)

YAHOO_QUOTE_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 QuantVision/1.0"}
MACRO_METRICS = [
    {"metric_code": "VIX", "metric_name": "CBOE Volatility Index", "ticker": "^VIX"},
    {"metric_code": "DXY", "metric_name": "US Dollar Index", "ticker": "DX-Y.NYB"},
    {"metric_code": "US10Y", "metric_name": "US 10Y Treasury Yield", "ticker": "^TNX"},
    {"metric_code": "TWDUSD", "metric_name": "Taiwan Dollar FX", "ticker": "TWD=X"},
    {"metric_code": "SOX", "metric_name": "PHLX Semiconductor", "ticker": "^SOX"},
    {"metric_code": "SPX", "metric_name": "S&P 500", "ticker": "^GSPC"},
    {"metric_code": "TWII", "metric_name": "Taiwan Weighted Index", "ticker": "^TWII"},
]


def infer_market(ticker: Optional[str]) -> Optional[str]:
    if not ticker:
        return None
    normalized = normalize_ticker(ticker)
    if normalized.endswith(".TW") or normalized.endswith(".TWO"):
        return "TW"
    if normalized.endswith(".HK"):
        return "HK"
    if normalized.startswith("^"):
        return "INDEX"
    return "US"


class MarketEventProvider:
    def __init__(self, session: Optional[requests.Session] = None):
        self._session = session or requests.Session()
        self._session.headers.update(REQUEST_HEADERS)

    async def sync_ticker_events(self, ticker: str) -> List[Dict[str, Any]]:
        normalized = normalize_ticker(ticker)
        loop = asyncio.get_running_loop()
        events = await loop.run_in_executor(None, self._fetch_ticker_events_sync, normalized)
        if events:
            await db.upsert_market_events(events)
        return await db.list_market_events(ticker=normalized, limit=20)

    async def sync_events_for_tickers(self, tickers: List[str]) -> int:
        total = 0
        for ticker in dict.fromkeys(normalize_ticker(item) for item in tickers if item):
            try:
                events = await self.sync_ticker_events(ticker)
                total += len(events)
            except Exception as exc:
                log.warning("event sync failed for %s: %s", ticker, exc)
        return total

    def _fetch_ticker_events_sync(self, ticker: str) -> List[Dict[str, Any]]:
        payload = self._request_quote_summary(ticker, modules="calendarEvents,summaryDetail,price")
        result = payload.get("quoteSummary", {}).get("result") or []
        if not result:
            return []
        source = result[0]
        market = infer_market(ticker)
        events: List[Dict[str, Any]] = []

        earnings = ((source.get("calendarEvents") or {}).get("earnings") or {}).get("earningsDate") or []
        for item in earnings:
            raw_date = (item or {}).get("raw")
            event_date = _timestamp_to_date(raw_date)
            if not event_date:
                continue
            events.append(
                {
                    "event_type": "earnings",
                    "market": market,
                    "ticker": ticker,
                    "title": f"{ticker} Earnings",
                    "description": "Yahoo Finance calendarEvents earningsDate",
                    "event_date": event_date,
                    "event_time": _timestamp_to_iso(raw_date),
                    "importance": "high",
                    "source": "yahoo_finance",
                    "url": f"https://finance.yahoo.com/quote/{urlquote(ticker)}",
                    "payload": {"raw": item},
                }
            )

        ex_dividend = ((source.get("summaryDetail") or {}).get("exDividendDate") or {}).get("raw")
        ex_dividend_date = _timestamp_to_date(ex_dividend)
        if ex_dividend_date:
            events.append(
                {
                    "event_type": "ex_dividend",
                    "market": market,
                    "ticker": ticker,
                    "title": f"{ticker} Ex-Dividend",
                    "description": "Yahoo Finance summaryDetail exDividendDate",
                    "event_date": ex_dividend_date,
                    "event_time": _timestamp_to_iso(ex_dividend),
                    "importance": "medium",
                    "source": "yahoo_finance",
                    "url": f"https://finance.yahoo.com/quote/{urlquote(ticker)}",
                    "payload": {"raw": ex_dividend},
                }
            )

        return events

    def _request_quote_summary(self, ticker: str, *, modules: str) -> Dict[str, Any]:
        response = self._session.get(
            YAHOO_QUOTE_SUMMARY_URL.format(ticker=urlquote(ticker)),
            params={"modules": modules},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()


class NewsProvider:
    def __init__(self, session: Optional[requests.Session] = None):
        self._session = session or requests.Session()
        self._session.headers.update(REQUEST_HEADERS)

    async def sync_ticker_news(self, ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
        normalized = normalize_ticker(ticker)
        loop = asyncio.get_running_loop()
        articles = await loop.run_in_executor(None, self._fetch_ticker_news_sync, normalized, limit)
        if articles:
            await db.upsert_news_articles(articles)
        return await db.list_news_articles(ticker=normalized, limit=limit)

    def _fetch_ticker_news_sync(self, ticker: str, limit: int) -> List[Dict[str, Any]]:
        response = self._session.get(
            YAHOO_SEARCH_URL,
            params={
                "q": ticker,
                "newsCount": max(1, min(limit, 20)),
                "quotesCount": 0,
                "enableFuzzyQuery": "false",
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        market = infer_market(ticker)
        articles = []
        for item in payload.get("news") or []:
            title = (item or {}).get("title")
            link = (item or {}).get("link")
            published = _timestamp_to_iso((item or {}).get("providerPublishTime"))
            if not title or not link or not published:
                continue
            articles.append(
                {
                    "ticker": ticker,
                    "market": market,
                    "title": title,
                    "summary": (item or {}).get("publisher"),
                    "published_at": published,
                    "source": (item or {}).get("publisher") or "yahoo_finance",
                    "url": link,
                    "sentiment": None,
                    "payload": {"raw": item},
                }
            )
        return articles


class MacroSnapshotProvider:
    def __init__(self, fetcher: Optional[DataFetcher] = None):
        self._fetcher = fetcher or DataFetcher()

    async def sync_macro_snapshots(self) -> List[Dict[str, Any]]:
        snapshot_date = date.today().isoformat()
        snapshots = []
        for metric in MACRO_METRICS:
            try:
                quote = await self._fetcher.fetch_realtime_quote(metric["ticker"])
            except Exception as exc:
                log.warning("macro quote fetch failed for %s: %s", metric["ticker"], exc)
                continue
            if not quote:
                continue
            snapshots.append(
                {
                    "metric_code": metric["metric_code"],
                    "metric_name": metric["metric_name"],
                    "value": quote.get("price"),
                    "date": snapshot_date,
                    "source": quote.get("source") or "yahoo_finance",
                    "payload": {
                        "ticker": metric["ticker"],
                        "change": quote.get("change"),
                        "change_pct": quote.get("change_pct"),
                        "quote_timestamp": quote.get("quote_timestamp"),
                        "is_delayed": quote.get("is_delayed", True),
                    },
                }
            )
        if snapshots:
            await db.upsert_macro_snapshots(snapshots)
        return await db.list_macro_snapshots(snapshot_date)


def _timestamp_to_date(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _timestamp_to_iso(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None
