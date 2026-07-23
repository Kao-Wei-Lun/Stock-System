from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


class StorageLifecycleMixin:
    async def record_storage_maintenance_run(
        self,
        *,
        action: str,
        source_table: str | None,
        cutoff_date: str | date | None,
        status: str,
        is_dry_run: bool,
        backup_id: str | None = None,
        batch_size: int = 0,
        processed_rows: int = 0,
        archived_rows: int = 0,
        cleaned_rows: int = 0,
        cursor: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        last_error: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> int:
        sql = """
            INSERT INTO `storage_maintenance_runs`
                (`action`, `source_table`, `cutoff_date`, `status`, `is_dry_run`,
                 `backup_id`, `batch_size`, `processed_rows`, `archived_rows`,
                 `cleaned_rows`, `cursor_json`, `result_json`, `last_error`,
                 `started_at`, `completed_at`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        sql,
                        (
                            action,
                            source_table,
                            cutoff_date,
                            status,
                            1 if is_dry_run else 0,
                            backup_id,
                            max(0, int(batch_size)),
                            max(0, int(processed_rows)),
                            max(0, int(archived_rows)),
                            max(0, int(cleaned_rows)),
                            json.dumps(cursor or {}, ensure_ascii=False),
                            json.dumps(result or {}, ensure_ascii=False),
                            str(last_error or "")[:2000] or None,
                            started_at or datetime.now(),
                            completed_at,
                        ),
                    )
                    return int(cur.lastrowid or 0)

    async def has_completed_storage_dry_run(
        self,
        *,
        action: str,
        source_table: str,
        cutoff_date: str | date,
    ) -> bool:
        row = await self._fetchone(
            """
            SELECT `id`
            FROM `storage_maintenance_runs`
            WHERE `action`=%s
              AND `source_table`=%s
              AND `cutoff_date`=%s
              AND `is_dry_run`=1
              AND `status`='completed'
            ORDER BY `completed_at` DESC, `id` DESC
            LIMIT 1
            """,
            (action, source_table, cutoff_date),
        )
        return bool(row)

    async def has_storage_maintenance_execution(
        self,
        *,
        action: str,
        source_table: str,
        cutoff_date: str | date,
    ) -> bool:
        row = await self._fetchone(
            """
            SELECT `id`
            FROM `storage_maintenance_runs`
            WHERE `action`=%s
              AND `source_table`=%s
              AND `cutoff_date`=%s
              AND `is_dry_run`=0
              AND `status` IN ('partial', 'completed')
            ORDER BY `id` DESC
            LIMIT 1
            """,
            (action, source_table, cutoff_date),
        )
        return bool(row)

    async def get_next_chip_branch_archive_group(
        self,
        *,
        cutoff_date: str | date,
    ) -> dict[str, Any] | None:
        candidate = await self._fetchone(
            """
            SELECT
                s.`snapshot_date`,
                COALESCE(s.`source`, '') AS `source`
            FROM `taiwan_chip_snapshots` AS s
                FORCE INDEX (`idx_taiwan_chip_snapshots_snapshot_date_source`)
            WHERE s.`snapshot_date` < %s
              AND s.`branch_payload_json` IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM `taiwan_chip_branch_archives` AS a
                  WHERE a.`snapshot_date`=s.`snapshot_date`
                    AND a.`source`=COALESCE(s.`source`, '')
                    AND a.`status` IN ('archived', 'cleaned')
              )
            ORDER BY s.`snapshot_date`, s.`source`, s.`id`
            LIMIT 1
            """,
            (cutoff_date,),
        )
        if not candidate:
            return None
        counts = await self._fetchone(
            """
            SELECT
                COUNT(*) AS `source_row_count`,
                MIN(`id`) AS `min_source_id`,
                MAX(`id`) AS `max_source_id`
            FROM `taiwan_chip_snapshots`
            WHERE `snapshot_date`=%s
              AND COALESCE(`source`, '')=%s
              AND `branch_payload_json` IS NOT NULL
            """,
            (candidate["snapshot_date"], candidate.get("source") or ""),
        )
        return {**candidate, **dict(counts or {})}

    async def list_chip_branch_payload_rows(
        self,
        *,
        snapshot_date: str | date,
        source: str,
    ) -> list[dict[str, Any]]:
        return await self._fetchall(
            """
            SELECT `id`, `ticker`, `branch_payload_json`
            FROM `taiwan_chip_snapshots`
            WHERE `snapshot_date`=%s
              AND COALESCE(`source`, '')=%s
              AND `branch_payload_json` IS NOT NULL
            ORDER BY `id`
            """,
            (snapshot_date, source),
        )

    async def upsert_chip_branch_archive(
        self,
        *,
        snapshot_date: str | date,
        source: str,
        archive_format: str,
        payload_blob: bytes,
        payload_sha256: str,
        source_row_count: int,
        original_size_bytes: int,
        compressed_size_bytes: int,
        min_source_id: int | None,
        max_source_id: int | None,
        backup_id: str,
        archived_at: datetime,
        cleanup_eligible_at: datetime,
    ) -> int:
        await self._execute(
            """
            INSERT INTO `taiwan_chip_branch_archives`
                (`snapshot_date`, `source`, `archive_format`, `payload_blob`,
                 `payload_sha256`, `source_row_count`, `original_size_bytes`,
                 `compressed_size_bytes`, `min_source_id`, `max_source_id`,
                 `backup_id`, `status`, `archived_at`, `cleanup_eligible_at`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'archived', %s, %s)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `archive_format`=`incoming`.`archive_format`,
                `payload_blob`=`incoming`.`payload_blob`,
                `payload_sha256`=`incoming`.`payload_sha256`,
                `source_row_count`=`incoming`.`source_row_count`,
                `original_size_bytes`=`incoming`.`original_size_bytes`,
                `compressed_size_bytes`=`incoming`.`compressed_size_bytes`,
                `min_source_id`=`incoming`.`min_source_id`,
                `max_source_id`=`incoming`.`max_source_id`,
                `backup_id`=`incoming`.`backup_id`,
                `status`='archived',
                `archived_at`=`incoming`.`archived_at`,
                `cleanup_eligible_at`=`incoming`.`cleanup_eligible_at`,
                `cleaned_at`=NULL
            """,
            (
                snapshot_date,
                source,
                archive_format,
                payload_blob,
                payload_sha256,
                source_row_count,
                original_size_bytes,
                compressed_size_bytes,
                min_source_id,
                max_source_id,
                backup_id,
                archived_at,
                cleanup_eligible_at,
            ),
        )
        row = await self._fetchone(
            """
            SELECT `id`
            FROM `taiwan_chip_branch_archives`
            WHERE `snapshot_date`=%s AND `source`=%s
            """,
            (snapshot_date, source),
        )
        return int((row or {}).get("id") or 0)

    async def get_chip_branch_archive(
        self,
        *,
        snapshot_date: str | date,
        source: str,
    ) -> dict[str, Any] | None:
        return await self._fetchone(
            """
            SELECT *
            FROM `taiwan_chip_branch_archives`
            WHERE `snapshot_date`=%s
              AND `source`=%s
              AND `status` IN ('archived', 'cleaned')
            LIMIT 1
            """,
            (snapshot_date, source),
        )

    async def get_next_chip_branch_cleanup_candidate(
        self,
        *,
        now: datetime,
    ) -> dict[str, Any] | None:
        return await self._fetchone(
            """
            SELECT *
            FROM `taiwan_chip_branch_archives`
            WHERE `status`='archived'
              AND `cleanup_eligible_at`<=%s
            ORDER BY `snapshot_date`, `source`, `id`
            LIMIT 1
            """,
            (now,),
        )

    async def clear_online_chip_branch_payload(
        self,
        *,
        archive_id: int,
        snapshot_date: str | date,
        source: str,
        cleaned_at: datetime,
    ) -> int:
        cleaned_rows = await self._execute(
            """
            UPDATE `taiwan_chip_snapshots`
            SET `branch_payload_json`=NULL
            WHERE `snapshot_date`=%s
              AND COALESCE(`source`, '')=%s
              AND `branch_payload_json` IS NOT NULL
            """,
            (snapshot_date, source),
        )
        await self._execute(
            """
            UPDATE `taiwan_chip_branch_archives`
            SET `status`='cleaned', `cleaned_at`=%s
            WHERE `id`=%s AND `status`='archived'
            """,
            (cleaned_at, archive_id),
        )
        return max(0, int(cleaned_rows))

    async def summarize_sync_log_day(self, summary_date: str | date) -> dict[str, int]:
        await self._execute(
            """
            INSERT INTO `sync_log_daily_summary`
                (`summary_date`, `ticker`, `status`, `entry_count`, `rows_added`,
                 `first_synced_at`, `last_synced_at`, `last_error_message`)
            SELECT *
            FROM (
                SELECT
                    DATE(`synced_at`) AS `summary_date`,
                    `ticker`,
                    `status`,
                    COUNT(*) AS `entry_count`,
                    COALESCE(SUM(`rows_added`), 0) AS `rows_added`,
                    MIN(`synced_at`) AS `first_synced_at`,
                    MAX(`synced_at`) AS `last_synced_at`,
                    LEFT(SUBSTRING_INDEX(GROUP_CONCAT(
                        CASE WHEN `status`<>'success' THEN `message` END
                        ORDER BY `synced_at` DESC SEPARATOR '\n'
                    ), '\n', 1), 500) AS `last_error_message`
                FROM `sync_log`
                WHERE `synced_at` >= %s
                  AND `synced_at` < DATE_ADD(%s, INTERVAL 1 DAY)
                GROUP BY DATE(`synced_at`), `ticker`, `status`
            ) AS `incoming`
            ON DUPLICATE KEY UPDATE
                `entry_count`=`incoming`.`entry_count`,
                `rows_added`=`incoming`.`rows_added`,
                `first_synced_at`=`incoming`.`first_synced_at`,
                `last_synced_at`=`incoming`.`last_synced_at`,
                `last_error_message`=`incoming`.`last_error_message`
            """,
            (summary_date, summary_date),
        )
        source = await self._fetchone(
            """
            SELECT COUNT(*) AS `entry_count`, COALESCE(SUM(`rows_added`), 0) AS `rows_added`
            FROM `sync_log`
            WHERE `synced_at` >= %s
              AND `synced_at` < DATE_ADD(%s, INTERVAL 1 DAY)
            """,
            (summary_date, summary_date),
        )
        summary = await self._fetchone(
            """
            SELECT COALESCE(SUM(`entry_count`), 0) AS `entry_count`,
                   COALESCE(SUM(`rows_added`), 0) AS `rows_added`
            FROM `sync_log_daily_summary`
            WHERE `summary_date`=%s
            """,
            (summary_date,),
        )
        return {
            "source_entry_count": int((source or {}).get("entry_count") or 0),
            "source_rows_added": int((source or {}).get("rows_added") or 0),
            "summary_entry_count": int((summary or {}).get("entry_count") or 0),
            "summary_rows_added": int((summary or {}).get("rows_added") or 0),
        }

    async def get_next_sync_log_summary_date(
        self,
        *,
        cutoff_date: str | date,
    ) -> str | None:
        row = await self._fetchone(
            """
            SELECT DATE(s.`synced_at`) AS `summary_date`
            FROM `sync_log` AS s
            LEFT JOIN (
                SELECT `summary_date`, SUM(`entry_count`) AS `entry_count`
                FROM `sync_log_daily_summary`
                GROUP BY `summary_date`
            ) AS summary
              ON summary.`summary_date`=DATE(s.`synced_at`)
            WHERE s.`synced_at` < %s
            GROUP BY DATE(s.`synced_at`), summary.`entry_count`
            HAVING COUNT(*)<>COALESCE(summary.`entry_count`, 0)
            ORDER BY `summary_date`
            LIMIT 1
            """,
            (cutoff_date,),
        )
        return str((row or {}).get("summary_date") or "") or None

    async def get_next_sync_log_cleanup_date(
        self,
        *,
        cutoff_date: str | date,
        summary_eligible_before: datetime,
    ) -> str | None:
        row = await self._fetchone(
            """
            SELECT DATE(s.`synced_at`) AS `summary_date`
            FROM `sync_log` AS s
            INNER JOIN (
                SELECT `summary_date`, MAX(`updated_at`) AS `updated_at`
                FROM `sync_log_daily_summary`
                GROUP BY `summary_date`
            ) AS summary
              ON summary.`summary_date`=DATE(s.`synced_at`)
             AND summary.`updated_at`<=%s
            WHERE s.`synced_at` < %s
            GROUP BY DATE(s.`synced_at`)
            ORDER BY `summary_date`
            LIMIT 1
            """,
            (summary_eligible_before, cutoff_date),
        )
        return str((row or {}).get("summary_date") or "") or None

    async def delete_sync_log_day_batch(
        self,
        *,
        summary_date: str | date,
        batch_size: int,
    ) -> int:
        return await self._execute(
            """
            DELETE FROM `sync_log`
            WHERE `synced_at` >= %s
              AND `synced_at` < DATE_ADD(%s, INTERVAL 1 DAY)
            ORDER BY `id`
            LIMIT %s
            """,
            (summary_date, summary_date, max(1, int(batch_size))),
        )
