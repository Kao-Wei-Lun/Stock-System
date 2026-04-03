from typing import Any, Dict, List, Optional
from database.helpers import *
from database.core import DEFAULT_OWNER_ID
# Import common serialization helpers here if needed

class WatchlistMixin:
    async def ensure_default_watchlist(self, tickers: List[str], group_name: str = "我的自選") -> None:
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT COUNT(*) AS `c` FROM `watchlist_groups`")
                    existing = (await cur.fetchone())["c"]
                    if existing:
                        return

                    await cur.execute(
                        """
                        INSERT INTO `watchlist_groups` (`name`, `sort_order`)
                        VALUES (%s, %s)
                        """,
                        (group_name, 0),
                    )
                    group_id = cur.lastrowid

                    for sort_order, ticker in enumerate(tickers):
                        await cur.execute(
                            """
                            INSERT INTO `watchlist_items` (`group_id`, `ticker`, `sort_order`)
                            VALUES (%s, %s, %s)
                            """,
                            (group_id, ticker, sort_order),
                        )

    async def ensure_watchlist_group_items(
        self,
        group_name: str,
        tickers: List[str],
        sort_order: int = 0,
    ) -> Optional[Dict]:
        clean_name = (group_name or "").strip()
        clean_tickers = list(dict.fromkeys((ticker or "").strip() for ticker in tickers if (ticker or "").strip()))
        if not clean_name or not clean_tickers:
            return None

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`, `name`, `sort_order`, `created_at`
                        FROM `watchlist_groups`
                        WHERE `name`=%s
                        LIMIT 1
                        """,
                        (clean_name,),
                    )
                    group = await cur.fetchone()

                async with conn.cursor() as cur:
                    if group:
                        group_id = group["id"]
                        await cur.execute(
                            """
                            UPDATE `watchlist_groups`
                            SET `sort_order`=%s
                            WHERE `id`=%s
                            """,
                            (sort_order, group_id),
                        )
                    else:
                        await cur.execute(
                            """
                            INSERT INTO `watchlist_groups` (`name`, `sort_order`)
                            VALUES (%s, %s)
                            """,
                            (clean_name, sort_order),
                        )
                        group_id = cur.lastrowid

                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`, `ticker`
                        FROM `watchlist_items`
                        WHERE `group_id`=%s
                        ORDER BY `sort_order` ASC, `id` ASC
                        """,
                        (group_id,),
                    )
                    existing_items = list(await cur.fetchall())

                existing_by_ticker = {row["ticker"]: row for row in existing_items}
                expected_set = set(clean_tickers)

                async with conn.cursor() as cur:
                    for index, ticker in enumerate(clean_tickers):
                        existing = existing_by_ticker.get(ticker)
                        if existing:
                            await cur.execute(
                                """
                                UPDATE `watchlist_items`
                                SET `sort_order`=%s
                                WHERE `id`=%s
                                """,
                                (index, existing["id"]),
                            )
                        else:
                            await cur.execute(
                                """
                                INSERT INTO `watchlist_items` (`group_id`, `ticker`, `sort_order`)
                                VALUES (%s, %s, %s)
                                """,
                                (group_id, ticker, index),
                            )

                    stale_ids = [row["id"] for row in existing_items if row["ticker"] not in expected_set]
                    if stale_ids:
                        await cur.executemany(
                            "DELETE FROM `watchlist_items` WHERE `id`=%s",
                            [(item_id,) for item_id in stale_ids],
                        )

        return await self.get_watchlist_group(group_id)

    async def get_watchlist_group(self, group_id: int) -> Optional[Dict]:
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT `id`, `name`, `sort_order`, `created_at`
                    FROM `watchlist_groups`
                    WHERE `id`=%s
                    """,
                    (group_id,),
                )
                return await cur.fetchone()

    async def get_watchlist_groups(self) -> List[Dict]:
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT `id`, `name`, `sort_order`, `created_at`
                    FROM `watchlist_groups`
                    ORDER BY `sort_order` ASC, `id` ASC
                    """
                )
                groups = list(await cur.fetchall())

                await cur.execute(
                    """
                    SELECT `id`, `group_id`, `ticker`, `tags_json`, `sort_order`, `created_at`
                    FROM `watchlist_items`
                    ORDER BY `group_id` ASC, `sort_order` ASC, `id` ASC
                    """
                )
                items = [_deserialize_watchlist_item(row) for row in await cur.fetchall()]

        grouped_items: Dict[int, List[Dict]] = {}
        for item in items:
            grouped_items.setdefault(item["group_id"], []).append(item)

        return [
            {
                **group,
                "items": grouped_items.get(group["id"], []),
            }
            for group in groups
        ]

    async def create_watchlist_group(self, name: str) -> Dict:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Group name is required")

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`
                        FROM `watchlist_groups`
                        WHERE `name`=%s
                        LIMIT 1
                        """,
                        (clean_name,),
                    )
                    duplicate = await cur.fetchone()
                    if duplicate:
                        raise ValueError("Group name already exists")

                    await cur.execute("SELECT COALESCE(MAX(`sort_order`), -1) + 1 AS `next_sort` FROM `watchlist_groups`")
                    next_sort = (await cur.fetchone())["next_sort"]

                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO `watchlist_groups` (`name`, `sort_order`)
                        VALUES (%s, %s)
                        """,
                        (clean_name, next_sort),
                    )
                    group_id = cur.lastrowid

        group = await self.get_watchlist_group(group_id)
        return group or {"id": group_id, "name": clean_name, "sort_order": next_sort, "items": []}

    async def rename_watchlist_group(self, group_id: int, name: str) -> Optional[Dict]:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Group name is required")

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`
                        FROM `watchlist_groups`
                        WHERE `name`=%s AND `id`<>%s
                        LIMIT 1
                        """,
                        (clean_name, group_id),
                    )
                    duplicate = await cur.fetchone()
                    if duplicate:
                        raise ValueError("Group name already exists")

                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE `watchlist_groups`
                        SET `name`=%s
                        WHERE `id`=%s
                        """,
                        (clean_name, group_id),
                    )
                    if cur.rowcount == 0:
                        return None

        return await self.get_watchlist_group(group_id)

    async def delete_watchlist_group(self, group_id: int) -> bool:
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("DELETE FROM `watchlist_groups` WHERE `id`=%s", (group_id,))
                    return cur.rowcount > 0

    async def add_watchlist_item(self, group_id: int, ticker: str, tags: Optional[List[str]] = None) -> Dict:
        normalized_tags = _normalize_watchlist_tags(tags)
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`
                        FROM `watchlist_items`
                        WHERE `group_id`=%s AND `ticker`=%s
                        LIMIT 1
                        """,
                        (group_id, ticker),
                    )
                    duplicate = await cur.fetchone()
                    if duplicate:
                        raise ValueError("Ticker already exists in this group")

                    await cur.execute(
                        "SELECT COALESCE(MAX(`sort_order`), -1) + 1 AS `next_sort` FROM `watchlist_items` WHERE `group_id`=%s",
                        (group_id,),
                    )
                    next_sort = (await cur.fetchone())["next_sort"]

                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO `watchlist_items` (`group_id`, `ticker`, `tags_json`, `sort_order`)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (group_id, ticker, _json_dumps(normalized_tags), next_sort),
                    )
                    item_id = cur.lastrowid

                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`, `group_id`, `ticker`, `tags_json`, `sort_order`, `created_at`
                        FROM `watchlist_items`
                        WHERE `id`=%s
                        """,
                        (item_id,),
                    )
                    return _deserialize_watchlist_item(await cur.fetchone())

    async def delete_watchlist_item(self, item_id: int) -> bool:
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("DELETE FROM `watchlist_items` WHERE `id`=%s", (item_id,))
                    return cur.rowcount > 0

    async def reorder_watchlist_items(self, group_id: int, item_ids: List[int]) -> bool:
        if not item_ids:
            return False

        unique_ids = list(dict.fromkeys(item_ids))
        if len(unique_ids) != len(item_ids):
            raise ValueError("Duplicate item ids are not allowed")

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`
                        FROM `watchlist_items`
                        WHERE `group_id`=%s
                        ORDER BY `sort_order` ASC, `id` ASC
                        """,
                        (group_id,),
                    )
                    rows = await cur.fetchall()
                    existing_ids = [row["id"] for row in rows]

                if not existing_ids:
                    return False

                if set(existing_ids) != set(unique_ids):
                    raise ValueError("Item ids do not match the selected group")

                async with conn.cursor() as cur:
                    await cur.executemany(
                        """
                        UPDATE `watchlist_items`
                        SET `sort_order`=%s
                        WHERE `id`=%s AND `group_id`=%s
                        """,
                        [
                            (sort_order, item_id, group_id)
                            for sort_order, item_id in enumerate(unique_ids)
                        ],
                    )

        return True

    async def search_tickers(self, q: str) -> List[Dict]:
        pattern = f"%{q}%"
        sql = """
            SELECT `ticker`, `name`
            FROM `stock_info`
            WHERE `ticker` LIKE %s OR `name` LIKE %s
            LIMIT 20
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (pattern, pattern))
                rows = await cur.fetchall()
        return list(rows)

