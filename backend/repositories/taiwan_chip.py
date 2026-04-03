from typing import Any, Dict, List, Optional
from database.helpers import *
from database.core import DEFAULT_OWNER_ID
# Import common serialization helpers here if needed

class TaiwanChipMixin:
    async def upsert_taiwan_chip_snapshots(self, snapshots: List[Dict[str, Any]]) -> int:
        if not snapshots:
            return 0
        normalized_snapshots = [_normalize_taiwan_chip_snapshot_payload(item) for item in snapshots]
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        """
                        INSERT INTO `taiwan_chip_snapshots`
                            (`ticker`, `market`, `snapshot_date`, `margin_balance`, `short_balance`,
                             `securities_lending_balance`, `institutional_net_buy_sell`, `source`,
                             `branch_payload_json`, `summary_json`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        AS `incoming`
                        ON DUPLICATE KEY UPDATE
                            `market`=`incoming`.`market`,
                            `margin_balance`=`incoming`.`margin_balance`,
                            `short_balance`=`incoming`.`short_balance`,
                            `securities_lending_balance`=`incoming`.`securities_lending_balance`,
                            `institutional_net_buy_sell`=`incoming`.`institutional_net_buy_sell`,
                            `source`=`incoming`.`source`,
                            `branch_payload_json`=`incoming`.`branch_payload_json`,
                            `summary_json`=`incoming`.`summary_json`
                        """,
                        [
                            (
                                item["ticker"],
                                item["market"],
                                item["snapshot_date"],
                                item["margin_balance"],
                                item["short_balance"],
                                item["securities_lending_balance"],
                                item["institutional_net_buy_sell"],
                                item["source"],
                                _json_dumps(item.get("branch_payload") or {}),
                                _json_dumps(item.get("summary") or {}),
                            )
                            for item in normalized_snapshots
                        ],
                    )
        return len(normalized_snapshots)

    async def get_taiwan_chip_snapshot(
        self,
        ticker: str,
        snapshot_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if snapshot_date:
            row = await self._fetchone(
                """
                SELECT *
                FROM `taiwan_chip_snapshots`
                WHERE `ticker`=%s AND `snapshot_date`=%s
                LIMIT 1
                """,
                (ticker, snapshot_date),
            )
        else:
            row = await self._fetchone(
                """
                SELECT *
                FROM `taiwan_chip_snapshots`
                WHERE `ticker`=%s
                ORDER BY `snapshot_date` DESC, `id` DESC
                LIMIT 1
                """,
                (ticker,),
            )
        return _deserialize_taiwan_chip_snapshot(row)

    async def list_taiwan_chip_snapshots(
        self,
        ticker: Optional[str] = None,
        limit: int = 30,
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
            FROM `taiwan_chip_snapshots`
            WHERE {' AND '.join(filters)}
            ORDER BY `snapshot_date` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_taiwan_chip_snapshot(item) for item in rows]

    async def upsert_institutional_snapshot(self, payload: Dict[str, Any]) -> None:
        resolved_date = payload.get("resolved_date")
        query_date = payload.get("query_date") or resolved_date
        if not resolved_date or not query_date:
            raise ValueError("Institutional snapshot requires query_date and resolved_date")

        sql = """
            INSERT INTO `institutional_snapshots`
                (`resolved_date`, `query_date`, `payload_json`)
            VALUES (%s, %s, %s)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `query_date` = `incoming`.`query_date`,
                `payload_json` = `incoming`.`payload_json`
        """
        params = (
            resolved_date,
            query_date,
            json.dumps(payload, ensure_ascii=False),
        )

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)

    async def get_institutional_snapshot(self, target_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        if target_date:
            sql = """
                SELECT `resolved_date`, `query_date`, `payload_json`
                FROM `institutional_snapshots`
                WHERE `resolved_date`<=%s
                ORDER BY `resolved_date` DESC
                LIMIT 1
            """
            params = (target_date.isoformat(),)
        else:
            sql = """
                SELECT `resolved_date`, `query_date`, `payload_json`
                FROM `institutional_snapshots`
                ORDER BY `resolved_date` DESC
                LIMIT 1
            """
            params = ()

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                row = await cur.fetchone()
        return self._deserialize_institutional_snapshot(row)

    async def get_institutional_snapshot_exact(self, target_date: date) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT `resolved_date`, `query_date`, `payload_json`
            FROM `institutional_snapshots`
            WHERE `resolved_date`=%s
            LIMIT 1
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (target_date.isoformat(),))
                row = await cur.fetchone()
        return self._deserialize_institutional_snapshot(row)

    async def get_institutional_snapshots(self, target_date: date, limit: int) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []

        sql = """
            SELECT `resolved_date`, `query_date`, `payload_json`
            FROM `institutional_snapshots`
            WHERE `resolved_date`<=%s
            ORDER BY `resolved_date` DESC
            LIMIT %s
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (target_date.isoformat(), limit))
                rows = await cur.fetchall()

        snapshots = [
            snapshot
            for snapshot in (
                self._deserialize_institutional_snapshot(row)
                for row in rows
            )
            if snapshot
        ]
        snapshots.reverse()
        return snapshots

