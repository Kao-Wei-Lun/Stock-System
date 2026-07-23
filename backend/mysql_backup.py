"""Safe MySQL backup, verification, retention, and test-restore tooling."""

from __future__ import annotations

import argparse
import gzip
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "backups" / "mysql"
DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
RESTORE_TARGET_PATTERN = re.compile(
    r"^[A-Za-z0-9_]+_restore_(?:test|drill)(?:_[A-Za-z0-9_]+)?$",
    re.IGNORECASE,
)
BACKUP_FORMAT_VERSION = 2
SUPPORTED_BACKUP_FORMAT_VERSIONS = {1, BACKUP_FORMAT_VERSION}
BACKUP_SCOPES = {"full", "critical", "market-history"}

# Scope A: data created or curated by the local user.  A critical backup keeps
# every table schema for compatibility, but only copies these table rows.
CRITICAL_SCOPE_INCLUDED_DATA_TABLES = (
    "schema_migrations",
    "user_profiles",
    "user_preferences",
    "workspace_presets",
    "fubon_api_accounts",
    "alerts",
    "alert_trigger_logs",
    "notifications",
    "sync_jobs",
    "sync_job_logs",
    "sync_log",
    "sync_log_daily_summary",
    "storage_maintenance_runs",
    "watchlist_groups",
    "watchlist_items",
    "backtest_runs",
    "backtest_trades",
    "backtest_equity_points",
    "trade_journal_entries",
    "trade_journal_tags",
    "trade_journal_attachments",
    "screener_presets",
    "journal_filter_presets",
    "asset_import_batches",
    "asset_accounts",
    "asset_cash_ledger",
    "asset_trade_ledger",
    "asset_positions_current",
    "asset_valuations_current",
    "asset_reconciliation_snapshots",
    "asset_price_overrides",
    "asset_fx_rates_daily",
    "asset_position_adjustments",
    "paper_trading_accounts",
    "paper_trading_bots",
    "paper_trading_positions",
    "paper_trading_orders",
    "paper_trading_fills",
    "paper_trading_equity_snapshots",
    "paper_trading_risk_events",
    "paper_trading_contract_resolutions",
    "paper_trading_cost_models",
    "paper_trading_replay_runs",
    "paper_trading_continuous_rolls",
)

# Scope B/C history.  Date columns are allow-listed so command construction
# never interpolates an arbitrary identifier supplied by a caller.
MARKET_HISTORY_DATE_COLUMNS = {
    "ohlcv": "date",
    "institutional_snapshots": "resolved_date",
    "taifex_institutional_meta": "resolved_date",
    "taifex_overview_daily": "resolved_date",
    "taifex_futures_daily": "resolved_date",
    "taifex_options_daily": "resolved_date",
    "taifex_call_put_daily": "resolved_date",
    "taifex_cash_summary_daily": "resolved_date",
    "taiwan_chip_snapshots": "snapshot_date",
    "fubon_market_snapshots": "snapshot_date",
    "taiwan_chip_branch_archives": "snapshot_date",
    "market_payload_archives": "business_date",
}
MARKET_HISTORY_TABLES = tuple(MARKET_HISTORY_DATE_COLUMNS)
REBUILDABLE_OR_HISTORY_DATA_TABLES = (
    *MARKET_HISTORY_TABLES,
    "stock_info",
    "market_quotes_latest",
    "market_events",
    "news_articles",
    "macro_snapshots",
    "tw_equity_universe",
    "tw_history_sync_status",
)

CORE_RESTORE_TABLES = {
    "critical": (
        "schema_migrations",
        "asset_accounts",
        "asset_cash_ledger",
        "asset_trade_ledger",
        "paper_trading_accounts",
        "user_preferences",
        "workspace_presets",
        "alerts",
    ),
    "market-history": ("ohlcv", "taiwan_chip_snapshots"),
    "full": ("schema_migrations", "asset_accounts", "ohlcv"),
}
ASSET_LEDGER_TABLES = (
    "asset_accounts",
    "asset_cash_ledger",
    "asset_trade_ledger",
    "asset_position_adjustments",
)


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


def _validate_restore_target(database: str) -> str:
    name = _validate_database_name(database)
    if not RESTORE_TARGET_PATTERN.fullmatch(name):
        raise BackupError(
            "Restore target must be an explicit temporary schema such as "
            "'quantvision_restore_drill_20260723'"
        )
    return name


