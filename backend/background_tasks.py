"""Background task services used by the API lifespan and scheduler."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from data_fetcher import normalize_ticker


@dataclass(slots=True)
class BackgroundTaskService:
    db: Any
    fetcher: Any
    quote_provider: Any
    macro_snapshot_provider: Any
    market_event_provider: Any
    news_provider: Any
    startup_download_tickers: list[str]
    startup_download_delay_seconds: float
    latest_data_sync_period: str
    latest_data_sync_interval: str
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))
    _tracked_sync_lock: asyncio.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._tracked_sync_lock = asyncio.Lock()

    async def get_tracked_sync_tickers(self) -> list[str]:
        groups = await self.db.get_watchlist_groups()
        tickers = [
            normalize_ticker(item["ticker"])
            for group in groups
            for item in group.get("items", [])
            if item.get("ticker")
        ]
        if not tickers:
            return list(self.startup_download_tickers)
        return list(dict.fromkeys(tickers))

    async def sync_tracked_market_data(
        self,
        period: str | None = None,
        interval: str | None = None,
        reason: str = "manual",
    ) -> dict:
        normalized_period = (period or self.latest_data_sync_period).lower()
        normalized_interval = (interval or self.latest_data_sync_interval).lower()
        tickers = await self.get_tracked_sync_tickers()

        async with self._tracked_sync_lock:
            self.logger.info(
                "Tracked market sync started: reason=%s tickers=%s period=%s interval=%s",
                reason,
                len(tickers),
                normalized_period,
                normalized_interval,
            )
            successes = []
            failures = []
            total_rows = 0
            for index, ticker in enumerate(tickers):
                try:
                    synced = await self.fetcher.fetch_and_store(
                        ticker,
                        period=normalized_period,
                        interval=normalized_interval,
                        include_info=False,
                    )
                    total_rows += synced
                    successes.append({"ticker": ticker, "synced": synced})
                    await self.db.log_sync(
                        ticker,
                        "success",
                        synced,
                        f"{reason}:{normalized_period}/{normalized_interval}",
                    )
                except Exception as exc:
                    message = str(exc)
                    failures.append({"ticker": ticker, "message": message})
                    await self.db.log_sync(ticker, "error", 0, f"{reason}:{message[:500]}")
                    self.logger.warning("Tracked sync failed for %s (%s): %s", ticker, reason, exc)
                if index < len(tickers) - 1:
                    await asyncio.sleep(self.startup_download_delay_seconds)

            self.logger.info(
                "Tracked market sync finished: reason=%s success=%s failure=%s rows=%s",
                reason,
                len(successes),
                len(failures),
                total_rows,
            )
            return {
                "reason": reason,
                "period": normalized_period,
                "interval": normalized_interval,
                "tickers": tickers,
                "success_count": len(successes),
                "failure_count": len(failures),
                "total_rows": total_rows,
                "results": successes,
                "failures": failures,
            }

    async def fetch_and_store_quote_snapshot(self, ticker: str) -> dict | None:
        ticker = normalize_ticker(ticker)
        quote = await self.quote_provider.fetch_quote(ticker)
        if not quote:
            return None
        return await self.db.upsert_market_quote(quote)

    async def sync_market_intelligence_snapshot(self, reason: str = "manual") -> dict:
        tickers = await self.get_tracked_sync_tickers()
        macro_items = await self.macro_snapshot_provider.sync_macro_snapshots()
        event_count = await self.market_event_provider.sync_events_for_tickers(tickers)
        news_count = 0
        for ticker in tickers[:20]:
            try:
                articles = await self.news_provider.sync_ticker_news(ticker, limit=6)
                news_count += len(articles)
            except Exception as exc:
                self.logger.debug("news sync failed for %s (%s): %s", ticker, reason, exc)
        return {
            "reason": reason,
            "macro_count": len(macro_items),
            "event_count": event_count,
            "news_count": news_count,
            "tracked_tickers": len(tickers),
        }

    async def fetch_startup_history_for_ticker(self, ticker: str) -> int:
        return await self.fetcher.fetch_and_store(ticker, period="2y", include_info=False)
