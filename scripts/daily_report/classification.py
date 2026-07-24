"""Signal classification rules and Traditional Chinese presentation labels."""

from __future__ import annotations

from typing import Any


SIGNAL_STATUS_ORDER = {
    "confirmed_uptrend": 0,
    "new_breakout": 1,
    "watch_only": 2,
    "failed_breakout": 3,
    "invalidated": 4,
}

SIGNAL_STATUS_LABELS = {
    "confirmed_uptrend": "已確認上升趨勢",
    "new_breakout": "新突破待確認",
    "watch_only": "觀察中",
    "failed_breakout": "突破失敗",
    "invalidated": "已失效",
}


def classify_signal(
    *,
    invalidated: bool,
    ever_broke: bool,
    latest_close: float,
    breakout_price: float,
    signal_days_5: int,
    breakout_hold_days: int,
) -> str:
    if invalidated:
        return "invalidated"
    if ever_broke and latest_close <= breakout_price:
        return "failed_breakout"
    if signal_days_5 >= 2 and latest_close > breakout_price and breakout_hold_days >= 2:
        return "confirmed_uptrend"
    if latest_close > breakout_price and breakout_hold_days < 2:
        return "new_breakout"
    return "watch_only"


def signal_status_label(status: str) -> str:
    return SIGNAL_STATUS_LABELS.get(status, status or "觀察中")


def signal_observation(status: str, row: dict[str, Any] | None = None) -> str:
    del row  # Reserved for future evidence-aware wording without changing the facade.
    messages = {
        "confirmed_uptrend": "續強優先觀察；回測確認價不破可續抱，跌破改降風險。",
        "new_breakout": "剛突破，隔日需量能與收盤續站確認價。",
        "watch_only": "連續入選但尚未突破，等待帶量站上確認價。",
        "failed_breakout": "曾突破但收回確認價下，先觀察是否重新站回。",
        "invalidated": "跌破低點或MA20，暫不追蹤為進攻名單。",
    }
    return messages.get(status, "維持觀察。")
