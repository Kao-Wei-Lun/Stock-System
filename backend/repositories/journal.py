from typing import Any, Dict, List, Optional
from database.helpers import *
from database.core import DEFAULT_OWNER_ID
# Import common serialization helpers here if needed

class JournalMixin:
    async def list_trade_journal_entries(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        *,
        ticker: Optional[str] = None,
        market: Optional[str] = None,
        strategy_code: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 200))
        filters = ["e.`owner_id`=%s"]
        params: List[Any] = [owner_id]

        if ticker:
            filters.append("e.`ticker`=%s")
            params.append(ticker)
        if market:
            filters.append("e.`market`=%s")
            params.append(market)
        if strategy_code:
            filters.append("e.`strategy_code`=%s")
            params.append(strategy_code)
        if tag:
            filters.append(
                """
                EXISTS (
                    SELECT 1
                    FROM `trade_journal_tags` AS tjt
                    WHERE tjt.`entry_id` = e.`id` AND tjt.`tag`=%s
                )
                """.strip()
            )
            params.append(tag)
        if search:
            filters.append(
                """
                (
                    e.`ticker` LIKE %s OR
                    e.`entry_reason` LIKE %s OR
                    e.`exit_reason` LIKE %s OR
                    e.`review_notes` LIKE %s
                )
                """.strip()
            )
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern, pattern])

        rows = await self._fetchall(
            f"""
            SELECT e.*
            FROM `trade_journal_entries` AS e
            WHERE {' AND '.join(filters)}
            ORDER BY e.`entry_time` DESC, e.`id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return await self._hydrate_trade_journal_entries(rows)

    async def get_trade_journal_entry(
        self,
        entry_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `trade_journal_entries`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (entry_id, owner_id),
        )
        if not row:
            return None
        hydrated = await self._hydrate_trade_journal_entries([row])
        return hydrated[0] if hydrated else None

    async def create_trade_journal_entry(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_trade_journal_payload(payload)
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO `trade_journal_entries`
                            (`owner_id`, `ticker`, `market`, `direction`, `strategy_code`,
                             `entry_time`, `entry_price`, `exit_time`, `exit_price`, `size`,
                             `stop_loss`, `take_profit`, `entry_reason`, `exit_reason`,
                             `emotion_tag`, `review_notes`, `result_json`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            owner_id,
                            normalized["ticker"],
                            normalized["market"],
                            normalized["direction"],
                            normalized["strategy_code"],
                            _parse_datetime_value(normalized["entry_time"]),
                            normalized["entry_price"],
                            _parse_datetime_value(normalized.get("exit_time")),
                            normalized["exit_price"],
                            normalized["size"],
                            normalized["stop_loss"],
                            normalized["take_profit"],
                            normalized["entry_reason"],
                            normalized["exit_reason"],
                            normalized["emotion_tag"],
                            normalized["review_notes"],
                            _json_dumps(normalized["result"]),
                        ),
                    )
                    entry_id = cur.lastrowid
                await self._replace_trade_journal_children(conn, entry_id, normalized["tags"], normalized["attachments"])

        entry = await self.get_trade_journal_entry(entry_id, owner_id=owner_id)
        if not entry:
            raise RuntimeError("Trade journal entry was not persisted")
        return entry

    async def update_trade_journal_entry(
        self,
        entry_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_trade_journal_entry(entry_id, owner_id=owner_id)
        if not existing:
            return None

        normalized = _normalize_trade_journal_payload(payload, existing=existing)
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE `trade_journal_entries`
                        SET `ticker`=%s,
                            `market`=%s,
                            `direction`=%s,
                            `strategy_code`=%s,
                            `entry_time`=%s,
                            `entry_price`=%s,
                            `exit_time`=%s,
                            `exit_price`=%s,
                            `size`=%s,
                            `stop_loss`=%s,
                            `take_profit`=%s,
                            `entry_reason`=%s,
                            `exit_reason`=%s,
                            `emotion_tag`=%s,
                            `review_notes`=%s,
                            `result_json`=%s
                        WHERE `id`=%s AND `owner_id`=%s
                        """,
                        (
                            normalized["ticker"],
                            normalized["market"],
                            normalized["direction"],
                            normalized["strategy_code"],
                            _parse_datetime_value(normalized["entry_time"]),
                            normalized["entry_price"],
                            _parse_datetime_value(normalized.get("exit_time")),
                            normalized["exit_price"],
                            normalized["size"],
                            normalized["stop_loss"],
                            normalized["take_profit"],
                            normalized["entry_reason"],
                            normalized["exit_reason"],
                            normalized["emotion_tag"],
                            normalized["review_notes"],
                            _json_dumps(normalized["result"]),
                            entry_id,
                            owner_id,
                        ),
                    )
                await self._replace_trade_journal_children(conn, entry_id, normalized["tags"], normalized["attachments"])

        return await self.get_trade_journal_entry(entry_id, owner_id=owner_id)

    async def delete_trade_journal_entry(
        self,
        entry_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> bool:
        deleted = await self._execute(
            "DELETE FROM `trade_journal_entries` WHERE `id`=%s AND `owner_id`=%s",
            (entry_id, owner_id),
        )
        return deleted > 0

    async def get_trade_journal_stats(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        *,
        ticker: Optional[str] = None,
        market: Optional[str] = None,
        strategy_code: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        entries = await self.list_trade_journal_entries(
            owner_id=owner_id,
            ticker=ticker,
            market=market,
            strategy_code=strategy_code,
            tag=tag,
            search=search,
            limit=500,
        )
        return build_journal_stats(entries)

    async def list_journal_filter_presets(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `journal_filter_presets`
            WHERE `owner_id`=%s
            ORDER BY COALESCE(`last_used_at`, `updated_at`) DESC, `updated_at` DESC, `id` DESC
            """,
            (owner_id,),
        )
        return [_deserialize_journal_filter_preset(row) for row in rows]

    async def get_journal_filter_preset(
        self,
        preset_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `journal_filter_presets`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (preset_id, owner_id),
        )
        return _deserialize_journal_filter_preset(row)

    async def create_journal_filter_preset(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_journal_filter_preset_payload(payload)
        preset_id = await self._execute_insert(
            """
            INSERT INTO `journal_filter_presets` (`owner_id`, `name`, `description`, `scope`, `filters_json`)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["name"],
                normalized["description"],
                normalized["scope"],
                _json_dumps(normalized["filters"]),
            ),
        )
        preset = await self.get_journal_filter_preset(preset_id, owner_id=owner_id)
        if not preset:
            raise RuntimeError("Journal filter preset was not persisted")
        return preset

    async def update_journal_filter_preset(
        self,
        preset_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_journal_filter_preset(preset_id, owner_id=owner_id)
        if not existing:
            return None
        normalized = _normalize_journal_filter_preset_payload(payload, existing=existing)
        updated = await self._execute(
            """
            UPDATE `journal_filter_presets`
            SET `name`=%s, `description`=%s, `scope`=%s, `filters_json`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["name"],
                normalized["description"],
                normalized["scope"],
                _json_dumps(normalized["filters"]),
                preset_id,
                owner_id,
            ),
        )
        if not updated:
            return None
        return await self.get_journal_filter_preset(preset_id, owner_id=owner_id)

    async def delete_journal_filter_preset(
        self,
        preset_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> bool:
        deleted = await self._execute(
            "DELETE FROM `journal_filter_presets` WHERE `id`=%s AND `owner_id`=%s",
            (preset_id, owner_id),
        )
        return bool(deleted)

    async def mark_journal_filter_preset_used(
        self,
        preset_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        updated = await self._execute(
            """
            UPDATE `journal_filter_presets`
            SET `use_count`=`use_count` + 1, `last_used_at`=UTC_TIMESTAMP()
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (preset_id, owner_id),
        )
        if not updated:
            return None
        return await self.get_journal_filter_preset(preset_id, owner_id=owner_id)

    async def _replace_trade_journal_children(
        self,
        conn,
        entry_id: int,
        tags: List[str],
        attachments: List[Dict[str, Any]],
    ) -> None:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM `trade_journal_tags` WHERE `entry_id`=%s", (entry_id,))
            await cur.execute("DELETE FROM `trade_journal_attachments` WHERE `entry_id`=%s", (entry_id,))

            if tags:
                await cur.executemany(
                    """
                    INSERT INTO `trade_journal_tags` (`entry_id`, `tag`)
                    VALUES (%s, %s)
                    """,
                    [(entry_id, tag) for tag in tags],
                )

            if attachments:
                await cur.executemany(
                    """
                    INSERT INTO `trade_journal_attachments` (`entry_id`, `file_path`, `file_type`)
                    VALUES (%s, %s, %s)
                    """,
                    [
                        (
                            entry_id,
                            attachment["file_path"],
                            attachment.get("file_type"),
                        )
                        for attachment in attachments
                    ],
                )

    async def _hydrate_trade_journal_entries(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        entries = [_deserialize_trade_journal_entry(row) for row in rows]
        entries = [entry for entry in entries if entry]
        if not entries:
            return []

        entry_ids = [entry["id"] for entry in entries]
        placeholders = ", ".join(["%s"] * len(entry_ids))
        tag_rows = await self._fetchall(
            f"""
            SELECT `id`, `entry_id`, `tag`
            FROM `trade_journal_tags`
            WHERE `entry_id` IN ({placeholders})
            ORDER BY `tag` ASC, `id` ASC
            """,
            tuple(entry_ids),
        )
        attachment_rows = await self._fetchall(
            f"""
            SELECT `id`, `entry_id`, `file_path`, `file_type`, `created_at`
            FROM `trade_journal_attachments`
            WHERE `entry_id` IN ({placeholders})
            ORDER BY `created_at` ASC, `id` ASC
            """,
            tuple(entry_ids),
        )

        tags_by_entry: Dict[int, List[str]] = {}
        for row in tag_rows:
            tags_by_entry.setdefault(row["entry_id"], []).append(row["tag"])

        attachments_by_entry: Dict[int, List[Dict[str, Any]]] = {}
        for row in attachment_rows:
            attachments_by_entry.setdefault(row["entry_id"], []).append(
                {
                    "id": row["id"],
                    "file_path": row["file_path"],
                    "file_type": row.get("file_type"),
                    "created_at": _datetime_to_iso(row.get("created_at")),
                }
            )

        for entry in entries:
            entry["tags"] = tags_by_entry.get(entry["id"], [])
            entry["attachments"] = attachments_by_entry.get(entry["id"], [])
        return entries

