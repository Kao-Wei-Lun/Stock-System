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
ASSET_IMPORT_BATCH_CHECKSUM = "645c3c38c721ffdfa82378bc21adea4fe480de2b3a197b53ef1dac8d85e9e002"
PAPER_MARGIN_RESILIENCE_CHECKSUM = "9f366ed311d7f59bbc699c266214e86018bb6ed9bbcbe6eba237654177decae5"
STORAGE_LIFECYCLE_CHECKSUM = "d9b063a6d7ed3066a72f5aacbce062455ec0107cfccd433f6ef785c316c2869d"
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


ASSET_IMPORT_BATCH_SQL = {
    "create_table": """
        CREATE TABLE IF NOT EXISTS `asset_import_batches` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT UNSIGNED NOT NULL,
            `import_type` VARCHAR(32) NOT NULL,
            `source_name` VARCHAR(255) NULL,
            `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
            `row_count` INT NOT NULL DEFAULT 0,
            `created_count` INT NOT NULL DEFAULT 0,
            `skipped_count` INT NOT NULL DEFAULT 0,
            `error_count` INT NOT NULL DEFAULT 0,
            `metadata_json` LONGTEXT NULL,
            `error_message` TEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `committed_at` TIMESTAMP NULL,
            `rolled_back_at` TIMESTAMP NULL,
            PRIMARY KEY (`id`),
            KEY `idx_asset_import_batches_owner_created` (`owner_id`, `created_at`),
            KEY `idx_asset_import_batches_owner_status` (`owner_id`, `status`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """.strip(),
    "trade_column": "ALTER TABLE `asset_trade_ledger` ADD COLUMN `import_batch_id` BIGINT UNSIGNED NULL AFTER `import_key`",
    "trade_index": "ALTER TABLE `asset_trade_ledger` ADD INDEX `idx_asset_trade_ledger_import_batch` (`owner_id`, `import_batch_id`)",
    "cash_column": "ALTER TABLE `asset_cash_ledger` ADD COLUMN `import_batch_id` BIGINT UNSIGNED NULL AFTER `import_key`",
    "cash_index": "ALTER TABLE `asset_cash_ledger` ADD INDEX `idx_asset_cash_ledger_import_batch` (`owner_id`, `import_batch_id`)",
}


