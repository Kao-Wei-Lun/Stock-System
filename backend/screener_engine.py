from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from typing import Any, Dict, List, Optional

from data_fetcher import normalize_ticker
from database import db
from macro_regime import build_macro_summary
from market_intelligence import infer_market


SCREEN_CACHE_TTL_SECONDS = 30
_screen_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
FUTURES_SIGNAL_MAP = {
    "^TWII": "臺股期貨",
    "0050.TW": "臺股期貨",
    "^TWOII": "櫃買指數期貨",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _mean_close(rows: List[Dict[str, Any]], count: int) -> Optional[float]:
    closes = [_safe_float(item.get("close"), float("nan")) for item in rows[-count:]]
    valid = [value for value in closes if value == value]
    if len(valid) < count:
        return None
    return mean(valid)


def _pct_change_over(rows: List[Dict[str, Any]], lookback: int) -> Optional[float]:
    if len(rows) <= lookback:
        return None
    old_close = _safe_float(rows[-lookback - 1].get("close"))
    latest_close = _safe_float(rows[-1].get("close"))
    if old_close <= 0:
        return None
    return (latest_close - old_close) / old_close * 100.0


def _range_pct(rows: List[Dict[str, Any]], lookback: int) -> Optional[float]:
    if len(rows) < lookback:
        return None
    window = rows[-lookback:]
    highs = [_safe_float(item.get("high")) for item in window]
    lows = [_safe_float(item.get("low")) for item in window]
    high = max(highs) if highs else 0
    low = min(value for value in lows if value > 0) if any(value > 0 for value in lows) else 0
    if low <= 0:
        return None
    return (high - low) / low * 100.0


def _distance_pct(value: float, anchor: Optional[float]) -> Optional[float]:
    if anchor in (None, 0):
        return None
    return (value - float(anchor)) / float(anchor) * 100.0


def normalize_screener_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(filters or {})
    market = str(source.get("market") or "ALL").upper()
    if market not in {"ALL", "US", "TW", "HK", "INDEX"}:
        market = "ALL"
    setup_type = str(source.get("setup_type") or "any").lower()
    if setup_type not in {"any", "accumulation"}:
        setup_type = "any"
    return {
        "search": str(source.get("search") or "").strip(),
        "market": market,
        "sector": str(source.get("sector") or "").strip(),
        "setup_type": setup_type,
        "min_price": _safe_float(source.get("min_price"), 0.0) or None,
        "max_price": _safe_float(source.get("max_price"), 0.0) or None,
        "min_volume_ratio": _safe_float(source.get("min_volume_ratio"), 0.0) or None,
        "min_setup_quality": _safe_int(source.get("min_setup_quality"), 0) or None,
        "min_accumulation_score": _safe_int(source.get("min_accumulation_score"), 0) or None,
        "decision_verdict": str(source.get("decision_verdict") or "any").lower(),
        "max_pe_ratio": _safe_float(source.get("max_pe_ratio"), 0.0) or None,
        "min_dividend_yield": _safe_float(source.get("min_dividend_yield"), 0.0) or None,
        "near_52w_high_pct": _safe_float(source.get("near_52w_high_pct"), 0.0) or None,
        "upcoming_event_days": _safe_int(source.get("upcoming_event_days"), 0) or None,
        "chip_bias": str(source.get("chip_bias") or "any").lower(),
        "ma_alignment": str(source.get("ma_alignment") or "any").lower(),
        "sort_by": str(source.get("sort_by") or "score").lower(),
        "limit": max(1, min(_safe_int(source.get("limit"), 50), 200)),
    }


def build_screener_presets() -> List[Dict[str, Any]]:
    return [
        {
            "name": "量增突破",
            "description": "量能放大且接近 52 週高點",
            "filters": {
                "min_volume_ratio": 1.5,
                "min_setup_quality": 4,
                "near_52w_high_pct": 5,
                "ma_alignment": "bullish",
                "sort_by": "score",
                "limit": 30,
            },
        },
        {
            "name": "事件觀察",
            "description": "近期有關鍵事件的標的",
            "filters": {
                "upcoming_event_days": 14,
                "sort_by": "event_date",
                "limit": 30,
            },
        },
        {
            "name": "潛伏起漲",
            "description": "盤整收斂且法人籌碼開始累積",
            "filters": {
                "market": "TW",
                "setup_type": "accumulation",
                "sort_by": "accumulation_score",
                "limit": 30,
            },
        },
        {
            "name": "台股籌碼偏多",
            "description": "聚焦台股籌碼偏多標的",
            "filters": {
                "market": "TW",
                "chip_bias": "bullish",
                "sort_by": "score",
                "limit": 30,
            },
        },
    ]


async def _institutional_signal_for_ticker(ticker: str) -> Optional[Dict[str, Any]]:
    commodity = FUTURES_SIGNAL_MAP.get(ticker)
    if not commodity:
        return None
    snapshot = await db.get_institutional_snapshot()
    if not snapshot:
        return None
    default_commodity = snapshot.get("default_futures_commodity")
    costs = snapshot.get("cost_estimates", {}).get("futures") or {}
    if not costs or default_commodity != commodity:
        return None
    spot = next((item for item in snapshot.get("spot_reference") or [] if item.get("ticker") == ticker), None)
    spot_price = _safe_float((spot or {}).get("price"), 0.0)
    institution_price = _safe_float((costs.get("institution_estimate") or {}).get("price"), 0.0)
    if not spot_price or not institution_price:
        return None
    basis = institution_price - spot_price
    return {
        "commodity": commodity,
        "basis": basis,
        "basis_pct": basis / spot_price * 100.0,
        "signal": "bullish" if basis > 0 else "bearish" if basis < 0 else "neutral",
    }


def _build_macro_cache_fragment(summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "overall_risk": summary.get("overall_risk"),
        "regime": summary.get("regime"),
        "trade_posture": summary.get("trade_posture"),
        "updated_at": summary.get("updated_at"),
    }


def _setup_quality(
    latest_close: float,
    volume_ratio: float,
    ma20: Optional[float],
    ma50: Optional[float],
    distance_to_high_pct: Optional[float],
    change_pct: float,
) -> int:
    quality = 0
    quality += 1 if volume_ratio >= 1.5 else 0
    quality += 1 if ma20 is not None and latest_close >= ma20 else 0
    quality += 1 if ma50 is not None and ma20 is not None and ma20 >= ma50 else 0
    quality += 1 if distance_to_high_pct is not None and distance_to_high_pct <= 5 else 0
    quality += 1 if change_pct > 0 else 0
    return quality


def _chip_sum(points: List[Dict[str, Any]], key: str, window: int) -> int:
    return sum(_safe_int(item.get(key)) for item in points[-window:])


def _chip_streak(points: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    direction = "neutral"
    days = 0
    for item in reversed(points):
        value = _safe_int(item.get(key))
        next_direction = "buy" if value > 0 else "sell" if value < 0 else "neutral"
        if next_direction == "neutral":
            if days == 0:
                break
            continue
        if days == 0:
            direction = next_direction
            days = 1
            continue
        if next_direction != direction:
            break
        days += 1
    return {"direction": direction, "days": days}


def _normalize_chip_history(points: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not points:
        return []
    return sorted(
        [dict(item) for item in points if isinstance(item, dict)],
        key=lambda item: (str(item.get("snapshot_date") or ""), _safe_int(item.get("id"))),
    )


def _build_accumulation_profile(
    *,
    ticker: str,
    market: str,
    latest_close: float,
    recent_rows: List[Dict[str, Any]],
    ma20: Optional[float],
    ma50: Optional[float],
    chip_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    range20 = _range_pct(recent_rows, 20)
    range60 = _range_pct(recent_rows, 60)
    ret20 = _pct_change_over(recent_rows, 20)
    ret60 = _pct_change_over(recent_rows, 60)
    high20 = max((_safe_float(item.get("high")) for item in recent_rows[-20:]), default=0.0)
    distance_to_20d_high = ((high20 - latest_close) / high20 * 100.0) if high20 > 0 else None
    ma20_distance = _distance_pct(latest_close, ma20)
    ma50_distance = _distance_pct(latest_close, ma50)

    points = _normalize_chip_history(chip_history)
    latest_chip = points[-1] if points else {}
    institutional_5d = _chip_sum(points, "institutional_net_buy_sell", 5)
    institutional_10d = _chip_sum(points, "institutional_net_buy_sell", 10)
    foreign_5d = _chip_sum(points, "foreign_net_buy_sell", 5)
    foreign_10d = _chip_sum(points, "foreign_net_buy_sell", 10)
    trust_10d = _chip_sum(points, "investment_trust_net_buy_sell", 10)
    institutional_streak = _chip_streak(points, "institutional_net_buy_sell")
    foreign_streak = _chip_streak(points, "foreign_net_buy_sell")

    score = 0
    reasons: List[str] = []
    flags: List[str] = []

    if range20 is not None:
        if range20 <= 10:
            score += 20
            reasons.append("20日區間高度收斂")
        elif range20 <= 15:
            score += 15
            reasons.append("20日盤整區間偏窄")
        elif range20 <= 22:
            score += 8
            reasons.append("仍在可接受盤整區間")
        else:
            flags.append("20日波動仍大")

    if ma20_distance is not None:
        if -3 <= ma20_distance <= 8:
            score += 15
            reasons.append("價格貼近 MA20")
        elif ma20_distance > 18:
            score -= 8
            flags.append("短線離 MA20 過遠")
    if ma50_distance is not None:
        if ma50 is not None and latest_close >= ma50 * 0.98:
            score += 10
            reasons.append("守在 MA50 附近或之上")
        else:
            flags.append("尚未站回 MA50")
    if ma20 is not None and ma50 is not None:
        if ma20 >= ma50:
            score += 10
            reasons.append("MA20 已不弱於 MA50")
        elif ma20 >= ma50 * 0.98:
            score += 6
            reasons.append("MA20 接近翻揚至 MA50")

    if ret20 is not None:
        if -8 <= ret20 <= 18:
            score += 15
            reasons.append("20日漲幅未過熱")
        elif 18 < ret20 <= 30:
            score += 5
            flags.append("已有一段漲幅，追價需保守")
        elif ret20 > 30:
            score -= 15
            flags.append("20日漲幅過熱，不屬於潛伏型")
    if distance_to_20d_high is not None:
        if 0 <= distance_to_20d_high <= 5:
            score += 12
            reasons.append("接近20日壓力區，具突破觀察價值")
        elif distance_to_20d_high <= 10:
            score += 8
            reasons.append("距20日高點不遠")

    chip_score = 0
    if institutional_5d > 0:
        chip_score += 10
        reasons.append("法人5日累積買超")
    if institutional_10d > 0:
        chip_score += 10
        reasons.append("法人10日累積買超")
    if foreign_5d > 0:
        chip_score += 8
        reasons.append("外資5日累積買超")
    if foreign_10d > 0:
        chip_score += 6
    if trust_10d > 0:
        chip_score += 5
    if institutional_streak["direction"] == "buy" and institutional_streak["days"] >= 3:
        chip_score += 8
        reasons.append(f"法人連{institutional_streak['days']}買")
    if foreign_streak["direction"] == "buy" and foreign_streak["days"] >= 3:
        chip_score += 8
        reasons.append(f"外資連{foreign_streak['days']}買")
    if latest_chip and _safe_int(latest_chip.get("institutional_net_buy_sell")) < 0:
        chip_score -= 8
        flags.append("最新一日法人轉賣")
    score += min(35, chip_score)

    if market == "TW" and points and chip_score <= 0:
        flags.append("尚未看到法人累積買超")
    if market == "TW" and not points:
        flags.append("缺少台股籌碼歷史")

    score = max(0, min(100, int(round(score))))
    chip_confirmed = market != "TW" or (bool(points) and chip_score > 0)
    not_overextended = ret20 is None or ret20 <= 30
    compression_ok = range20 is not None and range20 <= 22
    ma_support_ok = (
        (ma20 is not None and latest_close >= ma20 * 0.97)
        or (ma50 is not None and latest_close >= ma50 * 0.98)
    )
    qualified = score >= 58 and compression_ok and ma_support_ok and not_overextended and chip_confirmed
    stage = "breakout_watch" if distance_to_20d_high is not None and distance_to_20d_high <= 5 else "base_building"
    if ret20 is not None and ret20 > 30:
        stage = "overextended"
    elif not chip_confirmed:
        stage = "waiting_for_chip_confirmation"
    elif not compression_ok:
        stage = "wide_base"

    return {
        "ticker": ticker,
        "score": score,
        "qualified": qualified,
        "stage": stage,
        "range20_pct": round(range20, 2) if range20 is not None else None,
        "range60_pct": round(range60, 2) if range60 is not None else None,
        "ret20_pct": round(ret20, 2) if ret20 is not None else None,
        "ret60_pct": round(ret60, 2) if ret60 is not None else None,
        "distance_to_20d_high_pct": round(distance_to_20d_high, 2) if distance_to_20d_high is not None else None,
        "ma20_distance_pct": round(ma20_distance, 2) if ma20_distance is not None else None,
        "ma50_distance_pct": round(ma50_distance, 2) if ma50_distance is not None else None,
        "chip": {
            "latest_date": latest_chip.get("snapshot_date"),
            "institutional_5d_sum": institutional_5d,
            "institutional_10d_sum": institutional_10d,
            "foreign_5d_sum": foreign_5d,
            "foreign_10d_sum": foreign_10d,
            "investment_trust_10d_sum": trust_10d,
            "institutional_streak": institutional_streak,
            "foreign_streak": foreign_streak,
            "score": chip_score,
        },
        "reasons": reasons[:8],
        "flags": flags[:6],
    }


def _normalize_candle(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    close = _safe_float(row.get("close"))
    if close <= 0:
        return None
    open_price = _safe_float(row.get("open"), close) or close
    high = _safe_float(row.get("high"), max(open_price, close)) or max(open_price, close)
    low = _safe_float(row.get("low"), min(open_price, close)) or min(open_price, close)
    high = max(high, open_price, close)
    low = min(low, open_price, close)
    price_range = max(0.0, high - low)
    body = abs(close - open_price)
    upper_shadow = high - max(open_price, close)
    lower_shadow = min(open_price, close) - low
    body_pct = body / open_price * 100.0 if open_price > 0 else 0.0
    close_position = (close - low) / price_range if price_range > 0 else 0.5
    return {
        "date": row.get("date") or row.get("timestamp"),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": _safe_int(row.get("volume")),
        "range": price_range,
        "body": body,
        "body_pct": body_pct,
        "body_to_range": body / price_range if price_range > 0 else 0.0,
        "upper_shadow": upper_shadow,
        "lower_shadow": lower_shadow,
        "upper_shadow_to_range": upper_shadow / price_range if price_range > 0 else 0.0,
        "lower_shadow_to_range": lower_shadow / price_range if price_range > 0 else 0.0,
        "close_position": close_position,
        "direction": "bullish" if close > open_price else "bearish" if close < open_price else "neutral",
    }


def _build_candlestick_profile(
    recent_rows: List[Dict[str, Any]],
    *,
    ma20: Optional[float],
    volume_ratio: float,
) -> Dict[str, Any]:
    candles = [
        candle
        for candle in (_normalize_candle(item) for item in recent_rows[-25:])
        if candle is not None
    ]
    if len(candles) < 2:
        return {
            "score": 0,
            "bias": "insufficient_data",
            "summary": "K線資料不足，暫不判讀型態",
            "patterns": [],
            "latest": None,
            "flags": ["K線資料不足"],
        }

    last = candles[-1]
    prev = candles[-2]
    third = candles[-3] if len(candles) >= 3 else None
    score = 0
    patterns: List[Dict[str, Any]] = []
    flags: List[str] = []

    avg_volume = mean([item["volume"] for item in candles[-20:] if item["volume"] > 0]) if any(
        item["volume"] > 0 for item in candles[-20:]
    ) else 0
    volume_expanded = bool(avg_volume and last["volume"] >= avg_volume * 1.25) or volume_ratio >= 1.25
    near_ma20 = bool(
        ma20
        and (
            abs(_distance_pct(last["close"], ma20) or 999.0) <= 3
            or last["low"] <= ma20 <= last["high"]
        )
    )
    previous_high = max((item["high"] for item in candles[-11:-1]), default=0.0)
    recent_lows = [item["low"] for item in candles[-3:]]
    recent_closes = [item["close"] for item in candles[-3:]]

    def add_pattern(key: str, label: str, tone: str, impact: int, summary: str) -> None:
        nonlocal score
        score += impact
        patterns.append(
            {
                "key": key,
                "label": label,
                "tone": tone,
                "score": impact,
                "summary": summary,
            }
        )

    bullish_engulfing = (
        last["direction"] == "bullish"
        and prev["direction"] == "bearish"
        and last["open"] <= prev["close"]
        and last["close"] >= prev["open"]
        and last["body"] >= prev["body"] * 0.85
    )
    bearish_engulfing = (
        last["direction"] == "bearish"
        and prev["direction"] == "bullish"
        and last["open"] >= prev["close"]
        and last["close"] <= prev["open"]
        and last["body"] >= prev["body"] * 0.85
    )
    if bullish_engulfing:
        add_pattern("bullish_engulfing", "多方吞噬", "positive", 28, "紅K吞噬前一根黑K，短線買盤轉強")
    if bearish_engulfing:
        add_pattern("bearish_engulfing", "空方吞噬", "risk", -28, "黑K吞噬前一根紅K，短線賣壓轉強")

    if (
        third
        and third["direction"] == "bearish"
        and prev["body_to_range"] <= 0.35
        and last["direction"] == "bullish"
        and last["close"] >= (third["open"] + third["close"]) / 2
    ):
        add_pattern("morning_star", "晨星反轉", "positive", 24, "三日型態出現止跌後轉強訊號")

    hammer = (
        last["range"] > 0
        and last["lower_shadow"] >= max(last["body"] * 2, last["range"] * 0.35)
        and last["upper_shadow_to_range"] <= 0.25
        and last["close_position"] >= 0.55
    )
    if hammer:
        impact = 22 if near_ma20 else 16
        add_pattern(
            "hammer",
            "錘子線",
            "positive",
            impact,
            "下影線明顯，低檔或均線附近有承接" if near_ma20 else "下影線明顯，盤中賣壓被承接",
        )

    shooting_star = (
        last["range"] > 0
        and last["upper_shadow"] >= max(last["body"] * 2, last["range"] * 0.35)
        and last["lower_shadow_to_range"] <= 0.25
        and last["close_position"] <= 0.45
    )
    if shooting_star:
        add_pattern("shooting_star", "倒錘上影", "risk", -18, "上影線明顯，追價買盤受壓")

    if last["body_to_range"] <= 0.15:
        add_pattern("doji", "十字線", "neutral", 0, "多空拉鋸，需等待隔日方向確認")

    if last["direction"] == "bullish" and last["body_to_range"] >= 0.45 and last["close_position"] >= 0.78:
        impact = 20 if volume_expanded else 12
        add_pattern(
            "strong_bull_close",
            "強勢紅K收高",
            "positive",
            impact,
            "放量紅K收在相對高位" if volume_expanded else "紅K收在相對高位",
        )
    elif last["direction"] == "bearish" and last["body_to_range"] >= 0.45 and last["close_position"] <= 0.25:
        impact = -22 if volume_expanded else -14
        add_pattern(
            "weak_bear_close",
            "弱勢黑K收低",
            "risk",
            impact,
            "放量黑K收在相對低位" if volume_expanded else "黑K收在相對低位",
        )

    if previous_high > 0 and last["close"] >= previous_high * 0.995:
        add_pattern("breakout_attempt", "突破嘗試", "positive", 18, "收盤接近或突破近10日高點")

    if last["high"] <= prev["high"] and last["low"] >= prev["low"]:
        add_pattern("inside_bar", "母子收斂", "neutral", 6, "今日K線收在前一日區間內，等待區間表態")

    if len(recent_lows) == 3 and recent_lows[0] < recent_lows[1] < recent_lows[2]:
        add_pattern("higher_lows", "低點墊高", "positive", 8, "近三日低點逐步墊高")
    if len(recent_closes) == 3 and recent_closes[0] < recent_closes[1] < recent_closes[2]:
        add_pattern("higher_closes", "收盤轉強", "positive", 8, "近三日收盤價逐步走高")

    if last["upper_shadow"] >= max(last["body"] * 1.6, last["range"] * 0.3) and last["close_position"] < 0.65:
        flags.append("上影線偏長，突破前需確認賣壓消化")
    if volume_expanded and last["direction"] == "bearish":
        flags.append("放量黑K，隔日不宜追高")

    score = max(-100, min(100, int(round(score))))
    if score >= 35:
        bias = "bullish"
    elif score >= 15:
        bias = "constructive"
    elif score <= -25:
        bias = "bearish"
    else:
        bias = "neutral"
    if not patterns:
        patterns.append(
            {
                "key": "no_clear_pattern",
                "label": "未見明確型態",
                "tone": "neutral",
                "score": 0,
                "summary": "近幾根K線尚未形成明確多空訊號",
            }
        )
    summary = " / ".join(item["label"] for item in patterns[:4])
    return {
        "score": score,
        "bias": bias,
        "summary": summary,
        "patterns": patterns[:8],
        "latest": {
            "date": last.get("date"),
            "open": round(last["open"], 4),
            "high": round(last["high"], 4),
            "low": round(last["low"], 4),
            "close": round(last["close"], 4),
            "body_pct": round(last["body_pct"], 2),
            "close_position": round(last["close_position"], 2),
            "volume_expanded": volume_expanded,
            "near_ma20": near_ma20,
        },
        "flags": flags[:4],
    }


def _macro_adjustment(
    summary: Dict[str, Any],
    setup_quality: int,
    chip_bias: Optional[str],
    institutional_signal: Optional[Dict[str, Any]],
    change_pct: float,
) -> tuple[int, Optional[str]]:
    posture = str(summary.get("trade_posture") or "standby").lower()
    institutional_bias = (institutional_signal or {}).get("signal")
    confirmation_adjustment = 0
    confirmation_notes: List[str] = []

    if chip_bias == "bullish":
        confirmation_adjustment += 2
        confirmation_notes.append("籌碼偏多")
    elif chip_bias == "bearish":
        confirmation_adjustment -= 2
        confirmation_notes.append("籌碼偏空")

    if institutional_bias == "bullish":
        confirmation_adjustment += 2
        confirmation_notes.append("法人基差偏多")
    elif institutional_bias == "bearish":
        confirmation_adjustment -= 2
        confirmation_notes.append("法人基差偏空")

    if posture == "defensive":
        adjustment = -12
        note = "高風險日先降權"
        if setup_quality >= 4:
            adjustment += 6
            note = "高風險日僅保留最強 setup"
        elif setup_quality >= 3:
            adjustment += 3
            note = "高風險日但結構仍可觀察"
        adjustment += confirmation_adjustment
        if change_pct < 0:
            adjustment -= 4
        return adjustment, note

    if posture == "selective":
        adjustment = -4
        note = "震盪環境先控管出手"
        if setup_quality >= 4:
            adjustment += 6
            note = "震盪環境仍保留強勢候選"
        elif setup_quality >= 3:
            adjustment += 3
        adjustment += confirmation_adjustment
        return adjustment, note

    if posture == "offensive":
        adjustment = 4
        note = "順風環境提高趨勢權重"
        if setup_quality >= 4:
            adjustment += 5
        elif setup_quality >= 3:
            adjustment += 2
        if change_pct > 0:
            adjustment += 2
        adjustment += max(-1, confirmation_adjustment)
        return adjustment, note

    if posture == "balanced" and setup_quality >= 4:
        return 3 + max(-1, confirmation_adjustment), "中性盤保留強勢 setup"

    if confirmation_notes:
        return confirmation_adjustment, " / ".join(confirmation_notes[:2])
    return 0, None


def _score_tone(score: int) -> str:
    if score > 0:
        return "positive"
    if score < 0:
        return "risk"
    return "neutral"


def _format_pct(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}%"


def _decision_verdict(total_score: int, posture: str) -> tuple[str, str, str]:
    normalized_posture = str(posture or "standby").lower()
    if normalized_posture == "defensive":
        if total_score >= 80:
            return "priority", "逆風強勢候選", "市場偏防守，但這檔結構仍完整，可保留在高優先觀察名單。"
        if total_score >= 60:
            return "watch", "防守觀察", "目前偏高風險，建議只做觀察或極小倉位試單。"
        return "wait", "暫緩出手", "分數不足以對抗當前風險環境，先等待更明確的趨勢。"

    if total_score >= 80:
        return "priority", "優先候選", "趨勢、量價與確認條件同步，值得優先深挖進場劇本。"
    if total_score >= 60:
        return "watch", "觀察名單", "結構仍有可取之處，但需要更明確的觸發點與風險控制。"
    return "wait", "等待名單", "現階段條件偏弱，暫時不列為優先追蹤標的。"


def _build_decision_card(
    *,
    score: int,
    base_score: int,
    macro_adjustment: int,
    macro_adjustment_reason: Optional[str],
    macro_summary: Dict[str, Any],
    latest_close: float,
    ma20: Optional[float],
    ma50: Optional[float],
    distance_to_high_pct: Optional[float],
    change_pct: float,
    volume_ratio: float,
    pe_ratio: Optional[float],
    dividend_yield: Optional[float],
    chip_bias: Optional[str],
    chip_summary: Optional[Dict[str, Any]],
    institutional_signal: Optional[Dict[str, Any]],
    earliest_event: Optional[Dict[str, Any]],
    event_window_days: Optional[int],
    accumulation_profile: Optional[Dict[str, Any]] = None,
    candlestick_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    trend_score = 0
    trend_fragments: List[str] = []
    if ma20 is not None:
        if latest_close >= ma20:
            trend_score += 20
            trend_fragments.append("站上 MA20")
        else:
            trend_fragments.append("跌破 MA20")
    else:
        trend_fragments.append("MA20 資料不足")

    if ma20 is not None and ma50 is not None:
        if ma20 >= ma50:
            trend_score += 15
            trend_fragments.append("MA20 >= MA50")
        else:
            trend_fragments.append("MA20 < MA50")
    else:
        trend_fragments.append("均線長週期不足")

    relative_strength_score = 0
    relative_strength_fragments: List[str] = []
    if distance_to_high_pct is not None:
        relative_strength_fragments.append(f"距 52W 高 {_format_pct(distance_to_high_pct)}")
        if distance_to_high_pct <= 5:
            relative_strength_score += 15
    else:
        relative_strength_fragments.append("缺少 52W 高點資料")

    if change_pct > 0:
        relative_strength_score += 10
        relative_strength_fragments.append(f"單日動能 +{change_pct:.2f}%")
    elif change_pct < 0:
        relative_strength_score -= 5
        relative_strength_fragments.append(f"單日動能 {change_pct:.2f}%")
    else:
        relative_strength_fragments.append("單日動能持平")

    volume_score = 25 if volume_ratio >= 1.5 else 10 if volume_ratio >= 1.0 else 0
    volume_fragments = [
        f"量比 {volume_ratio:.2f}x",
        "量能放大" if volume_ratio >= 1.5 else "量能平穩" if volume_ratio >= 1.0 else "量能不足",
    ]

    confirmation_score = 0
    confirmation_fragments: List[str] = []
    if chip_bias == "bullish":
        confirmation_score += 15
        confirmation_fragments.append("台股籌碼偏多")
    elif chip_bias == "bearish":
        confirmation_score -= 10
        confirmation_fragments.append("台股籌碼偏空")
    elif chip_summary:
        confirmation_fragments.append("籌碼偏向中性")
    else:
        confirmation_fragments.append("無籌碼確認")

    institutional_bias = (institutional_signal or {}).get("signal")
    if institutional_bias == "bullish":
        confirmation_score += 10
        confirmation_fragments.append("法人基差偏多")
    elif institutional_bias == "bearish":
        confirmation_fragments.append("法人基差偏空")
    elif institutional_signal:
        confirmation_fragments.append("法人基差中性")
    else:
        confirmation_fragments.append("無法人基差確認")

    if earliest_event:
        event_label = earliest_event.get("title") or earliest_event.get("event_type") or "近期事件"
        event_summary = f"{earliest_event.get('event_date') or '待定'} · {event_label}"
        event_tone = "risk" if str(earliest_event.get("importance") or "").lower() == "high" else "neutral"
    elif event_window_days:
        event_summary = f"{event_window_days} 日內無重大事件"
        event_tone = "positive"
    else:
        event_summary = "未啟用事件視窗"
        event_tone = "neutral"

    fundamental_fragments: List[str] = []
    fundamental_tone = "neutral"
    if pe_ratio is not None:
        fundamental_fragments.append(f"PE {pe_ratio:.1f}")
        if 0 < pe_ratio <= 25:
            fundamental_tone = "positive"
    else:
        fundamental_fragments.append("PE 未同步")
    if dividend_yield is not None:
        fundamental_fragments.append(f"殖利率 {_format_pct(dividend_yield * 100.0)}")
        if dividend_yield >= 0.02:
            fundamental_tone = "positive"
    else:
        fundamental_fragments.append("殖利率未同步")

    posture = str(macro_summary.get("trade_posture") or "standby").lower()
    macro_fragments = [
        f"市場 posture {posture}",
        macro_adjustment_reason or "未額外調整",
    ]

    verdict_key, verdict, summary = _decision_verdict(score, posture)
    accumulation_section = None
    if accumulation_profile:
        accumulation_bits = []
        if accumulation_profile.get("stage"):
            accumulation_bits.append(str(accumulation_profile["stage"]))
        if accumulation_profile.get("range20_pct") is not None:
            accumulation_bits.append(f"20日區間 {_format_pct(accumulation_profile.get('range20_pct'))}")
        if accumulation_profile.get("ret20_pct") is not None:
            accumulation_bits.append(f"20日漲幅 {_format_pct(accumulation_profile.get('ret20_pct'))}")
        reasons = accumulation_profile.get("reasons") or []
        flags = accumulation_profile.get("flags") or []
        accumulation_bits.extend(str(item) for item in reasons[:3])
        accumulation_bits.extend(str(item) for item in flags[:2])
        accumulation_section = {
            "key": "accumulation",
            "label": "潛伏起漲",
            "score": accumulation_profile.get("score") or 0,
            "tone": "positive" if accumulation_profile.get("qualified") else "neutral",
            "summary": " / ".join(accumulation_bits) or "尚未形成潛伏起漲型態",
        }
    candlestick_section = None
    if candlestick_profile:
        candlestick_bits = []
        bias = candlestick_profile.get("bias")
        if bias:
            candlestick_bits.append(str(bias))
        patterns = candlestick_profile.get("patterns") or []
        candlestick_bits.extend(
            f"{item.get('label')}: {item.get('summary')}"
            for item in patterns[:3]
            if isinstance(item, dict)
        )
        flags = candlestick_profile.get("flags") or []
        candlestick_bits.extend(str(item) for item in flags[:2])
        candlestick_score = _safe_int(candlestick_profile.get("score"))
        candlestick_section = {
            "key": "candlestick",
            "label": "K線型態",
            "score": candlestick_score,
            "tone": "positive" if candlestick_score > 0 else "risk" if candlestick_score < 0 else "neutral",
            "summary": " / ".join(candlestick_bits) or "K線尚未形成明確型態",
        }
    sections = [
        {
            "key": "trend",
            "label": "趨勢結構",
            "score": trend_score,
            "tone": _score_tone(trend_score),
            "summary": " / ".join(trend_fragments),
        },
        {
            "key": "relative_strength",
            "label": "相對強弱",
            "score": relative_strength_score,
            "tone": _score_tone(relative_strength_score),
            "summary": " / ".join(relative_strength_fragments),
        },
        {
            "key": "volume",
            "label": "量價動能",
            "score": volume_score,
            "tone": _score_tone(volume_score),
            "summary": " / ".join(volume_fragments),
        },
        *([candlestick_section] if candlestick_section else []),
        {
            "key": "confirmation",
            "label": "籌碼確認",
            "score": confirmation_score,
            "tone": _score_tone(confirmation_score),
            "summary": " / ".join(confirmation_fragments),
        },
        {
            "key": "event",
            "label": "事件風險",
            "score": 0,
            "tone": event_tone,
            "summary": event_summary,
        },
        {
            "key": "fundamentals",
            "label": "基本面",
            "score": 0,
            "tone": fundamental_tone,
            "summary": " / ".join(fundamental_fragments),
        },
        *([accumulation_section] if accumulation_section else []),
        {
            "key": "macro",
            "label": "市場風險",
            "score": macro_adjustment,
            "tone": _score_tone(macro_adjustment),
            "summary": " / ".join(fragment for fragment in macro_fragments if fragment),
        },
    ]

    return {
        "verdict": verdict,
        "verdict_key": verdict_key,
        "summary": summary,
        "total_score": score,
        "base_score": base_score,
        "macro_adjustment": macro_adjustment,
        "setup_quality": None,
        "sections": sections,
        "source_note": "所有決策卡因子皆由本地資料庫快照與歷史資料重建。",
    }


class ScreenerEngine:
    async def run(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        normalized_filters = normalize_screener_filters(filters)
        macro_summary = build_macro_summary(await db.list_macro_snapshots())
        cache_key = json.dumps(
            {
                "filters": normalized_filters,
                "macro": _build_macro_cache_fragment(macro_summary),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        now = time.time()
        cached = _screen_cache.get(cache_key)
        if cached and now - cached[0] < SCREEN_CACHE_TTL_SECONDS:
            return cached[1]

        universe = await db.list_screenable_tickers(limit=500)
        results: List[Dict[str, Any]] = []
        today = date.today()
        date_to = (today + timedelta(days=normalized_filters["upcoming_event_days"] or 0)).isoformat()
        needs_accumulation = (
            normalized_filters["setup_type"] == "accumulation"
            or normalized_filters["sort_by"] == "accumulation_score"
            or normalized_filters["min_accumulation_score"] is not None
        )

        for row in universe:
            ticker = normalize_ticker(row.get("ticker"))
            if not ticker:
                continue

            market = infer_market(ticker) or "UNKNOWN"
            if normalized_filters["market"] != "ALL" and market != normalized_filters["market"]:
                continue

            latest_close = _safe_float(row.get("close"))
            if normalized_filters["min_price"] is not None and latest_close < normalized_filters["min_price"]:
                continue
            if normalized_filters["max_price"] is not None and latest_close > normalized_filters["max_price"]:
                continue

            name = row.get("name") or ticker
            sector = row.get("sector") or ""
            if normalized_filters["search"]:
                haystack = f"{ticker} {name} {sector} {row.get('industry') or ''}".lower()
                if normalized_filters["search"].lower() not in haystack:
                    continue
            if normalized_filters["sector"] and normalized_filters["sector"].lower() not in sector.lower():
                continue

            pe_ratio = row.get("pe_ratio")
            if normalized_filters["max_pe_ratio"] is not None and pe_ratio is not None and pe_ratio > normalized_filters["max_pe_ratio"]:
                continue
            dividend_yield = row.get("dividend_yield")
            if normalized_filters["min_dividend_yield"] is not None and (
                dividend_yield is None or dividend_yield < normalized_filters["min_dividend_yield"]
            ):
                continue

            recent_rows = await db.get_recent_ohlcv_rows(ticker, limit=260)
            if len(recent_rows) < 20:
                continue
            ma20 = _mean_close(recent_rows, 20)
            ma50 = _mean_close(recent_rows, 50) if len(recent_rows) >= 50 else None
            volume = _safe_int(row.get("volume"))
            avg_volume = max(1, _safe_int(row.get("avg_volume"), volume or 1))
            volume_ratio = volume / avg_volume if avg_volume else 0.0

            if normalized_filters["min_volume_ratio"] is not None and volume_ratio < normalized_filters["min_volume_ratio"]:
                continue
            if normalized_filters["ma_alignment"] == "bullish":
                if ma20 is None or ma50 is None or latest_close < ma20 or ma20 < ma50:
                    continue

            week_52_high = row.get("week_52_high")
            distance_to_high_pct = None
            if week_52_high:
                distance_to_high_pct = max(0.0, (week_52_high - latest_close) / week_52_high * 100.0)
                if normalized_filters["near_52w_high_pct"] is not None and distance_to_high_pct > normalized_filters["near_52w_high_pct"]:
                    continue

            accumulation_candidate = True
            if needs_accumulation:
                pre_range20 = _range_pct(recent_rows, 20)
                pre_ret20 = _pct_change_over(recent_rows, 20)
                pre_ma_support = (
                    (ma20 is not None and latest_close >= ma20 * 0.97)
                    or (ma50 is not None and latest_close >= ma50 * 0.98)
                )
                accumulation_candidate = (
                    pre_range20 is not None
                    and pre_range20 <= 22
                    and (pre_ret20 is None or pre_ret20 <= 30)
                    and pre_ma_support
                )
                if normalized_filters["setup_type"] == "accumulation" and not accumulation_candidate:
                    continue

            events = []
            if normalized_filters["upcoming_event_days"] is not None:
                events = await db.list_market_events(
                    ticker=ticker,
                    date_from=today.isoformat(),
                    date_to=date_to,
                    limit=5,
                )
                if not events:
                    continue
            earliest_event = events[0] if events else None

            chip_snapshot = await db.get_taiwan_chip_snapshot(ticker) if market == "TW" else None
            chip_summary = chip_snapshot.get("summary") if chip_snapshot else None
            chip_bias = chip_summary.get("bias") if isinstance(chip_summary, dict) else None
            if normalized_filters["chip_bias"] in {"bullish", "bearish"} and chip_bias != normalized_filters["chip_bias"]:
                continue
            chip_history = []
            if needs_accumulation and accumulation_candidate and market == "TW":
                try:
                    chip_history = await db.list_taiwan_chip_snapshots(ticker, limit=20)
                except Exception:
                    chip_history = []

            institutional_signal = await _institutional_signal_for_ticker(ticker)
            change_pct = _safe_float(row.get("quote_change_pct"))
            candlestick_profile = _build_candlestick_profile(
                recent_rows,
                ma20=ma20,
                volume_ratio=volume_ratio,
            )
            accumulation_profile = (
                _build_accumulation_profile(
                    ticker=ticker,
                    market=market,
                    latest_close=latest_close,
                    recent_rows=recent_rows,
                    ma20=ma20,
                    ma50=ma50,
                    chip_history=chip_history,
                )
                if needs_accumulation
                else None
            )
            if (
                normalized_filters["min_accumulation_score"] is not None
                and (accumulation_profile or {}).get("score", 0) < normalized_filters["min_accumulation_score"]
            ):
                continue
            if normalized_filters["setup_type"] == "accumulation" and not (accumulation_profile or {}).get("qualified"):
                continue
            base_score = 0
            base_score += 25 if volume_ratio >= 1.5 else 10 if volume_ratio >= 1.0 else 0
            base_score += 20 if ma20 is not None and latest_close >= ma20 else 0
            base_score += 15 if ma50 is not None and ma20 is not None and ma20 >= ma50 else 0
            base_score += 15 if distance_to_high_pct is not None and distance_to_high_pct <= 5 else 0
            base_score += 15 if chip_bias == "bullish" else -10 if chip_bias == "bearish" else 0
            base_score += 10 if change_pct > 0 else -5 if change_pct < 0 else 0
            base_score += 10 if institutional_signal and institutional_signal.get("signal") == "bullish" else 0

            setup_quality = _setup_quality(
                latest_close=latest_close,
                volume_ratio=volume_ratio,
                ma20=ma20,
                ma50=ma50,
                distance_to_high_pct=distance_to_high_pct,
                change_pct=change_pct,
            )
            macro_adjustment, macro_adjustment_reason = _macro_adjustment(
                macro_summary,
                setup_quality,
                chip_bias,
                institutional_signal,
                change_pct,
            )
            if normalized_filters["min_setup_quality"] is not None and setup_quality < normalized_filters["min_setup_quality"]:
                continue
            score = base_score + macro_adjustment
            decision_card = _build_decision_card(
                score=score,
                base_score=base_score,
                macro_adjustment=macro_adjustment,
                macro_adjustment_reason=macro_adjustment_reason,
                macro_summary=macro_summary,
                latest_close=latest_close,
                ma20=ma20,
                ma50=ma50,
                distance_to_high_pct=distance_to_high_pct,
                change_pct=change_pct,
                volume_ratio=volume_ratio,
                pe_ratio=pe_ratio,
                dividend_yield=dividend_yield,
                chip_bias=chip_bias,
                chip_summary=chip_summary,
                institutional_signal=institutional_signal,
                earliest_event=earliest_event,
                event_window_days=normalized_filters["upcoming_event_days"],
                accumulation_profile=accumulation_profile,
                candlestick_profile=candlestick_profile,
            )
            decision_card["setup_quality"] = setup_quality
            if normalized_filters["decision_verdict"] in {"priority", "watch", "wait"} and (
                decision_card.get("verdict_key") != normalized_filters["decision_verdict"]
            ):
                continue

            results.append(
                {
                    "ticker": ticker,
                    "market": market,
                    "name": name,
                    "sector": sector,
                    "industry": row.get("industry"),
                    "close": latest_close,
                    "volume": volume,
                    "avg_volume": avg_volume,
                    "volume_ratio": round(volume_ratio, 2),
                    "change_pct": round(change_pct, 2),
                    "pe_ratio": pe_ratio,
                    "dividend_yield": dividend_yield,
                    "week_52_high": week_52_high,
                    "distance_to_52w_high_pct": round(distance_to_high_pct, 2) if distance_to_high_pct is not None else None,
                    "ma20": round(ma20, 4) if ma20 is not None else None,
                    "ma50": round(ma50, 4) if ma50 is not None else None,
                    "base_score": base_score,
                    "macro_adjustment": macro_adjustment,
                    "macro_adjustment_reason": macro_adjustment_reason,
                    "setup_quality": setup_quality,
                    "candlestick_score": (candlestick_profile or {}).get("score"),
                    "candlestick_profile": candlestick_profile,
                    "accumulation_score": (accumulation_profile or {}).get("score"),
                    "accumulation_profile": accumulation_profile,
                    "score": score,
                    "decision_card": decision_card,
                    "next_event": earliest_event,
                    "chip_summary": chip_summary,
                    "institutional_signal": institutional_signal,
                    "updated_at": row.get("quote_timestamp") or row.get("date"),
                }
            )

        sort_by = normalized_filters["sort_by"]
        if sort_by == "change_pct":
            results.sort(key=lambda item: item.get("change_pct") or 0, reverse=True)
        elif sort_by == "volume_ratio":
            results.sort(key=lambda item: item.get("volume_ratio") or 0, reverse=True)
        elif sort_by == "setup_quality":
            results.sort(key=lambda item: (item.get("setup_quality") or 0, item.get("score") or 0), reverse=True)
        elif sort_by == "macro_adjustment":
            results.sort(key=lambda item: (item.get("macro_adjustment") or 0, item.get("score") or 0), reverse=True)
        elif sort_by == "candlestick_score":
            results.sort(
                key=lambda item: (
                    item.get("candlestick_score") or 0,
                    item.get("score") or 0,
                    item.get("change_pct") or 0,
                ),
                reverse=True,
            )
        elif sort_by == "accumulation_score":
            results.sort(
                key=lambda item: (
                    item.get("accumulation_score") or 0,
                    item.get("score") or 0,
                    item.get("change_pct") or 0,
                ),
                reverse=True,
            )
        elif sort_by == "event_date":
            results.sort(key=lambda item: (item.get("next_event") or {}).get("event_date") or "9999-12-31")
        else:
            results.sort(key=lambda item: (item.get("score") or 0, item.get("change_pct") or 0), reverse=True)

        payload = {
            "filters": normalized_filters,
            "items": results[: normalized_filters["limit"]],
            "total": len(results),
            "market_context": macro_summary,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        _screen_cache[cache_key] = (now, payload)
        return payload
