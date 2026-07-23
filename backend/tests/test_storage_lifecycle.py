from __future__ import annotations

from datetime import date

import pytest

import storage_lifecycle
from storage_lifecycle import (
    AUDITED_TABLES,
    StorageLifecycleAuditor,
    StorageLifecycleError,
)


class FakeReadOnlyExecutor:
    def __init__(self):
        self.queries: list[tuple[str, str | None]] = []

    def query(self, sql: str, *, database: str | None = None):
        normalized = " ".join(sql.split())
        self.queries.append((normalized, database))
        assert normalized.upper().startswith("SELECT ")
        assert not any(
            token in normalized.upper()
            for token in ("DELETE ", "UPDATE ", "INSERT ", "ALTER ", "DROP ", "OPTIMIZE ")
        )
        if "INFORMATION_SCHEMA`.`TABLES" in normalized:
            return [
                [table, "1000", "100000", "20000", "100"]
                for table in AUDITED_TABLES
            ]
        if "MIN(" in normalized:
            return [["2024-01-01", "2026-07-22"]]
        if "DATE_FORMAT" in normalized:
            return [["2026-06", "90"], ["2026-07", "100"]]
        if "recent_sample" in normalized:
            return [["100", "5", "800.5"]]
        if "COUNT(*)" in normalized:
            return [["250"]]
        raise AssertionError(f"Unexpected query: {normalized}")


def test_storage_audit_is_read_only_and_excludes_personal_tables():
    executor = FakeReadOnlyExecutor()
    auditor = StorageLifecycleAuditor(
        executor,
        database="quantvision",
        max_runtime_seconds=60,
    )

    result = auditor.audit(today=date(2026, 7, 23))

    assert result["read_only"] is True
    assert [item["table"] for item in result["tables"]] == list(AUDITED_TABLES)
    assert not any(
        item["table"].startswith(("asset_", "paper_trading_"))
        for item in result["tables"]
    )
    chip = next(item for item in result["tables"] if item["table"] == "taiwan_chip_snapshots")
    assert chip["archive_cutoff"] == "2024-07-23"
    assert chip["archive_candidate_rows"] == 250
    assert chip["payload_null_ratio_sample"] == 0.05
    assert chip["estimated_archive_candidate_bytes"] == 200125
    ohlcv = next(item for item in result["tables"] if item["table"] == "ohlcv")
    assert ohlcv["archive_cutoff"] is None
    assert ohlcv["archive_candidate_rows"] == 0


def test_storage_dry_run_never_allows_mutation(monkeypatch, tmp_path):
    executor = FakeReadOnlyExecutor()
    auditor = StorageLifecycleAuditor(executor, database="quantvision")
    monkeypatch.setattr(
        storage_lifecycle,
        "latest_backup_status",
        lambda *_args, **_kwargs: {
            "healthy": True,
            "backup_id": "history-1",
            "created_at": "2026-07-23T00:00:00+00:00",
            "error": None,
        },
    )

    result = auditor.dry_run(today=date(2026, 7, 23), backup_dir=tmp_path)

    assert result["dry_run"] is True
    assert result["mutation_allowed"] is False
    assert result["backup_gate"]["backup_id"] == "history-1"
    assert all(item["would_mutate"] is False for item in result["actions"])
    assert all(item["auto_cleanup"] is False for item in result["actions"])
    assert "asset_*" in result["excluded_tables"]
    assert "paper_trading_*" in result["excluded_tables"]


def test_storage_auditor_rejects_unsafe_database_identifier():
    with pytest.raises(StorageLifecycleError, match="Unsafe SQL identifier"):
        StorageLifecycleAuditor(FakeReadOnlyExecutor(), database="quantvision`; DROP DATABASE")
