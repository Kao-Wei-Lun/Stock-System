"""Read-only storage lifecycle audit and archive planning.

The module deliberately keeps audit/planning separate from mutation.  Phase 20
maintenance commands must produce and review a dry-run before an archive or
cleanup executor is allowed to change data.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from dotenv import load_dotenv
from logging_config import configure_logging

from mysql_backup import (
    DEFAULT_BACKUP_DIR,
    BackupError,
    MysqlSettings,
    latest_backup_status,
    mysql_defaults_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDITED_TABLES = (
    "ohlcv",
    "taiwan_chip_snapshots",
    "sync_log",
    "news_articles",
    "fubon_market_snapshots",
)
PROTECTED_TABLE_PREFIXES = ("asset_", "paper_trading_")
IDENTIFIER_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


class StorageLifecycleError(RuntimeError):
    pass


@dataclass(frozen=True)
class LifecyclePolicy:
    table: str
    date_column: str
    online_days: int | None
    action: str
    payload_column: str | None = None
    data_class: str = "C"
    auto_cleanup: bool = False


POLICIES: tuple[LifecyclePolicy, ...] = (
    LifecyclePolicy(
        table="ohlcv",
        date_column="date",
        online_days=None,
        action="retain_online",
        data_class="C",
        auto_cleanup=False,
    ),
    LifecyclePolicy(
        table="taiwan_chip_snapshots",
        date_column="snapshot_date",
        online_days=730,
        action="archive_branch_payload",
        payload_column="branch_payload_json",
        data_class="B",
        auto_cleanup=False,
    ),
    LifecyclePolicy(
        table="sync_log",
        date_column="synced_at",
        online_days=90,
        action="summarize_then_archive_rows",
        data_class="A",
        auto_cleanup=False,
    ),
    LifecyclePolicy(
        table="news_articles",
        date_column="published_at",
        online_days=365,
        action="clear_archived_payload_only",
        payload_column="payload_json",
        data_class="C",
        auto_cleanup=False,
    ),
    LifecyclePolicy(
        table="fubon_market_snapshots",
        date_column="snapshot_date",
        online_days=365,
        action="archive_compressed_payload",
        payload_column="payload_json",
        data_class="B",
        auto_cleanup=False,
    ),
)


class QueryExecutor(Protocol):
    def query(self, sql: str, *, database: str | None = None) -> list[list[str]]:
        ...


def _validate_identifier(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or any(char not in IDENTIFIER_CHARS for char in normalized):
        raise StorageLifecycleError(f"Unsafe SQL identifier: {value!r}")
    return normalized


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return default


def _parse_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "", "NULL") else None
    except (TypeError, ValueError):
        return None


def _cutoff_date(policy: LifecyclePolicy, today: date) -> date | None:
    return today - timedelta(days=policy.online_days) if policy.online_days is not None else None


class MysqlCliQueryExecutor:
    def __init__(
        self,
        settings: MysqlSettings,
        *,
        mysql_path: str | None = None,
        timeout_seconds: int = 120,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ):
        candidate = mysql_path or os.environ.get("MYSQL_CLIENT_PATH") or "mysql"
        resolved = shutil.which(candidate)
        if not resolved and Path(candidate).is_file():
            resolved = str(Path(candidate).resolve())
        if not resolved and os.name == "nt":
            from mysql_backup import _resolve_tool

            try:
                resolved = _resolve_tool(mysql_path, "MYSQL_CLIENT_PATH", "mysql")
            except BackupError as exc:
                raise StorageLifecycleError(str(exc)) from exc
        if not resolved:
            raise StorageLifecycleError("Unable to find mysql client")
        self._settings = settings
        self._tool = resolved
        self._timeout_seconds = max(1, int(timeout_seconds))
        self._runner = runner

    def query(self, sql: str, *, database: str | None = None) -> list[list[str]]:
        with mysql_defaults_file(self._settings) as defaults_path:
            command = [
                self._tool,
                f"--defaults-extra-file={defaults_path}",
                "--batch",
                "--skip-column-names",
            ]
            if database:
                command.append(_validate_identifier(database))
            command.append(f"--execute={sql}")
            try:
                result = self._runner(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=self._timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise StorageLifecycleError(
                    f"Storage audit query timed out after {self._timeout_seconds} seconds"
                ) from exc
        if result.returncode != 0:
            stderr = (
                result.stderr.decode("utf-8", errors="replace")
                if isinstance(result.stderr, bytes)
                else str(result.stderr or "")
            )
            raise StorageLifecycleError(stderr.strip()[:500] or "MySQL audit query failed")
        stdout = (
            result.stdout.decode("utf-8", errors="replace")
            if isinstance(result.stdout, bytes)
            else str(result.stdout or "")
        )
        return [line.split("\t") for line in stdout.splitlines() if line.strip()]


class StorageLifecycleAuditor:
    def __init__(
        self,
        executor: QueryExecutor,
        *,
        database: str,
        policies: tuple[LifecyclePolicy, ...] = POLICIES,
        max_runtime_seconds: int = 300,
    ):
        self._executor = executor
        self._database = _validate_identifier(database)
        self._policies = policies
        self._max_runtime_seconds = max(1, int(max_runtime_seconds))

    def _ensure_runtime(self, started: float) -> None:
        if time.monotonic() - started > self._max_runtime_seconds:
            raise StorageLifecycleError(
                f"Storage audit exceeded {self._max_runtime_seconds} seconds"
            )

    def audit(self, *, today: date | None = None) -> dict[str, Any]:
        reference_date = today or datetime.now(timezone.utc).date()
        started = time.monotonic()
        table_names = tuple(policy.table for policy in self._policies)
        quoted_names = ", ".join(f"'{name}'" for name in table_names)
        size_rows = self._executor.query(
            """
            SELECT
                `TABLE_NAME`,
                COALESCE(`TABLE_ROWS`, 0),
                COALESCE(`DATA_LENGTH`, 0),
                COALESCE(`INDEX_LENGTH`, 0),
                COALESCE(`AVG_ROW_LENGTH`, 0)
            FROM `INFORMATION_SCHEMA`.`TABLES`
            WHERE `TABLE_SCHEMA`='%s'
              AND `TABLE_NAME` IN (%s)
            ORDER BY `TABLE_NAME`
            """
            % (self._database, quoted_names)
        )
        size_by_table = {
            row[0]: {
                "estimated_rows": _parse_int(row[1]) if len(row) > 1 else 0,
                "data_bytes": _parse_int(row[2]) if len(row) > 2 else 0,
                "index_bytes": _parse_int(row[3]) if len(row) > 3 else 0,
                "average_row_bytes": _parse_int(row[4]) if len(row) > 4 else 0,
            }
            for row in size_rows
            if row and row[0] in table_names
        }

        table_audits: list[dict[str, Any]] = []
        for policy in self._policies:
            self._ensure_runtime(started)
            table = _validate_identifier(policy.table)
            date_column = _validate_identifier(policy.date_column)
            range_rows = self._executor.query(
                f"SELECT MIN(`{date_column}`), MAX(`{date_column}`) FROM `{table}`",
                database=self._database,
            )
            min_date = None
            max_date = None
            if range_rows and len(range_rows[0]) >= 2:
                min_date = None if range_rows[0][0] == "NULL" else range_rows[0][0]
                max_date = None if range_rows[0][1] == "NULL" else range_rows[0][1]

            recent_start = reference_date - timedelta(days=365)
            monthly_rows = self._executor.query(
                (
                    f"SELECT DATE_FORMAT(`{date_column}`, '%Y-%m'), COUNT(*) "
                    f"FROM `{table}` "
                    f"WHERE `{date_column}` >= '{recent_start.isoformat()}' "
                    f"GROUP BY DATE_FORMAT(`{date_column}`, '%Y-%m') "
                    "ORDER BY 1"
                ),
                database=self._database,
            )
            monthly_counts = {
                row[0]: _parse_int(row[1])
                for row in monthly_rows
                if len(row) >= 2
            }

            null_ratio = None
            average_payload_bytes = None
            if policy.payload_column:
                payload_column = _validate_identifier(policy.payload_column)
                sample_rows = self._executor.query(
                    (
                        "SELECT COUNT(*), "
                        f"SUM(`{payload_column}` IS NULL), "
                        f"AVG(OCTET_LENGTH(`{payload_column}`)) "
                        "FROM ("
                        f"SELECT `{payload_column}` FROM `{table}` "
                        f"ORDER BY `{date_column}` DESC LIMIT 10000"
                        ") AS `recent_sample`"
                    ),
                    database=self._database,
                )
                if sample_rows and len(sample_rows[0]) >= 3:
                    sample_count = _parse_int(sample_rows[0][0])
                    null_count = _parse_int(sample_rows[0][1])
                    null_ratio = round(null_count / sample_count, 6) if sample_count else None
                    average_payload_bytes = _parse_float(sample_rows[0][2])

            cutoff = _cutoff_date(policy, reference_date)
            candidate_rows = 0
            if cutoff:
                count_rows = self._executor.query(
                    f"SELECT COUNT(*) FROM `{table}` WHERE `{date_column}` < '{cutoff.isoformat()}'",
                    database=self._database,
                )
                if count_rows and count_rows[0]:
                    candidate_rows = _parse_int(count_rows[0][0])

            size_info = size_by_table.get(
                table,
                {
                    "estimated_rows": 0,
                    "data_bytes": 0,
                    "index_bytes": 0,
                    "average_row_bytes": 0,
                },
            )
            estimated_candidate_bytes = int(
                candidate_rows
                * (
                    average_payload_bytes
                    if average_payload_bytes is not None
                    else size_info["average_row_bytes"]
                )
            )
            table_audits.append(
                {
                    "table": table,
                    "data_class": policy.data_class,
                    "policy": asdict(policy),
                    **size_info,
                    "min_business_date": min_date,
                    "max_business_date": max_date,
                    "monthly_rows_last_12_months": monthly_counts,
                    "payload_null_ratio_sample": null_ratio,
                    "average_payload_bytes_sample": (
                        round(average_payload_bytes, 2)
                        if average_payload_bytes is not None
                        else None
                    ),
                    "duplicate_ratio": 0.0,
                    "duplicate_basis": "protected_by_unique_key",
                    "archive_cutoff": cutoff.isoformat() if cutoff else None,
                    "archive_candidate_rows": candidate_rows,
                    "estimated_archive_candidate_bytes": estimated_candidate_bytes,
                }
            )

        return {
            "read_only": True,
            "database": self._database,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "reference_date": reference_date.isoformat(),
            "max_runtime_seconds": self._max_runtime_seconds,
            "duration_seconds": round(time.monotonic() - started, 3),
            "tables": table_audits,
            "protected_prefixes": list(PROTECTED_TABLE_PREFIXES),
        }

    def dry_run(
        self,
        *,
        today: date | None = None,
        backup_dir: Path = DEFAULT_BACKUP_DIR,
    ) -> dict[str, Any]:
        audit = self.audit(today=today)
        history_backup = latest_backup_status(
            backup_dir,
            scope="market-history",
            max_age_hours=24 * 7,
        )
        actions = []
        for item in audit["tables"]:
            policy = item["policy"]
            actions.append(
                {
                    "table": item["table"],
                    "action": policy["action"],
                    "cutoff": item["archive_cutoff"],
                    "candidate_rows": item["archive_candidate_rows"],
                    "estimated_bytes": item["estimated_archive_candidate_bytes"],
                    "would_mutate": False,
                    "auto_cleanup": False,
                    "requires_backup_scope": (
                        "market-history"
                        if policy["data_class"] in {"B", "C"}
                        else "critical"
                    ),
                }
            )
        return {
            "dry_run": True,
            "mutation_allowed": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "audit": audit,
            "backup_gate": {
                "scope": "market-history",
                "healthy": bool(history_backup.get("healthy")),
                "backup_id": history_backup.get("backup_id"),
                "created_at": history_backup.get("created_at"),
                "error": history_backup.get("error"),
            },
            "actions": actions,
            "excluded_tables": [
                "asset_*",
                "paper_trading_*",
            ],
            "next_step": "review_and_record_dry_run_before_archive",
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit", "dry-run"))
    parser.add_argument("--today")
    parser.add_argument("--max-runtime-seconds", type=int, default=300)
    parser.add_argument("--mysql-path")
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv(PROJECT_ROOT / ".env")
    configure_logging(profile="backup", console_enabled=False)
    activity_log = logging.getLogger("backup.lifecycle")
    args = build_parser().parse_args(argv)
    activity_log.info("Storage lifecycle started command=%s", args.command)
    try:
        reference_date = date.fromisoformat(args.today) if args.today else None
        settings = MysqlSettings.from_env()
        executor = MysqlCliQueryExecutor(
            settings,
            mysql_path=args.mysql_path,
            timeout_seconds=min(max(args.max_runtime_seconds, 1), 300),
        )
        auditor = StorageLifecycleAuditor(
            executor,
            database=settings.database,
            max_runtime_seconds=args.max_runtime_seconds,
        )
        result = (
            auditor.audit(today=reference_date)
            if args.command == "audit"
            else auditor.dry_run(today=reference_date, backup_dir=args.backup_dir)
        )
    except (BackupError, StorageLifecycleError, ValueError) as exc:
        activity_log.error(
            "Storage lifecycle failed command=%s category=lifecycle_error message=%s",
            args.command,
            exc,
        )
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    activity_log.info("Storage lifecycle completed command=%s", args.command)
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
