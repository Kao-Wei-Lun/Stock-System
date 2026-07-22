"""Shared market-data freshness helpers.

Freshness must be based on the market timestamp, not the time an old payload was
read from or rewritten to the database.  A four-day tolerance keeps daily
snapshots valid across normal weekends while still rejecting abandoned records.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any


WATCHLIST_STALE_AFTER_SECONDS = 4 * 24 * 60 * 60


def parse_market_timestamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def market_data_freshness(
    timestamp: Any,
    *,
    stale_after_seconds: int = WATCHLIST_STALE_AFTER_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    parsed = parse_market_timestamp(timestamp)
    threshold = max(1, int(stale_after_seconds))
    if parsed is None:
        return {
            "data_timestamp": None,
            "data_age_seconds": None,
            "freshness_threshold_seconds": threshold,
            "freshness_status": "missing",
            "is_stale": True,
        }

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age_seconds = max(0, int((reference.astimezone(timezone.utc) - parsed).total_seconds()))
    is_stale = age_seconds > threshold
    return {
        "data_timestamp": parsed.isoformat(),
        "data_age_seconds": age_seconds,
        "freshness_threshold_seconds": threshold,
        "freshness_status": "stale" if is_stale else "current",
        "is_stale": is_stale,
    }


def is_at_least_as_recent(candidate: Any, reference: Any) -> bool:
    candidate_time = parse_market_timestamp(candidate)
    reference_time = parse_market_timestamp(reference)
    if candidate_time is None:
        return False
    if reference_time is None:
        return True
    return candidate_time >= reference_time
