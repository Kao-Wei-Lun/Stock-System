from datetime import datetime, timezone

from market_freshness import is_at_least_as_recent, market_data_freshness


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
