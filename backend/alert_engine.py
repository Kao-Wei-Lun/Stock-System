from __future__ import annotations

import logging
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List, Optional

from database import DEFAULT_OWNER_ID

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
    }
    return mapping.get(str(value or "").strip().lower(), mapping.get(str(value or "").strip(), ""))


def evaluate_alert_rule(alert: Dict[str, Any], quote: Dict[str, Any]) -> Dict[str, Any]:
    alert_type = str(alert.get("type") or "").strip().lower()
    condition = normalize_alert_condition(alert.get("condition"))
    threshold = alert.get("value")
    condition_payload = dict(alert.get("condition_payload") or {})

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
    )
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

    updated_payload = {
        **condition_payload,
        "last_observed_value": current_value,
        "last_secondary_value": secondary_value,
        "last_quote_timestamp": quote.get("quote_timestamp") or quote.get("synced_at"),
        "last_source": quote.get("source"),
    }

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
    def __init__(self, db, quote_provider, owner_id: int = DEFAULT_OWNER_ID):
        self._db = db
        self._quote_provider = quote_provider
        self._owner_id = owner_id

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
        quote = await self._quote_provider.fetch_quote(ticker)
        if quote:
            quote = await self._db.upsert_market_quote(quote)
        else:
            quote = await self._db.get_market_quote(ticker)
        if not quote:
            return False

        market_data = dict(quote)
        if alert_type in {"rsi", "macd", "volume"} and hasattr(self._db, "get_recent_ohlcv_rows"):
            rows = await self._db.get_recent_ohlcv_rows(ticker, limit=80)
            if rows:
                market_data.update(_build_indicator_market_data(_merge_quote_into_rows(rows, quote)))

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
                "evaluation": evaluation,
                "alert": {
                    "id": alert.get("id"),
                    "name": alert.get("name"),
                    "type": alert.get("type"),
                    "condition": alert.get("condition"),
                },
            },
        )
        await self._db.create_notification(
            {
                "category": "alert",
                "level": "warning",
                "title": alert.get("notification_title") or alert.get("name") or f"{ticker} alert triggered",
                "message": self._build_notification_message(ticker, alert, evaluation),
                "related_entity_type": "alert",
                "related_entity_id": alert.get("id"),
                "payload": {
                    "quote": quote,
                    "alert_id": alert.get("id"),
                    "ticker": ticker,
                    "source": quote.get("source"),
                    "trigger_value": evaluation["current_value"],
                    "threshold_value": evaluation["threshold_value"],
                },
            },
            owner_id=self._owner_id,
        )
        return True

    @staticmethod
    def _build_notification_message(ticker: str, alert: Dict[str, Any], evaluation: Dict[str, Any]) -> str:
        condition = alert.get("condition") or ""
        threshold_value = evaluation.get("threshold_value")
        current_value = evaluation.get("current_value")
        if threshold_value in (None, ""):
            return f"{ticker} {alert.get('type')} {condition} -> {current_value}"
        return f"{ticker} {alert.get('type')} {condition} {threshold_value} -> {current_value}"
