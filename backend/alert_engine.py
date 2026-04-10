from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from math import sqrt
from statistics import mean
from typing import Any, Dict, List, Optional

from database import DEFAULT_OWNER_ID
from external_notifications import NullExternalNotificationDispatcher
from macro_regime import build_macro_summary

log = logging.getLogger(__name__)


def normalize_alert_condition(value: Optional[str]) -> str:
    mapping = {
        "大於": "gt",
        "小於": "lt",
        "上穿": "cross_up",
        "下穿": "cross_down",
        "黃金交叉": "cross_up",
        "死亡交叉": "cross_down",
        "gt": "gt",
        "lt": "lt",
        "cross_up": "cross_up",
        "cross_down": "cross_down",
        "high": "high",
        "medium_or_high": "medium_or_high",
        "risk_off": "risk_off",
        "offensive": "offensive",
        "進入高風險": "high",
        "進入中風險以上": "medium_or_high",
        "進入risk-off": "risk_off",
        "進入偏進攻": "offensive",
        "within_days": "within_days",
        "事件前提醒": "within_days",
        "高異常": "high",
        "中度以上異常": "medium_or_high",
    }
    return mapping.get(str(value or "").strip().lower(), mapping.get(str(value or "").strip(), ""))


def evaluate_alert_rule(alert: Dict[str, Any], quote: Dict[str, Any]) -> Dict[str, Any]:
    alert_type = str(alert.get("type") or "").strip().lower()
    condition = normalize_alert_condition(alert.get("condition"))
    threshold = alert.get("value")
    condition_payload = dict(alert.get("condition_payload") or {})
    metric = str(condition_payload.get("metric") or "").strip().lower()

    current_value = None
    previous_value = None
    threshold_value = threshold
    secondary_value = None
    previous_secondary_value = None

    if alert_type == "price":
        current_value = quote.get("price")
        previous_value = condition_payload.get("last_observed_value")
    elif alert_type == "pct":
        current_value = quote.get("change_pct")
        previous_value = condition_payload.get("last_observed_value")
    elif alert_type == "rsi":
        current_value = quote.get("rsi")
        previous_value = quote.get("rsi_prev", condition_payload.get("last_observed_value"))
    elif alert_type == "macd":
        current_value = quote.get("macd")
        previous_value = quote.get("macd_prev")
        secondary_value = quote.get("macd_signal")
        previous_secondary_value = quote.get("macd_signal_prev")
        if condition in {"cross_up", "cross_down"}:
            threshold_value = secondary_value
    elif alert_type == "volume":
        current_value = quote.get("volume_ratio")
        previous_value = condition_payload.get("last_observed_value")
    elif alert_type == "basis":
        current_value = quote.get("basis_pct") if metric in {"", "basis_pct"} else quote.get("basis")
        previous_value = condition_payload.get("last_observed_value")
    elif alert_type == "institutional":
        if condition in {"high", "medium_or_high"}:
            current_value = str(quote.get("institutional_anomaly_level") or "").strip().lower() or None
            threshold_value = condition
        else:
            current_value = quote.get("institutional_anomaly_score")
            previous_value = condition_payload.get("last_observed_value")
    elif alert_type == "event":
        if condition != "within_days":
            return {
                "matched": False,
                "reason": "unsupported_condition",
                "condition_payload": condition_payload,
                "current_value": None,
                "threshold_value": threshold,
            }
        current_value = quote.get("days_until_event")
    elif alert_type == "market_risk":
        overall_risk = str(quote.get("macro_overall_risk") or "").strip().lower() or None
        regime = str(quote.get("macro_regime") or "").strip().lower() or None
        posture = str(quote.get("macro_trade_posture") or "").strip().lower() or None
        threshold_value = condition
        if condition in {"high", "medium_or_high"}:
            current_value = overall_risk
        elif condition == "risk_off":
            current_value = regime
        elif condition == "offensive":
            current_value = posture
        else:
            return {
                "matched": False,
                "reason": "unsupported_condition",
                "condition_payload": condition_payload,
                "current_value": None,
                "threshold_value": threshold_value,
            }
    else:
        return {
            "matched": False,
            "reason": "unsupported_type",
            "condition_payload": condition_payload,
            "current_value": None,
            "threshold_value": threshold,
        }

    missing_threshold = threshold is None and not (
        alert_type == "macd" and condition in {"cross_up", "cross_down"}
    ) and not (
        alert_type == "institutional" and condition in {"high", "medium_or_high"}
    ) and alert_type != "market_risk"
    if current_value is None or missing_threshold:
        return {
            "matched": False,
            "reason": "missing_value",
            "condition_payload": condition_payload,
            "current_value": current_value,
            "threshold_value": threshold_value,
        }

    matched = False
    if condition == "gt":
        matched = current_value > threshold
    elif condition == "lt":
        matched = current_value < threshold
    elif condition == "cross_up":
        if secondary_value is not None and previous_value is not None and previous_secondary_value is not None:
            matched = previous_value <= previous_secondary_value and current_value > secondary_value
        elif previous_value is not None and threshold is not None:
            matched = previous_value <= threshold < current_value
    elif condition == "cross_down":
        if secondary_value is not None and previous_value is not None and previous_secondary_value is not None:
            matched = previous_value >= previous_secondary_value and current_value < secondary_value
        elif previous_value is not None and threshold is not None:
            matched = previous_value >= threshold > current_value
    elif alert_type == "institutional":
        if condition == "high":
            matched = current_value == "high"
        elif condition == "medium_or_high":
            matched = current_value in {"medium", "high"}
    elif alert_type == "event" and condition == "within_days":
        matched = current_value <= threshold
    elif alert_type == "market_risk":
        if condition == "high":
            matched = current_value == "high"
        elif condition == "medium_or_high":
            matched = current_value in {"medium", "high"}
        elif condition == "risk_off":
            matched = current_value == "risk_off"
        elif condition == "offensive":
            matched = current_value == "offensive"

    updated_payload = {
        **condition_payload,
        "last_observed_value": current_value,
        "last_secondary_value": secondary_value,
        "last_quote_timestamp": quote.get("quote_timestamp") or quote.get("synced_at"),
        "last_source": quote.get("source"),
    }
    if quote.get("macro_overall_risk") is not None:
        updated_payload["last_macro_overall_risk"] = quote.get("macro_overall_risk")
    if quote.get("macro_regime") is not None:
        updated_payload["last_macro_regime"] = quote.get("macro_regime")
    if quote.get("macro_trade_posture") is not None:
        updated_payload["last_macro_trade_posture"] = quote.get("macro_trade_posture")
    if quote.get("basis") is not None:
        updated_payload["last_basis"] = quote.get("basis")
    if quote.get("basis_pct") is not None:
        updated_payload["last_basis_pct"] = quote.get("basis_pct")
    if quote.get("basis_spot_price") is not None:
        updated_payload["last_basis_spot_price"] = quote.get("basis_spot_price")
    if quote.get("basis_institution_price") is not None:
        updated_payload["last_basis_institution_price"] = quote.get("basis_institution_price")
    if quote.get("basis_spot_label") is not None:
        updated_payload["last_basis_spot_label"] = quote.get("basis_spot_label")
    if quote.get("basis_futures_commodity") is not None:
        updated_payload["last_basis_futures_commodity"] = quote.get("basis_futures_commodity")
    if quote.get("institutional_anomaly_score") is not None:
        updated_payload["last_institutional_anomaly_score"] = quote.get("institutional_anomaly_score")
    if quote.get("institutional_anomaly_level") is not None:
        updated_payload["last_institutional_anomaly_level"] = quote.get("institutional_anomaly_level")
    if quote.get("institutional_anomaly_title") is not None:
        updated_payload["last_institutional_anomaly_title"] = quote.get("institutional_anomaly_title")
    if quote.get("institutional_anomaly_detail") is not None:
        updated_payload["last_institutional_anomaly_detail"] = quote.get("institutional_anomaly_detail")
    if quote.get("days_until_event") is not None:
        updated_payload["last_days_until_event"] = quote.get("days_until_event")
    if quote.get("event_title") is not None:
        updated_payload["last_event_title"] = quote.get("event_title")
    if quote.get("event_type") is not None:
        updated_payload["last_event_type"] = quote.get("event_type")
    if quote.get("event_date") is not None:
        updated_payload["last_event_date"] = quote.get("event_date")
    if quote.get("event_importance") is not None:
        updated_payload["last_event_importance"] = quote.get("event_importance")

    return {
        "matched": matched,
        "reason": "matched" if matched else "not_matched",
        "condition_payload": updated_payload,
        "current_value": current_value,
        "threshold_value": threshold_value,
    }


