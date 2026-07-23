from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mysql_backup import (
    BackupError,
    CRITICAL_SCOPE_INCLUDED_DATA_TABLES,
    MARKET_HISTORY_TABLES,
    MysqlSettings,
    create_backup,
    drop_restore_target,
    latest_backup_status,
    prune_backups,
    restore_backup,
    verify_backup,
    verify_restored_database,
)


def build_settings() -> MysqlSettings:
    return MysqlSettings(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="super-secret",
        database="quantvision",
    )


def create_fake_tool(tmp_path: Path, name: str) -> str:
    path = tmp_path / name
    path.write_text("fake", encoding="utf-8")
    return str(path)


def create_manifest(tmp_path: Path, *, source_database: str = "quantvision") -> Path:
    dump_path = tmp_path / "quantvision_20260722T010000Z.sql"
    dump_path.write_bytes(b"CREATE TABLE sample (id INT);\n")
    manifest = {
        "format_version": 1,
        "backup_id": "20260722T010000Z",
        "created_at": "2026-07-22T01:00:00+00:00",
        "source": {"database": source_database},
        "dump_file": dump_path.name,
        "size_bytes": dump_path.stat().st_size,
        "sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
    }
    manifest_path = tmp_path / "quantvision_20260722T010000Z.manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_backup_uses_temporary_defaults_file_and_excludes_password_from_manifest(tmp_path):
    commands = []
    defaults_contents = []

    def fake_runner(command, **kwargs):
        commands.append(command)
        defaults_path = Path(command[1].split("=", 1)[1])
        defaults_contents.append(defaults_path.read_text(encoding="utf-8"))
        kwargs["stdout"].write(b"CREATE TABLE sample (id INT);\n")
        return subprocess.CompletedProcess(command, 0, stderr=b"")

    result = create_backup(
        build_settings(),
        backup_dir=tmp_path / "backups",
        retention_days=30,
        keep_minimum=7,
        mysqldump_path=create_fake_tool(tmp_path, "mysqldump.exe"),
        runner=fake_runner,
        now=datetime(2026, 7, 22, 1, 0, tzinfo=timezone.utc),
    )

    manifest_path = Path(result["backup_dir"]) / result["manifest_file"]
    manifest_text = manifest_path.read_text(encoding="utf-8")
    assert verify_backup(manifest_path)["valid"] is True
    assert "super-secret" in defaults_contents[0]
    assert "super-secret" not in manifest_text
    assert '"user"' not in manifest_text
    assert all("super-secret" not in argument for argument in commands[0])
    assert not Path(commands[0][1].split("=", 1)[1]).exists()


def test_critical_backup_preserves_schema_but_excludes_rebuildable_table_data(tmp_path):
    commands = []

    def fake_runner(command, **kwargs):
        commands.append(command)
        kwargs["stdout"].write(b"CREATE TABLE sample (id INT);\n")
        return subprocess.CompletedProcess(command, 0, stderr=b"")

    result = create_backup(
        build_settings(),
        backup_dir=tmp_path / "backups",
        scope="critical",
        mysqldump_path=create_fake_tool(tmp_path, "mysqldump.exe"),
        runner=fake_runner,
        now=datetime(2026, 7, 22, 1, 0, tzinfo=timezone.utc),
    )

    assert result["scope"] == "critical"
    assert result["format_version"] == 2
    assert result["compression"] == "gzip"
    assert result["included_data_tables"] == list(CRITICAL_SCOPE_INCLUDED_DATA_TABLES)
    assert "taiwan_chip_snapshots" in result["excluded_data_tables"]
    assert "ohlcv" in result["excluded_data_tables"]
    assert "--no-data" in commands[0]
    assert "--no-create-info" in commands[1]
    assert "asset_trade_ledger" in commands[1]
    assert "ohlcv" not in commands[1]


def test_backup_timeout_removes_partial_file(tmp_path):
    def timed_out(_command, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="mysqldump", timeout=2)

    backup_dir = tmp_path / "backups"
    with pytest.raises(BackupError, match="timed out after 2 seconds"):
        create_backup(
            build_settings(),
            backup_dir=backup_dir,
            timeout_seconds=2,
            mysqldump_path=create_fake_tool(tmp_path, "mysqldump.exe"),
            runner=timed_out,
        )

    assert list(backup_dir.glob("*.part")) == []