def _asset_import_batch_checksum() -> str:
    encoded = json.dumps(ASSET_IMPORT_BATCH_SQL, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _asset_import_batch_planner(state: SchemaState) -> List[str]:
    statements: list[str] = []
    if "asset_import_batches" not in state.tables:
        statements.append(ASSET_IMPORT_BATCH_SQL["create_table"])
    for table_name, column_key, index_key in (
        ("asset_trade_ledger", "trade_column", "trade_index"),
        ("asset_cash_ledger", "cash_column", "cash_index"),
    ):
        if table_name not in state.tables or "import_batch_id" not in state.columns.get(table_name, set()):
            statements.append(ASSET_IMPORT_BATCH_SQL[column_key])
        index_name = f"idx_{table_name}_import_batch"
        if table_name not in state.tables or index_name not in state.indexes.get(table_name, set()):
            statements.append(ASSET_IMPORT_BATCH_SQL[index_key])
    return statements


PAPER_MARGIN_RESILIENCE_SQL = {
    "margin_last_attempt_at": """
        ALTER TABLE `paper_trading_accounts`
        ADD COLUMN `margin_last_attempt_at` DATETIME NULL AFTER `margin_sync_error`
    """.strip(),
    "margin_last_success_at": """
        ALTER TABLE `paper_trading_accounts`
        ADD COLUMN `margin_last_success_at` DATETIME NULL AFTER `margin_last_attempt_at`
    """.strip(),
    "margin_last_error": """
        ALTER TABLE `paper_trading_accounts`
        ADD COLUMN `margin_last_error` TEXT NULL AFTER `margin_last_success_at`
    """.strip(),
    "margin_error_category": """
        ALTER TABLE `paper_trading_accounts`
        ADD COLUMN `margin_error_category` VARCHAR(64) NULL AFTER `margin_last_error`
    """.strip(),
    "margin_next_retry_at": """
        ALTER TABLE `paper_trading_accounts`
        ADD COLUMN `margin_next_retry_at` DATETIME NULL AFTER `margin_error_category`
    """.strip(),
}


def _paper_margin_resilience_checksum() -> str:
    encoded = json.dumps(
        PAPER_MARGIN_RESILIENCE_SQL,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _paper_margin_resilience_planner(state: SchemaState) -> List[str]:
    table_name = "paper_trading_accounts"
    present = state.columns.get(table_name, set())
    if table_name not in state.tables:
        return list(PAPER_MARGIN_RESILIENCE_SQL.values())
    return [
        statement
        for column, statement in PAPER_MARGIN_RESILIENCE_SQL.items()
        if column not in present
    ]


STORAGE_LIFECYCLE_SQL = {
    "taiwan_chip_branch_archives": """
        CREATE TABLE IF NOT EXISTS `taiwan_chip_branch_archives` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `snapshot_date` DATE NOT NULL,
            `source` VARCHAR(128) NOT NULL,
            `archive_format` VARCHAR(32) NOT NULL DEFAULT 'gzip_jsonl_v1',
            `payload_blob` LONGBLOB NOT NULL,
            `payload_sha256` CHAR(64) NOT NULL,
            `source_row_count` BIGINT NOT NULL,
            `original_size_bytes` BIGINT NOT NULL,
            `compressed_size_bytes` BIGINT NOT NULL,
            `min_source_id` BIGINT NULL,
            `max_source_id` BIGINT NULL,
            `backup_id` VARCHAR(128) NOT NULL,
            `status` VARCHAR(32) NOT NULL DEFAULT 'archived',
            `archived_at` DATETIME NOT NULL,
            `cleanup_eligible_at` DATETIME NOT NULL,
            `cleaned_at` DATETIME NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_chip_branch_archive_date_source` (`snapshot_date`, `source`),
            KEY `idx_chip_branch_archive_cleanup` (`status`, `cleanup_eligible_at`, `snapshot_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """.strip(),
    "sync_log_daily_summary": """
        CREATE TABLE IF NOT EXISTS `sync_log_daily_summary` (
            `summary_date` DATE NOT NULL,
            `ticker` VARCHAR(32) NOT NULL,
            `status` VARCHAR(32) NOT NULL,
            `entry_count` BIGINT NOT NULL,
            `rows_added` BIGINT NOT NULL,
            `first_synced_at` DATETIME NULL,
            `last_synced_at` DATETIME NULL,
            `last_error_message` VARCHAR(500) NULL,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`summary_date`, `ticker`, `status`),
            KEY `idx_sync_log_daily_summary_status` (`status`, `summary_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """.strip(),
    "market_payload_archives": """
        CREATE TABLE IF NOT EXISTS `market_payload_archives` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `source_table` VARCHAR(64) NOT NULL,
            `archive_key` VARCHAR(128) NOT NULL,
            `business_date` DATE NOT NULL,
            `archive_format` VARCHAR(32) NOT NULL DEFAULT 'gzip_jsonl_v1',
            `payload_blob` LONGBLOB NOT NULL,
            `payload_sha256` CHAR(64) NOT NULL,
            `source_row_count` BIGINT NOT NULL,
            `original_size_bytes` BIGINT NOT NULL,
            `compressed_size_bytes` BIGINT NOT NULL,
            `backup_id` VARCHAR(128) NOT NULL,
            `status` VARCHAR(32) NOT NULL DEFAULT 'archived',
            `archived_at` DATETIME NOT NULL,
            `cleanup_eligible_at` DATETIME NOT NULL,
            `cleaned_at` DATETIME NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_market_payload_archive_identity`
                (`source_table`, `archive_key`, `business_date`),
            KEY `idx_market_payload_archive_cleanup`
                (`source_table`, `status`, `cleanup_eligible_at`, `business_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """.strip(),
    "storage_maintenance_runs": """
        CREATE TABLE IF NOT EXISTS `storage_maintenance_runs` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `action` VARCHAR(64) NOT NULL,
            `source_table` VARCHAR(64) NULL,
            `cutoff_date` DATE NULL,
            `status` VARCHAR(32) NOT NULL,
            `is_dry_run` TINYINT NOT NULL DEFAULT 1,
            `backup_id` VARCHAR(128) NULL,
            `batch_size` INT NOT NULL DEFAULT 0,
            `processed_rows` BIGINT NOT NULL DEFAULT 0,
            `archived_rows` BIGINT NOT NULL DEFAULT 0,
            `cleaned_rows` BIGINT NOT NULL DEFAULT 0,
            `cursor_json` LONGTEXT NULL,
            `result_json` LONGTEXT NULL,
            `last_error` TEXT NULL,
            `started_at` DATETIME NOT NULL,
            `completed_at` DATETIME NULL,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_storage_maintenance_runs_status` (`status`, `updated_at`),
            KEY `idx_storage_maintenance_runs_table` (`source_table`, `action`, `started_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """.strip(),
}
STORAGE_LIFECYCLE_NEWS_SQL = {
    "canonical_url_hash": """
        ALTER TABLE `news_articles`
        ADD COLUMN `canonical_url_hash` CHAR(64) NULL AFTER `url`
    """.strip(),
    "provider_id": """
        ALTER TABLE `news_articles`
        ADD COLUMN `provider_id` VARCHAR(128) NULL AFTER `source`
    """.strip(),
    "canonical_index": """
        ALTER TABLE `news_articles`
        ADD UNIQUE INDEX `uq_news_articles_ticker_canonical`
            (`ticker`, `canonical_url_hash`)
    """.strip(),
    "provider_index": """
        ALTER TABLE `news_articles`
        ADD INDEX `idx_news_articles_source_provider`
            (`source`, `provider_id`)
    """.strip(),
}


def _storage_lifecycle_checksum() -> str:
    encoded = json.dumps(
        {
            "tables": STORAGE_LIFECYCLE_SQL,
            "news": STORAGE_LIFECYCLE_NEWS_SQL,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _storage_lifecycle_planner(state: SchemaState) -> List[str]:
    statements = [
        statement
        for table_name, statement in STORAGE_LIFECYCLE_SQL.items()
        if table_name not in state.tables
    ]
    if "news_articles" not in state.tables:
        statements.extend(STORAGE_LIFECYCLE_NEWS_SQL.values())
        return statements
    news_columns = state.columns.get("news_articles", set())
    news_indexes = state.indexes.get("news_articles", set())
    if "canonical_url_hash" not in news_columns:
        statements.append(STORAGE_LIFECYCLE_NEWS_SQL["canonical_url_hash"])
    if "provider_id" not in news_columns:
        statements.append(STORAGE_LIFECYCLE_NEWS_SQL["provider_id"])
    if "uq_news_articles_ticker_canonical" not in news_indexes:
        statements.append(STORAGE_LIFECYCLE_NEWS_SQL["canonical_index"])
    if "idx_news_articles_source_provider" not in news_indexes:
        statements.append(STORAGE_LIFECYCLE_NEWS_SQL["provider_index"])
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
    MigrationSpec(
        version="20260722_0003",
        description="Add atomic asset import batches and rollback audit",
        checksum=ASSET_IMPORT_BATCH_CHECKSUM,
        planner=_asset_import_batch_planner,
    ),
    MigrationSpec(
        version="20260723_0001",
        description="Add resilient paper trading margin refresh metadata",
        checksum=PAPER_MARGIN_RESILIENCE_CHECKSUM,
        planner=_paper_margin_resilience_planner,
    ),
    MigrationSpec(
        version="20260723_0002",
        description="Add bounded storage lifecycle archive metadata",
        checksum=STORAGE_LIFECYCLE_CHECKSUM,
        planner=_storage_lifecycle_planner,
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
