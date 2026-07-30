"""Market-aware quote refresh coordination for non-Taiwan instruments.

The coordinator keeps provider traffic bounded and exposes one source of truth
for background refreshes, API requests, and data-quality explanations. Taiwan
stocks, indexes, and futures remain on the Fubon/TAIFEX paths.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from data_fetcher import normalize_ticker
from fubon_symbols import is_exact_futopt_contract
from market_freshness import market_aware_freshness, market_session_state, parse_market_timestamp


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value else None


def _error_category(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}".lower()
    if "429" in text or "too many request" in text or "rate limit" in text:
        return "rate_limit"
    if "timeout" in text or isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "timeout"
    if any(token in text for token in ("401", "403", "unauthorized", "forbidden")):
        return "authentication"
    if "empty" in text or "no quote" in text:
        return "empty_response"
    return "provider_error"


def is_taiwan_provider_ticker(ticker: str) -> bool:
    symbol = normalize_ticker(ticker)
    return (
        symbol.startswith("*")
        or symbol.endswith((".TW", ".TWO"))
        or symbol in {"^TWII", "^TWOII", "TX", "TXF", "MTX", "MXF", "TMF", "EXF", "FXF"}
        or is_exact_futopt_contract(symbol)
    )


@dataclass(slots=True)
class QuoteRefreshState:
    ticker: str
    provider: str
    market: str
    expected_freshness_seconds: int
    priority: str = "watchlist"
    last_attempt: datetime | None = None
    last_success: datetime | None = None
    last_provider_timestamp: datetime | None = None
    next_refresh: datetime | None = None
    backoff_until: datetime | None = None
    last_error_category: str | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    refresh_status: str = "pending"

    def snapshot(self, *, now: datetime | None = None) -> dict[str, Any]:
        reference = now or datetime.now(timezone.utc)
        return {
            **asdict(self),
            "last_attempt": _iso(self.last_attempt),
            "last_success": _iso(self.last_success),
            "last_provider_timestamp": _iso(self.last_provider_timestamp),
            "next_refresh": _iso(self.next_refresh),
            "backoff_until": _iso(self.backoff_until),
            "in_backoff": bool(self.backoff_until and reference < self.backoff_until),
        }


class QuoteRefreshService:
    def __init__(
        self,
        *,
        fetch_and_store_quote: Callable[[str], Any],
        get_cached_quote: Callable[[str], Any],
        get_watchlist_tickers: Callable[[], Any],
        get_active_tickers: Callable[[], Any],
        broadcast_quote: Callable[[str, dict], Any] | None = None,
        enabled: bool = True,
        max_concurrency: int = 2,
        scan_interval_seconds: float = 15.0,
        active_open_interval_seconds: int = 60,
        watchlist_open_interval_seconds: int = 300,
        crypto_interval_seconds: int = 180,
        closed_interval_seconds: int = 1800,
        manual_min_interval_seconds: int = 10,
        request_timeout_seconds: float = 20.0,
        startup_delay_seconds: float = 8.0,
        clock: Callable[[], datetime] | None = None,
        logger: logging.Logger | None = None,
    ):
        self.enabled = bool(enabled)
        self._fetch_and_store_quote = fetch_and_store_quote
        self._get_cached_quote = get_cached_quote
        self._get_watchlist_tickers = get_watchlist_tickers
        self._get_active_tickers = get_active_tickers
        self._broadcast_quote = broadcast_quote
        self._max_concurrency = max(1, int(max_concurrency))
        self._semaphore = asyncio.Semaphore(self._max_concurrency)
        self._scan_interval_seconds = max(1.0, float(scan_interval_seconds))
        self._active_open_interval_seconds = max(15, int(active_open_interval_seconds))
        self._watchlist_open_interval_seconds = max(30, int(watchlist_open_interval_seconds))
        self._crypto_interval_seconds = max(30, int(crypto_interval_seconds))
        self._closed_interval_seconds = max(300, int(closed_interval_seconds))
        self._manual_min_interval_seconds = max(1, int(manual_min_interval_seconds))
        self._request_timeout_seconds = max(1.0, float(request_timeout_seconds))
        self._startup_delay_seconds = max(0.0, float(startup_delay_seconds))
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._log = logger or logging.getLogger(__name__)
        self._states: dict[str, QuoteRefreshState] = {}
        self._flights: dict[str, asyncio.Task] = {}
        self._flight_lock = asyncio.Lock()
        self._provider_backoff_until: datetime | None = None
        self._provider_failures = 0
        self._request_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._throttled_count = 0
        self._active_requests = 0
        self._peak_concurrency = 0
        self._last_scan_at: datetime | None = None

    @staticmethod
    def supports_background_refresh(ticker: str) -> bool:
        return bool(normalize_ticker(ticker)) and not is_taiwan_provider_ticker(ticker)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _interval_for(self, ticker: str, priority: str, now: datetime) -> tuple[int, dict[str, Any]]:
        session = market_session_state(ticker, now=now)
        if session["market"] == "always_open":
            interval = self._crypto_interval_seconds
        elif session["market_is_open"]:
            interval = (
                self._active_open_interval_seconds
                if priority == "active"
                else self._watchlist_open_interval_seconds
            )
        else:
            interval = self._closed_interval_seconds
        return interval, session

    def _ensure_state(self, ticker: str, *, priority: str | None = None) -> QuoteRefreshState:
        normalized = normalize_ticker(ticker)
        now = self._now()
        selected_priority = priority or "watchlist"
        interval, session = self._interval_for(normalized, selected_priority, now)
        state = self._states.get(normalized)
        if state is None:
            state = QuoteRefreshState(
                ticker=normalized,
                provider="fubon_neo" if is_taiwan_provider_ticker(normalized) else "yahoo_finance",
                market=session["market"],
                expected_freshness_seconds=interval,
                priority=selected_priority,
            )
            self._states[normalized] = state
        else:
            state.market = session["market"]
            if priority is not None:
                state.priority = selected_priority
            state.expected_freshness_seconds = interval
        return state

    def state_for(self, ticker: str) -> dict[str, Any]:
        state = self._ensure_state(ticker, priority=None)
        now = self._now()
        snapshot = state.snapshot(now=now)
        session = market_session_state(ticker, now=now)
        snapshot.update({
            "market_is_open": session["market_is_open"],
            "market_timezone": session["market_timezone"],
            "next_market_open": session["next_market_open"],
            "provider_degraded": bool(
                (state.backoff_until and now < state.backoff_until)
                or (self._provider_backoff_until and now < self._provider_backoff_until)
            ),
        })
        return snapshot

    def enrich_freshness(self, ticker: str, freshness: dict[str, Any]) -> dict[str, Any]:
        state = self.state_for(ticker)
        if freshness.get("freshness_status") == "missing":
            stale_reason = "missing_quote"
        elif freshness.get("is_stale") and state.get("in_backoff"):
            stale_reason = "provider_backoff"
        elif freshness.get("is_stale") and freshness.get("market_is_open"):
            stale_reason = "market_open_quote_expired"
        elif freshness.get("is_stale"):
            stale_reason = "completed_session_missing"
        elif freshness.get("freshness_status") == "market_closed":
            stale_reason = "market_closed_latest_session_valid"
        else:
            stale_reason = None
        return {
            **freshness,
            "stale_reason": stale_reason,
            "refresh_status": state["refresh_status"],
            "refresh_provider": state["provider"],
            "next_refresh": state["next_refresh"],
            "backoff_until": state["backoff_until"],
            "last_refresh_error_category": state["last_error_category"],
            "provider_degraded": state["provider_degraded"],
        }

    async def get_for_api(self, ticker: str, *, force: bool = False) -> dict | None:
        normalized = normalize_ticker(ticker)
        if is_taiwan_provider_ticker(normalized):
            quote = await self._refresh_direct(normalized)
            return await self._decorate_quote(normalized, quote)

        cached = await self._get_cached_quote(normalized)
        now = self._now()
        state = self._ensure_state(normalized, priority="active")
        freshness = market_aware_freshness(
            (cached or {}).get("quote_timestamp") or (cached or {}).get("synced_at"),
            ticker=normalized,
            data_origin="quote",
            now=now,
        )
        due = (
            force
            or cached is None
            or freshness.get("is_stale")
            or state.next_refresh is None
            or now >= state.next_refresh
        )
        quote = await self.refresh(normalized, priority="active", manual=force) if due else cached
        return await self._decorate_quote(normalized, quote or cached)

    async def _refresh_direct(self, ticker: str) -> dict | None:
        try:
            return await asyncio.wait_for(
                self._fetch_and_store_quote(ticker),
                timeout=self._request_timeout_seconds,
            )
        except Exception:
            return await self._get_cached_quote(ticker)

    async def _decorate_quote(self, ticker: str, quote: dict | None) -> dict | None:
        if not quote:
            return None
        result = dict(quote)
        freshness = market_aware_freshness(
            result.get("quote_timestamp") or result.get("synced_at"),
            ticker=ticker,
            data_origin="quote",
            now=self._now(),
        )
        result.update(self.enrich_freshness(ticker, freshness))
        return result

    async def refresh(
        self,
        ticker: str,
        *,
        priority: str = "watchlist",
        manual: bool = False,
    ) -> dict | None:
        normalized = normalize_ticker(ticker)
        if not self.supports_background_refresh(normalized):
            return await self._refresh_direct(normalized)

        now = self._now()
        state = self._ensure_state(normalized, priority=priority)
        if manual and state.last_attempt:
            retry_at = state.last_attempt + timedelta(seconds=self._manual_min_interval_seconds)
            if now < retry_at:
                self._throttled_count += 1
                state.refresh_status = "throttled"
                state.next_refresh = retry_at
                return await self._get_cached_quote(normalized)

        backoff_until = max(
            [value for value in (state.backoff_until, self._provider_backoff_until) if value],
            default=None,
        )
        if backoff_until and now < backoff_until:
            self._throttled_count += 1
            state.refresh_status = "backoff"
            state.next_refresh = backoff_until
            return await self._get_cached_quote(normalized)

        async with self._flight_lock:
            task = self._flights.get(normalized)
            if task is None:
                task = asyncio.create_task(
                    self._perform_refresh(normalized, priority=priority),
                    name=f"quote-refresh:{normalized}",
                )
                self._flights[normalized] = task
        try:
            return await task
        finally:
            async with self._flight_lock:
                if self._flights.get(normalized) is task and task.done():
                    self._flights.pop(normalized, None)

    async def _perform_refresh(self, ticker: str, *, priority: str) -> dict | None:
        state = self._ensure_state(ticker, priority=priority)
        now = self._now()
        state.last_attempt = now
        state.refresh_status = "refreshing"
        self._request_count += 1
        try:
            async with self._semaphore:
                self._active_requests += 1
                self._peak_concurrency = max(self._peak_concurrency, self._active_requests)
                try:
                    quote = await asyncio.wait_for(
                        self._fetch_and_store_quote(ticker),
                        timeout=self._request_timeout_seconds,
                    )
                finally:
                    self._active_requests -= 1
            if not quote:
                raise RuntimeError("provider returned no quote")

            completed_at = self._now()
            interval, _ = self._interval_for(ticker, priority, completed_at)
            state.expected_freshness_seconds = interval
            state.last_success = completed_at
            state.last_provider_timestamp = parse_market_timestamp(
                quote.get("quote_timestamp") or quote.get("synced_at")
            )
            state.next_refresh = completed_at + timedelta(seconds=interval)
            state.backoff_until = None
            state.last_error_category = None
            state.last_error = None
            state.consecutive_failures = 0
            state.refresh_status = "refreshed"
            self._provider_failures = 0
            self._provider_backoff_until = None
            self._success_count += 1
            if callable(self._broadcast_quote):
                await self._broadcast_quote(
                    ticker,
                    {
                        "type": "quote",
                        "ticker": ticker,
                        "data": quote,
                        "ts": int(completed_at.timestamp() * 1000),
                    },
                )
            return quote
        except asyncio.CancelledError:
            state.refresh_status = "cancelled"
            raise
        except Exception as exc:
            failed_at = self._now()
            category = _error_category(exc)
            state.consecutive_failures += 1
            self._provider_failures += 1
            base_seconds = 300 if category == "rate_limit" else 30
            backoff_seconds = min(3600, base_seconds * (2 ** min(state.consecutive_failures - 1, 5)))
            state.backoff_until = failed_at + timedelta(seconds=backoff_seconds)
            state.next_refresh = state.backoff_until
            state.last_error_category = category
            state.last_error = str(exc)[:300]
            state.refresh_status = "backoff"
            if category == "rate_limit":
                provider_backoff = min(3600, 300 * (2 ** min(self._provider_failures - 1, 3)))
                self._provider_backoff_until = failed_at + timedelta(seconds=provider_backoff)
            self._failure_count += 1
            self._log.warning(
                "Quote refresh failed for %s category=%s backoff=%ss: %s",
                ticker,
                category,
                backoff_seconds,
                exc,
            )
            return await self._get_cached_quote(ticker)

    async def refresh_due(self) -> dict[str, Any]:
        now = self._now()
        self._last_scan_at = now
        active = {
            normalize_ticker(ticker)
            for ticker in (self._get_active_tickers() or [])
            if self.supports_background_refresh(ticker)
        }
        watchlist = {
            normalize_ticker(ticker)
            for ticker in await self._get_watchlist_tickers()
            if self.supports_background_refresh(ticker)
        }
        candidates = sorted(active | watchlist)
        due: list[tuple[str, str]] = []
        for ticker in candidates:
            priority = "active" if ticker in active else "watchlist"
            state = self._ensure_state(ticker, priority=priority)
            if state.next_refresh is None or now >= state.next_refresh:
                due.append((ticker, priority))

        results = await asyncio.gather(
            *(self.refresh(ticker, priority=priority) for ticker, priority in due),
            return_exceptions=True,
        )
        failures = sum(1 for result in results if isinstance(result, BaseException) or result is None)
        return {
            "candidate_count": len(candidates),
            "due_count": len(due),
            "success_count": len(results) - failures,
            "failure_count": failures,
        }

    async def run(self) -> None:
        if self._startup_delay_seconds:
            await asyncio.sleep(self._startup_delay_seconds)
        while True:
            try:
                await self.refresh_due()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._log.exception("Overseas quote scheduler scan failed: %s", exc)
            await asyncio.sleep(self._scan_interval_seconds)

    def status(self) -> dict[str, Any]:
        now = self._now()
        states = [
            state.snapshot(now=now)
            for state in self._states.values()
            if state.provider == "yahoo_finance"
        ]
        degraded = [
            state for state in states
            if state["in_backoff"] or state["last_error_category"]
        ]
        return {
            "configured": True,
            "enabled": self.enabled,
            "provider": "yahoo_finance",
            "max_concurrency": self._max_concurrency,
            "active_requests": self._active_requests,
            "peak_concurrency": self._peak_concurrency,
            "in_flight": len(self._flights),
            "tracked_count": len(states),
            "degraded_count": len(degraded),
            "request_count": self._request_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "throttled_count": self._throttled_count,
            "last_scan_at": _iso(self._last_scan_at),
            "provider_backoff_until": _iso(self._provider_backoff_until),
            "states": states[:100],
        }