def _normalize_backup_date(value: str | date | None, field_name: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        try:
            parsed = date.fromisoformat(str(value).strip())
        except ValueError as exc:
            raise BackupError(f"{field_name} must use YYYY-MM-DD format") from exc
    return parsed


def _normalize_date_range(
    start_date: str | date | None,
    end_date: str | date | None,
) -> tuple[date | None, date | None]:
    start = _normalize_backup_date(start_date, "start_date")
    end = _normalize_backup_date(end_date, "end_date")
    if start and end and start > end:
        raise BackupError("start_date must be on or before end_date")
    return start, end


def _history_where_clause(column: str, start_date: date | None, end_date: date | None) -> str | None:
    conditions: list[str] = []
    if start_date:
        conditions.append(f"`{column}` >= '{start_date.isoformat()}'")
    if end_date:
        next_day = end_date + timedelta(days=1)
        conditions.append(f"`{column}` < '{next_day.isoformat()}'")
    return " AND ".join(conditions) or None


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


def _run_mysql_query(
    tool: str,
    defaults_path: Path,
    sql: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    database: str | None = None,
) -> list[list[str]]:
    command = [
        tool,
        f"--defaults-extra-file={defaults_path}",
        "--batch",
        "--skip-column-names",
    ]
    if database:
        command.append(database)
    command.append(f"--execute={sql}")
    result = runner(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise BackupError(f"MySQL metadata query failed: {_safe_error(result.stderr)}")
    output = (
        result.stdout.decode("utf-8", errors="replace")
        if isinstance(result.stdout, bytes)
        else str(result.stdout or "")
    )
    return [line.split("\t") for line in output.splitlines() if line.strip()]


def _inspect_source_metadata(
    settings: MysqlSettings,
    *,
    mysql_tool: str,
    defaults_path: Path,
    scope: str,
    start_date: date | None,
    end_date: date | None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    rows = _run_mysql_query(
        mysql_tool,
        defaults_path,
        (
            "SELECT TABLE_NAME, COALESCE(TABLE_ROWS, 0) "
            "FROM INFORMATION_SCHEMA.TABLES "
            f"WHERE TABLE_SCHEMA='{settings.database}' AND TABLE_TYPE='BASE TABLE' "
            "ORDER BY TABLE_NAME"
        ),
        runner=runner,
    )
    estimates = {
        row[0]: max(0, int(row[1] or 0))
        for row in rows
        if len(row) >= 2 and DATABASE_NAME_PATTERN.fullmatch(row[0])
    }
    available_tables = tuple(sorted(estimates))
    if scope == "critical":
        included = tuple(table for table in CRITICAL_SCOPE_INCLUDED_DATA_TABLES if table in estimates)
    elif scope == "market-history":
        included = tuple(table for table in MARKET_HISTORY_TABLES if table in estimates)
    else:
        included = available_tables

    table_stats: dict[str, dict[str, Any]] = {}
    metadata_warnings: list[str] = []
    for table in included:
        stats: dict[str, Any] = {
            "row_count": estimates.get(table, 0),
            "row_count_kind": "estimate",
        }
        if scope == "critical":
            try:
                count_rows = _run_mysql_query(
                    mysql_tool,
                    defaults_path,
                    f"SELECT COUNT(*) FROM `{table}`",
                    database=settings.database,
                    runner=runner,
                )
                if count_rows and count_rows[0]:
                    stats["row_count"] = max(0, int(count_rows[0][0] or 0))
                    stats["row_count_kind"] = "exact"
            except (BackupError, TypeError, ValueError):
                metadata_warnings.append(f"{table}:exact_count_unavailable")
        date_column = MARKET_HISTORY_DATE_COLUMNS.get(table)
        if date_column:
            where_clause = _history_where_clause(date_column, start_date, end_date)
            if scope == "market-history" and where_clause:
                try:
                    count_rows = _run_mysql_query(
                        mysql_tool,
                        defaults_path,
                        f"SELECT COUNT(*) FROM `{table}` WHERE {where_clause}",
                        database=settings.database,
                        runner=runner,
                    )
                    if count_rows and count_rows[0]:
                        stats["row_count"] = max(0, int(count_rows[0][0] or 0))
                        stats["row_count_kind"] = "exact"
                except (BackupError, TypeError, ValueError):
                    metadata_warnings.append(f"{table}:range_count_unavailable")
            sql = f"SELECT MIN(`{date_column}`), MAX(`{date_column}`) FROM `{table}`"
            if where_clause:
                sql += f" WHERE {where_clause}"
            try:
                date_rows = _run_mysql_query(
                    mysql_tool,
                    defaults_path,
                    sql,
                    database=settings.database,
                    runner=runner,
                )
                if date_rows and len(date_rows[0]) >= 2:
                    stats["date_column"] = date_column
                    stats["min_business_date"] = None if date_rows[0][0] == "NULL" else date_rows[0][0]
                    stats["max_business_date"] = None if date_rows[0][1] == "NULL" else date_rows[0][1]
            except BackupError:
                metadata_warnings.append(f"{table}:date_range_unavailable")
        table_stats[table] = stats

    migration_version = None
    if "schema_migrations" in estimates:
        try:
            migration_rows = _run_mysql_query(
                mysql_tool,
                defaults_path,
                "SELECT MAX(`version`) FROM `schema_migrations`",
                database=settings.database,
                runner=runner,
            )
            if migration_rows and migration_rows[0] and migration_rows[0][0] != "NULL":
                migration_version = migration_rows[0][0]
        except BackupError:
            metadata_warnings.append("schema_migrations:version_unavailable")

    return {
        "available_tables": available_tables,
        "included_data_tables": included,
        "excluded_data_tables": tuple(table for table in available_tables if table not in included),
        "table_stats": table_stats,
        "migration_version": migration_version,
        "metadata_warnings": metadata_warnings,
    }


def create_backup(
    settings: MysqlSettings,
    *,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    retention_days: int = 30,
    keep_minimum: int = 7,
    scope: str = "full",
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    compression: str = "gzip",
    max_total_bytes: int | None = None,
    keep_minimum_per_scope: int = 1,
    timeout_seconds: int = 60 * 60,
    mysqldump_path: str | None = None,
    mysql_path: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    now: datetime | None = None,
    collect_metadata: bool | None = None,
) -> dict[str, Any]:
    _validate_database_name(settings.database)
    scope = str(scope or "full").strip().lower()
    if scope not in BACKUP_SCOPES:
        raise BackupError(f"Unsupported backup scope: {scope}")
    start, end = _normalize_date_range(start_date, end_date)
    if scope != "market-history" and (start or end):
        raise BackupError("start_date/end_date are supported only for market-history backups")
    compression = str(compression or "gzip").strip().lower()
    if compression not in {"gzip", "none"}:
        raise BackupError("compression must be either 'gzip' or 'none'")
    timeout_seconds = max(1, int(timeout_seconds))
    tool = _resolve_tool(mysqldump_path, "MYSQLDUMP_PATH", "mysqldump")
    created_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    backup_id = (
        f"{created_at.strftime('%Y%m%dT%H%M%S')}"
        f"{created_at.microsecond:06d}Z-{scope}"
    )
    backup_dir = Path(backup_dir).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    dump_suffix = ".sql.gz" if compression == "gzip" else ".sql"
    dump_path = backup_dir / f"quantvision_{backup_id}{dump_suffix}"
    manifest_path = backup_dir / f"quantvision_{backup_id}.manifest.json"
    partial_path = dump_path.with_name(f"{dump_path.name}.part")
    sql_partial_path = backup_dir / f"quantvision_{backup_id}.sql.part"

    metadata: dict[str, Any] = {}
    should_collect_metadata = runner is subprocess.run if collect_metadata is None else bool(collect_metadata)
    uncompressed_size_bytes = 0
    try:
        with mysql_defaults_file(settings) as defaults_path:
            if should_collect_metadata:
                mysql_tool = _resolve_tool(mysql_path, "MYSQL_CLIENT_PATH", "mysql")
                metadata = _inspect_source_metadata(
                    settings,
                    mysql_tool=mysql_tool,
                    defaults_path=defaults_path,
                    scope=scope,
                    start_date=start,
                    end_date=end,
                    runner=runner,
                )
            if scope == "critical":
                included_data_tables = tuple(
                    metadata.get("included_data_tables") or CRITICAL_SCOPE_INCLUDED_DATA_TABLES
                )
            elif scope == "market-history":
                included_data_tables = tuple(
                    metadata.get("included_data_tables") or MARKET_HISTORY_TABLES
                )
            else:
                included_data_tables = tuple(metadata.get("included_data_tables") or ("*",))
            if metadata.get("excluded_data_tables"):
                excluded_data_tables = tuple(metadata["excluded_data_tables"])
            elif scope == "critical":
                excluded_data_tables = REBUILDABLE_OR_HISTORY_DATA_TABLES
            else:
                excluded_data_tables = ()

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
                commands = [
                    [*base_command, "--routines", "--events", "--triggers", "--no-data", settings.database],
                    [
                        *base_command,
                        "--no-create-info",
                        "--skip-triggers",
                        settings.database,
                        *included_data_tables,
                    ],
                ]
            elif scope == "market-history":
                commands = [
                    [
                        *base_command,
                        "--routines",
                        "--events",
                        "--triggers",
                        "--no-data",
                        settings.database,
                        *included_data_tables,
                    ]
                ]
                for table in included_data_tables:
                    command = [
                        *base_command,
                        "--no-create-info",
                        "--skip-triggers",
                    ]
                    date_column = MARKET_HISTORY_DATE_COLUMNS[table]
                    where_clause = _history_where_clause(date_column, start, end)
                    if where_clause:
                        command.append(f"--where={where_clause}")
                    command.extend([settings.database, table])
                    commands.append(command)
            else:
                commands = [[*base_command, "--routines", "--events", "--triggers", settings.database]]

            working_path = sql_partial_path if compression == "gzip" else partial_path
            with working_path.open("wb") as output:
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
            if working_path.exists():
                uncompressed_size_bytes = working_path.stat().st_size
            if completed is not None and completed.returncode == 0 and compression == "gzip":
                with sql_partial_path.open("rb") as source, partial_path.open("wb") as raw_compressed:
                    with gzip.GzipFile(
                        filename=dump_path.with_suffix("").name,
                        mode="wb",
                        fileobj=raw_compressed,
                        mtime=0,
                    ) as compressed:
                        shutil.copyfileobj(source, compressed, length=1024 * 1024)
                sql_partial_path.unlink(missing_ok=True)
    except subprocess.TimeoutExpired as exc:
        partial_path.unlink(missing_ok=True)
        sql_partial_path.unlink(missing_ok=True)
        raise BackupError(f"mysqldump timed out after {timeout_seconds} seconds") from exc
    except Exception:
        partial_path.unlink(missing_ok=True)
        sql_partial_path.unlink(missing_ok=True)
        raise
    if completed is None or completed.returncode != 0:
        partial_path.unlink(missing_ok=True)
        sql_partial_path.unlink(missing_ok=True)
        raise BackupError(f"mysqldump failed: {_safe_error(completed.stderr)}")
    if not partial_path.exists() or partial_path.stat().st_size == 0:
        partial_path.unlink(missing_ok=True)
        sql_partial_path.unlink(missing_ok=True)
        raise BackupError("mysqldump produced an empty backup")

    partial_path.replace(dump_path)
    table_stats = dict(metadata.get("table_stats") or {})
    min_dates = [
        str(item["min_business_date"])
        for item in table_stats.values()
        if item.get("min_business_date")
    ]
    max_dates = [
        str(item["max_business_date"])
        for item in table_stats.values()
        if item.get("max_business_date")
    ]
    manifest = {
        "format_version": BACKUP_FORMAT_VERSION,
        "schema_version": metadata.get("migration_version"),
        "backup_id": backup_id,
        "created_at": created_at.isoformat(),
        "verified_at": created_at.isoformat(),
        "scope": scope,
        "data_class": "A" if scope == "critical" else ("B/C" if scope == "market-history" else "A/B/C"),
        "included_data_tables": list(included_data_tables),
        "excluded_data_tables": list(excluded_data_tables),
        "business_date_range": {
            "requested_start": start.isoformat() if start else None,
            "requested_end": end.isoformat() if end else None,
            "min": min(min_dates) if min_dates else None,
            "max": max(max_dates) if max_dates else None,
        },
        "table_stats": table_stats,
        "metadata_warnings": list(metadata.get("metadata_warnings") or []),
        "source": {
            "host": settings.host,
            "port": settings.port,
            "database": settings.database,
            "charset": settings.charset,
        },
        "dump_file": dump_path.name,
        "compression": compression,
        "size_bytes": dump_path.stat().st_size,
        "compressed_size_bytes": dump_path.stat().st_size,
        "uncompressed_size_bytes": uncompressed_size_bytes,
        "sha256": sha256_file(dump_path),
        "rpo_target_hours": 24 if scope == "critical" else (168 if scope == "market-history" else None),
        "rto_target_minutes": 60 if scope == "critical" else None,
    }
    temporary_manifest = manifest_path.with_suffix(".json.part")
    temporary_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_manifest.replace(manifest_path)
    try:
        verify_backup(manifest_path)
    except BackupError:
        dump_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise
    removed = prune_backups(
        backup_dir,
        retention_days=max(0, int(retention_days)),
        keep_minimum=max(1, int(keep_minimum)),
        keep_minimum_per_scope=max(1, int(keep_minimum_per_scope)),
        max_total_bytes=max_total_bytes,
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
        manifest.get("format_version") in SUPPORTED_BACKUP_FORMAT_VERSIONS
        and dump_name
        and dump_name == manifest.get("dump_file")
        and size_bytes == expected_size
        and manifest.get("sha256")
    )
    compression = str(
        manifest.get("compression") or ("gzip" if dump_name.endswith(".gz") else "none")
    )
    if structurally_valid and compression == "gzip":
        try:
            with gzip.open(dump_path, "rb") as handle:
                handle.read(1)
        except (OSError, EOFError):
            structurally_valid = False
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
        "compression": compression,
        "business_date_range": manifest.get("business_date_range"),
        "included_data_tables": manifest.get("included_data_tables") or [],
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
    if manifest.get("format_version") not in SUPPORTED_BACKUP_FORMAT_VERSIONS:
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
    compression = str(manifest.get("compression") or ("gzip" if dump_name.endswith(".gz") else "none"))
    if compression not in {"gzip", "none"}:
        raise BackupError("Unsupported backup compression")
    if compression == "gzip":
        try:
            with gzip.open(dump_path, "rb") as handle:
                uncompressed_size = 0
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    uncompressed_size += len(chunk)
        except (OSError, EOFError) as exc:
            raise BackupError("Backup gzip stream is corrupted") from exc
        expected_uncompressed_size = manifest.get("uncompressed_size_bytes")
        if (
            expected_uncompressed_size is not None
            and uncompressed_size != int(expected_uncompressed_size)
        ):
            raise BackupError("Backup uncompressed size does not match manifest")
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
    keep_minimum_per_scope: int = 1,
    max_total_bytes: int | None = None,
    now: datetime | None = None,
) -> list[str]:
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = reference - timedelta(days=max(0, retention_days))
    root = Path(backup_dir).resolve()
    records: list[dict[str, Any]] = []
    for manifest_path in root.glob("quantvision_*.manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            created_at = datetime.fromisoformat(str(manifest["created_at"]))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            dump_name = Path(str(manifest.get("dump_file") or "")).name
            dump_path = (root / dump_name).resolve()
            expected_size = int(manifest.get("size_bytes") or -1)
            healthy = bool(
                dump_name
                and dump_path.parent == root
                and dump_path.is_file()
                and dump_path.stat().st_size == expected_size
                and manifest.get("sha256")
            )
            compression = str(
                manifest.get("compression") or ("gzip" if dump_name.endswith(".gz") else "none")
            )
            if healthy and compression == "gzip":
                try:
                    with gzip.open(dump_path, "rb") as handle:
                        handle.read(1)
                except (OSError, EOFError):
                    healthy = False
            records.append(
                {
                    "created_at": created_at.astimezone(timezone.utc),
                    "manifest_path": manifest_path,
                    "dump_path": dump_path,
                    "manifest": manifest,
                    "scope": str(manifest.get("scope") or "full").lower(),
                    "size_bytes": max(0, expected_size),
                    "healthy": healthy,
                }
            )
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            continue
    records.sort(key=lambda item: item["created_at"], reverse=True)

    healthy_records = [record for record in records if record["healthy"]]
    protected: set[Path] = {
        record["manifest_path"]
        for record in healthy_records[: max(1, int(keep_minimum))]
    }
    scope_minimum = max(1, int(keep_minimum_per_scope))
    scopes = {record["scope"] for record in healthy_records}
    for scope in scopes:
        protected.update(
            record["manifest_path"]
            for record in [item for item in healthy_records if item["scope"] == scope][:scope_minimum]
        )

    removed: list[str] = []

    def remove_record(record: dict[str, Any]) -> None:
        if record["manifest_path"] in protected or not record["healthy"]:
            return
        record["dump_path"].unlink(missing_ok=True)
        record["manifest_path"].unlink(missing_ok=True)
        record["removed"] = True
        removed.append(
            str(record["manifest"].get("backup_id") or record["manifest_path"].stem)
        )

    for record in healthy_records:
        if record["created_at"] < cutoff:
            remove_record(record)

    if max_total_bytes is not None:
        byte_limit = max(0, int(max_total_bytes))
        remaining_bytes = sum(
            record["size_bytes"]
            for record in healthy_records
            if not record.get("removed")
        )
        for record in reversed(healthy_records):
            if remaining_bytes <= byte_limit:
                break
            if record["manifest_path"] in protected or record.get("removed"):
                continue
            remove_record(record)
            if record.get("removed"):
                remaining_bytes -= record["size_bytes"]
    return removed


def verify_restored_database(
    settings: MysqlSettings,
    manifest: Mapping[str, Any],
    *,
    target_database: str,
    mysql_path: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    """Validate restored structure and aggregates without logging private rows."""
    target = _validate_restore_target(target_database)
    tool = _resolve_tool(mysql_path, "MYSQL_CLIENT_PATH", "mysql")
    scope = str(manifest.get("scope") or "full").lower()
    source_database = _validate_database_name(
        str((manifest.get("source") or {}).get("database") or settings.database)
    )
    with mysql_defaults_file(settings) as defaults_path:
        table_rows = _run_mysql_query(
            tool,
            defaults_path,
            (
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_SCHEMA='{target}' AND TABLE_TYPE='BASE TABLE' "
                "ORDER BY TABLE_NAME"
            ),
            runner=runner,
        )
        restored_tables = {row[0] for row in table_rows if row}
        missing_core_tables = [
            table
            for table in CORE_RESTORE_TABLES.get(scope, CORE_RESTORE_TABLES["full"])
            if table not in restored_tables
        ]

        expected_migration = manifest.get("schema_version")
        migration_required = (
            scope in {"critical", "full"}
            or "schema_migrations" in set(manifest.get("included_data_tables") or ())
        )
        migration_matches = not migration_required or expected_migration in (None, "")
        restored_migration = None
        if "schema_migrations" in restored_tables:
            migration_rows = _run_mysql_query(
                tool,
                defaults_path,
                "SELECT MAX(`version`) FROM `schema_migrations`",
                database=target,
                runner=runner,
            )
            if migration_rows and migration_rows[0] and migration_rows[0][0] != "NULL":
                restored_migration = migration_rows[0][0]
            migration_matches = expected_migration in (None, "") or restored_migration == expected_migration

        exact_count_failures: list[str] = []
        date_range_failures: list[str] = []
        for table, stats in (manifest.get("table_stats") or {}).items():
            if table not in restored_tables or not DATABASE_NAME_PATTERN.fullmatch(str(table)):
                continue
            if stats.get("row_count_kind") == "exact":
                count_rows = _run_mysql_query(
                    tool,
                    defaults_path,
                    f"SELECT COUNT(*) FROM `{table}`",
                    database=target,
                    runner=runner,
                )
                actual_count = int(count_rows[0][0]) if count_rows and count_rows[0] else -1
                if actual_count != int(stats.get("row_count") or 0):
                    exact_count_failures.append(str(table))
            date_column = stats.get("date_column")
            if (
                date_column
                and table in MARKET_HISTORY_DATE_COLUMNS
                and date_column == MARKET_HISTORY_DATE_COLUMNS[table]
            ):
                range_rows = _run_mysql_query(
                    tool,
                    defaults_path,
                    f"SELECT MIN(`{date_column}`), MAX(`{date_column}`) FROM `{table}`",
                    database=target,
                    runner=runner,
                )
                actual_min = None
                actual_max = None
                if range_rows and len(range_rows[0]) >= 2:
                    actual_min = None if range_rows[0][0] == "NULL" else range_rows[0][0]
                    actual_max = None if range_rows[0][1] == "NULL" else range_rows[0][1]
                if actual_min != stats.get("min_business_date") or actual_max != stats.get("max_business_date"):
                    date_range_failures.append(str(table))

        asset_tables = [
            table
            for table in ASSET_LEDGER_TABLES
            if table in restored_tables
            and table in set(manifest.get("included_data_tables") or CRITICAL_SCOPE_INCLUDED_DATA_TABLES)
        ]
        asset_checksum_failures: list[str] = []
        for table in asset_tables:
            source_checksum = _run_mysql_query(
                tool,
                defaults_path,
                f"CHECKSUM TABLE `{table}`",
                database=source_database,
                runner=runner,
            )
            target_checksum = _run_mysql_query(
                tool,
                defaults_path,
                f"CHECKSUM TABLE `{table}`",
                database=target,
                runner=runner,
            )
            source_value = source_checksum[0][-1] if source_checksum and source_checksum[0] else None
            target_value = target_checksum[0][-1] if target_checksum and target_checksum[0] else None
            if source_value in (None, "NULL") or source_value != target_value:
                asset_checksum_failures.append(table)

    valid = not (
        missing_core_tables
        or exact_count_failures
        or date_range_failures
        or asset_checksum_failures
        or not migration_matches
    )
    return {
        "valid": valid,
        "scope": scope,
        "target_database": target,
        "core_tables_present": not missing_core_tables,
        "missing_core_tables": missing_core_tables,
        "migration_matches": migration_matches,
        "restored_migration_version": restored_migration,
        "exact_row_counts_match": not exact_count_failures,
        "exact_count_failures": exact_count_failures,
        "date_ranges_match": not date_range_failures,
        "date_range_failures": date_range_failures,
        "asset_overview_rebuildable": bool(asset_tables) and not asset_checksum_failures,
        "asset_checksum_failures": asset_checksum_failures,
    }


def restore_backup(
    settings: MysqlSettings,
    manifest_path: Path,
    *,
    target_database: str,
    allow_existing_target: bool = False,
    allow_source_overwrite: bool = False,
    dry_run: bool = False,
    verify_restore: bool = False,
    mysql_path: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    verification = verify_backup(manifest_path)
    manifest = verification["manifest"]
    requested_target = _validate_database_name(target_database)
    source_database = str((manifest.get("source") or {}).get("database") or "")
    if requested_target == source_database:
        raise BackupError("Refusing to overwrite the source database")
    target = _validate_restore_target(requested_target)
    if dry_run:
        return {
            "dry_run": True,
            "verified": True,
            "source_database": source_database,
            "target_database": target,
            "would_allow_existing_target": bool(allow_existing_target),
            "would_verify_restore": bool(verify_restore),
        }

    tool = _resolve_tool(mysql_path, "MYSQL_CLIENT_PATH", "mysql")
    restore_started = time.perf_counter()
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
        dump_path = Path(verification["dump_path"])
        compression = str(
            manifest.get("compression") or ("gzip" if dump_path.name.endswith(".gz") else "none")
        )
        restore_temp_path: Path | None = None
        try:
            if compression == "gzip":
                temp_handle = tempfile.NamedTemporaryFile(
                    "wb",
                    suffix=".restore.sql",
                    delete=False,
                )
                restore_temp_path = Path(temp_handle.name)
                try:
                    with gzip.open(dump_path, "rb") as compressed_input:
                        shutil.copyfileobj(
                            compressed_input,
                            temp_handle,
                            length=1024 * 1024,
                        )
                finally:
                    temp_handle.close()
                restore_input_path = restore_temp_path
            else:
                restore_input_path = dump_path
            with restore_input_path.open("rb") as dump_input:
                restore_result = runner(
                    [*common, target],
                    stdin=dump_input,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
        finally:
            if restore_temp_path is not None:
                restore_temp_path.unlink(missing_ok=True)
        if restore_result.returncode != 0:
            raise BackupError(f"MySQL restore failed: {_safe_error(restore_result.stderr)}")
    result = {
        "dry_run": False,
        "verified": True,
        "source_database": source_database,
        "target_database": target,
        "restored": True,
        "restore_duration_seconds": round(time.perf_counter() - restore_started, 3),
    }
    if verify_restore:
        post_restore = verify_restored_database(
            settings,
            manifest,
            target_database=target,
            mysql_path=mysql_path,
            runner=runner,
        )
        if not post_restore["valid"]:
            failure_reasons = [
                *post_restore["missing_core_tables"],
                *post_restore["exact_count_failures"],
                *post_restore["date_range_failures"],
                *post_restore["asset_checksum_failures"],
            ]
            if not post_restore["migration_matches"]:
                failure_reasons.append("migration_version")
            raise BackupError(
                "Restore completed but verification failed: "
                + ", ".join(failure_reasons)
            )
        result["post_restore_verification"] = post_restore
    return result


def drop_restore_target(
    settings: MysqlSettings,
    target_database: str,
    *,
    mysql_path: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    """Drop only a schema whose name satisfies the strict restore-drill pattern."""
    target = _validate_restore_target(target_database)
    if target == settings.database:
        raise BackupError("Refusing to drop the source database")
    tool = _resolve_tool(mysql_path, "MYSQL_CLIENT_PATH", "mysql")
    with mysql_defaults_file(settings) as defaults_path:
        _run_mysql_query(
            tool,
            defaults_path,
            f"DROP DATABASE IF EXISTS `{target}`",
            runner=runner,
        )
    return {"dropped": True, "target_database": target}


def run_restore_drill(
    settings: MysqlSettings,
    manifest_path: Path,
    *,
    target_database: str | None = None,
    cleanup: bool = True,
    mysql_path: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    now: datetime | None = None,
) -> dict[str, Any]:
    target = target_database or (
        f"{settings.database}_restore_drill_"
        f"{(now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    target = _validate_restore_target(target)
    result = restore_backup(
        settings,
        manifest_path,
        target_database=target,
        verify_restore=True,
        mysql_path=mysql_path,
        runner=runner,
    )
    cleaned_up = False
    if cleanup:
        drop_restore_target(
            settings,
            target,
            mysql_path=mysql_path,
            runner=runner,
        )
        cleaned_up = True
    return {
        **result,
        "drill": True,
        "cleaned_up": cleaned_up,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Create and verify a MySQL backup")
    backup_parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    backup_parser.add_argument("--retention-days", type=int, default=30)
    backup_parser.add_argument("--keep-minimum", type=int, default=7)
    backup_parser.add_argument("--keep-minimum-per-scope", type=int, default=1)
    backup_parser.add_argument("--max-total-bytes", type=int)
    backup_parser.add_argument("--scope", choices=sorted(BACKUP_SCOPES), default="full")
    backup_parser.add_argument("--start-date")
    backup_parser.add_argument("--end-date")
    backup_parser.add_argument("--compression", choices=("gzip", "none"), default="gzip")
    backup_parser.add_argument("--timeout-seconds", type=int, default=60 * 60)
    backup_parser.add_argument("--mysqldump-path")
    backup_parser.add_argument("--mysql-path")

    verify_parser = subparsers.add_parser("verify", help="Verify a backup manifest and checksum")
    verify_parser.add_argument("manifest", type=Path)

    restore_parser = subparsers.add_parser("restore", help="Restore a verified backup")
    restore_parser.add_argument("manifest", type=Path)
    restore_parser.add_argument("--target-database", required=True)
    restore_parser.add_argument("--allow-existing-target", action="store_true")
    restore_parser.add_argument("--allow-source-overwrite", action="store_true")
    restore_parser.add_argument("--dry-run", action="store_true")
    restore_parser.add_argument("--verify-restore", action="store_true")
    restore_parser.add_argument("--mysql-path")

    drill_parser = subparsers.add_parser(
        "drill",
        help="Restore, verify, and optionally remove a temporary drill schema",
    )
    drill_parser.add_argument("manifest", type=Path)
    drill_parser.add_argument("--target-database")
    drill_parser.add_argument("--keep-target", action="store_true")
    drill_parser.add_argument("--mysql-path")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv(PROJECT_ROOT / ".env")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "backup":
            result = create_backup(
                MysqlSettings.from_env(),
                backup_dir=args.backup_dir,
                retention_days=args.retention_days,
                keep_minimum=args.keep_minimum,
                keep_minimum_per_scope=args.keep_minimum_per_scope,
                max_total_bytes=args.max_total_bytes,
                scope=args.scope,
                start_date=args.start_date,
                end_date=args.end_date,
                compression=args.compression,
                timeout_seconds=args.timeout_seconds,
                mysqldump_path=args.mysqldump_path,
                mysql_path=args.mysql_path,
            )
            verify_backup(Path(result["backup_dir"]) / result["manifest_file"])
        elif args.command == "verify":
            result = verify_backup(args.manifest)
        elif args.command == "restore":
            result = restore_backup(
                MysqlSettings.from_env(),
                args.manifest,
                target_database=args.target_database,
                allow_existing_target=args.allow_existing_target,
                allow_source_overwrite=args.allow_source_overwrite,
                dry_run=args.dry_run,
                verify_restore=args.verify_restore,
                mysql_path=args.mysql_path,
            )
        else:
            result = run_restore_drill(
                MysqlSettings.from_env(),
                args.manifest,
                target_database=args.target_database,
                cleanup=not args.keep_target,
                mysql_path=args.mysql_path,
            )
    except BackupError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
