from typing import Any, Dict, List, Optional
from database.helpers import *
from database.core import DEFAULT_OWNER_ID
# Import common serialization helpers here if needed

class IntelligenceMixin:
    async def connect(self):
        try:
            server_pool = await aiomysql.create_pool(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                charset=MYSQL_CHARSET,
                autocommit=True,
                minsize=1,
                maxsize=5,
            )
        except OperationalError as exc:
            raise RuntimeError(_build_mysql_error_message(exc)) from exc
        except Exception as exc:
            raise RuntimeError(_build_mysql_connection_error_message(exc)) from exc
        try:
            async with server_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `SCHEMA_NAME` AS `schema_name`
                        FROM `INFORMATION_SCHEMA`.`SCHEMATA`
                        WHERE `SCHEMA_NAME`=%s
                        """,
                        (MYSQL_DATABASE,),
                    )
                    database_exists = await cur.fetchone()
                    if not database_exists:
                        await cur.execute(
                            f"CREATE DATABASE `{_escape_identifier(MYSQL_DATABASE)}` "
                            f"CHARACTER SET {MYSQL_CHARSET} COLLATE {MYSQL_CHARSET}_unicode_ci"
                        )
        finally:
            server_pool.close()
            await server_pool.wait_closed()

        try:
            self._pool = await aiomysql.create_pool(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                db=MYSQL_DATABASE,
                charset=MYSQL_CHARSET,
                autocommit=True,
                minsize=1,
                maxsize=10,
            )
        except OperationalError as exc:
            raise RuntimeError(_build_mysql_error_message(exc)) from exc
        except Exception as exc:
            raise RuntimeError(_build_mysql_connection_error_message(exc)) from exc

    async def close(self):
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()

    async def create_tables(self):
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT `TABLE_NAME` AS `table_name`
                    FROM `INFORMATION_SCHEMA`.`TABLES`
                    WHERE `TABLE_SCHEMA`=%s
                    """,
                    (MYSQL_DATABASE,),
                )
                existing_tables: Set[str] = {row["table_name"] for row in await cur.fetchall()}
                await cur.execute(
                    """
                    SELECT `TABLE_NAME` AS `table_name`, `COLUMN_NAME` AS `column_name`
                    FROM `INFORMATION_SCHEMA`.`COLUMNS`
                    WHERE `TABLE_SCHEMA`=%s
                    """,
                    (MYSQL_DATABASE,),
                )
                existing_columns: Dict[str, Set[str]] = {}
                for row in await cur.fetchall():
                    existing_columns.setdefault(row["table_name"], set()).add(row["column_name"])
            async with conn.cursor() as cur:
                for statement in build_schema_plan(existing_tables, existing_columns):
                    await cur.execute(statement)
        await self.ensure_default_owner()

    async def list_active_alerts(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `alerts`
            WHERE `owner_id`=%s AND `active`=1
            ORDER BY `updated_at` ASC, `id` ASC
            """,
            (owner_id,),
        )
        return [_deserialize_alert(row) for row in rows]

    async def upsert_market_events(self, events: List[Dict[str, Any]]) -> int:
        if not events:
            return 0
        normalized_events = [_normalize_market_event_payload(item) for item in events]
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        """
                        INSERT INTO `market_events`
                            (`event_type`, `market`, `ticker`, `title`, `description`,
                             `event_date`, `event_time`, `importance`, `source`, `url`, `payload_json`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        AS `incoming`
                        ON DUPLICATE KEY UPDATE
                            `market`=`incoming`.`market`,
                            `description`=`incoming`.`description`,
                            `event_time`=`incoming`.`event_time`,
                            `importance`=`incoming`.`importance`,
                            `source`=`incoming`.`source`,
                            `url`=`incoming`.`url`,
                            `payload_json`=`incoming`.`payload_json`
                        """,
                        [
                            (
                                item["event_type"],
                                item["market"],
                                item["ticker"],
                                item["title"],
                                item["description"],
                                item["event_date"],
                                _parse_datetime_value(item.get("event_time")),
                                item["importance"],
                                item["source"],
                                item["url"],
                                _json_dumps(item.get("payload") or {}),
                            )
                            for item in normalized_events
                        ],
                    )
        return len(normalized_events)

    async def list_market_events(
        self,
        *,
        ticker: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 500))
        filters = ["1=1"]
        params: List[Any] = []
        if ticker:
            filters.append("`ticker`=%s")
            params.append(ticker)
        if date_from:
            filters.append("`event_date`>=%s")
            params.append(date_from)
        if date_to:
            filters.append("`event_date`<=%s")
            params.append(date_to)
        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `market_events`
            WHERE {' AND '.join(filters)}
            ORDER BY `event_date` ASC, `event_time` ASC, `id` ASC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_market_event(item) for item in rows]

    async def upsert_news_articles(self, articles: List[Dict[str, Any]]) -> int:
        if not articles:
            return 0
        normalized_articles = [_normalize_news_article_payload(item) for item in articles]
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        """
                        INSERT INTO `news_articles`
                            (`ticker`, `market`, `title`, `summary`, `published_at`, `source`, `url`, `sentiment`, `payload_json`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        AS `incoming`
                        ON DUPLICATE KEY UPDATE
                            `market`=`incoming`.`market`,
                            `summary`=`incoming`.`summary`,
                            `source`=`incoming`.`source`,
                            `url`=`incoming`.`url`,
                            `sentiment`=`incoming`.`sentiment`,
                            `payload_json`=`incoming`.`payload_json`
                        """,
                        [
                            (
                                item["ticker"],
                                item["market"],
                                item["title"],
                                item["summary"],
                                _parse_datetime_value(item["published_at"]),
                                item["source"],
                                item["url"],
                                item["sentiment"],
                                _json_dumps(item.get("payload") or {}),
                            )
                            for item in normalized_articles
                        ],
                    )
        return len(normalized_articles)

    async def list_news_articles(
        self,
        *,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 200))
        filters = ["1=1"]
        params: List[Any] = []
        if ticker:
            filters.append("`ticker`=%s")
            params.append(ticker)
        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `news_articles`
            WHERE {' AND '.join(filters)}
            ORDER BY `published_at` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_news_article(item) for item in rows]

    async def upsert_macro_snapshots(self, snapshots: List[Dict[str, Any]]) -> int:
        if not snapshots:
            return 0
        normalized_snapshots = [_normalize_macro_snapshot_payload(item) for item in snapshots]
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        """
                        INSERT INTO `macro_snapshots`
                            (`metric_code`, `metric_name`, `value`, `snapshot_date`, `source`, `payload_json`)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        AS `incoming`
                        ON DUPLICATE KEY UPDATE
                            `metric_name`=`incoming`.`metric_name`,
                            `value`=`incoming`.`value`,
                            `source`=`incoming`.`source`,
                            `payload_json`=`incoming`.`payload_json`
                        """,
                        [
                            (
                                item["metric_code"],
                                item["metric_name"],
                                item["value"],
                                item["snapshot_date"],
                                item["source"],
                                _json_dumps(item.get("payload") or {}),
                            )
                            for item in normalized_snapshots
                        ],
                    )
        return len(normalized_snapshots)

    async def list_macro_snapshots(
        self,
        snapshot_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if snapshot_date:
            rows = await self._fetchall(
                """
                SELECT *
                FROM `macro_snapshots`
                WHERE `snapshot_date`=%s
                ORDER BY `metric_code` ASC
                """,
                (snapshot_date,),
            )
        else:
            row = await self._fetchone(
                """
                SELECT MAX(`snapshot_date`) AS `snapshot_date`
                FROM `macro_snapshots`
                """
            )
            latest_date = row.get("snapshot_date") if row else None
            if not latest_date:
                return []
            rows = await self._fetchall(
                """
                SELECT *
                FROM `macro_snapshots`
                WHERE `snapshot_date`=%s
                ORDER BY `metric_code` ASC
                """,
                (_date_to_iso(latest_date),),
            )
        return [_deserialize_macro_snapshot(item) for item in rows]

    async def list_screener_presets(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `screener_presets`
            WHERE `owner_id`=%s
            ORDER BY `updated_at` DESC, `id` DESC
            """,
            (owner_id,),
        )
        return [_deserialize_screener_preset(row) for row in rows]

    async def get_screener_preset(
        self,
        preset_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `screener_presets`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (preset_id, owner_id),
        )
        return _deserialize_screener_preset(row)

    async def create_screener_preset(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_screener_preset_payload(payload)
        preset_id = await self._execute_insert(
            """
            INSERT INTO `screener_presets` (`owner_id`, `name`, `description`, `filters_json`)
            VALUES (%s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["name"],
                normalized["description"],
                _json_dumps(normalized["filters"]),
            ),
        )
        preset = await self.get_screener_preset(preset_id, owner_id=owner_id)
        if not preset:
            raise RuntimeError("Screener preset was not persisted")
        return preset

    async def update_screener_preset(
        self,
        preset_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_screener_preset(preset_id, owner_id=owner_id)
        if not existing:
            return None
        normalized = _normalize_screener_preset_payload(payload, existing=existing)
        updated = await self._execute(
            """
            UPDATE `screener_presets`
            SET `name`=%s, `description`=%s, `filters_json`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["name"],
                normalized["description"],
                _json_dumps(normalized["filters"]),
                preset_id,
                owner_id,
            ),
        )
        if not updated:
            return None
        return await self.get_screener_preset(preset_id, owner_id=owner_id)

    async def delete_screener_preset(
        self,
        preset_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> bool:
        deleted = await self._execute(
            "DELETE FROM `screener_presets` WHERE `id`=%s AND `owner_id`=%s",
            (preset_id, owner_id),
        )
        return bool(deleted)

