from __future__ import annotations

from typing import Any, Dict, List


def _unknown_macro_summary() -> Dict[str, Any]:
    return {
        "overall_risk": "unknown",
        "regime": "unknown",
        "trade_posture": "standby",
        "decision_hint": "尚未同步足夠的宏觀快照，暫時不要把市場環境當成進場依據。",
        "drivers": [],
        "risk_drivers": [],
        "tailwinds": [],
    }


def build_macro_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return _unknown_macro_summary()

    item_map = {item.get("metric_code"): item for item in items}
    risk_drivers: List[Dict[str, Any]] = []
    tailwinds: List[Dict[str, Any]] = []
    risk_score = 0
    tailwind_score = 0

    def append_signal(target: List[Dict[str, Any]], tone: str, label: str, value: str) -> None:
        target.append({"tone": tone, "label": label, "value": value})

    vix = item_map.get("VIX")
    if vix and vix.get("value") is not None:
        vix_value = float(vix["value"])
        if vix_value >= 25:
            append_signal(risk_drivers, "risk", "VIX 偏高", f"{vix_value:.2f}")
            risk_score += 2
        elif vix_value >= 18:
            append_signal(risk_drivers, "caution", "VIX 升溫", f"{vix_value:.2f}")
            risk_score += 1
        elif vix_value <= 16:
            append_signal(tailwinds, "positive", "VIX 穩定", f"{vix_value:.2f}")
            tailwind_score += 1

    us10y = item_map.get("US10Y")
    if us10y and us10y.get("value") is not None:
        us10y_value = float(us10y["value"])
        if us10y_value >= 4.5:
            append_signal(risk_drivers, "caution", "美債殖利率偏高", f"{us10y_value:.2f}")
            risk_score += 1
        elif us10y_value <= 4.1:
            append_signal(tailwinds, "positive", "債殖壓力緩和", f"{us10y_value:.2f}")
            tailwind_score += 1

    dxy = item_map.get("DXY")
    dxy_change_pct = (dxy or {}).get("change_pct")
    if dxy_change_pct is not None:
        dxy_change_pct = float(dxy_change_pct)
        if dxy_change_pct >= 0.7:
            append_signal(risk_drivers, "caution", "美元走強", f"{dxy_change_pct:+.2f}%")
            risk_score += 1
        elif dxy_change_pct <= -0.5:
            append_signal(tailwinds, "positive", "美元轉弱", f"{dxy_change_pct:+.2f}%")
            tailwind_score += 1

    sox = item_map.get("SOX")
    sox_change_pct = (sox or {}).get("change_pct")
    if sox_change_pct is not None:
        sox_change_pct = float(sox_change_pct)
        if sox_change_pct <= -1.5:
            append_signal(risk_drivers, "risk", "費半轉弱", f"{sox_change_pct:+.2f}%")
            risk_score += 1
        elif sox_change_pct >= 1.5:
            append_signal(tailwinds, "positive", "費半偏強", f"{sox_change_pct:+.2f}%")
            tailwind_score += 1

    twii = item_map.get("TWII")
    twii_change_pct = (twii or {}).get("change_pct")
    if twii_change_pct is not None:
        twii_change_pct = float(twii_change_pct)
        if twii_change_pct <= -1.2:
            append_signal(risk_drivers, "risk", "台股指數承壓", f"{twii_change_pct:+.2f}%")
            risk_score += 1
        elif twii_change_pct >= 0.8:
            append_signal(tailwinds, "positive", "台股指數回穩", f"{twii_change_pct:+.2f}%")
            tailwind_score += 1

    if risk_score >= 4:
        overall_risk = "high"
        regime = "risk_off"
        trade_posture = "defensive"
        decision_hint = "系統性風險升高，今天優先保留現金、降低部位，等待風險收斂。"
    elif risk_score >= 2:
        overall_risk = "medium"
        regime = "mixed"
        trade_posture = "selective"
        decision_hint = "環境偏震盪，只做最強標的，並縮小部位與嚴守停損。"
    elif risk_score == 0 and tailwind_score >= 2:
        overall_risk = "low"
        regime = "trend_supportive"
        trade_posture = "offensive"
        decision_hint = "宏觀風向對風險資產較友善，可優先觀察強勢趨勢股與突破型機會。"
    else:
        overall_risk = "low" if risk_score == 0 else "medium"
        regime = "neutral"
        trade_posture = "balanced"
        decision_hint = "市場沒有明確順風，先等待突破、回踩確認或事件催化再出手。"

    return {
        "overall_risk": overall_risk,
        "regime": regime,
        "trade_posture": trade_posture,
        "decision_hint": decision_hint,
        "risk_score": risk_score,
        "tailwind_score": tailwind_score,
        "drivers": (risk_drivers + tailwinds)[:6],
        "risk_drivers": risk_drivers[:4],
        "tailwinds": tailwinds[:4],
        "updated_at": max(
            (item.get("quote_timestamp") or item.get("created_at") or item.get("date") or "")
            for item in items
        ),
    }


def build_macro_dashboard_payload(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "snapshot_date": items[0].get("date") if items else None,
        "items": items,
        "summary": build_macro_summary(items),
    }
