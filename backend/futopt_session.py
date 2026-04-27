from __future__ import annotations

from datetime import datetime, time as time_of_day
from zoneinfo import ZoneInfo

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

DAY_SESSION_OPEN = time_of_day(8, 45)
DAY_SESSION_CLOSE = time_of_day(13, 45)
NIGHT_SESSION_OPEN = time_of_day(15, 0)
NIGHT_SESSION_CLOSE = time_of_day(5, 0)


def taipei_now() -> datetime:
    return datetime.now(TAIPEI_TZ)


def is_futopt_after_hours(now: datetime | None = None) -> bool:
    if now is None:
        current = taipei_now()
    else:
        current = now.astimezone(TAIPEI_TZ) if now.tzinfo else now.replace(tzinfo=TAIPEI_TZ)
    t = current.time()
    return t >= NIGHT_SESSION_OPEN or t <= NIGHT_SESSION_CLOSE


def is_futopt_trading_time(now: datetime) -> bool:
    current = now.astimezone(TAIPEI_TZ) if now.tzinfo else now.replace(tzinfo=TAIPEI_TZ)
    t = current.time()
    return DAY_SESSION_OPEN <= t <= DAY_SESSION_CLOSE or is_futopt_after_hours(current)


def resolve_futopt_session(session: str | None = None, *, now: datetime | None = None) -> str:
    raw = str(session or "").strip().upper()
    if raw in {"AFTERHOURS", "AFTER_HOURS", "NIGHT", "NIGHT_SESSION"}:
        return "AFTERHOURS"
    if raw == "REGULAR":
        return "REGULAR"
    return "AFTERHOURS" if is_futopt_after_hours(now) else "REGULAR"
