"""Versioned schema migration registry and pure planning helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Set

from models.schema import (
    CREATE_TABLE_STATEMENTS,
    REQUIRED_COLUMN_MIGRATIONS,
    REQUIRED_INDEX_MIGRATIONS,
    build_schema_plan,
)


MIGRATION_TABLE = "schema_migrations"
BASELINE_SCHEMA_CHECKSUM = "f935b31f6cc21b27ba44c87c6cf95b1c135b428cfa3cd687fe59b2fcf7fa447b"
ASSET_IMPORT_DEDUPE_CHECKSUM = "9790c8b4e2025cfa99df6426c8988c92010b60e47bcf453351e8caa3b7bd08ab"
CREATE_MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `schema_migrations` (
    `version` VARCHAR(64) NOT NULL,
    `description` VARCHAR(255) NOT NULL,
    `checksum` CHAR(64) NOT NULL,
    `statement_count` INT NOT NULL DEFAULT 0,
    `applied_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""".strip()


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SchemaState:
    tables: Set[str]
    columns: Dict[str, Set[str]]
    indexes: Dict[str, Set[str]]


@dataclass(frozen=True)
class MigrationSpec:
    version: str
    description: str
    checksum: str
    planner: Callable[[SchemaState], List[str]]


def _schema_definition_checksum() -> str:
    payload = {
        "tables": CREATE_TABLE_STATEMENTS,
        "columns": REQUIRED_COLUMN_MIGRATIONS,
        "indexes": REQUIRED_INDEX_MIGRATIONS,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _baseline_planner(state: SchemaState) -> List[str]:
    return build_schema_plan(state.tables, state.columns, state.indexes)


ASSET_IMPORT_DEDUPE_SQL = {
    "asset_trade_ledger": {
        "column": """
            ALTER TABLE `asset_trade_ledger`
            ADD COLUMN `import_key` CHAR(64) NULL AFTER `source`
        """.strip(),
        "index": """
            ALTER TABLE `asset_trade_ledger`
            ADD UNIQUE INDEX `uq_asset_trade_ledger_owner_import_key` (`owner_id`, `import_key`)
        """.strip(),
    },
    "asset_cash_ledger": {
        "column": """
            ALTER TABLE `asset_cash_ledger`
            ADD COLUMN `import_key` CHAR(64) NULL AFTER `source`
        """.strip(),
        "index": """
            ALTER TABLE `asset_cash_ledger`
            ADD UNIQUE INDEX `uq_asset_cash_ledger_owner_import_key` (`owner_id`, `import_key`)
        """.strip(),
    },
}


def _asset_import_dedupe_checksum() -> str:
    encoded = json.dumps(ASSET_IMPORT_DEDUPE_SQL, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _asset_import_dedupe_planner(state: SchemaState) -> List[str]:
    statements: list[str] = []
    for table_name, definitions in ASSET_IMPORT_DEDUPE_SQL.items():
        # On a new database the baseline table is created earlier in the same
        # apply operation, so absent tables still need their follow-up ALTERs.
        if table_name not in state.tables or "import_key" not in state.columns.get(table_name, set()):
            statements.append(definitions["column"])
        index_name = f"uq_{table_name}_owner_import_key"
        if table_name not in state.tables or index_name not in state.indexes.get(table_name, set()):
            statements.append(definitions["index"])
    return statements


# When desired schema definitions change, add a new MigrationSpec instead of
# editing the baseline version or its frozen checksum. The helper above can be
# used to calculate the checksum for a newly introduced schema snapshot.
MIGRATIONS: tuple[MigrationSpec, ...] = (
    MigrationSpec(
        version="20260722_0001",
        description="Baseline QuantVision schema",
        checksum=BASELINE_SCHEMA_CHECKSUM,
        planner=_baseline_planner,
    ),
    MigrationSpec(
        version="20260722_0002",
        description="Add durable asset CSV import deduplication keys",
        checksum=ASSET_IMPORT_DEDUPE_CHECKSUM,
        planner=_asset_import_dedupe_planner,
    ),
)


def normalize_applied_migrations(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("version")): dict(row)
        for row in rows
        if row.get("version")
    }


def build_versioned_migration_plan(
    state: SchemaState,
    applied_rows: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    applied = normalize_applied_migrations(applied_rows)
    pending: list[dict[str, Any]] = []
    applied_versions: list[str] = []
    for migration in MIGRATIONS:
        record = applied.get(migration.version)
        if record:
            if str(record.get("checksum") or "") != migration.checksum:
                raise MigrationError(
                    f"Migration checksum drift detected for {migration.version}; "
                    "create a new migration version instead of editing an applied migration"
                )
            applied_versions.append(migration.version)
            continue
        statements = migration.planner(state)
        pending.append(
            {
                "version": migration.version,
                "description": migration.description,
                "checksum": migration.checksum,
                "statements": statements,
                "statement_count": len(statements),
            }
        )
    known_versions = {migration.version for migration in MIGRATIONS}
    unknown_versions = sorted(version for version in applied if version not in known_versions)
    return {
        "current_version": MIGRATIONS[-1].version if MIGRATIONS else None,
        "applied_versions": applied_versions,
        "unknown_applied_versions": unknown_versions,
        "pending": pending,
        "pending_count": len(pending),
        "statement_count": sum(item["statement_count"] for item in pending),
        "up_to_date": not pending and not unknown_versions,
    }
