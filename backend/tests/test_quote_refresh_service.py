import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest

from market_freshness import market_session_state
from quote_refresh_service import QuoteRefreshService, is_taiwan_provider_ticker


def test_market_session_state_handles_dst_lunch_weekend_holiday_and_crypto():
    summer = market_session_state(
        "AAPL",
        now=datetime(2026, 7, 23, 14, 0, tzinfo=timezone.utc),
    )
    winter_before_open = market_session_state(
        "AAPL",
        now=datetime(2026, 1, 23, 14, 0, tzinfo=timezone.utc),
    )
    hong_kong_lunch = market_session_state(
        "0700.HK",
        now=datetime(2026, 7, 23, 4, 30, tzinfo=timezone.utc),
    )
    sunday = market_session_state(
        "AAPL",
        now=datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc),
    )
    holiday = market_session_state(
        "AAPL",
        now=datetime(2026, 7, 23, 15, 0, tzinfo=timezone.utc),
        holidays={date(2026, 7, 23)},
    )
    crypto = market_session_state(
        "BTC-USD",
        now=datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc),
    )

    assert summer["market_is_open"] is True
    assert winter_before_open["market_is_open"] is False
    assert hong_kong_lunch["market_is_open"] is False
    assert hong_kong_lunch["session_status"] == "break"
    assert sunday["next_market_open"].startswith("2026-07-27T13:30:00")
    assert holiday["market_is_open"] is False
    assert crypto["market_is_open"] is True
    assert crypto["session_status"] == "open_24_7"


def _service(
    fetch,
    *,
    cached=None,
    watchlist=None,
    active=None,
    clock=None,
    max_concurrency=2,
    manual_min_interval_seconds=10,
):
    quote_cache = cached if cached is not None else {}

    async def get_cached(ticker):
        return quote_cache.get(ticker)

    async def tracked():
        return list(watchlist or [])

    return QuoteRefreshService(
        fetch_and_store_quote=fetch,
        get_cached_quote=get_cached,
        get_watchlist_tickers=tracked,
        get_active_tickers=lambda: list(active or []),
        max_concurrency=max_concurrency,
        manual_min_interval_seconds=manual_min_interval_seconds,
        startup_delay_seconds=0,
        clock=clock,
    )


@pytest.mark.anyio
async def test_quote_refresh_uses_single_flight_for_same_ticker():
    calls = 0

    async def fetch(ticker):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return {
            "ticker": ticker,
            "source": "yahoo_finance",
            "quote_timestamp": "2026-07-23T14:00:00+00:00",
        }

    service = _service(fetch)
    results = await asyncio.gather(*(service.refresh("AAPL") for _ in range(8)))

    assert calls == 1
    assert all(item["ticker"] == "AAPL" for item in results)
    assert service.status()["in_flight"] == 0


@pytest.mark.anyio
async def test_quote_refresh_bounds_concurrency_and_excludes_taiwan_symbols():
    active_requests = 0
    peak = 0
    calls = []

    async def fetch(ticker):
        nonlocal active_requests, peak
        calls.append(ticker)
        active_requests += 1
        peak = max(peak, active_requests)
        await asyncio.sleep(0.02)
        active_requests -= 1
        return {
            "ticker": ticker,
            "source": "yahoo_finance",
            "quote_timestamp": "2026-07-23T14:00:00+00:00",
        }

    service = _service(
        fetch,
        watchlist=[
            "AAPL",
            "MSFT",
            "NVDA",
            "0700.HK",
            "2330.TW",
            "^TWII",
            "*TMFF",
            "TMFH6",
            "TXFE6",
        ],
        max_concurrency=2,
    )
    summary = await service.refresh_due()

    assert summary["candidate_count"] == 4
    assert set(calls) == {"AAPL", "MSFT", "NVDA", "0700.HK"}
    assert peak <= 2
    assert service.status()["peak_concurrency"] <= 2


def test_exact_futopt_contracts_never_use_overseas_quote_provider():
    assert is_taiwan_provider_ticker("TMFH6") is True
    assert is_taiwan_provider_ticker("TXFE6") is True
    assert is_taiwan_provider_ticker("TXO20000E6") is True


@pytest.mark.anyio
async def test_rate_limit_enters_provider_backoff_without_retry_storm():
    now = [datetime(2026, 7, 23, 14, 0, tzinfo=timezone.utc)]
    calls = 0
    cached = {
        "AAPL": {
            "ticker": "AAPL",
            "source": "yahoo_finance",
            "quote_timestamp": "2026-07-23T13:00:00+00:00",
        },
    }

    async def fetch(_ticker):
        nonlocal calls
        calls += 1
        raise RuntimeError("HTTP 429 Too Many Requests")

    service = _service(fetch, cached=cached, clock=lambda: now[0])
    first = await service.refresh("AAPL")
    second = await service.refresh("MSFT")

    assert first == cached["AAPL"]
    assert second is None
    assert calls == 1
    assert service.state_for("AAPL")["last_error_category"] == "rate_limit"
    assert service.state_for("MSFT")["refresh_status"] == "backoff"
    assert service.status()["provider_backoff_until"] is not None


@pytest.mark.anyio
async def test_manual_refresh_is_throttled_and_reports_next_refresh():
    now = [datetime(2026, 7, 23, 14, 0, tzinfo=timezone.utc)]
    cached = {}
    calls = 0

    async def fetch(ticker):
        nonlocal calls
        calls += 1
        payload = {
            "ticker": ticker,
            "source": "yahoo_finance",
            "quote_timestamp": now[0].isoformat(),
        }
        cached[ticker] = payload
        return payload

    service = _service(
        fetch,
        cached=cached,
        clock=lambda: now[0],
        manual_min_interval_seconds=10,
    )
    await service.get_for_api("AAPL", force=True)
    throttled = await service.get_for_api("AAPL", force=True)

    assert calls == 1
    assert throttled["refresh_status"] == "throttled"
    assert throttled["next_refresh"] == (now[0] + timedelta(seconds=10)).isoformat()


@pytest.mark.anyio
async def test_api_decoration_explains_closed_market_snapshot():
    now = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    cached = {
        "AAPL": {
            "ticker": "AAPL",
            "source": "yahoo_finance",
            "quote_timestamp": "2026-07-24T20:00:00+00:00",
        },
    }

    async def fetch(_ticker):
        raise AssertionError("valid closed-market cache should not be refreshed")

    service = _service(fetch, cached=cached, clock=lambda: now)
    state = service._ensure_state("AAPL", priority="active")
    state.next_refresh = now + timedelta(minutes=30)
    result = await service.get_for_api("AAPL")

    assert result["freshness_status"] == "market_closed"
    assert result["is_stale"] is False
    assert result["stale_reason"] == "market_closed_latest_session_valid"