def _safe_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _series_anomaly_stats(values: List[float]) -> Optional[Dict[str, float]]:
    if len(values) < 4:
        return None

    latest = values[-1]
    previous_values = values[:-1]
    average = mean(previous_values)
    variance = mean([(value - average) ** 2 for value in previous_values]) if previous_values else 0.0
    deviation = sqrt(variance) if variance > 0 else 0.0
    z_score = (latest - average) / deviation if deviation > 0 else 0.0
    relative_shift = abs(latest - average) / max(abs(average), 1.0)
    return {
        "latest": latest,
        "average": average,
        "score": max(abs(z_score), relative_shift * 1.8),
    }


SPOT_REFERENCE_BY_COMMODITY = {
    "臺股期貨": "^TWII",
    "小型臺指期貨": "^TWII",
    "微型臺指期貨": "^TWII",
    "臺灣永續期貨": "^TWII",
    "臺灣生技期貨": "^TWII",
    "櫃買指數期貨": "^TWOII",
}


def _detect_basis_market_data(
    snapshot: Optional[Dict[str, Any]],
    quote: Dict[str, Any],
    ticker: str,
    condition_payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not snapshot:
        return None

    futures_commodity = (
        condition_payload.get("futures_commodity")
        or snapshot.get("default_futures_commodity")
        or (snapshot.get("futures_commodities") or [None])[0]
    )
    target_ticker = str(condition_payload.get("spot_ticker") or ticker or "").strip().upper()
    mapped_ticker = SPOT_REFERENCE_BY_COMMODITY.get(str(futures_commodity or "").strip())
    spot_reference = None
    for item in snapshot.get("spot_reference") or []:
        item_ticker = str(item.get("ticker") or "").strip().upper()
        if item_ticker and item_ticker == target_ticker:
            spot_reference = item
            break
        if not spot_reference and mapped_ticker and item_ticker == mapped_ticker:
            spot_reference = item

    spot_price = _safe_float(quote.get("price"))
    if spot_price is None:
        spot_price = _safe_float((spot_reference or {}).get("price"))

    futures_costs = ((snapshot.get("cost_estimates") or {}).get("futures") or {})
    institution_price = _safe_float(((futures_costs.get("institution_estimate") or {}).get("price")))
    if spot_price is None or institution_price is None or spot_price == 0:
        return None

    basis = institution_price - spot_price
    return {
        "basis": basis,
        "basis_pct": (basis / spot_price) * 100,
        "basis_spot_price": spot_price,
        "basis_institution_price": institution_price,
        "basis_spot_label": (spot_reference or {}).get("label") or (spot_reference or {}).get("ticker") or ticker,
        "basis_futures_commodity": futures_commodity,
        "quote_timestamp": quote.get("quote_timestamp") or snapshot.get("resolved_date"),
        "source": quote.get("source") or "local_db",
    }


def _snapshot_futures_total(snapshot: Dict[str, Any], commodity: Optional[str], key: str) -> float:
    total = 0.0
    for row in snapshot.get("futures") or []:
        if commodity and row.get("commodity") != commodity:
            continue
        total += _safe_float(row.get(key)) or 0.0
    return total


def _snapshot_foreign_call_put_balance(snapshot: Dict[str, Any], commodity: Optional[str]) -> float:
    balance = 0.0
    for row in snapshot.get("call_puts") or []:
        if commodity and row.get("commodity") != commodity:
            continue
        if row.get("institution") != "外資":
            continue
        volume = _safe_float(row.get("oi_net_volume")) or 0.0
        balance += volume if row.get("option_side") == "買權" else -volume
    return balance


def _snapshot_cash_total(snapshot: Dict[str, Any]) -> float:
    rows = snapshot.get("cash_summary_aggregated") or snapshot.get("cash_summary") or []
    total = 0.0
    for row in rows:
        total += _safe_float(row.get("net_amount")) or 0.0
    return total


def _detect_institutional_market_data(
    snapshots: List[Dict[str, Any]],
    condition_payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not snapshots:
        return None

    latest_snapshot = snapshots[-1]
    futures_commodity = (
        condition_payload.get("futures_commodity")
        or latest_snapshot.get("default_futures_commodity")
        or (latest_snapshot.get("futures_commodities") or [None])[0]
    )
    options_commodity = (
        condition_payload.get("options_commodity")
        or latest_snapshot.get("default_options_commodity")
        or (latest_snapshot.get("options_commodities") or [None])[0]
    )

    candidate_specs = [
        {
            "title": "期貨未平倉淨口數異常",
            "detail_prefix": f"{futures_commodity or '期貨'} / 三大法人",
            "values": [_snapshot_futures_total(item, futures_commodity, "oi_net_volume") for item in snapshots],
        },
        {
            "title": "期貨當日交易淨口數異常",
            "detail_prefix": f"{futures_commodity or '期貨'} / 交易口數",
            "values": [_snapshot_futures_total(item, futures_commodity, "trade_net_volume") for item in snapshots],
        },
        {
            "title": "外資選擇權偏向擴大",
            "detail_prefix": f"{options_commodity or '選擇權'} / 外資 Call-Put",
            "values": [_snapshot_foreign_call_put_balance(item, options_commodity) for item in snapshots],
        },
        {
            "title": "現貨三大法人買賣超異常",
            "detail_prefix": "TWSE 現貨 / 三大法人",
            "values": [_snapshot_cash_total(item) for item in snapshots],
        },
    ]

    candidates = []
    for item in candidate_specs:
        stats = _series_anomaly_stats(item["values"])
        if not stats or stats["score"] < 1.8:
            continue
        candidates.append(
            {
                "title": item["title"],
                "detail": (
                    f"{item['detail_prefix']} 最新 {stats['latest']:.2f}，"
                    f"近窗均值 {stats['average']:.2f}"
                ),
                "score": stats["score"],
                "current_value": stats["latest"],
                "average_value": stats["average"],
            }
        )

    if not candidates:
        return {
            "institutional_anomaly_score": 0.0,
            "institutional_anomaly_level": "normal",
            "institutional_anomaly_title": "",
            "institutional_anomaly_detail": "",
            "quote_timestamp": latest_snapshot.get("resolved_date"),
            "source": "local_db",
        }

    best = max(candidates, key=lambda item: item["score"])
    level = "high" if best["score"] >= 2.7 else "medium"
    return {
        "institutional_anomaly_score": best["score"],
        "institutional_anomaly_level": level,
        "institutional_anomaly_title": best["title"],
        "institutional_anomaly_detail": best["detail"],
        "institutional_current_value": best["current_value"],
        "institutional_average_value": best["average_value"],
        "institutional_futures_commodity": futures_commodity,
        "institutional_options_commodity": options_commodity,
        "quote_timestamp": latest_snapshot.get("resolved_date"),
        "source": "local_db",
    }


def _event_matches_filters(
    event: Dict[str, Any],
    ticker: str,
    condition_payload: Dict[str, Any],
) -> bool:
    scope = str(condition_payload.get("event_scope") or "").strip().lower()
    target_ticker = str(ticker or "").strip().upper()
    event_ticker = str(event.get("ticker") or "").strip().upper()

    if scope == "market":
        if event_ticker and event_ticker != "MARKET":
            return False
    elif target_ticker and target_ticker != "MARKET" and event_ticker != target_ticker:
        return False

    expected_type = str(condition_payload.get("event_type") or "").strip().lower()
    if expected_type and str(event.get("event_type") or "").strip().lower() != expected_type:
        return False

    expected_title = str(condition_payload.get("event_title") or "").strip().lower()
    if expected_title and expected_title not in str(event.get("title") or "").strip().lower():
        return False

    expected_importance = str(condition_payload.get("importance") or "").strip().lower()
    if expected_importance and str(event.get("importance") or "").strip().lower() != expected_importance:
        return False

    return True


def _detect_event_market_data(
    events: List[Dict[str, Any]],
    ticker: str,
    condition_payload: Dict[str, Any],
) -> Dict[str, Any]:
    reference_date = _safe_date(condition_payload.get("reference_date")) or datetime.now(timezone.utc).date()
    matching_items = []
    for item in events:
        if not _event_matches_filters(item, ticker, condition_payload):
            continue
        event_date = _safe_date(item.get("event_date"))
        if event_date is None:
            continue
        days_until = (event_date - reference_date).days
        if days_until < 0:
            continue
        matching_items.append((days_until, item))

    if not matching_items:
        return {
            "ticker": ticker,
            "source": "local_db",
            "quote_timestamp": reference_date.isoformat(),
        }

    days_until, matched_event = min(matching_items, key=lambda item: (item[0], item[1].get("event_time") or ""))
    return {
        "ticker": ticker,
        "source": "local_db",
        "quote_timestamp": matched_event.get("event_time") or matched_event.get("event_date"),
        "days_until_event": days_until,
        "event_title": matched_event.get("title"),
        "event_type": matched_event.get("event_type"),
        "event_date": matched_event.get("event_date"),
        "event_importance": matched_event.get("importance"),
        "event_description": matched_event.get("description"),
        "event_url": matched_event.get("url"),
    }


def _calc_ema(values: List[float], period: int) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(values)
    if period <= 0 or not values:
        return result

    multiplier = 2 / (period + 1)
    seed = None
    for index, value in enumerate(values):
        if index < period - 1:
            continue
        if seed is None:
            seed = sum(values[index - period + 1:index + 1]) / period
            result[index] = seed
            continue
        seed = (value - seed) * multiplier + seed
        result[index] = seed
    return result


def _calc_rsi(values: List[float], period: int = 14) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(values)
    if len(values) <= period:
        return result

    gains = []
    losses = []
    for index in range(1, len(values)):
        delta = values[index] - values[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result[period] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + (avg_gain / avg_loss)))

    for index in range(period + 1, len(values)):
        gain = gains[index - 1]
        loss = losses[index - 1]
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        result[index] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + (avg_gain / avg_loss)))

    return result


