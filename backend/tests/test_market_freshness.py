from datetime import datetime, timezone

from market_freshness import is_at_least_as_recent, market_aware_freshness, market_data_freshness


def test_market_data_freshness_uses_market_timestamp_age():
    now = datetime(2026, 7, 22, 4, 0, tzinfo=timezone.utc)

    current = market_data_freshness("2026-07-20T04:00:00Z", now=now)
    stale = market_data_freshness("2026-04-08T04:00:00Z", now=now)

    assert current["freshness_status"] == "current"
    assert current["is_stale"] is False
    assert stale["freshness_status"] == "stale"
    assert stale["is_stale"] is True
    assert stale["data_age_seconds"] > stale["freshness_threshold_seconds"]


def test_market_timestamp_comparison_handles_date_and_iso_values():
    assert is_at_least_as_recent("2026-07-22", "2026-04-08T04:00:00+00:00") is True
    assert is_at_least_as_recent(None, "2026-04-08") is False


def test_market_aware_daily_data_stays_current_during_session_and_weekend():
    during_taiwan_session = datetime(2026, 7, 22, 4, 0, tzinfo=timezone.utc)
    result = market_aware_freshness(
        "2026-07-21",
        ticker="2330.TW",
        data_origin="ohlcv",
        now=during_taiwan_session,
    )
    assert result["market_is_open"] is True
    assert result["expected_session_date"] == "2026-07-21"
    assert result["is_stale"] is False

    sunday = datetime(2026, 7, 26, 4, 0, tzinfo=timezone.utc)
    weekend = market_aware_freshness("2026-07-24", ticker="2330.TW", data_origin="ohlcv", now=sunday)
    assert weekend["expected_session_date"] == "2026-07-24"
    assert weekend["is_stale"] is False


def test_market_aware_quote_becomes_stale_quickly_while_market_is_open():
    result = market_aware_freshness(
        "2026-07-22T02:00:00+00:00",
        ticker="2330.TW",
        data_origin="quote",
        now=datetime(2026, 7, 22, 4, 0, tzinfo=timezone.utc),
    )
    assert result["market_is_open"] is True
    assert result["freshness_threshold_seconds"] == 1800
    assert result["is_stale"] is True


def test_market_aware_freshness_flags_multi_session_old_daily_data():
    result = market_aware_freshness(
        "2026-07-16",
        ticker="AAPL",
        data_origin="ohlcv",
        now=datetime(2026, 7, 22, 22, 0, tzinfo=timezone.utc),
    )
    assert result["expected_session_date"] == "2026-07-22"
    assert result["session_lag"] > 1
    assert result["is_stale"] is True


def test_taiwan_futures_night_session_uses_intraday_threshold():
    result = market_aware_freshness(
        "2026-07-22T08:00:00+00:00",
        ticker="*TMFF",
        data_origin="quote",
        now=datetime(2026, 7, 22, 8, 45, tzinfo=timezone.utc),
    )
    assert result["market"] == "taiwan_futures"
    assert result["market_is_open"] is True
    assert result["is_stale"] is True
