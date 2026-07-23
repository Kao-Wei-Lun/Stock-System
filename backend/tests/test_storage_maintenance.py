from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from chip_archive_codec import encode_chip_branch_archive
from storage_maintenance import (
    StorageMaintenanceError,
    StorageMaintenanceService,
    find_covering_backup,
)


def create_history_backup(
    tmp_path: Path,
    *,
    backup_id: str = "history-1",
    date_from: str = "2024-01-01",
    date_to: str = "2024-01-31",
) -> Path:
    sql = b"CREATE TABLE sample (id INT);\n"
    dump_path = tmp_path / f"quantvision_{backup_id}.sql.gz"
    with gzip.open(dump_path, "wb") as handle:
        handle.write(sql)
    manifest = {
        "format_version": 2,
        "backup_id": backup_id,
        "created_at": "2026-07-23T00:00:00+00:00",
        "scope": "market-history",
        "source": {"database": "quantvision"},
        "table_stats": {
            "taiwan_chip_snapshots": {
                "min_business_date": date_from,
                "max_business_date": date_to,
            }
        },
        "dump_file": dump_path.name,
        "compression": "gzip",
        "size_bytes": dump_path.stat().st_size,
        "uncompressed_size_bytes": len(sql),
        "sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
    }
    manifest_path = tmp_path / f"quantvision_{backup_id}.manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def create_critical_backup(tmp_path: Path, *, backup_id: str = "critical-1") -> Path:
    manifest_path = create_history_backup(tmp_path, backup_id=backup_id)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["scope"] = "critical"
    manifest["table_stats"] = {}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_find_covering_backup_requires_verified_date_coverage(tmp_path):
    create_history_backup(tmp_path)
    now = datetime(2026, 7, 23, 12, tzinfo=timezone.utc)

    covered = find_covering_backup(
        tmp_path,
        scope="market-history",
        business_date="2024-01-10",
        now=now,
        max_age_hours=24 * 7,
    )
    missing = find_covering_backup(
        tmp_path,
        scope="market-history",
        business_date="2023-12-31",
        now=now,
        max_age_hours=24 * 7,
    )

    assert covered["backup_id"] == "history-1"
    assert missing is None


class AsyncTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeMaintenanceDb:
    def __init__(self):
        self.dry_run_completed = False
        self.records = []
        self.group = {
            "snapshot_date": "2024-01-10",
            "source": "twse_t86",
            "source_row_count": 2,
        }
        self.rows = [
            {"id": 1, "ticker": "2317.TW", "branch_payload_json": '{"branches":[]}'},
            {"id": 2, "ticker": "2330.TW", "branch_payload_json": '{"branches":[]}'},
        ]
        self.archive = None
        self.cleared = False
        self.summary_date = "2026-03-24"
        self.cleanup_date = "2026-03-24"
        self.summary_totals = {
            "source_entry_count": 100,
            "source_rows_added": 500,
            "summary_entry_count": 100,
            "summary_rows_added": 500,
        }
        self.execution_started = False
        self.deleted_rows = 25

    async def get_next_chip_branch_archive_group(self, *, cutoff_date):
        return None if self.archive else dict(self.group)

    async def record_storage_maintenance_run(self, **payload):
        self.records.append(payload)
        if payload["is_dry_run"] and payload["status"] == "completed":
            self.dry_run_completed = True
        return len(self.records)

    async def has_completed_storage_dry_run(self, **_payload):
        return self.dry_run_completed

    async def list_chip_branch_payload_rows(self, **_payload):
        return list(self.rows)

    def transaction(self):
        return AsyncTransaction()

    async def upsert_chip_branch_archive(self, **payload):
        self.archive = {"id": 1, **payload, "status": "archived"}
        return 1

    async def get_chip_branch_archive(self, **_payload):
        return dict(self.archive) if self.archive else None

    async def get_next_chip_branch_cleanup_candidate(self, **_payload):
        return dict(self.archive) if self.archive and not self.cleared else None

    async def clear_online_chip_branch_payload(self, **_payload):
        self.cleared = True
        return len(self.rows)

    async def get_next_sync_log_summary_date(self, **_payload):
        return self.summary_date

    async def summarize_sync_log_day(self, _summary_date):
        return dict(self.summary_totals)

    async def get_next_sync_log_cleanup_date(self, **_payload):
        return self.cleanup_date

    async def has_storage_maintenance_execution(self, **_payload):
        return self.execution_started

    async def delete_sync_log_day_batch(self, **_payload):
        self.execution_started = True
        return self.deleted_rows


@pytest.mark.anyio
async def test_chip_archive_requires_recorded_dry_run(tmp_path):
    db = FakeMaintenanceDb()
    service = StorageMaintenanceService(
        db,
        backup_dir=tmp_path,
        clock=lambda: datetime(2026, 7, 23, 12, tzinfo=timezone.utc),
    )

    with pytest.raises(StorageMaintenanceError, match="completed dry-run"):
        await service.archive_chip_branches(
            cutoff_date="2024-07-23",
            execute=True,
        )