def test_failed_backup_preserves_previous_healthy_backup(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    previous_manifest = create_manifest(backup_dir)
    previous_dump = backup_dir / "quantvision_20260722T010000Z.sql"

    def failed_runner(command, **_kwargs):
        return subprocess.CompletedProcess(command, 1, stderr=b"simulated failure")

    with pytest.raises(BackupError, match="mysqldump failed"):
        create_backup(
            build_settings(),
            backup_dir=backup_dir,
            scope="full",
            mysqldump_path=create_fake_tool(tmp_path, "mysqldump.exe"),
            runner=failed_runner,
            now=datetime(2026, 7, 23, 1, 0, tzinfo=timezone.utc),
        )

    assert previous_manifest.exists()
    assert previous_dump.exists()
    assert verify_backup(previous_manifest)["valid"] is True


def test_latest_backup_status_detects_current_stale_and_missing_files(tmp_path):
    manifest_path = create_manifest(tmp_path)
    current = latest_backup_status(
        tmp_path,
        max_age_hours=36,
        now=datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc),
    )
    assert current["healthy"] is True
    assert current["scope"] == "full"

    stale = latest_backup_status(
        tmp_path,
        max_age_hours=1,
        now=datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc),
    )
    assert stale["healthy"] is False
    assert "older than" in stale["error"]

    (tmp_path / "quantvision_20260722T010000Z.sql").unlink()
    missing = latest_backup_status(tmp_path, now=datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc))
    assert missing["healthy"] is False
    assert "do not match" in missing["error"]


def test_verify_backup_detects_tampering(tmp_path):
    manifest_path = create_manifest(tmp_path)
    dump_path = tmp_path / "quantvision_20260722T010000Z.sql"
    dump_path.write_bytes(dump_path.read_bytes() + b"-- changed\n")

    with pytest.raises(BackupError, match="size does not match"):
        verify_backup(manifest_path)


def test_restore_refuses_source_database_without_explicit_override(tmp_path):
    manifest_path = create_manifest(tmp_path)

    with pytest.raises(BackupError, match="Refusing to overwrite"):
        restore_backup(
            build_settings(),
            manifest_path,
            target_database="quantvision",
            dry_run=True,
        )


def test_restore_dry_run_verifies_backup_without_running_mysql(tmp_path):
    manifest_path = create_manifest(tmp_path)

    result = restore_backup(
        build_settings(),
        manifest_path,
        target_database="quantvision_restore_test",
        dry_run=True,
    )

    assert result == {
        "dry_run": True,
        "verified": True,
        "source_database": "quantvision",
        "target_database": "quantvision_restore_test",
        "would_allow_existing_target": False,
        "would_verify_restore": False,
    }


def test_restore_refuses_existing_target_by_default(tmp_path):
    manifest_path = create_manifest(tmp_path)

    def fake_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=b"quantvision_restore_test\n", stderr=b"")

    with pytest.raises(BackupError, match="already exists"):
        restore_backup(
            build_settings(),
            manifest_path,
            target_database="quantvision_restore_test",
            mysql_path=create_fake_tool(tmp_path, "mysql.exe"),
            runner=fake_runner,
        )


