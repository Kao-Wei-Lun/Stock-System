"""Candidate score calculation and stable ranking."""

from __future__ import annotations

from typing import Any, Callable

from .classification import SIGNAL_STATUS_ORDER


SCORE_FIELDS = (
    "price_score",
    "breakout_score",
    "volume_score",
    "institutional_score",
    "kline_score",
)


def candidate_score_breakdown(
    *,
    close: float | None,
    breakout_price: float | None,
    signal_low: float | None,
    candle: dict[str, Any],
    volume_expanded: bool,
    volume_ratio: float | None,
    chip: dict[str, Any],
    kline_summary: str,
    validation: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Calculate bounded components; 100 points requires independent confirmation."""
    if close is None or close <= 0:
        price_score = 10
    elif signal_low is not None and close < signal_low:
        price_score = 0
    elif breakout_price is not None and breakout_price > 0 and close > breakout_price:
        price_score = 30
    elif (
        breakout_price is not None
        and breakout_price > 0
        and abs((breakout_price - close) / breakout_price) <= 0.015
    ):
        price_score = 20
    else:
        price_score = 10

    high = candle.get("high")
    breakout_hold_days = int((validation or {}).get("breakout_hold_days") or 0)
    breakout_confirmed = bool((validation or {}).get("breakout_confirmed"))
    intraday_break = (
        isinstance(high, (int, float))
        and breakout_price is not None
        and breakout_price > 0
        and high > breakout_price
    )
    if breakout_confirmed and breakout_hold_days >= 2:
        breakout_score = 25
    elif breakout_price is not None and close is not None and close > breakout_price:
        breakout_score = 18
    elif intraday_break:
        breakout_score = 8
    else:
        breakout_score = 5

    is_red = bool(candle.get("is_red"))
    is_black = bool(candle.get("is_black"))
    long_upper = bool(candle.get("long_upper"))
    if volume_expanded and is_black and (volume_ratio is None or volume_ratio >= 2.0):
        volume_score = 0
    elif volume_expanded and long_upper:
        volume_score = 10
    elif volume_expanded and is_red:
        volume_score = 20
    elif volume_expanded:
        volume_score = 10
    else:
        volume_score = 5

    inst5 = chip.get("institutional_5d_sum")
    fore5 = chip.get("foreign_5d_sum")
    inst_positive = isinstance(inst5, (int, float)) and inst5 > 0
    fore_positive = isinstance(fore5, (int, float)) and fore5 > 0
    if inst_positive and fore_positive:
        institutional_score = 15
    elif inst_positive or fore_positive:
        institutional_score = 8
    else:
        institutional_score = 0

    if any(word in kline_summary for word in ("明確轉弱", "跌破", "轉弱")):
        kline_score = 0
    elif any(word in kline_summary for word in ("弱勢黑K", "長上影")) or (long_upper and is_black):
        kline_score = 2
    elif any(word in kline_summary for word in ("十字", "錘子", "母子", "收斂")):
        kline_score = 6
    elif any(word in kline_summary for word in ("強勢紅K收高", "低點墊高", "收盤轉強", "突破嘗試")):
        kline_score = 10
    else:
        kline_score = 6 if is_red else 2

    result = {
        "price_score": price_score,
        "breakout_score": breakout_score,
        "volume_score": volume_score,
        "institutional_score": institutional_score,
        "kline_score": kline_score,
    }
    result["total_score"] = sum(result[field] for field in SCORE_FIELDS)
    return result


def attach_candidate_scores(
    candidates: list[dict],
    validation_by_ticker: dict[str, dict],
    score_candidate: Callable[[dict, dict | None], dict[str, int]],
) -> list[dict]:
    rows: list[dict] = []
    for item in candidates:
        row = dict(item)
        ticker = str(row.get("ticker") or "").upper().strip()
        row.update(score_candidate(row, validation_by_ticker.get(ticker)))
        rows.append(row)
    return rows


def sort_candidates_by_total_score(
    candidates: list[dict],
    validation_by_ticker: dict[str, dict],
) -> list[dict]:
    def rank(indexed: tuple[int, dict]) -> tuple[float, int, int]:
        index, candidate = indexed
        ticker = str(candidate.get("ticker") or "").upper().strip()
        status = (validation_by_ticker.get(ticker) or {}).get("signal_status")
        return (
            -float(candidate.get("total_score") or 0),
            SIGNAL_STATUS_ORDER.get(str(status), 9),
            index,
        )

    return [candidate for _, candidate in sorted(enumerate(candidates), key=rank)]
