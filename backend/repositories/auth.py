from typing import Any, Dict

from database.helpers import _serialize_user_profile
from database.core import (
    DEFAULT_OWNER_DISPLAY_NAME,
    DEFAULT_OWNER_ID,
    DEFAULT_OWNER_TIMEZONE,
    DEFAULT_OWNER_USERNAME,
)
# Import common serialization helpers here if needed

class AuthMixin:
    async def ensure_default_owner(self) -> Dict[str, Any]:
        sql = """
            INSERT INTO `user_profiles`
                (`id`, `username`, `display_name`, `timezone`, `is_active`)
            VALUES (%s, %s, %s, %s, 1)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `display_name` = `incoming`.`display_name`,
                `timezone` = `incoming`.`timezone`,
                `is_active` = 1
        """
        await self._execute(
            sql,
            (
                DEFAULT_OWNER_ID,
                DEFAULT_OWNER_USERNAME,
                DEFAULT_OWNER_DISPLAY_NAME,
                DEFAULT_OWNER_TIMEZONE,
            ),
        )
        owner = await self._fetchone(
            """
            SELECT `id`, `username`, `display_name`, `timezone`, `is_active`, `created_at`, `updated_at`
            FROM `user_profiles`
            WHERE `id`=%s
            """,
            (DEFAULT_OWNER_ID,),
        )
        return _serialize_user_profile(owner)