def _calc_macd(
    values: List[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[List[Optional[float]], List[Optional[float]]]:
    ema_fast = _calc_ema(values, fast)
    ema_slow = _calc_ema(values, slow)
    macd_line: List[Optional[float]] = [None] * len(values)
    for index in range(len(values)):
        if ema_fast[index] is None or ema_slow[index] is None:
            continue
        macd_line[index] = ema_fast[index] - ema_slow[index]

    compact = [value for value in macd_line if value is not None]
    signal_compact = _calc_ema(compact, signal)
    signal_line: List[Optional[float]] = [None] * len(values)
    compact_index = 0
    for index, value in enumerate(macd_line):
        if value is None:
            continue
        signal_line[index] = signal_compact[compact_index]
        compact_index += 1
    return macd_line, signal_line


def _merge_quote_into_rows(rows: List[Dict[str, Any]], quote: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not rows or not quote:
        return rows

    latest = dict(rows[-1])
    price = _safe_float(quote.get("price"))
    open_price = _safe_float(quote.get("open")) or _safe_float(latest.get("open")) or price
    high = _safe_float(quote.get("high")) or price
    low = _safe_float(quote.get("low")) or price
    volume = _safe_float(quote.get("volume"))

    if price is not None:
        latest["close"] = price
        latest["open"] = open_price
        latest["high"] = max(
            value for value in [_safe_float(latest.get("high")), high, price] if value is not None
        )
        latest["low"] = min(
            value for value in [_safe_float(latest.get("low")), low, price] if value is not None
        )
    if volume is not None:
        latest["volume"] = volume

    merged = list(rows)
    merged[-1] = latest
    return merged


def _build_indicator_market_data(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    closes = [_safe_float(row.get("close")) for row in rows]
    closes = [value for value in closes if value is not None]
    if len(closes) < 2:
        return {}

    rsi_series = _calc_rsi(closes, period=14)
    macd_line, signal_line = _calc_macd(closes)

    latest_volume = _safe_float(rows[-1].get("volume"))
    baseline_volumes = [_safe_float(row.get("volume")) for row in rows[-21:-1]]
    baseline_volumes = [value for value in baseline_volumes if value is not None]
    avg_volume = mean(baseline_volumes) if baseline_volumes else None

    return {
        "rsi": rsi_series[-1],
        "rsi_prev": rsi_series[-2] if len(rsi_series) >= 2 else None,
        "macd": macd_line[-1],
        "macd_prev": macd_line[-2] if len(macd_line) >= 2 else None,
        "macd_signal": signal_line[-1],
        "macd_signal_prev": signal_line[-2] if len(signal_line) >= 2 else None,
        "avg_volume": avg_volume,
        "volume_ratio": (latest_volume / avg_volume) if latest_volume is not None and avg_volume not in (None, 0) else None,
    }


class AlertEngine:
    def __init__(self, db, quote_provider, owner_id: int = DEFAULT_OWNER_ID, external_notifier=None):
        self._db = db
        self._quote_provider = quote_provider
        self._owner_id = owner_id
        self._external_notifier = external_notifier or NullExternalNotificationDispatcher()

    async def evaluate_active_alerts(self) -> int:
        triggered_count = 0
        alerts = await self._db.list_active_alerts(owner_id=self._owner_id)
        for alert in alerts:
            try:
                if await self.evaluate_alert(alert):
                    triggered_count += 1
            except Exception as exc:
                log.warning("alert evaluation failed for %s: %s", alert.get("id"), exc)
        return triggered_count

    async def evaluate_alert(self, alert: Dict[str, Any]) -> bool:
        ticker = alert.get("ticker")
        if not ticker:
            return False

        alert_type = str(alert.get("type") or "").strip().lower()
        condition_payload = dict(alert.get("condition_payload") or {})
        macro_summary = None
        quote: Dict[str, Any]
        if alert_type == "market_risk":
            macro_items = await self._db.list_macro_snapshots() if hasattr(self._db, "list_macro_snapshots") else []
            macro_summary = build_macro_summary(macro_items or [])
            if macro_summary.get("overall_risk") == "unknown":
                return False
            quote = {
                "ticker": ticker,
                "source": "local_db",
                "quote_timestamp": macro_summary.get("updated_at"),
                "macro_overall_risk": macro_summary.get("overall_risk"),
                "macro_regime": macro_summary.get("regime"),
                "macro_trade_posture": macro_summary.get("trade_posture"),
                "macro_summary": macro_summary,
            }
            market_data = dict(quote)
        elif alert_type == "institutional":
            if not hasattr(self._db, "get_institutional_snapshot"):
                return False
            history_days = max(4, _safe_int(condition_payload.get("history_days")) or 30)
            latest_snapshot = await self._db.get_institutional_snapshot()
            if not latest_snapshot:
                return False
            snapshots = [latest_snapshot]
            if hasattr(self._db, "get_institutional_snapshots"):
                snapshot_date = _safe_date(latest_snapshot.get("resolved_date"))
                if snapshot_date:
                    snapshots = await self._db.get_institutional_snapshots(snapshot_date, history_days) or snapshots
            market_data = _detect_institutional_market_data(snapshots, condition_payload)
            if not market_data:
                return False
            quote = {
                "ticker": ticker,
                **market_data,
            }
        elif alert_type == "event":
            if not hasattr(self._db, "list_market_events"):
                return False
            reference_date = _safe_date(condition_payload.get("reference_date")) or datetime.now(timezone.utc).date()
            lookahead_days = max(1, _safe_int(alert.get("value")) or 7)
            events = await self._db.list_market_events(
                ticker=None if str(ticker).strip().upper() == "MARKET" else ticker,
                date_from=reference_date.isoformat(),
                date_to=(reference_date + timedelta(days=lookahead_days)).isoformat(),
                limit=50,
            )
            market_data = _detect_event_market_data(events or [], ticker, condition_payload)
            quote = dict(market_data)
        else:
            quote = await self._quote_provider.fetch_quote(ticker)
            if quote:
                quote = await self._db.upsert_market_quote(quote)
            else:
                quote = await self._db.get_market_quote(ticker)
            if not quote and alert_type != "basis":
                return False

            quote = quote or {
                "ticker": ticker,
                "source": "local_db",
            }
            market_data = dict(quote)
            if alert_type in {"rsi", "macd", "volume"} and hasattr(self._db, "get_recent_ohlcv_rows"):
                rows = await self._db.get_recent_ohlcv_rows(ticker, limit=80)
                if rows:
                    market_data.update(_build_indicator_market_data(_merge_quote_into_rows(rows, quote)))
            if alert_type == "basis" and hasattr(self._db, "get_institutional_snapshot"):
                latest_snapshot = await self._db.get_institutional_snapshot()
                basis_data = _detect_basis_market_data(latest_snapshot, market_data, ticker, condition_payload)
                if not basis_data:
                    return False
                market_data.update(basis_data)
            if hasattr(self._db, "list_macro_snapshots"):
                macro_items = await self._db.list_macro_snapshots()
                macro_summary = build_macro_summary(macro_items or [])
                if macro_summary.get("overall_risk") != "unknown":
                    market_data.update(
                        {
                            "macro_overall_risk": macro_summary.get("overall_risk"),
                            "macro_regime": macro_summary.get("regime"),
                            "macro_trade_posture": macro_summary.get("trade_posture"),
                        }
                    )
                else:
                    macro_summary = None
            quote = dict(market_data)

        evaluation = evaluate_alert_rule(alert, market_data)
        now_iso = datetime.now(timezone.utc).isoformat()
        update_payload = {
            "condition_payload": evaluation["condition_payload"],
            "last_evaluated_at": now_iso,
        }

        if not evaluation["matched"]:
            await self._db.update_alert(alert["id"], update_payload, owner_id=self._owner_id)
            return False

        update_payload.update(
            {
                "active": False,
                "triggered": True,
                "triggered_at": now_iso,
            }
        )
        await self._db.update_alert(alert["id"], update_payload, owner_id=self._owner_id)

        await self._db.create_alert_trigger_log(
            alert["id"],
            ticker,
            owner_id=self._owner_id,
            trigger_value=evaluation["current_value"],
            threshold_value=evaluation["threshold_value"],
            payload={
                "quote": quote,
                "macro_summary": macro_summary,
                "evaluation": evaluation,
                "context_source": condition_payload.get("context_source"),
                "context_group_name": condition_payload.get("context_group_name"),
                "context_tags": condition_payload.get("context_tags"),
                "snapshot_price": condition_payload.get("snapshot_price"),
                "snapshot_source": condition_payload.get("snapshot_source"),
                "snapshot_timestamp": condition_payload.get("snapshot_timestamp"),
                "alert": {
                    "id": alert.get("id"),
                    "name": alert.get("name"),
                    "type": alert.get("type"),
                    "condition": alert.get("condition"),
                },
            },
        )
        notification = await self._db.create_notification(
            {
                "category": "alert",
                "level": "warning",
                "title": alert.get("notification_title") or alert.get("name") or (
                    "Market risk alert triggered" if alert_type == "market_risk" else f"{ticker} alert triggered"
                ),
                "message": self._build_notification_message(ticker, alert, evaluation),
                "related_entity_type": "alert",
                "related_entity_id": alert.get("id"),
                "payload": {
                    "quote": quote,
                    "alert_id": alert.get("id"),
                    "source": quote.get("source"),
                    "trigger_value": evaluation["current_value"],
                    "threshold_value": evaluation["threshold_value"],
                    "context_source": condition_payload.get("context_source"),
                    "context_group_name": condition_payload.get("context_group_name"),
                    "context_tags": condition_payload.get("context_tags"),
                    "snapshot_price": condition_payload.get("snapshot_price"),
                    "snapshot_source": condition_payload.get("snapshot_source"),
                    "snapshot_timestamp": condition_payload.get("snapshot_timestamp"),
                    "macro_summary": macro_summary,
                    "alert_type": alert.get("type"),
                    "alert_condition": alert.get("condition"),
                    **({"ticker": ticker} if alert_type != "market_risk" else {}),
                },
            },
            owner_id=self._owner_id,
        )
        try:
            await self._external_notifier.send_alert(notification)
        except Exception as exc:
            log.warning("external alert notification failed for alert %s: %s", alert.get("id"), exc)
        return True

    @staticmethod
    def _build_notification_message(ticker: str, alert: Dict[str, Any], evaluation: Dict[str, Any]) -> str:
        alert_type = str(alert.get("type") or "").strip().lower()
        condition = alert.get("condition") or ""
        threshold_value = evaluation.get("threshold_value")
        current_value = evaluation.get("current_value")
        payload = evaluation.get("condition_payload") or {}
        if alert_type == "market_risk":
            label_map = {
                "high": "高風險",
                "medium": "中風險",
                "low": "低風險",
                "medium_or_high": "中風險以上",
                "risk_off": "risk-off",
                "offensive": "偏進攻",
                "balanced": "平衡觀察",
                "defensive": "防守控倉",
                "selective": "選擇性出手",
            }
            return (
                "市場風險警報觸發："
                f"{label_map.get(str(threshold_value), threshold_value)} -> "
                f"{label_map.get(str(current_value), current_value)}"
            )
        if alert_type == "basis":
            basis_label = payload.get("last_basis_futures_commodity") or ticker
            spot_label = payload.get("last_basis_spot_label") or ticker
            if payload.get("metric") == "basis":
                return f"{basis_label} / {spot_label} Basis {condition} {threshold_value} -> {current_value}"
            if threshold_value in (None, ""):
                return f"{basis_label} / {spot_label} Basis -> {current_value:.2f}%"
            return f"{basis_label} / {spot_label} Basis {condition} {threshold_value:.2f}% -> {current_value:.2f}%"
        if alert_type == "institutional":
            title = payload.get("last_institutional_anomaly_title") or "法人異常值"
            detail = payload.get("last_institutional_anomaly_detail") or ""
            level = payload.get("last_institutional_anomaly_level") or current_value or "normal"
            return f"法人異常警報觸發：{title}（{level}）{f'，{detail}' if detail else ''}"
        if alert_type == "event":
            event_title = payload.get("last_event_title") or "市場事件"
            event_date = payload.get("last_event_date") or "未定"
            if current_value in (None, ""):
                return f"{ticker} 事件提醒：{event_title}（{event_date}）"
            return f"{ticker} 事件提醒：{event_title} 將在 {current_value} 日內發生（{event_date}）"
        if threshold_value in (None, ""):
            return f"{ticker} {alert.get('type')} {condition} -> {current_value}"
        return f"{ticker} {alert.get('type')} {condition} {threshold_value} -> {current_value}"
