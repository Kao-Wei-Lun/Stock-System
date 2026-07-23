"""Bounded, resumable archive maintenance with mandatory dry-run and backup gates."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from chip_archive_codec import (
    ChipArchiveError,
    decode_chip_branch_archive,
    encode_chip_branch_archive,
)
from mysql_backup import (
    BACKUP_SCOPES,
    DEFAULT_BACKUP_DIR,
    BackupError,
    verify_backup,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

class StorageMaintenanceError(RuntimeError):
    pass


def _parse_manifest_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def find_covering_backup(
    backup_dir: Path,
    *,
    scope: str,
    business_date: str | date | None = None,
    backup_id: str | None = None,
    now: datetime | None = None,
    max_age_hours: float | None = None,
) -> dict[str, Any] | None:
    requested_scope = str(scope or "").strip().lower()
    if requested_scope not in BACKUP_SCOPES:
        raise StorageMaintenanceError(f"Unsupported backup scope: {scope}")
    required_date = _parse_manifest_date(business_date)
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    candidates: list[tuple[datetime, Path, dict[str, Any]]] = []
    for manifest_path in Path(backup_dir).glob("quantvision_*.manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_scope = str(manifest.get("scope") or "full").lower()
            if manifest_scope not in {requested_scope, "full"}:
                continue
            if backup_id and str(manifest.get("backup_id")) != str(backup_id):
                continue
            created_at = datetime.fromisoformat(str(manifest["created_at"]))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            created_at = created_at.astimezone(timezone.utc)
            if max_age_hours is not None:
                age_hours = max(0.0, (reference - created_at).total_seconds() / 3600)
                if age_hours > max(0.0, float(max_age_hours)):
                    continue
            if required_date and manifest_scope != "full":
                stats = (manifest.get("table_stats") or {}).get("taiwan_chip_snapshots") or {}
                range_payload = manifest.get("business_date_range") or {}
                range_start = _parse_manifest_date(
                    stats.get("min_business_date")
                    or range_payload.get("requested_start")
                    or range_payload.get("min")
                )
                range_end = _parse_manifest_date(
                    stats.get("max_business_date")
                    or range_payload.get("requested_end")
                    or range_payload.get("max")
                )
                if not range_start or not range_end or not (range_start <= required_date <= range_end):
                    continue
            candidates.append((created_at, manifest_path, manifest))
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            continue
    for _created_at, manifest_path, manifest in sorted(
        candidates,
        key=lambda item: item[0],
        reverse=True,
    ):
        try:
            verify_backup(manifest_path)
        except BackupError:
            continue
        return {
            "backup_id": manifest.get("backup_id"),
            "scope": manifest.get("scope") or "full",
            "created_at": manifest.get("created_at"),
            "manifest_path": str(manifest_path.resolve()),
        }
    return None


class StorageMaintenanceService:
    def __init__(
        self,
        db: Any,
        *,
        backup_dir: Path = DEFAULT_BACKUP_DIR,
        max_runtime_seconds: int = 60,
        archive_grace_days: int = 1,
        clock=None,
    ):
        self._db = db
        self._backup_dir = Path(backup_dir)
        self._max_runtime_seconds = max(1, int(max_runtime_seconds))
        self._archive_grace_days = max(1, int(archive_grace_days))
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    async def _next_chip_archive_group(self, cutoff: date) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(
                self._db.get_next_chip_branch_archive_group(
                    cutoff_date=cutoff.isoformat()
                ),
                timeout=min(self._max_runtime_seconds, 30),
            )
        except TimeoutError as exc:
            raise StorageMaintenanceError(
                "Chip archive candidate query exceeded its bounded runtime"
            ) from exc

    async def archive_chip_branches(
        self,
        *,
        cutoff_date: str | date,
        execute: bool = False,
        max_groups: int = 1,
        backup_id: str | None = None,
    ) -> dict[str, Any]:
        cutoff = _parse_manifest_date(cutoff_date)
        if cutoff is None:
            raise StorageMaintenanceError("cutoff_date must use YYYY-MM-DD")
        action = "archive_chip_branch_payload"
        started_at = self._now()
        first_group = await self._next_chip_archive_group(cutoff)
        if not execute:
            next_group = dict(first_group or {})
            if next_group.get("snapshot_date") is not None:
                parsed_group_date = _parse_manifest_date(next_group["snapshot_date"])
                next_group["snapshot_date"] = (
                    parsed_group_date.isoformat() if parsed_group_date else None
                )
            result = {
                "dry_run": True,
                "mutation_allowed": False,
                "action": action,
                "source_table": "taiwan_chip_snapshots",
                "cutoff_date": cutoff.isoformat(),
                "next_group": next_group,
                "max_groups": max(1, int(max_groups)),
            }
            await self._db.record_storage_maintenance_run(
                action=action,
                source_table="taiwan_chip_snapshots",
                cutoff_date=cutoff,
                status="completed",
                is_dry_run=True,
                result=result,
                started_at=started_at,
                completed_at=self._now(),
            )
            return result

        if not await self._db.has_completed_storage_dry_run(
            action=action,
            source_table="taiwan_chip_snapshots",
            cutoff_date=cutoff,
        ):
            raise StorageMaintenanceError(
                "Archive execution refused until a completed dry-run is recorded"
            )

        processed_rows = 0
        archived_rows = 0
        archived_groups = 0
        last_cursor: dict[str, Any] = {}
        started_monotonic = time.monotonic()
        while archived_groups < max(1, int(max_groups)):
            if time.monotonic() - started_monotonic >= self._max_runtime_seconds:
                break
            group = await self._next_chip_archive_group(cutoff)
            if not group:
                break
            group_date = _parse_manifest_date(group.get("snapshot_date"))
            source = str(group.get("source") or "")
            if group_date is None:
                raise StorageMaintenanceError("Archive candidate has an invalid snapshot date")
            backup = find_covering_backup(
                self._backup_dir,
                scope="market-history",
                business_date=group_date,
                backup_id=backup_id,
                now=self._now(),
                max_age_hours=24 * 7,
            )
            if not backup:
                raise StorageMaintenanceError(
                    f"No verified market-history backup covers {group_date.isoformat()}"
                )
            rows = await self._db.list_chip_branch_payload_rows(
                snapshot_date=group_date,
                source=source,
            )
            expected_rows = int(group.get("source_row_count") or 0)
            if len(rows) != expected_rows:
                raise StorageMaintenanceError("Archive source row count changed during the batch")
            encoded = encode_chip_branch_archive(rows)
            decode_chip_branch_archive(
                encoded["payload_blob"],
                expected_sha256=encoded["payload_sha256"],
                expected_row_count=expected_rows,
            )
            archived_at = self._now()
            cleanup_eligible_at = archived_at + timedelta(days=self._archive_grace_days)
            async with self._db.transaction():
                archive_id = await self._db.upsert_chip_branch_archive(
                    snapshot_date=group_date,
                    source=source,
                    backup_id=str(backup["backup_id"]),
                    archived_at=archived_at.replace(tzinfo=None),
                    cleanup_eligible_at=cleanup_eligible_at.replace(tzinfo=None),
                    **encoded,
                )
            stored = await self._db.get_chip_branch_archive(
                snapshot_date=group_date,
                source=source,
            )
            if not stored or int(stored.get("id") or 0) != archive_id:
                raise StorageMaintenanceError("Archived payload could not be read back")
            decode_chip_branch_archive(
                stored["payload_blob"],
                expected_sha256=stored.get("payload_sha256"),
                expected_row_count=stored.get("source_row_count"),
            )
            processed_rows += expected_rows
            archived_rows += expected_rows
            archived_groups += 1
            last_cursor = {
                "snapshot_date": group_date.isoformat(),
                "source": source,
                "archive_id": archive_id,
            }

        status = "completed" if archived_groups < max(1, int(max_groups)) else "partial"
        result = {
            "dry_run": False,
            "action": action,
            "status": status,
            "processed_rows": processed_rows,
            "archived_rows": archived_rows,
            "archived_groups": archived_groups,
            "cursor": last_cursor,
            "cleanup_performed": False,
        }
        await self._db.record_storage_maintenance_run(
            action=action,
            source_table="taiwan_chip_snapshots",
            cutoff_date=cutoff,
            status=status,
            is_dry_run=False,
            backup_id=backup_id,
            batch_size=max(1, int(max_groups)),
            processed_rows=processed_rows,
            archived_rows=archived_rows,
            cursor=last_cursor,
            result=result,
            started_at=started_at,
            completed_at=self._now(),
        )
        return result
    async def cleanup_chip_branches(
        self,
        *,
        execute: bool = False,
        max_groups: int = 1,
    ) -> dict[str, Any]:
        action = "cleanup_chip_branch_payload"
        started_at = self._now()
        candidate = await self._db.get_next_chip_branch_cleanup_candidate(
            now=started_at.replace(tzinfo=None)
        )
        cutoff = _parse_manifest_date((candidate or {}).get("snapshot_date")) or started_at.date()
        if not execute:
            result = {
                "dry_run": True,
                "mutation_allowed": False,
                "action": action,
                "source_table": "taiwan_chip_snapshots",
                "candidate_archive_id": (candidate or {}).get("id"),
                "candidate_date": (
                    cutoff.isoformat() if candidate else None
                ),
                "max_groups": max(1, int(max_groups)),
            }
            await self._db.record_storage_maintenance_run(
                action=action,
                source_table="taiwan_chip_snapshots",
                cutoff_date=cutoff,
                status="completed",
                is_dry_run=True,
                result=result,
                started_at=started_at,
                completed_at=self._now(),
            )
            return result

        if not candidate:
            return {
                "dry_run": False,
                "action": action,
                "status": "completed",
                "cleaned_rows": 0,
                "cleaned_groups": 0,
            }
        if not await self._db.has_completed_storage_dry_run(
            action=action,
            source_table="taiwan_chip_snapshots",
            cutoff_date=cutoff,
        ):
            raise StorageMaintenanceError(
                "Cleanup execution refused until a completed dry-run is recorded"
            )
        backup = find_covering_backup(
            self._backup_dir,
            scope="market-history",
            business_date=cutoff,
            backup_id=str(candidate.get("backup_id") or ""),
            now=self._now(),
            max_age_hours=None,
        )
        if not backup:
            raise StorageMaintenanceError("Cleanup refused because the archive backup is unavailable")
        try:
            decoded = decode_chip_branch_archive(
                candidate["payload_blob"],
                expected_sha256=candidate.get("payload_sha256"),
                expected_row_count=candidate.get("source_row_count"),
            )
        except ChipArchiveError as exc:
            raise StorageMaintenanceError(str(exc)) from exc
        expected_rows = len(decoded)
        async with self._db.transaction():
            cleaned_rows = await self._db.clear_online_chip_branch_payload(
                archive_id=int(candidate["id"]),
                snapshot_date=cutoff,
                source=str(candidate.get("source") or ""),
                cleaned_at=self._now().replace(tzinfo=None),
            )
            if cleaned_rows != expected_rows:
                raise StorageMaintenanceError(
                    "Cleanup row count does not match the verified archive"
                )
        result = {
            "dry_run": False,
            "action": action,
            "status": "partial",
            "cleaned_rows": cleaned_rows,
            "cleaned_groups": 1,
            "archive_id": int(candidate["id"]),
        }
        await self._db.record_storage_maintenance_run(
            action=action,
            source_table="taiwan_chip_snapshots",
            cutoff_date=cutoff,
            status="partial",
            is_dry_run=False,
            backup_id=str(candidate.get("backup_id") or ""),
            batch_size=max(1, int(max_groups)),
            cleaned_rows=cleaned_rows,
            result=result,
            started_at=started_at,
            completed_at=self._now(),
        )
        return result

    async def summarize_sync_log(
        self,
        *,
        cutoff_date: str | date,
        execute: bool = False,
    ) -> dict[str, Any]:
        cutoff = _parse_manifest_date(cutoff_date)
        if cutoff is None:
            raise StorageMaintenanceError("cutoff_date must use YYYY-MM-DD")
        action = "summarize_sync_log"
        started_at = self._now()
        summary_date = await self._db.get_next_sync_log_summary_date(
            cutoff_date=cutoff.isoformat()
        )
        if not execute:
            result = {
                "dry_run": True,
                "mutation_allowed": False,
                "action": action,
                "source_table": "sync_log",
                "cutoff_date": cutoff.isoformat(),
                "next_summary_date": summary_date,
            }
            await self._db.record_storage_maintenance_run(
                action=action,
                source_table="sync_log",
                cutoff_date=cutoff,
                status="completed",
                is_dry_run=True,
                result=result,
                started_at=started_at,
                completed_at=self._now(),
            )
            return result
        if not await self._db.has_completed_storage_dry_run(
            action=action,
            source_table="sync_log",
            cutoff_date=cutoff,
        ):
            raise StorageMaintenanceError(
                "Sync summary execution refused until a completed dry-run is recorded"
            )
        if not summary_date:
            return {
                "dry_run": False,
                "action": action,
                "status": "completed",
                "summary_date": None,
                "source_entry_count": 0,
            }
        backup = find_covering_backup(
            self._backup_dir,
            scope="critical",
            now=self._now(),
            max_age_hours=36,
        )
        if not backup:
            raise StorageMaintenanceError(
                "Sync summary refused because no recent verified critical backup exists"
            )
        async with self._db.transaction():
            totals = await self._db.summarize_sync_log_day(summary_date)
            if (
                totals["source_entry_count"] != totals["summary_entry_count"]
                or totals["source_rows_added"] != totals["summary_rows_added"]
            ):
                raise StorageMaintenanceError("Sync summary aggregate mismatch")
        result = {
            "dry_run": False,
            "action": action,
            "status": "partial",
            "summary_date": summary_date,
            **totals,
        }
        await self._db.record_storage_maintenance_run(
            action=action,
            source_table="sync_log",
            cutoff_date=cutoff,
            status="partial",
            is_dry_run=False,
            backup_id=str(backup["backup_id"]),
            processed_rows=totals["source_entry_count"],
            result=result,
            started_at=started_at,
            completed_at=self._now(),
        )
        return result

    async def cleanup_sync_log(
        self,
        *,
        cutoff_date: str | date,
        execute: bool = False,
        batch_size: int = 5000,
    ) -> dict[str, Any]:
        cutoff = _parse_manifest_date(cutoff_date)
        if cutoff is None:
            raise StorageMaintenanceError("cutoff_date must use YYYY-MM-DD")
        action = "cleanup_sync_log"
        started_at = self._now()
        eligible_before = started_at - timedelta(days=self._archive_grace_days)
        cleanup_date = await self._db.get_next_sync_log_cleanup_date(
            cutoff_date=cutoff.isoformat(),
            summary_eligible_before=eligible_before.replace(tzinfo=None),
        )
        bounded_batch = max(1, min(int(batch_size), 50_000))
        if not execute:
            result = {
                "dry_run": True,
                "mutation_allowed": False,
                "action": action,
                "source_table": "sync_log",
                "cutoff_date": cutoff.isoformat(),
                "next_cleanup_date": cleanup_date,
                "batch_size": bounded_batch,
            }
            await self._db.record_storage_maintenance_run(
                action=action,
                source_table="sync_log",
                cutoff_date=cutoff,
                status="completed",
                is_dry_run=True,
                batch_size=bounded_batch,
                result=result,
                started_at=started_at,
                completed_at=self._now(),
            )
            return result
        if not await self._db.has_completed_storage_dry_run(
            action=action,
            source_table="sync_log",
            cutoff_date=cutoff,
        ):
            raise StorageMaintenanceError(
                "Sync cleanup refused until a completed dry-run is recorded"
            )
        if not cleanup_date:
            return {
                "dry_run": False,
                "action": action,
                "status": "completed",
                "cleaned_rows": 0,
                "cleanup_date": None,
            }
        backup = find_covering_backup(
            self._backup_dir,
            scope="critical",
            now=self._now(),
            max_age_hours=36,
        )
        if not backup:
            raise StorageMaintenanceError(
                "Sync cleanup refused because no recent verified critical backup exists"
            )
        already_started = await self._db.has_storage_maintenance_execution(
            action=action,
            source_table="sync_log",
            cutoff_date=cleanup_date,
        )
        if not already_started:
            totals = await self._db.summarize_sync_log_day(cleanup_date)
            if (
                totals["source_entry_count"] != totals["summary_entry_count"]
                or totals["source_rows_added"] != totals["summary_rows_added"]
            ):
                raise StorageMaintenanceError("Sync cleanup summary does not match source")
        async with self._db.transaction():
            cleaned_rows = await self._db.delete_sync_log_day_batch(
                summary_date=cleanup_date,
                batch_size=bounded_batch,
            )
        status = "partial" if cleaned_rows >= bounded_batch else "completed"
        result = {
            "dry_run": False,
            "action": action,
            "status": status,
            "cleanup_date": cleanup_date,
            "cleaned_rows": max(0, int(cleaned_rows)),
            "batch_size": bounded_batch,
        }
        await self._db.record_storage_maintenance_run(
            action=action,
            source_table="sync_log",
            cutoff_date=cleanup_date,
            status=status,
            is_dry_run=False,
            backup_id=str(backup["backup_id"]),
            batch_size=bounded_batch,
            cleaned_rows=max(0, int(cleaned_rows)),
            cursor={"summary_date": cleanup_date},
            result=result,
            started_at=started_at,
            completed_at=self._now(),
        )
        return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("archive-chip", "cleanup-chip", "summarize-sync", "cleanup-sync"),
    )
    parser.add_argument("--cutoff-date")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--backup-id")
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--max-runtime-seconds", type=int, default=60)
    parser.add_argument("--max-groups", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--archive-grace-days", type=int, default=1)
    return parser


async def _run_cli(args) -> dict[str, Any]:
    from database import db

    connected = False
    try:
        await db.connect()
        connected = True
        await db.create_tables(auto_apply=False)
        service = StorageMaintenanceService(
            db,
            backup_dir=args.backup_dir,
            max_runtime_seconds=args.max_runtime_seconds,
            archive_grace_days=args.archive_grace_days,
        )
        if args.action == "archive-chip":
            if not args.cutoff_date:
                raise StorageMaintenanceError("--cutoff-date is required for archive-chip")
            return await service.archive_chip_branches(
                cutoff_date=args.cutoff_date,
                execute=args.execute,
                max_groups=args.max_groups,
                backup_id=args.backup_id,
            )
        if args.action == "cleanup-chip":
            return await service.cleanup_chip_branches(
                execute=args.execute,
                max_groups=args.max_groups,
            )
        if args.action == "summarize-sync":
            if not args.cutoff_date:
                raise StorageMaintenanceError("--cutoff-date is required for summarize-sync")
            return await service.summarize_sync_log(
                cutoff_date=args.cutoff_date,
                execute=args.execute,
            )
        if not args.cutoff_date:
            raise StorageMaintenanceError("--cutoff-date is required for cleanup-sync")
        return await service.cleanup_sync_log(
            cutoff_date=args.cutoff_date,
            execute=args.execute,
            batch_size=args.batch_size,
        )
    finally:
        if connected:
            await db.close()


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv(PROJECT_ROOT / ".env")
    args = build_parser().parse_args(argv)
    try:
        result = asyncio.run(_run_cli(args))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
