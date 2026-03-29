from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import DEFAULT_OWNER_ID

log = logging.getLogger(__name__)


def normalize_alert_condition(value: Optional[str]) -> str:
    mapping = {
        "大於": "gt",
        "小於": "lt",
        "上穿": "cross_up",
        "下穿": "cross_down",
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

    if alert_type == "price":
        current_value = quote.get("price")
    elif alert_type == "pct":
        current_value = quote.get("change_pct")
    else:
        return {
            "matched": False,
            "reason": "unsupported_type",
            "condition_payload": condition_payload,
            "current_value": None,
            "threshold_value": threshold,
        }

    if current_value is None or threshold is None:
        return {
            "matched": False,
            "reason": "missing_value",
            "condition_payload": condition_payload,
            "current_value": current_value,
            "threshold_value": threshold,
        }

    previous_value = condition_payload.get("last_observed_value")
    matched = False

    if condition == "gt":
        matched = current_value > threshold
    elif condition == "lt":
        matched = current_value < threshold
    elif condition == "cross_up" and previous_value is not None:
        matched = previous_value <= threshold < current_value
    elif condition == "cross_down" and previous_value is not None:
        matched = previous_value >= threshold > current_value

    updated_payload = {
        **condition_payload,
        "last_observed_value": current_value,
        "last_quote_timestamp": quote.get("quote_timestamp") or quote.get("synced_at"),
        "last_source": quote.get("source"),
    }

    return {
        "matched": matched,
        "reason": "matched" if matched else "not_matched",
        "condition_payload": updated_payload,
        "current_value": current_value,
        "threshold_value": threshold,
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

        quote = await self._quote_provider.fetch_quote(ticker)
        if quote:
            quote = await self._db.upsert_market_quote(quote)
        else:
            quote = await self._db.get_market_quote(ticker)
        if not quote:
            return False

        evaluation = evaluate_alert_rule(alert, quote)
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
                "message": (
                    f"{ticker} {alert.get('type')} {alert.get('condition')} {alert.get('value')} "
                    f"-> {evaluation['current_value']}"
                ),
                "related_entity_type": "alert",
                "related_entity_id": alert.get("id"),
                "payload": {
                    "quote": quote,
                    "alert_id": alert.get("id"),
                    "trigger_value": evaluation["current_value"],
                    "threshold_value": evaluation["threshold_value"],
                },
            },
            owner_id=self._owner_id,
        )
        return True
