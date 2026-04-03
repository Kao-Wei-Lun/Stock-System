from typing import Any, Dict, List, Optional
from database.helpers import *
from database.core import DEFAULT_OWNER_ID
# Import common serialization helpers here if needed

class WorkspaceMixin:
    async def list_workspace_presets(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `workspace_presets`
            WHERE `owner_id`=%s
            ORDER BY `updated_at` DESC, `id` DESC
            """,
            (owner_id,),
        )
        return [_deserialize_workspace_preset(row) for row in rows]

    async def get_workspace_preset(
        self,
        workspace_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `workspace_presets`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (workspace_id, owner_id),
        )
        return _deserialize_workspace_preset(row)

    async def create_workspace_preset(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_workspace_payload(payload)
        if normalized["is_default"]:
            await self._execute(
                "UPDATE `workspace_presets` SET `is_default`=0 WHERE `owner_id`=%s",
                (owner_id,),
            )

        workspace_id = await self._execute_insert(
            """
            INSERT INTO `workspace_presets`
                (`owner_id`, `name`, `chart_layout`, `active_ticker`, `current_period`,
                 `current_interval`, `workspace_tab`, `comparison_mode`, `payload_json`, `is_default`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["name"],
                normalized["chart_layout"],
                normalized["active_ticker"],
                normalized["current_period"],
                normalized["current_interval"],
                normalized["workspace_tab"],
                normalized["comparison_mode"],
                _json_dumps(normalized["payload"]),
                1 if normalized["is_default"] else 0,
            ),
        )
        workspace = await self.get_workspace_preset(workspace_id, owner_id=owner_id)
        if not workspace:
            raise RuntimeError("Workspace preset was not persisted")
        return workspace

    async def update_workspace_preset(
        self,
        workspace_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_workspace_preset(workspace_id, owner_id=owner_id)
        if not existing:
            return None

        normalized = _normalize_workspace_payload(payload, existing=existing)
        if normalized["is_default"]:
            await self._execute(
                "UPDATE `workspace_presets` SET `is_default`=0 WHERE `owner_id`=%s AND `id`<>%s",
                (owner_id, workspace_id),
            )

        await self._execute(
            """
            UPDATE `workspace_presets`
            SET `name`=%s,
                `chart_layout`=%s,
                `active_ticker`=%s,
                `current_period`=%s,
                `current_interval`=%s,
                `workspace_tab`=%s,
                `comparison_mode`=%s,
                `payload_json`=%s,
                `is_default`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["name"],
                normalized["chart_layout"],
                normalized["active_ticker"],
                normalized["current_period"],
                normalized["current_interval"],
                normalized["workspace_tab"],
                normalized["comparison_mode"],
                _json_dumps(normalized["payload"]),
                1 if normalized["is_default"] else 0,
                workspace_id,
                owner_id,
            ),
        )
        return await self.get_workspace_preset(workspace_id, owner_id=owner_id)

    async def delete_workspace_preset(
        self,
        workspace_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> bool:
        deleted = await self._execute(
            "DELETE FROM `workspace_presets` WHERE `id`=%s AND `owner_id`=%s",
            (workspace_id, owner_id),
        )
        return deleted > 0

