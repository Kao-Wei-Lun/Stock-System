"""Safe MySQL backup, verification, retention, and test-restore tooling."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "backups" / "mysql"
DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
BACKUP_FORMAT_VERSION = 1
BACKUP_SCOPES = {"full", "critical"}
CRITICAL_SCOPE_EXCLUDED_DATA_TABLES = ("taiwan_chip_snapshots", "ohlcv")


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class MysqlSettings:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "MysqlSettings":
        source = env if env is not None else os.environ
        values = {
            "host": str(source.get("MYSQL_HOST") or "127.0.0.1").strip(),
            "port": str(source.get("MYSQL_PORT") or "3306").strip(),
            "user": str(source.get("MYSQL_USER") or "root").strip(),
            "password": str(source.get("MYSQL_PASSWORD") or ""),
            "database": str(source.get("MYSQL_DATABASE") or "quantvision").strip(),
            "charset": str(source.get("MYSQL_CHARSET") or "utf8mb4").strip(),
        }
        if not values["host"] or not values["user"] or not values["password"]:
            raise BackupError("MYSQL_HOST, MYSQL_USER, and MYSQL_PASSWORD are required")
        _validate_database_name(values["database"])
        try:
            port = int(values["port"])
        except ValueError as exc:
            raise BackupError("MYSQL_PORT must be an integer") from exc
        if not 1 <= port <= 65535:
            raise BackupError("MYSQL_PORT must be between 1 and 65535")
        return cls(
            host=values["host"],
            port=port,
            user=values["user"],
            password=values["password"],
            database=values["database"],
            charset=values["charset"] or "utf8mb4",
        )


def _validate_database_name(database: str) -> str:
    name = str(database or "").strip()
    if not DATABASE_NAME_PATTERN.fullmatch(name):
        raise BackupError("Database names may contain only letters, digits, and underscores")
    return name


def _option_file_value(value: Any) -> str:
    text = str(value)
    if "\n" in text or "\r" in text:
        raise BackupError("MySQL credentials may not contain line breaks")
    return text.replace("\\", "\\\\").replace('"', '\\"')


@contextmanager
def mysql_defaults_file(settings: MysqlSettings) -> Iterator[Path]:
    content = "\n".join(
        [
            "[client]",
            f'host="{_option_file_value(settings.host)}"',
            f"port={settings.port}",
            f'user="{_option_file_value(settings.user)}"',
            f'password="{_option_file_value(settings.password)}"',
            f'default-character-set="{_option_file_value(settings.charset)}"',
            "",
        ]
    )
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".cnf", delete=False)
    path = Path(handle.name)
    try:
        handle.write(content)
        handle.close()
        path.chmod(0o600)
        yield path
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _resolve_tool(explicit: str | None, env_name: str, fallback: str) -> str:
    candidate = explicit or os.environ.get(env_name) or fallback
    resolved = shutil.which(candidate)
    if resolved:
        return resolved
    path = Path(candidate).expanduser()
    if path.is_file():
        return str(path.resolve())
    if os.name == "nt" and not explicit and not os.environ.get(env_name):
        patterns = (
            f"C:/Program Files/MySQL/MySQL Server */bin/{fallback}.exe",
            f"C:/Program Files/MariaDB */bin/{fallback}.exe",
        )
        discovered = sorted(
            (Path(item) for pattern in patterns for item in glob.glob(pattern)),
            reverse=True,
        )
        if discovered:
            return str(discovered[0].resolve())
    raise BackupError(f"Unable to find {fallback}; set {env_name} to the executable path")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_error(stderr: Any) -> str:
    if isinstance(stderr, bytes):
        text = stderr.decode("utf-8", errors="replace")
    else:
        text = str(stderr or "")
    return text.strip()[:500] or "unknown MySQL client error"


def create_backup(
    settings: MysqlSettings,
    *,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    retention_days: int = 30,
    keep_minimum: int = 7,
    scope: str = "full",
    timeout_seconds: int = 60 * 60,
    mysqldump_path: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    now: datetime | None = None,
) -> dict[str, Any]:
    scope = str(scope or "full").strip().lower()
    if scope not in BACKUP_SCOPES:
        raise BackupError(f"Unsupported backup scope: {scope}")
    timeout_seconds = max(1, int(timeout_seconds))
    tool = _resolve_tool(mysqldump_path, "MYSQLDUMP_PATH", "mysqldump")
    created_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    backup_id = created_at.strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path(backup_dir).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    dump_path = backup_dir / f"quantvision_{backup_id}.sql"
    manifest_path = backup_dir / f"quantvision_{backup_id}.manifest.json"
    partial_path = dump_path.with_suffix(".sql.part")

    excluded_data_tables = list(CRITICAL_SCOPE_EXCLUDED_DATA_TABLES if scope == "critical" else ())
    try:
        with mysql_defaults_file(settings) as defaults_path, partial_path.open("wb") as output:
            base_command = [
                tool,
                f"--defaults-extra-file={defaults_path}",
                "--single-transaction",
                "--quick",
                "--hex-blob",
                "--skip-lock-tables",
                f"--default-character-set={settings.charset}",
            ]
            if scope == "critical":
                # --ignore-table-data is unavailable in some MySQL releases.
                # Two portable passes preserve every schema while omitting only
                # the rebuildable high-volume table rows.
                commands = [
                    [*base_command, "--routines", "--events", "--triggers", "--no-data", settings.database],
                    [
                        *base_command,
                        "--no-create-info",
                        "--skip-triggers",
                        *[
                            f"--ignore-table={settings.database}.{table}"
                            for table in excluded_data_tables
                        ],
                        settings.database,
                    ],
                ]
            else:
                commands = [[*base_command, "--routines", "--events", "--triggers", settings.database]]
            completed = None
            for command in commands:
                completed = runner(
                    command,
                    stdout=output,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=timeout_seconds,
                )
                if completed.returncode != 0:
                    break
    except subprocess.TimeoutExpired as exc:
        partial_path.unlink(missing_ok=True)
        raise BackupError(f"mysqldump timed out after {timeout_seconds} seconds") from exc
    except Exception:
        partial_path.unlink(missing_ok=True)
        raise
    if completed is None or completed.returncode != 0:
        partial_path.unlink(missing_ok=True)
        raise BackupError(f"mysqldump failed: {_safe_error(completed.stderr)}")
    if not partial_path.exists() or partial_path.stat().st_size == 0:
        partial_path.unlink(missing_ok=True)
        raise BackupError("mysqldump produced an empty backup")

    partial_path.replace(dump_path)
    manifest = {
        "format_version": BACKUP_FORMAT_VERSION,
        "backup_id": backup_id,
        "created_at": created_at.isoformat(),
        "verified_at": created_at.isoformat(),
        "scope": scope,
        "excluded_data_tables": excluded_data_tables,
        "source": {
            "host": settings.host,
            "port": settings.port,
            "user": settings.user,
            "database": settings.database,
            "charset": settings.charset,
        },
        "dump_file": dump_path.name,
        "size_bytes": dump_path.stat().st_size,
        "sha256": sha256_file(dump_path),
    }
    temporary_manifest = manifest_path.with_suffix(".json.part")
    temporary_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_manifest.replace(manifest_path)
    removed = prune_backups(
        backup_dir,
        retention_days=max(0, int(retention_days)),
        keep_minimum=max(1, int(keep_minimum)),
        now=created_at,
    )
    return {
        **manifest,
        "manifest_file": manifest_path.name,
        "backup_dir": str(backup_dir),
        "removed_backup_ids": removed,
    }


def latest_backup_status(
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    *,
    max_age_hours: float = 36,
    scope: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a cheap health check without re-hashing multi-gigabyte dump files."""
    requested_scope = str(scope).strip().lower() if scope else None
    if requested_scope and requested_scope not in BACKUP_SCOPES:
        raise BackupError(f"Unsupported backup scope: {requested_scope}")
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    candidates: list[tuple[datetime, Path, dict[str, Any]]] = []
    invalid_manifests: list[str] = []
    for manifest_path in Path(backup_dir).glob("quantvision_*.manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_scope = str(manifest.get("scope") or "full").lower()
            if requested_scope and manifest_scope != requested_scope:
                continue
            created_at = datetime.fromisoformat(str(manifest["created_at"]))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            candidates.append((created_at.astimezone(timezone.utc), manifest_path, manifest))
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            invalid_manifests.append(manifest_path.name)
    if not candidates:
        return {
            "status": "warning",
            "healthy": False,
            "scope": requested_scope,
            "error": "No verified backup manifest was found",
            "invalid_manifests": invalid_manifests,
        }
    created_at, manifest_path, manifest = max(candidates, key=lambda item: item[0])
    dump_name = Path(str(manifest.get("dump_file") or "")).name
    dump_path = manifest_path.parent / dump_name
    size_bytes = dump_path.stat().st_size if dump_path.is_file() else None
    expected_size = manifest.get("size_bytes")
    structurally_valid = bool(
        manifest.get("format_version") == BACKUP_FORMAT_VERSION
        and dump_name
        and dump_name == manifest.get("dump_file")
        and size_bytes == expected_size
        and manifest.get("sha256")
    )
    age_hours = max(0.0, (reference - created_at).total_seconds() / 3600)
    stale = age_hours > max(0.0, float(max_age_hours))
    healthy = structurally_valid and not stale
    error = None
    if not structurally_valid:
        error = "Latest backup files do not match the manifest"
    elif stale:
        error = f"Latest backup is older than {float(max_age_hours):g} hours"
    return {
        "status": "healthy" if healthy else "warning",
        "healthy": healthy,
        "scope": str(manifest.get("scope") or "full"),
        "backup_id": manifest.get("backup_id"),
        "created_at": created_at.isoformat(),
        "age_hours": round(age_hours, 2),
        "size_bytes": size_bytes,
        "manifest_path": str(manifest_path.resolve()),
        "dump_path": str(dump_path.resolve()),
        "excluded_data_tables": manifest.get("excluded_data_tables") or [],
        "checksum_recorded": bool(manifest.get("sha256")),
        "error": error,
        "invalid_manifests": invalid_manifests,
    }


def verify_backup(manifest_path: Path) -> dict[str, Any]:
    manifest_path = Path(manifest_path).resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError(f"Unable to read backup manifest: {exc}") from exc
    if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
        raise BackupError("Unsupported backup manifest version")
    dump_name = Path(str(manifest.get("dump_file") or "")).name
    if not dump_name or dump_name != manifest.get("dump_file"):
        raise BackupError("Invalid dump filename in manifest")
    dump_path = manifest_path.parent / dump_name
    if not dump_path.is_file():
        raise BackupError(f"Backup dump is missing: {dump_path}")
    actual_size = dump_path.stat().st_size
    actual_sha256 = sha256_file(dump_path)
    if actual_size != manifest.get("size_bytes"):
        raise BackupError("Backup size does not match manifest")
    if actual_sha256 != manifest.get("sha256"):
        raise BackupError("Backup checksum does not match manifest")
    return {
        "valid": True,
        "manifest": manifest,
        "manifest_path": str(manifest_path),
        "dump_path": str(dump_path),
    }


def prune_backups(
    backup_dir: Path,
    *,
    retention_days: int,
    keep_minimum: int,
    now: datetime | None = None,
) -> list[str]:
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = reference - timedelta(days=max(0, retention_days))
    records: list[tuple[datetime, Path, dict[str, Any]]] = []
    for manifest_path in Path(backup_dir).glob("quantvision_*.manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            created_at = datetime.fromisoformat(str(manifest["created_at"]))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            records.append((created_at.astimezone(timezone.utc), manifest_path, manifest))
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            continue
    records.sort(key=lambda item: item[0], reverse=True)
    removed: list[str] = []
    for created_at, manifest_path, manifest in records[max(1, keep_minimum):]:
        if created_at >= cutoff:
            continue
        dump_path = manifest_path.parent / Path(str(manifest.get("dump_file") or "")).name
        dump_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        removed.append(str(manifest.get("backup_id") or manifest_path.stem))
    return removed


def restore_backup(
    settings: MysqlSettings,
    manifest_path: Path,
    *,
    target_database: str,
    allow_existing_target: bool = False,
    allow_source_overwrite: bool = False,
    dry_run: bool = False,
    mysql_path: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    verification = verify_backup(manifest_path)
    manifest = verification["manifest"]
    target = _validate_database_name(target_database)
    source_database = str((manifest.get("source") or {}).get("database") or "")
    if target == source_database and not allow_source_overwrite:
        raise BackupError(
            "Refusing to overwrite the source database; use --allow-source-overwrite only after a verified backup"
        )
    if dry_run:
        return {
            "dry_run": True,
            "verified": True,
            "source_database": source_database,
            "target_database": target,
            "would_allow_existing_target": bool(allow_existing_target),
        }

    tool = _resolve_tool(mysql_path, "MYSQL_CLIENT_PATH", "mysql")
    with mysql_defaults_file(settings) as defaults_path:
        common = [tool, f"--defaults-extra-file={defaults_path}", "--batch", "--skip-column-names"]
        escaped_target = target.replace("'", "''")
        exists_result = runner(
            [
                *common,
                f"--execute=SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='{escaped_target}'",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if exists_result.returncode != 0:
            raise BackupError(f"Unable to inspect restore target: {_safe_error(exists_result.stderr)}")
        exists_output = exists_result.stdout.decode("utf-8", errors="replace") if isinstance(exists_result.stdout, bytes) else str(exists_result.stdout or "")
        target_exists = target in {line.strip() for line in exists_output.splitlines()}
        if target_exists and not allow_existing_target:
            raise BackupError("Restore target already exists; choose a new database or use --allow-existing-target")
        if not target_exists:
            create_result = runner(
                [
                    *common,
                    f"--execute=CREATE DATABASE `{target}` CHARACTER SET {settings.charset}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if create_result.returncode != 0:
                raise BackupError(f"Unable to create restore target: {_safe_error(create_result.stderr)}")
        with Path(verification["dump_path"]).open("rb") as dump_input:
            restore_result = runner(
                [*common, target],
                stdin=dump_input,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        if restore_result.returncode != 0:
            raise BackupError(f"MySQL restore failed: {_safe_error(restore_result.stderr)}")
    return {
        "dry_run": False,
        "verified": True,
        "source_database": source_database,
        "target_database": target,
        "restored": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Create and verify a MySQL backup")
    backup_parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    backup_parser.add_argument("--retention-days", type=int, default=30)
    backup_parser.add_argument("--keep-minimum", type=int, default=7)
    backup_parser.add_argument("--scope", choices=sorted(BACKUP_SCOPES), default="full")
    backup_parser.add_argument("--timeout-seconds", type=int, default=60 * 60)
    backup_parser.add_argument("--mysqldump-path")

    verify_parser = subparsers.add_parser("verify", help="Verify a backup manifest and checksum")
    verify_parser.add_argument("manifest", type=Path)

    restore_parser = subparsers.add_parser("restore", help="Restore a verified backup")
    restore_parser.add_argument("manifest", type=Path)
    restore_parser.add_argument("--target-database", required=True)
    restore_parser.add_argument("--allow-existing-target", action="store_true")
    restore_parser.add_argument("--allow-source-overwrite", action="store_true")
    restore_parser.add_argument("--dry-run", action="store_true")
    restore_parser.add_argument("--mysql-path")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "backup":
            result = create_backup(
                MysqlSettings.from_env(),
                backup_dir=args.backup_dir,
                retention_days=args.retention_days,
                keep_minimum=args.keep_minimum,
                scope=args.scope,
                timeout_seconds=args.timeout_seconds,
                mysqldump_path=args.mysqldump_path,
            )
            verify_backup(Path(result["backup_dir"]) / result["manifest_file"])
        elif args.command == "verify":
            result = verify_backup(args.manifest)
        else:
            result = restore_backup(
                MysqlSettings.from_env(),
                args.manifest,
                target_database=args.target_database,
                allow_existing_target=args.allow_existing_target,
                allow_source_overwrite=args.allow_source_overwrite,
                dry_run=args.dry_run,
                mysql_path=args.mysql_path,
            )
    except BackupError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
