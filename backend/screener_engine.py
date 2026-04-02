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


def normalize_screener_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(filters or {})
    market = str(source.get("market") or "ALL").upper()
    if market not in {"ALL", "US", "TW", "HK", "INDEX"}:
        market = "ALL"
    return {
        "search": str(source.get("search") or "").strip(),
        "market": market,
        "sector": str(source.get("sector") or "").strip(),
        "min_price": _safe_float(source.get("min_price"), 0.0) or None,
        "max_price": _safe_float(source.get("max_price"), 0.0) or None,
        "min_volume_ratio": _safe_float(source.get("min_volume_ratio"), 0.0) or None,
        "min_setup_quality": _safe_int(source.get("min_setup_quality"), 0) or None,
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

            institutional_signal = await _institutional_signal_for_ticker(ticker)
            change_pct = _safe_float(row.get("quote_change_pct"))
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