@pytest.mark.anyio
async def test_chip_archive_commits_one_verified_group_and_is_resumable(tmp_path):
    create_history_backup(tmp_path)
    db = FakeMaintenanceDb()
    service = StorageMaintenanceService(
        db,
        backup_dir=tmp_path,
        clock=lambda: datetime(2026, 7, 23, 12, tzinfo=timezone.utc),
    )

    dry_run = await service.archive_chip_branches(cutoff_date="2024-07-23")
    result = await service.archive_chip_branches(
        cutoff_date="2024-07-23",
        execute=True,
        max_groups=1,
    )

    assert dry_run["mutation_allowed"] is False
    assert result["archived_rows"] == 2
    assert result["archived_groups"] == 1
    assert result["cleanup_performed"] is False
    assert db.archive["backup_id"] == "history-1"
    assert db.archive["source_row_count"] == 2


@pytest.mark.anyio
async def test_chip_archive_refuses_when_backup_does_not_cover_candidate_date(tmp_path):
    create_history_backup(tmp_path, date_from="2026-07-22", date_to="2026-07-22")
    db = FakeMaintenanceDb()
    db.dry_run_completed = True
    service = StorageMaintenanceService(
        db,
        backup_dir=tmp_path,
        clock=lambda: datetime(2026, 7, 23, 12, tzinfo=timezone.utc),
    )

    with pytest.raises(StorageMaintenanceError, match="No verified market-history backup covers"):
        await service.archive_chip_branches(
            cutoff_date="2024-07-23",
            execute=True,
        )


@pytest.mark.anyio
async def test_cleanup_revalidates_archive_and_backup_before_clearing(tmp_path):
    create_history_backup(tmp_path)
    db = FakeMaintenanceDb()
    encoded = encode_chip_branch_archive(db.rows)
    db.archive = {
        "id": 1,
        "snapshot_date": "2024-01-10",
        "source": "twse_t86",
        "backup_id": "history-1",
        **encoded,
    }
    db.dry_run_completed = True
    service = StorageMaintenanceService(
        db,
        backup_dir=tmp_path,
        clock=lambda: datetime(2026, 7, 23, 12, tzinfo=timezone.utc),
    )

    result = await service.cleanup_chip_branches(execute=True)

    assert result["cleaned_rows"] == 2
    assert db.cleared is True


@pytest.mark.anyio
async def test_cleanup_checksum_mismatch_blocks_online_clear(tmp_path):
    create_history_backup(tmp_path)
    db = FakeMaintenanceDb()
    encoded = encode_chip_branch_archive(db.rows)
    db.archive = {
        "id": 1,
        "snapshot_date": "2024-01-10",
        "source": "twse_t86",
        "backup_id": "history-1",
        **encoded,
        "payload_sha256": "0" * 64,
    }
    db.dry_run_completed = True
    service = StorageMaintenanceService(
        db,
        backup_dir=tmp_path,
        clock=lambda: datetime(2026, 7, 23, 12, tzinfo=timezone.utc),
    )

    with pytest.raises(StorageMaintenanceError, match="checksum mismatch"):
        await service.cleanup_chip_branches(execute=True)

    assert db.cleared is False


@pytest.mark.anyio
async def test_sync_summary_requires_dry_run_and_recent_critical_backup(tmp_path):
    create_critical_backup(tmp_path)
    db = FakeMaintenanceDb()
    service = StorageMaintenanceService(
        db,
        backup_dir=tmp_path,
        clock=lambda: datetime(2026, 7, 23, 12, tzinfo=timezone.utc),
    )

    with pytest.raises(StorageMaintenanceError, match="completed dry-run"):
        await service.summarize_sync_log(
            cutoff_date="2026-04-24",
            execute=True,
        )

    dry_run = await service.summarize_sync_log(cutoff_date="2026-04-24")
    result = await service.summarize_sync_log(
        cutoff_date="2026-04-24",
        execute=True,
    )

    assert dry_run["mutation_allowed"] is False
    assert result["summary_date"] == "2026-03-24"
    assert result["source_entry_count"] == result["summary_entry_count"]


@pytest.mark.anyio
async def test_sync_summary_mismatch_rolls_back(tmp_path):
    create_critical_backup(tmp_path)
    db = FakeMaintenanceDb()
    db.dry_run_completed = True
    db.summary_totals["summary_entry_count"] = 99
    service = StorageMaintenanceService(
        db,
        backup_dir=tmp_path,
        clock=lambda: datetime(2026, 7, 23, 12, tzinfo=timezone.utc),
    )

    with pytest.raises(StorageMaintenanceError, match="aggregate mismatch"):
        await service.summarize_sync_log(
            cutoff_date="2026-04-24",
            execute=True,
        )


@pytest.mark.anyio
async def test_sync_cleanup_is_bounded_and_resumable(tmp_path):
    create_critical_backup(tmp_path)
    db = FakeMaintenanceDb()
    service = StorageMaintenanceService(
        db,
        backup_dir=tmp_path,
        clock=lambda: datetime(2026, 7, 23, 12, tzinfo=timezone.utc),
    )

    dry_run = await service.cleanup_sync_log(
        cutoff_date="2026-04-24",
        batch_size=20,
    )
    result = await service.cleanup_sync_log(
        cutoff_date="2026-04-24",
        execute=True,
        batch_size=20,
    )

    assert dry_run["mutation_allowed"] is False
    assert dry_run["batch_size"] == 20
    assert result["cleaned_rows"] == 25
    assert result["status"] == "partial"
    assert db.execution_started is True
