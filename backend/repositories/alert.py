from typing import Any, Dict, List, Optional
from database.helpers import *
from database.core import DEFAULT_OWNER_ID
# Import common serialization helpers here if needed

class AlertMixin:
    async def list_alerts(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `alerts`
            WHERE `owner_id`=%s
            ORDER BY `active` DESC, `updated_at` DESC, `id` DESC
            """,
            (owner_id,),
        )
        return [_deserialize_alert(row) for row in rows]

    async def get_alert(self, alert_id: int, owner_id: int = DEFAULT_OWNER_ID) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `alerts`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (alert_id, owner_id),
        )
        return _deserialize_alert(row)

    async def create_alert(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_alert_payload(payload)
        alert_id = await self._execute_insert(
            """
            INSERT INTO `alerts`
                (`owner_id`, `name`, `ticker`, `type`, `condition`, `value`, `value2`,
                 `timeframe`, `condition_json`, `notification_title`, `note`,
                 `active`, `triggered`, `triggered_at`, `last_evaluated_at`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["name"],
                normalized["ticker"],
                normalized["type"],
                normalized["condition"],
                normalized["value"],
                normalized["value2"],
                normalized["timeframe"],
                _json_dumps(normalized["condition_payload"]),
                normalized["notification_title"],
                normalized["note"],
                1 if normalized["active"] else 0,
                1 if normalized["triggered"] else 0,
                _parse_datetime_value(normalized.get("triggered_at")),
                _parse_datetime_value(normalized.get("last_evaluated_at")),
            ),
        )
        alert = await self.get_alert(alert_id, owner_id=owner_id)
        if not alert:
            raise RuntimeError("Alert was not persisted")
        return alert

    async def update_alert(
        self,
        alert_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_alert(alert_id, owner_id=owner_id)
        if not existing:
            return None

        normalized = _normalize_alert_payload(payload, existing=existing)
        await self._execute(
            """
            UPDATE `alerts`
            SET `name`=%s,
                `ticker`=%s,
                `type`=%s,
                `condition`=%s,
                `value`=%s,
                `value2`=%s,
                `timeframe`=%s,
                `condition_json`=%s,
                `notification_title`=%s,
                `note`=%s,
                `active`=%s,
                `triggered`=%s,
                `triggered_at`=%s,
                `last_evaluated_at`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["name"],
                normalized["ticker"],
                normalized["type"],
                normalized["condition"],
                normalized["value"],
                normalized["value2"],
                normalized["timeframe"],
                _json_dumps(normalized["condition_payload"]),
                normalized["notification_title"],
                normalized["note"],
                1 if normalized["active"] else 0,
                1 if normalized["triggered"] else 0,
                _parse_datetime_value(normalized.get("triggered_at")),
                _parse_datetime_value(normalized.get("last_evaluated_at")),
                alert_id,
                owner_id,
            ),
        )
        return await self.get_alert(alert_id, owner_id=owner_id)

    async def delete_alert(self, alert_id: int, owner_id: int = DEFAULT_OWNER_ID) -> bool:
        deleted = await self._execute(
            "DELETE FROM `alerts` WHERE `id`=%s AND `owner_id`=%s",
            (alert_id, owner_id),
        )
        return deleted > 0

    async def create_alert_trigger_log(
        self,
        alert_id: int,
        ticker: str,
        payload: Optional[Dict[str, Any]] = None,
        owner_id: int = DEFAULT_OWNER_ID,
        trigger_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
    ) -> Dict[str, Any]:
        record_id = await self._execute_insert(
            """
            INSERT INTO `alert_trigger_logs`
                (`alert_id`, `owner_id`, `ticker`, `trigger_value`, `threshold_value`, `payload_json`)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                alert_id,
                owner_id,
                ticker,
                trigger_value,
                threshold_value,
                _json_dumps(payload or {}),
            ),
        )
        row = await self._fetchone(
            """
            SELECT *
            FROM `alert_trigger_logs`
            WHERE `id`=%s
            LIMIT 1
            """,
            (record_id,),
        )
        return _deserialize_alert_trigger_log(row)

    async def list_alert_trigger_logs(
        self,
        alert_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `alert_trigger_logs`
            WHERE `alert_id`=%s AND `owner_id`=%s
            ORDER BY `created_at` DESC, `id` DESC
            LIMIT %s
            """,
            (alert_id, owner_id, max(1, min(limit, 200))),
        )
        return [_deserialize_alert_trigger_log(row) for row in rows]

