from typing import Any, Dict, List, Optional
from database.helpers import *
from database.core import DEFAULT_OWNER_ID
# Import common serialization helpers here if needed

class NotificationMixin:
    async def create_notification(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_notification_payload(payload)
        notification_id = await self._execute_insert(
            """
            INSERT INTO `notifications`
                (`owner_id`, `category`, `level`, `title`, `message`,
                 `related_entity_type`, `related_entity_id`, `link_url`, `payload_json`, `read_at`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["category"],
                normalized["level"],
                normalized["title"],
                normalized["message"],
                normalized["related_entity_type"],
                normalized["related_entity_id"],
                normalized["link_url"],
                _json_dumps(normalized["payload"]),
                _parse_datetime_value(normalized.get("read_at")),
            ),
        )
        notification = await self.get_notification(notification_id, owner_id=owner_id)
        if not notification:
            raise RuntimeError("Notification was not persisted")
        return notification

    async def get_notification(
        self,
        notification_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `notifications`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (notification_id, owner_id),
        )
        return _deserialize_notification(row)

    async def list_notifications(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 200))
        filters = ["`owner_id`=%s"]
        params: List[Any] = [owner_id]
        if unread_only:
            filters.append("`read_at` IS NULL")

        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `notifications`
            WHERE {' AND '.join(filters)}
            ORDER BY `created_at` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_notification(row) for row in rows]

    async def mark_notification_read(
        self,
        notification_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        return await self.set_notification_read_state(notification_id, True, owner_id=owner_id)

    async def set_notification_read_state(
        self,
        notification_id: int,
        read: bool,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        updated = await self._execute(
            """
            UPDATE `notifications`
            SET `read_at`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                datetime.now(timezone.utc).replace(tzinfo=None) if read else None,
                notification_id,
                owner_id,
            ),
        )
        if not updated:
            return None
        return await self.get_notification(notification_id, owner_id=owner_id)

