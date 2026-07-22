from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mysql_backup import (
    BackupError,
    MysqlSettings,
    create_backup,
    latest_backup_status,
    prune_backups,
    restore_backup,
    verify_backup,
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
    import hashlib

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
    assert result["excluded_data_tables"] == ["taiwan_chip_snapshots", "ohlcv"]
    assert "--no-data" in commands[0]
    assert "--no-create-info" in commands[1]
    assert "--ignore-table=quantvision.taiwan_chip_snapshots" in commands[1]
    assert "--ignore-table=quantvision.ohlcv" in commands[1]


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


def test_retention_keeps_minimum_newest_backups(tmp_path):
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    for index, age_days in enumerate((1, 10, 40, 50)):
        created_at = now - timedelta(days=age_days)
        backup_id = f"backup-{index}"
        dump_path = tmp_path / f"quantvision_{index}.sql"
        dump_path.write_text("sql", encoding="utf-8")
        manifest = {
            "backup_id": backup_id,
            "created_at": created_at.isoformat(),
            "dump_file": dump_path.name,
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
