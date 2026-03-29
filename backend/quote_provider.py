from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from data_fetcher import normalize_ticker


class QuoteProvider(ABC):
    provider_name = "abstract"
    quote_type = "snapshot"
    is_delayed = True

    @abstractmethod
    async def fetch_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class YahooFinanceQuoteProvider(QuoteProvider):
    provider_name = "yahoo_finance"
    quote_type = "delayed_snapshot"
    is_delayed = True

    def __init__(self, fetcher):
        self._fetcher = fetcher

    async def fetch_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        normalized_ticker = normalize_ticker(ticker)
        quote = await self._fetcher.fetch_realtime_quote(normalized_ticker)
        if not quote:
            return None

        payload = dict(quote)
        payload["ticker"] = normalized_ticker
        payload.setdefault("source", self.provider_name)
        payload.setdefault("quote_type", self.quote_type)
        payload.setdefault("is_delayed", self.is_delayed)
        return payload
