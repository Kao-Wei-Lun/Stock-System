"""Shared market-data freshness helpers.

Freshness must be based on the market timestamp, not the time an old payload was
read from or rewritten to the database.  A four-day tolerance keeps daily
snapshots valid across normal weekends while still rejecting abandoned records.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Any
from zoneinfo import ZoneInfo


WATCHLIST_STALE_AFTER_SECONDS = 4 * 24 * 60 * 60
INTRADAY_STALE_AFTER_SECONDS = 30 * 60
DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class MarketSessionProfile:
    name: str
    timezone: str
    open_time: time
    close_time: time
    sessions: tuple[tuple[time, time], ...] = ()


def market_session_profile(ticker: str) -> MarketSessionProfile:
    symbol = str(ticker or "").strip().upper()
    if symbol.startswith("*") or symbol in {"TXF", "MXF", "TMF", "EXF", "FXF"}:
        return MarketSessionProfile("taiwan_futures", "Asia/Taipei", time(8, 45), time(13, 45))
    if symbol.endswith((".TW", ".TWO")) or symbol in {"^TWII", "^TWOII"}:
        return MarketSessionProfile("taiwan", "Asia/Taipei", time(9, 0), time(13, 30))
    if symbol.endswith(".HK") or symbol == "^HSI":
        return MarketSessionProfile(
            "hong_kong",
            "Asia/Hong_Kong",
            time(9, 30),
            time(16, 0),
            ((time(9, 30), time(12, 0)), (time(13, 0), time(16, 0))),
        )
    if symbol == "^N225":
        return MarketSessionProfile(
            "japan",
            "Asia/Tokyo",
            time(9, 0),
            time(15, 30),
            ((time(9, 0), time(11, 30)), (time(12, 30), time(15, 30))),
        )
    if symbol.endswith(".SS") or symbol.endswith(".SZ"):
        return MarketSessionProfile(
            "china",
            "Asia/Shanghai",
            time(9, 30),
            time(15, 0),
            ((time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))),
        )
    if symbol.endswith("-USD"):
        return MarketSessionProfile("always_open", "UTC", time(0, 0), time(23, 59, 59))
    if symbol == "^STOXX50E":
        return MarketSessionProfile("europe", "Europe/Berlin", time(9, 0), time(17, 30))
    return MarketSessionProfile("us", "America/New_York", time(9, 30), time(16, 0))


def _profile_sessions(profile: MarketSessionProfile) -> tuple[tuple[time, time], ...]:
    return profile.sessions or ((profile.open_time, profile.close_time),)


def market_session_state(
    ticker: str,
    *,
    now: datetime | None = None,
    holidays: set[date] | None = None,
) -> dict[str, Any]:
    """Return timezone-safe current/next session state.

    ``ZoneInfo`` performs daylight-saving conversion for New York and Europe.
    The optional holiday set lets deployments inject exchange calendars without
    making quote refresh depend on an external calendar service.
    """
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    profile = market_session_profile(ticker)
    local_now = reference.astimezone(ZoneInfo(profile.timezone))
    closed_dates = holidays or set()
    if profile.name == "always_open":
        return {
            "market": profile.name,
            "market_timezone": profile.timezone,
            "market_is_open": True,
            "session_status": "open_24_7",
            "next_market_open": local_now.astimezone(timezone.utc).isoformat(),
        }
    if profile.name == "taiwan_futures":
        _, is_open = _expected_completed_session(reference, profile)
        return {
            "market": profile.name,
            "market_timezone": profile.timezone,
            "market_is_open": is_open,
            "session_status": "open" if is_open else "closed",
            "next_market_open": None,
        }

    local_time = local_now.time()
    valid_day = local_now.weekday() < 5 and local_now.date() not in closed_dates
    sessions = _profile_sessions(profile)
    is_open = valid_day and any(start <= local_time <= end for start, end in sessions)
    if is_open:
        next_open = local_now
        status = "open"
    else:
        status = "break" if valid_day and profile.open_time <= local_time <= profile.close_time else "closed"
        next_open = None
        for offset in range(0, 10):
            candidate_date = local_now.date() + timedelta(days=offset)
            if candidate_date.weekday() >= 5 or candidate_date in closed_dates:
                continue
            for start, _ in sessions:
                candidate = datetime.combine(candidate_date, start, tzinfo=ZoneInfo(profile.timezone))
                if candidate > local_now:
                    next_open = candidate
                    break
            if next_open:
                break
    return {
        "market": profile.name,
        "market_timezone": profile.timezone,
        "market_is_open": is_open,
        "session_status": status,
        "next_market_open": next_open.astimezone(timezone.utc).isoformat() if next_open else None,
    }


def _previous_weekday(value: date) -> date:
    candidate = value - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _expected_completed_session(reference: datetime, profile: MarketSessionProfile) -> tuple[date, bool]:
    local_now = reference.astimezone(ZoneInfo(profile.timezone))
    if profile.name == "always_open":
        return local_now.date(), True
    if profile.name == "taiwan_futures":
        local_time = local_now.time()
        day_session = local_now.weekday() < 5 and time(8, 45) <= local_time <= time(13, 45)
        evening_session = local_now.weekday() < 5 and local_time >= time(15, 0)
        overnight_session = local_now.weekday() in {1, 2, 3, 4, 5} and local_time <= time(5, 0)
        is_open = day_session or evening_session or overnight_session
        if is_open or (local_now.weekday() < 5 and local_time >= time(13, 45)):
            return local_now.date(), is_open
        return _previous_weekday(local_now.date()), is_open
    weekday = local_now.weekday() < 5
    is_open = weekday and any(start <= local_now.time() <= end for start, end in _profile_sessions(profile))
    if weekday and local_now.time() >= profile.close_time:
        return local_now.date(), is_open
    return _previous_weekday(local_now.date()), is_open


def _market_date(value: Any, profile: MarketSessionProfile) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if DATE_ONLY_PATTERN.fullmatch(text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    parsed = parse_market_timestamp(value)
    return parsed.astimezone(ZoneInfo(profile.timezone)).date() if parsed else None


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


def market_aware_freshness(
    timestamp: Any,
    *,
    ticker: str,
    data_origin: str = "quote",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate freshness against the latest completed weekday market session.

    Exchange holidays are intentionally handled with one completed-session grace
    day so a personal dashboard does not raise a false alarm on a holiday.
    """
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    profile = market_session_profile(ticker)
    expected_date, market_is_open = _expected_completed_session(reference, profile)
    base = market_data_freshness(timestamp, now=reference)
    observed_date = _market_date(timestamp, profile)
    if observed_date is None:
        return {
            **base,
            "market": profile.name,
            "market_timezone": profile.timezone,
            "market_is_open": market_is_open,
            "expected_session_date": expected_date.isoformat(),
            "observed_session_date": None,
        }

    if profile.name == "always_open":
        threshold = INTRADAY_STALE_AFTER_SECONDS if data_origin == "quote" else WATCHLIST_STALE_AFTER_SECONDS
        result = market_data_freshness(timestamp, stale_after_seconds=threshold, now=reference)
        session_lag = max(0, (expected_date - observed_date).days)
    else:
        session_lag = 0
        cursor = expected_date
        while observed_date < cursor:
            session_lag += 1
            cursor = _previous_weekday(cursor)
        if data_origin == "quote" and market_is_open:
            result = market_data_freshness(
                timestamp,
                stale_after_seconds=INTRADAY_STALE_AFTER_SECONDS,
                now=reference,
            )
        else:
            is_stale = session_lag > 1
            result = {
                **base,
                "freshness_status": "stale" if is_stale else ("market_closed" if not market_is_open else "current"),
                "is_stale": is_stale,
            }
    return {
        **result,
        "market": profile.name,
        "market_timezone": profile.timezone,
        "market_is_open": market_is_open,
        "expected_session_date": expected_date.isoformat(),
        "observed_session_date": observed_date.isoformat(),
        "session_lag": session_lag,
        "freshness_policy": "market_session_weekday_with_one_session_holiday_grace",
    }


def is_at_least_as_recent(candidate: Any, reference: Any) -> bool:
    candidate_time = parse_market_timestamp(candidate)
    reference_time = parse_market_timestamp(reference)
    if candidate_time is None:
        return False
    if reference_time is None:
        return True
    return candidate_time >= reference_time