def test_restore_creates_new_target_and_imports_verified_dump(tmp_path):
    manifest_path = create_manifest(tmp_path)
    commands = []

    def fake_runner(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    result = restore_backup(
        build_settings(),
        manifest_path,
        target_database="quantvision_restore_test",
        mysql_path=create_fake_tool(tmp_path, "mysql.exe"),
        runner=fake_runner,
    )

    assert result["restored"] is True
    assert len(commands) == 3
    assert commands[-1][-1] == "quantvision_restore_test"
    assert all("super-secret" not in argument for command in commands for argument in command)


def test_restore_decompresses_gzip_before_passing_sql_to_mysql(tmp_path):
    sql = b"CREATE TABLE sample (id INT);\n"
    dump_path = tmp_path / "quantvision_critical.sql.gz"
    with gzip.open(dump_path, "wb") as handle:
        handle.write(sql)
    manifest = {
        "format_version": 2,
        "backup_id": "critical",
        "created_at": "2026-07-22T01:00:00+00:00",
        "scope": "critical",
        "source": {"database": "quantvision"},
        "dump_file": dump_path.name,
        "compression": "gzip",
        "size_bytes": dump_path.stat().st_size,
        "sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
    }
    manifest_path = tmp_path / "quantvision_critical.manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    restored_payloads = []

    def fake_runner(command, **kwargs):
        if "stdin" in kwargs:
            restored_payloads.append(kwargs["stdin"].read())
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    result = restore_backup(
        build_settings(),
        manifest_path,
        target_database="quantvision_restore_test_gzip",
        mysql_path=create_fake_tool(tmp_path, "mysql.exe"),
        runner=fake_runner,
    )

    assert result["restored"] is True
    assert restored_payloads == [sql]


def test_retention_keeps_minimum_newest_backups(tmp_path):
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    for index, age_days in enumerate((1, 10, 40, 50)):
        created_at = now - timedelta(days=age_days)
        backup_id = f"backup-{index}"
        dump_path = tmp_path / f"quantvision_{index}.sql"
        dump_path.write_text("sql", encoding="utf-8")
        manifest = {
            "format_version": 1,
            "backup_id": backup_id,
            "created_at": created_at.isoformat(),
            "dump_file": dump_path.name,
            "size_bytes": dump_path.stat().st_size,
            "sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
        }
        (tmp_path / f"quantvision_{index}.manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

    removed = prune_backups(tmp_path, retention_days=30, keep_minimum=2, now=now)

    assert removed == ["backup-2", "backup-3"]
    assert (tmp_path / "quantvision_0.sql").exists()
    assert (tmp_path / "quantvision_1.sql").exists()
    assert not (tmp_path / "quantvision_2.sql").exists()


def test_market_history_backup_supports_date_range_and_compressed_manifest(tmp_path):
    commands = []

    def fake_runner(command, **kwargs):
        commands.append(command)
        kwargs["stdout"].write(b"INSERT INTO sample VALUES (1);\n")
        return subprocess.CompletedProcess(command, 0, stderr=b"")

    result = create_backup(
        build_settings(),
        backup_dir=tmp_path / "backups",
        scope="market-history",
        start_date="2026-07-01",
        end_date="2026-07-22",
        mysqldump_path=create_fake_tool(tmp_path, "mysqldump.exe"),
        runner=fake_runner,
        now=datetime(2026, 7, 22, 1, 0, tzinfo=timezone.utc),
    )

    manifest_path = Path(result["backup_dir"]) / result["manifest_file"]
    assert verify_backup(manifest_path)["valid"] is True
    assert result["included_data_tables"] == list(MARKET_HISTORY_TABLES)
    assert result["business_date_range"]["requested_start"] == "2026-07-01"
    assert result["business_date_range"]["requested_end"] == "2026-07-22"
    assert result["dump_file"].endswith(".sql.gz")
    assert "--no-data" in commands[0]
    ohlcv_command = next(command for command in commands if command[-1] == "ohlcv")
    assert "--where=`date` >= '2026-07-01' AND `date` < '2026-07-23'" in ohlcv_command


@pytest.mark.parametrize(
    ("start_date", "end_date", "message"),
    [
        ("2026/07/01", None, "YYYY-MM-DD"),
        ("2026-07-23", "2026-07-22", "on or before"),
    ],
)
def test_market_history_backup_rejects_invalid_date_ranges(
    tmp_path,
    start_date,
    end_date,
    message,
):
    with pytest.raises(BackupError, match=message):
        create_backup(
            build_settings(),
            backup_dir=tmp_path,
            scope="market-history",
            start_date=start_date,
            end_date=end_date,
            mysqldump_path=create_fake_tool(tmp_path, "mysqldump.exe"),
            runner=lambda *_args, **_kwargs: None,
        )


def test_restore_rejects_non_temporary_schema_even_for_dry_run(tmp_path):
    manifest_path = create_manifest(tmp_path)

    with pytest.raises(BackupError, match="explicit temporary schema"):
        restore_backup(
            build_settings(),
            manifest_path,
            target_database="quantvision_copy",
            dry_run=True,
        )


def test_drop_restore_target_refuses_non_temporary_schema(tmp_path):
    with pytest.raises(BackupError, match="explicit temporary schema"):
        drop_restore_target(
            build_settings(),
            "quantvision_copy",
            mysql_path=create_fake_tool(tmp_path, "mysql.exe"),
        )


def test_verify_backup_rejects_corrupted_gzip_even_when_checksum_matches(tmp_path):
    dump_path = tmp_path / "quantvision_corrupt.sql.gz"
    dump_path.write_bytes(b"not-a-gzip-stream")
    manifest = {
        "format_version": 2,
        "backup_id": "corrupt",
        "created_at": "2026-07-22T01:00:00+00:00",
        "scope": "critical",
        "source": {"database": "quantvision"},
        "dump_file": dump_path.name,
        "compression": "gzip",
        "size_bytes": dump_path.stat().st_size,
        "sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
    }
    manifest_path = tmp_path / "quantvision_corrupt.manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(BackupError, match="gzip stream is corrupted"):
        verify_backup(manifest_path)


def test_retention_by_bytes_keeps_last_healthy_backup_for_each_scope(tmp_path):
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)

    def add_backup(index: int, scope: str, age_days: int, size: int):
        dump_path = tmp_path / f"quantvision_{index}.sql"
        dump_path.write_bytes(b"x" * size)
        manifest = {
            "format_version": 2,
            "backup_id": f"backup-{index}",
            "created_at": (now - timedelta(days=age_days)).isoformat(),
            "scope": scope,
            "dump_file": dump_path.name,
            "size_bytes": size,
            "sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
        }
        (tmp_path / f"quantvision_{index}.manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

    add_backup(0, "critical", 1, 10)
    add_backup(1, "critical", 2, 10)
    add_backup(2, "market-history", 3, 10)

    removed = prune_backups(
        tmp_path,
        retention_days=365,
        keep_minimum=1,
        keep_minimum_per_scope=1,
        max_total_bytes=15,
        now=now,
    )

    assert removed == ["backup-1"]
    assert (tmp_path / "quantvision_0.sql").exists()
    assert (tmp_path / "quantvision_2.sql").exists()


def test_restore_verification_checks_migrations_counts_and_asset_checksums(tmp_path):
    manifest = {
        "format_version": 2,
        "scope": "critical",
        "schema_version": "20260723_0001",
        "source": {"database": "quantvision"},
        "included_data_tables": list(CRITICAL_SCOPE_INCLUDED_DATA_TABLES),
        "table_stats": {
            "asset_accounts": {"row_count": 2, "row_count_kind": "exact"},
        },
    }
    required_tables = {
        "schema_migrations",
        "asset_accounts",
        "asset_cash_ledger",
        "asset_trade_ledger",
        "asset_position_adjustments",
        "paper_trading_accounts",
        "user_preferences",
        "workspace_presets",
        "alerts",
    }

    def fake_runner(command, **_kwargs):
        sql = next((item.split("=", 1)[1] for item in command if item.startswith("--execute=")), "")
        if "INFORMATION_SCHEMA.TABLES" in sql:
            stdout = ("\n".join(sorted(required_tables)) + "\n").encode()
        elif "MAX(`version`)" in sql:
            stdout = b"20260723_0001\n"
        elif "COUNT(*)" in sql:
            stdout = b"2\n"
        elif "CHECKSUM TABLE" in sql:
            stdout = b"asset_table\t12345\n"
        else:
            stdout = b""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr=b"")

    result = verify_restored_database(
        build_settings(),
        manifest,
        target_database="quantvision_restore_drill_20260723",
        mysql_path=create_fake_tool(tmp_path, "mysql.exe"),
        runner=fake_runner,
    )

    assert result["valid"] is True
    assert result["migration_matches"] is True
    assert result["exact_row_counts_match"] is True
    assert result["asset_overview_rebuildable"] is True


def test_market_history_restore_does_not_require_schema_migration_table(tmp_path):
    manifest = {
        "format_version": 2,
        "scope": "market-history",
        "schema_version": "20260723_0001",
        "source": {"database": "quantvision"},
        "included_data_tables": ["ohlcv", "taiwan_chip_snapshots"],
        "table_stats": {},
    }

    def fake_runner(command, **_kwargs):
        sql = next((item.split("=", 1)[1] for item in command if item.startswith("--execute=")), "")
        stdout = b"ohlcv\ntaiwan_chip_snapshots\n" if "INFORMATION_SCHEMA.TABLES" in sql else b""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr=b"")

    result = verify_restored_database(
        build_settings(),
        manifest,
        target_database="quantvision_restore_drill_history",
        mysql_path=create_fake_tool(tmp_path, "mysql.exe"),
        runner=fake_runner,
    )

    assert result["valid"] is True
    assert result["migration_matches"] is True
