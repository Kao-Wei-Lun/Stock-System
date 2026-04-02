"""
Database layer backed by MySQL.
"""

import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import aiomysql
from dotenv import load_dotenv
from journal_service import build_journal_stats, compute_trade_result
from pymysql.err import OperationalError

from display_name_resolver import resolve_display_name

log = logging.getLogger(__name__)

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "quantvision")
MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4")

DEFAULT_OWNER_ID = 1
DEFAULT_OWNER_USERNAME = "local-owner"
DEFAULT_OWNER_DISPLAY_NAME = "Local Owner"
DEFAULT_OWNER_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Taipei").strip() or "Asia/Taipei"

CREATE_TABLE_STATEMENTS = {
    "ohlcv": """
        CREATE TABLE `ohlcv` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `ticker` VARCHAR(32) NOT NULL,
            `date` VARCHAR(32) NOT NULL,
            `interval` VARCHAR(16) NOT NULL DEFAULT '1d',
            `open` DOUBLE NOT NULL,
            `high` DOUBLE NOT NULL,
            `low` DOUBLE NOT NULL,
            `close` DOUBLE NOT NULL,
            `volume` BIGINT NOT NULL DEFAULT 0,
            `adj_close` DOUBLE NULL,
            `source` VARCHAR(64) NOT NULL DEFAULT 'yahoo_finance',
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_ohlcv_ticker_date_interval` (`ticker`, `date`, `interval`),
            KEY `idx_ohlcv_ticker_date` (`ticker`, `interval`, `date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "stock_info": """
        CREATE TABLE `stock_info` (
            `ticker` VARCHAR(32) NOT NULL,
            `name` VARCHAR(255) NULL,
            `sector` VARCHAR(255) NULL,
            `industry` VARCHAR(255) NULL,
            `market_cap` BIGINT NULL,
            `pe_ratio` DOUBLE NULL,
            `dividend_yield` DOUBLE NULL,
            `week_52_high` DOUBLE NULL,
            `week_52_low` DOUBLE NULL,
            `avg_volume` BIGINT NULL,
            `description` TEXT NULL,
            `currency` VARCHAR(16) NULL,
            `exchange` VARCHAR(32) NULL,
            `country` VARCHAR(64) NULL,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`ticker`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "sync_log": """
        CREATE TABLE `sync_log` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `ticker` VARCHAR(32) NOT NULL,
            `status` VARCHAR(32) NOT NULL,
            `rows_added` BIGINT NOT NULL DEFAULT 0,
            `message` TEXT NULL,
            `synced_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_sync_log_ticker_synced_at` (`ticker`, `synced_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "user_profiles": """
        CREATE TABLE `user_profiles` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `username` VARCHAR(64) NOT NULL,
            `display_name` VARCHAR(128) NOT NULL,
            `timezone` VARCHAR(64) NOT NULL DEFAULT 'Asia/Taipei',
            `is_active` TINYINT NOT NULL DEFAULT 1,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_user_profiles_username` (`username`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "user_preferences": """
        CREATE TABLE `user_preferences` (
            `owner_id` BIGINT NOT NULL,
            `preferences_json` LONGTEXT NOT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`owner_id`),
            CONSTRAINT `fk_user_preferences_owner`
                FOREIGN KEY (`owner_id`) REFERENCES `user_profiles` (`id`)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "workspace_presets": """
        CREATE TABLE `workspace_presets` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL,
            `name` VARCHAR(128) NOT NULL,
            `chart_layout` VARCHAR(32) NOT NULL DEFAULT 'single',
            `active_ticker` VARCHAR(32) NULL,
            `current_period` VARCHAR(16) NOT NULL DEFAULT '1y',
            `current_interval` VARCHAR(16) NOT NULL DEFAULT '1d',
            `workspace_tab` VARCHAR(32) NOT NULL DEFAULT 'chart',
            `comparison_mode` VARCHAR(32) NOT NULL DEFAULT 'percent',
            `payload_json` LONGTEXT NOT NULL,
            `is_default` TINYINT NOT NULL DEFAULT 0,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_workspace_presets_owner_name` (`owner_id`, `name`),
            KEY `idx_workspace_presets_owner_updated` (`owner_id`, `updated_at`),
            CONSTRAINT `fk_workspace_presets_owner`
                FOREIGN KEY (`owner_id`) REFERENCES `user_profiles` (`id`)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "market_quotes_latest": """
        CREATE TABLE `market_quotes_latest` (
            `ticker` VARCHAR(32) NOT NULL,
            `source` VARCHAR(64) NOT NULL,
            `quote_type` VARCHAR(64) NOT NULL DEFAULT 'delayed_snapshot',
            `is_delayed` TINYINT NOT NULL DEFAULT 1,
            `name` VARCHAR(255) NULL,
            `currency` VARCHAR(16) NULL,
            `price` DOUBLE NULL,
            `open` DOUBLE NULL,
            `high` DOUBLE NULL,
            `low` DOUBLE NULL,
            `prev_close` DOUBLE NULL,
            `change_amount` DOUBLE NULL,
            `change_pct` DOUBLE NULL,
            `volume` BIGINT NULL,
            `market_cap` BIGINT NULL,
            `quote_timestamp` DATETIME NULL,
            `payload_json` LONGTEXT NOT NULL,
            `synced_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`ticker`),
            KEY `idx_market_quotes_latest_synced_at` (`synced_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "alerts": """
        CREATE TABLE `alerts` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `name` VARCHAR(128) NULL,
            `ticker` VARCHAR(32) NOT NULL,
            `type` VARCHAR(32) NOT NULL,
            `condition` VARCHAR(32) NOT NULL,
            `value` DOUBLE NULL,
            `value2` DOUBLE NULL,
            `timeframe` VARCHAR(16) NOT NULL DEFAULT '1d',
            `condition_json` LONGTEXT NULL,
            `notification_title` VARCHAR(255) NULL,
            `note` TEXT NULL,
            `active` TINYINT NOT NULL DEFAULT 1,
            `triggered` TINYINT NOT NULL DEFAULT 0,
            `triggered_at` DATETIME NULL,
            `last_evaluated_at` DATETIME NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_alerts_owner_active` (`owner_id`, `active`, `updated_at`),
            KEY `idx_alerts_ticker` (`ticker`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "alert_trigger_logs": """
        CREATE TABLE `alert_trigger_logs` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `alert_id` BIGINT NOT NULL,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `ticker` VARCHAR(32) NOT NULL,
            `trigger_value` DOUBLE NULL,
            `threshold_value` DOUBLE NULL,
            `payload_json` LONGTEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_alert_trigger_logs_alert_id` (`alert_id`, `created_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "notifications": """
        CREATE TABLE `notifications` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `category` VARCHAR(64) NOT NULL DEFAULT 'system',
            `level` VARCHAR(32) NOT NULL DEFAULT 'info',
            `title` VARCHAR(255) NOT NULL,
            `message` TEXT NOT NULL,
            `related_entity_type` VARCHAR(64) NULL,
            `related_entity_id` BIGINT NULL,
            `link_url` VARCHAR(255) NULL,
            `payload_json` LONGTEXT NULL,
            `read_at` DATETIME NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_notifications_owner_created` (`owner_id`, `created_at`),
            KEY `idx_notifications_owner_read` (`owner_id`, `read_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "sync_jobs": """
        CREATE TABLE `sync_jobs` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `job_type` VARCHAR(64) NOT NULL,
            `scope` VARCHAR(128) NULL,
            `status` VARCHAR(32) NOT NULL DEFAULT 'pending',
            `payload_json` LONGTEXT NULL,
            `error_message` TEXT NULL,
            `requested_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `started_at` DATETIME NULL,
            `finished_at` DATETIME NULL,
            PRIMARY KEY (`id`),
            KEY `idx_sync_jobs_status_requested` (`status`, `requested_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "sync_job_logs": """
        CREATE TABLE `sync_job_logs` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `sync_job_id` BIGINT NOT NULL,
            `ticker` VARCHAR(32) NULL,
            `status` VARCHAR(32) NOT NULL,
            `rows_added` BIGINT NOT NULL DEFAULT 0,
            `message` TEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_sync_job_logs_job_created` (`sync_job_id`, `created_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "watchlist_groups": """
        CREATE TABLE `watchlist_groups` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `name` VARCHAR(128) NOT NULL,
            `sort_order` INT NOT NULL DEFAULT 0,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_watchlist_groups_name` (`name`),
            KEY `idx_watchlist_groups_owner_sort` (`owner_id`, `sort_order`, `id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "watchlist_items": """
        CREATE TABLE `watchlist_items` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `group_id` BIGINT NOT NULL,
            `ticker` VARCHAR(32) NOT NULL,
            `tags_json` LONGTEXT NULL,
            `sort_order` INT NOT NULL DEFAULT 0,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_watchlist_items_group_ticker` (`group_id`, `ticker`),
            KEY `idx_watchlist_items_group_order` (`group_id`, `sort_order`, `id`),
            CONSTRAINT `fk_watchlist_items_group`
                FOREIGN KEY (`group_id`) REFERENCES `watchlist_groups` (`id`)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "institutional_snapshots": """
        CREATE TABLE `institutional_snapshots` (
            `resolved_date` DATE NOT NULL,
            `query_date` DATE NOT NULL,
            `payload_json` LONGTEXT NOT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`resolved_date`),
            KEY `idx_institutional_query_date` (`query_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "backtest_runs": """
        CREATE TABLE `backtest_runs` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `ticker` VARCHAR(32) NOT NULL,
            `strategy_key` VARCHAR(64) NOT NULL,
            `strategy_name` VARCHAR(128) NOT NULL,
            `interval` VARCHAR(16) NOT NULL DEFAULT '1d',
            `start_date` DATE NOT NULL,
            `end_date` DATE NOT NULL,
            `initial_capital` DOUBLE NOT NULL,
            `final_equity` DOUBLE NOT NULL,
            `total_return_pct` DOUBLE NOT NULL DEFAULT 0,
            `max_drawdown_pct` DOUBLE NOT NULL DEFAULT 0,
            `sharpe_ratio` DOUBLE NOT NULL DEFAULT 0,
            `trade_count` INT NOT NULL DEFAULT 0,
            `win_rate_pct` DOUBLE NOT NULL DEFAULT 0,
            `bars_count` INT NOT NULL DEFAULT 0,
            `fee_rate` DOUBLE NOT NULL DEFAULT 0,
            `slippage_rate` DOUBLE NOT NULL DEFAULT 0,
            `stop_loss_pct` DOUBLE NULL,
            `take_profit_pct` DOUBLE NULL,
            `position_sizing` VARCHAR(32) NOT NULL DEFAULT 'full_equity',
            `summary_json` LONGTEXT NOT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_backtest_runs_owner_created` (`owner_id`, `created_at`),
            KEY `idx_backtest_runs_ticker_created` (`ticker`, `created_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "backtest_trades": """
        CREATE TABLE `backtest_trades` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `backtest_run_id` BIGINT NOT NULL,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `ticker` VARCHAR(32) NOT NULL,
            `side` VARCHAR(16) NOT NULL DEFAULT 'long',
            `entry_date` DATETIME NOT NULL,
            `entry_price` DOUBLE NOT NULL,
            `exit_date` DATETIME NOT NULL,
            `exit_price` DOUBLE NOT NULL,
            `quantity` DOUBLE NOT NULL,
            `gross_pnl` DOUBLE NOT NULL DEFAULT 0,
            `net_pnl` DOUBLE NOT NULL DEFAULT 0,
            `return_pct` DOUBLE NOT NULL DEFAULT 0,
            `fee_amount` DOUBLE NOT NULL DEFAULT 0,
            `holding_bars` INT NOT NULL DEFAULT 0,
            `exit_reason` VARCHAR(64) NULL,
            `payload_json` LONGTEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_backtest_trades_run_entry` (`backtest_run_id`, `entry_date`),
            CONSTRAINT `fk_backtest_trades_run`
                FOREIGN KEY (`backtest_run_id`) REFERENCES `backtest_runs` (`id`)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "backtest_equity_points": """
        CREATE TABLE `backtest_equity_points` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `backtest_run_id` BIGINT NOT NULL,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `point_date` DATETIME NOT NULL,
            `equity` DOUBLE NOT NULL,
            `cash` DOUBLE NOT NULL,
            `position_qty` DOUBLE NOT NULL DEFAULT 0,
            `close_price` DOUBLE NULL,
            `payload_json` LONGTEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_backtest_equity_points_run_date` (`backtest_run_id`, `point_date`),
            CONSTRAINT `fk_backtest_equity_points_run`
                FOREIGN KEY (`backtest_run_id`) REFERENCES `backtest_runs` (`id`)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "trade_journal_entries": """
        CREATE TABLE `trade_journal_entries` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `ticker` VARCHAR(32) NOT NULL,
            `market` VARCHAR(32) NULL,
            `direction` VARCHAR(16) NOT NULL DEFAULT 'long',
            `strategy_code` VARCHAR(64) NULL,
            `entry_time` DATETIME NOT NULL,
            `entry_price` DOUBLE NOT NULL,
            `exit_time` DATETIME NULL,
            `exit_price` DOUBLE NULL,
            `size` DOUBLE NOT NULL DEFAULT 0,
            `stop_loss` DOUBLE NULL,
            `take_profit` DOUBLE NULL,
            `entry_reason` TEXT NULL,
            `exit_reason` TEXT NULL,
            `emotion_tag` VARCHAR(64) NULL,
            `review_notes` LONGTEXT NULL,
            `result_json` LONGTEXT NOT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_trade_journal_owner_created` (`owner_id`, `created_at`),
            KEY `idx_trade_journal_ticker_entry` (`ticker`, `entry_time`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "trade_journal_tags": """
        CREATE TABLE `trade_journal_tags` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `entry_id` BIGINT NOT NULL,
            `tag` VARCHAR(64) NOT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_trade_journal_tags_entry_tag` (`entry_id`, `tag`),
            KEY `idx_trade_journal_tags_tag` (`tag`),
            CONSTRAINT `fk_trade_journal_tags_entry`
                FOREIGN KEY (`entry_id`) REFERENCES `trade_journal_entries` (`id`)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "trade_journal_attachments": """
        CREATE TABLE `trade_journal_attachments` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `entry_id` BIGINT NOT NULL,
            `file_path` VARCHAR(512) NOT NULL,
            `file_type` VARCHAR(64) NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_trade_journal_attachments_entry` (`entry_id`, `created_at`),
            CONSTRAINT `fk_trade_journal_attachments_entry`
                FOREIGN KEY (`entry_id`) REFERENCES `trade_journal_entries` (`id`)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "market_events": """
        CREATE TABLE `market_events` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `event_type` VARCHAR(64) NOT NULL,
            `market` VARCHAR(32) NULL,
            `ticker` VARCHAR(32) NULL,
            `title` VARCHAR(255) NOT NULL,
            `description` TEXT NULL,
            `event_date` DATE NOT NULL,
            `event_time` DATETIME NULL,
            `importance` VARCHAR(32) NULL,
            `source` VARCHAR(128) NULL,
            `url` VARCHAR(512) NULL,
            `payload_json` LONGTEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_market_events_identity` (`event_type`, `ticker`, `event_date`, `title`),
            KEY `idx_market_events_event_date` (`event_date`, `ticker`),
            KEY `idx_market_events_ticker` (`ticker`, `event_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "news_articles": """
        CREATE TABLE `news_articles` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `ticker` VARCHAR(32) NULL,
            `market` VARCHAR(32) NULL,
            `title` VARCHAR(255) NOT NULL,
            `summary` TEXT NULL,
            `published_at` DATETIME NOT NULL,
            `source` VARCHAR(128) NULL,
            `url` VARCHAR(512) NULL,
            `sentiment` VARCHAR(32) NULL,
            `payload_json` LONGTEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_news_articles_identity` (`ticker`, `published_at`, `title`),
            KEY `idx_news_articles_published_at` (`published_at`, `ticker`),
            KEY `idx_news_articles_ticker` (`ticker`, `published_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "macro_snapshots": """
        CREATE TABLE `macro_snapshots` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `metric_code` VARCHAR(64) NOT NULL,
            `metric_name` VARCHAR(128) NOT NULL,
            `value` DOUBLE NULL,
            `snapshot_date` DATE NOT NULL,
            `source` VARCHAR(128) NULL,
            `payload_json` LONGTEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_macro_snapshots_metric_date` (`metric_code`, `snapshot_date`),
            KEY `idx_macro_snapshots_snapshot_date` (`snapshot_date`, `metric_code`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "taiwan_chip_snapshots": """
        CREATE TABLE `taiwan_chip_snapshots` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `ticker` VARCHAR(32) NOT NULL,
            `market` VARCHAR(32) NULL,
            `snapshot_date` DATE NOT NULL,
            `margin_balance` BIGINT NULL,
            `short_balance` BIGINT NULL,
            `securities_lending_balance` BIGINT NULL,
            `institutional_net_buy_sell` BIGINT NULL,
            `source` VARCHAR(128) NULL,
            `branch_payload_json` JSON NULL,
            `summary_json` JSON NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_taiwan_chip_snapshots_ticker_date` (`ticker`, `snapshot_date`),
            KEY `idx_taiwan_chip_snapshots_ticker` (`ticker`, `snapshot_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "screener_presets": """
        CREATE TABLE `screener_presets` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `name` VARCHAR(128) NOT NULL,
            `description` VARCHAR(512) NULL,
            `filters_json` JSON NOT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_screener_presets_owner_name` (`owner_id`, `name`),
            KEY `idx_screener_presets_owner_updated` (`owner_id`, `updated_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "journal_filter_presets": """
        CREATE TABLE `journal_filter_presets` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `name` VARCHAR(128) NOT NULL,
            `description` VARCHAR(512) NULL,
            `scope` VARCHAR(32) NOT NULL DEFAULT 'ticker',
            `filters_json` JSON NOT NULL,
            `use_count` INT NOT NULL DEFAULT 0,
            `last_used_at` DATETIME NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_journal_filter_presets_owner_name` (`owner_id`, `name`),
            KEY `idx_journal_filter_presets_owner_updated` (`owner_id`, `updated_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
}

REQUIRED_COLUMN_MIGRATIONS = {
    "ohlcv": {
        "source": """
            ALTER TABLE `ohlcv`
            ADD COLUMN `source` VARCHAR(64) NOT NULL DEFAULT 'yahoo_finance' AFTER `adj_close`
        """,
        "updated_at": """
            ALTER TABLE `ohlcv`
            ADD COLUMN `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            AFTER `created_at`
        """,
    },
    "watchlist_groups": {
        "owner_id": """
            ALTER TABLE `watchlist_groups`
            ADD COLUMN `owner_id` BIGINT NOT NULL DEFAULT 1 AFTER `id`
        """,
    },
    "watchlist_items": {
        "tags_json": """
            ALTER TABLE `watchlist_items`
            ADD COLUMN `tags_json` LONGTEXT NULL AFTER `ticker`
        """,
    },
    "alerts": {
        "owner_id": """
            ALTER TABLE `alerts`
            ADD COLUMN `owner_id` BIGINT NOT NULL DEFAULT 1 AFTER `id`
        """,
        "name": """
            ALTER TABLE `alerts`
            ADD COLUMN `name` VARCHAR(128) NULL AFTER `owner_id`
        """,
        "timeframe": """
            ALTER TABLE `alerts`
            ADD COLUMN `timeframe` VARCHAR(16) NOT NULL DEFAULT '1d' AFTER `value2`
        """,
        "condition_json": """
            ALTER TABLE `alerts`
            ADD COLUMN `condition_json` LONGTEXT NULL AFTER `timeframe`
        """,
        "notification_title": """
            ALTER TABLE `alerts`
            ADD COLUMN `notification_title` VARCHAR(255) NULL AFTER `condition_json`
        """,
        "note": """
            ALTER TABLE `alerts`
            ADD COLUMN `note` TEXT NULL AFTER `notification_title`
        """,
        "last_evaluated_at": """
            ALTER TABLE `alerts`
            ADD COLUMN `last_evaluated_at` DATETIME NULL AFTER `triggered_at`
        """,
        "updated_at": """
            ALTER TABLE `alerts`
            ADD COLUMN `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            AFTER `created_at`
        """,
    },
    "journal_filter_presets": {
        "use_count": """
            ALTER TABLE `journal_filter_presets`
            ADD COLUMN `use_count` INT NOT NULL DEFAULT 0 AFTER `filters_json`
        """,
        "last_used_at": """
            ALTER TABLE `journal_filter_presets`
            ADD COLUMN `last_used_at` DATETIME NULL AFTER `use_count`
        """,
    },
}


def build_schema_plan(existing_tables: Set[str], existing_columns: Dict[str, Set[str]]) -> List[str]:
    plan: List[str] = []
    for table_name, statement in CREATE_TABLE_STATEMENTS.items():
        if table_name not in existing_tables:
            plan.append(statement.strip())

    for table_name, column_statements in REQUIRED_COLUMN_MIGRATIONS.items():
        if table_name not in existing_tables:
            continue
        present_columns = existing_columns.get(table_name, set())
        for column_name, statement in column_statements.items():
            if column_name not in present_columns:
                plan.append(statement.strip())

    return plan


class Database:
    def __init__(self):
        self._pool: Optional[aiomysql.Pool] = None
        self._lock = asyncio.Lock()

    async def connect(self):
        try:
            server_pool = await aiomysql.create_pool(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                charset=MYSQL_CHARSET,
                autocommit=True,
                minsize=1,
                maxsize=5,
            )
        except OperationalError as exc:
            raise RuntimeError(_build_mysql_error_message(exc)) from exc
        except Exception as exc:
            raise RuntimeError(_build_mysql_connection_error_message(exc)) from exc
        try:
            async with server_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `SCHEMA_NAME` AS `schema_name`
                        FROM `INFORMATION_SCHEMA`.`SCHEMATA`
                        WHERE `SCHEMA_NAME`=%s
                        """,
                        (MYSQL_DATABASE,),
                    )
                    database_exists = await cur.fetchone()
                    if not database_exists:
                        await cur.execute(
                            f"CREATE DATABASE `{_escape_identifier(MYSQL_DATABASE)}` "
                            f"CHARACTER SET {MYSQL_CHARSET} COLLATE {MYSQL_CHARSET}_unicode_ci"
                        )
        finally:
            server_pool.close()
            await server_pool.wait_closed()

        try:
            self._pool = await aiomysql.create_pool(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                db=MYSQL_DATABASE,
                charset=MYSQL_CHARSET,
                autocommit=True,
                minsize=1,
                maxsize=10,
            )
        except OperationalError as exc:
            raise RuntimeError(_build_mysql_error_message(exc)) from exc
        except Exception as exc:
            raise RuntimeError(_build_mysql_connection_error_message(exc)) from exc

    async def close(self):
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()

    async def create_tables(self):
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT `TABLE_NAME` AS `table_name`
                    FROM `INFORMATION_SCHEMA`.`TABLES`
                    WHERE `TABLE_SCHEMA`=%s
                    """,
                    (MYSQL_DATABASE,),
                )
                existing_tables: Set[str] = {row["table_name"] for row in await cur.fetchall()}
                await cur.execute(
                    """
                    SELECT `TABLE_NAME` AS `table_name`, `COLUMN_NAME` AS `column_name`
                    FROM `INFORMATION_SCHEMA`.`COLUMNS`
                    WHERE `TABLE_SCHEMA`=%s
                    """,
                    (MYSQL_DATABASE,),
                )
                existing_columns: Dict[str, Set[str]] = {}
                for row in await cur.fetchall():
                    existing_columns.setdefault(row["table_name"], set()).add(row["column_name"])
            async with conn.cursor() as cur:
                for statement in build_schema_plan(existing_tables, existing_columns):
                    await cur.execute(statement)
        await self.ensure_default_owner()

    async def _fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                return await cur.fetchone()

    async def _fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()
        return list(rows)

    async def _execute(self, sql: str, params: tuple = ()) -> int:
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)
                    return cur.rowcount

    async def _execute_insert(self, sql: str, params: tuple = ()) -> int:
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)
                    return cur.lastrowid

    async def ensure_default_owner(self) -> Dict[str, Any]:
        sql = """
            INSERT INTO `user_profiles`
                (`id`, `username`, `display_name`, `timezone`, `is_active`)
            VALUES (%s, %s, %s, %s, 1)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `display_name` = `incoming`.`display_name`,
                `timezone` = `incoming`.`timezone`,
                `is_active` = 1
        """
        await self._execute(
            sql,
            (
                DEFAULT_OWNER_ID,
                DEFAULT_OWNER_USERNAME,
                DEFAULT_OWNER_DISPLAY_NAME,
                DEFAULT_OWNER_TIMEZONE,
            ),
        )
        owner = await self._fetchone(
            """
            SELECT `id`, `username`, `display_name`, `timezone`, `is_active`, `created_at`, `updated_at`
            FROM `user_profiles`
            WHERE `id`=%s
            """,
            (DEFAULT_OWNER_ID,),
        )
        return _serialize_user_profile(owner)

    async def upsert_ohlcv_batch(self, ticker: str, rows: List[Dict], interval: str = "1d") -> int:
        if not rows:
            return 0

        sql = """
            INSERT INTO `ohlcv`
                (`ticker`, `date`, `interval`, `open`, `high`, `low`, `close`, `volume`, `adj_close`, `source`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `open` = `incoming`.`open`,
                `high` = `incoming`.`high`,
                `low` = `incoming`.`low`,
                `close` = `incoming`.`close`,
                `volume` = `incoming`.`volume`,
                `adj_close` = `incoming`.`adj_close`,
                `source` = `incoming`.`source`
        """
        params = [
            (
                ticker,
                row["date"],
                interval,
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row.get("volume", 0),
                row.get("adj_close"),
                row.get("source", "yahoo_finance"),
            )
            for row in rows
        ]

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(sql, params)
        return len(rows)

    async def delete_ohlcv_range(
        self,
        ticker: str,
        interval: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> int:
        conditions = ["`ticker`=%s", "`interval`=%s"]
        params: List = [ticker, interval]

        if start_date:
            conditions.append("`date`>=%s")
            params.append(start_date)
        if end_date:
            conditions.append("`date`<=%s")
            params.append(end_date)

        sql = f"DELETE FROM `ohlcv` WHERE {' AND '.join(conditions)}"
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, tuple(params))
                    return cur.rowcount

    async def get_ohlcv(self, ticker: str, period: str = "1y", interval: str = "1d") -> List[Dict]:
        since = _period_to_date(period)
        sql = """
            SELECT `date`, `open`, `high`, `low`, `close`, `volume`, `adj_close`, `source`, `updated_at`
            FROM `ohlcv`
            WHERE `ticker`=%s AND `interval`=%s AND `date`>=%s
            ORDER BY `date` ASC
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (ticker, interval, since))
                rows = await cur.fetchall()
        return list(rows)

    async def get_ohlcv_range(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> List[Dict]:
        sql = """
            SELECT `date`, `open`, `high`, `low`, `close`, `volume`, `adj_close`, `source`, `updated_at`
            FROM `ohlcv`
            WHERE `ticker`=%s AND `interval`=%s AND `date`>=%s AND `date`<=%s
            ORDER BY `date` ASC
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (ticker, interval, start_date, end_date))
                rows = await cur.fetchall()
        return list(rows)

    async def get_latest_ohlcv(self, ticker: str) -> Optional[Dict]:
        sql = """
            SELECT *
            FROM `ohlcv`
            WHERE `ticker`=%s AND `interval`='1d'
            ORDER BY `date` DESC
            LIMIT 1
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (ticker,))
                return await cur.fetchone()

    async def get_prev_close(self, ticker: str) -> Optional[float]:
        sql = """
            SELECT `close`
            FROM `ohlcv`
            WHERE `ticker`=%s AND `interval`='1d'
            ORDER BY `date` DESC
            LIMIT 1 OFFSET 1
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (ticker,))
                row = await cur.fetchone()
        return row["close"] if row else None

    async def upsert_stock_info(self, ticker: str, info: Dict):
        sql = """
            INSERT INTO `stock_info`
                (`ticker`, `name`, `sector`, `industry`, `market_cap`, `pe_ratio`,
                 `dividend_yield`, `week_52_high`, `week_52_low`, `avg_volume`,
                 `description`, `currency`, `exchange`, `country`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `name` = `incoming`.`name`,
                `sector` = `incoming`.`sector`,
                `industry` = `incoming`.`industry`,
                `market_cap` = `incoming`.`market_cap`,
                `pe_ratio` = `incoming`.`pe_ratio`,
                `dividend_yield` = `incoming`.`dividend_yield`,
                `week_52_high` = `incoming`.`week_52_high`,
                `week_52_low` = `incoming`.`week_52_low`,
                `avg_volume` = `incoming`.`avg_volume`,
                `description` = `incoming`.`description`,
                `currency` = `incoming`.`currency`,
                `exchange` = `incoming`.`exchange`,
                `country` = `incoming`.`country`
        """
        params = (
            ticker,
            info.get("longName") or info.get("shortName") or ticker,
            info.get("sector"),
            info.get("industry"),
            info.get("marketCap"),
            info.get("trailingPE"),
            info.get("dividendYield"),
            info.get("fiftyTwoWeekHigh"),
            info.get("fiftyTwoWeekLow"),
            info.get("averageVolume"),
            (info.get("longBusinessSummary") or "")[:500],
            info.get("currency"),
            info.get("exchange"),
            info.get("country"),
        )

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)

    async def get_stock_info(self, ticker: str) -> Optional[Dict]:
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM `stock_info` WHERE `ticker`=%s", (ticker,))
                return await cur.fetchone()

    async def list_screenable_tickers(self, limit: int = 400) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 1000))
        rows = await self._fetchall(
            """
            SELECT
                o.`ticker`,
                o.`date`,
                o.`open`,
                o.`high`,
                o.`low`,
                o.`close`,
                o.`volume`,
                si.`name`,
                si.`sector`,
                si.`industry`,
                si.`market_cap`,
                si.`pe_ratio`,
                si.`dividend_yield`,
                si.`week_52_high`,
                si.`week_52_low`,
                si.`avg_volume`,
                si.`exchange`,
                si.`country`,
                mq.`change_pct` AS `quote_change_pct`,
                mq.`quote_timestamp`,
                mq.`source` AS `quote_source`
            FROM `ohlcv` AS o
            INNER JOIN (
                SELECT `ticker`, MAX(`date`) AS `latest_date`
                FROM `ohlcv`
                WHERE `interval`='1d'
                GROUP BY `ticker`
            ) AS latest
                ON latest.`ticker` = o.`ticker`
               AND latest.`latest_date` = o.`date`
            LEFT JOIN `stock_info` AS si ON si.`ticker` = o.`ticker`
            LEFT JOIN `market_quotes_latest` AS mq ON mq.`ticker` = o.`ticker`
            WHERE o.`interval`='1d'
            ORDER BY o.`date` DESC, o.`ticker` ASC
            LIMIT %s
            """,
            (clean_limit,),
        )
        return list(rows)

    async def get_recent_ohlcv_rows(
        self,
        ticker: str,
        limit: int = 260,
        interval: str = "1d",
    ) -> List[Dict[str, Any]]:
        clean_limit = max(2, min(limit, 1000))
        rows = await self._fetchall(
            """
            SELECT `date`, `open`, `high`, `low`, `close`, `volume`, `adj_close`, `source`, `updated_at`
            FROM `ohlcv`
            WHERE `ticker`=%s AND `interval`=%s
            ORDER BY `date` DESC
            LIMIT %s
            """,
            (ticker, interval, clean_limit),
        )
        return list(reversed(rows))

    async def list_workspace_presets(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `workspace_presets`
            WHERE `owner_id`=%s
            ORDER BY `updated_at` DESC, `id` DESC
            """,
            (owner_id,),
        )
        return [_deserialize_workspace_preset(row) for row in rows]

    async def get_workspace_preset(
        self,
        workspace_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `workspace_presets`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (workspace_id, owner_id),
        )
        return _deserialize_workspace_preset(row)

    async def create_workspace_preset(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_workspace_payload(payload)
        if normalized["is_default"]:
            await self._execute(
                "UPDATE `workspace_presets` SET `is_default`=0 WHERE `owner_id`=%s",
                (owner_id,),
            )

        workspace_id = await self._execute_insert(
            """
            INSERT INTO `workspace_presets`
                (`owner_id`, `name`, `chart_layout`, `active_ticker`, `current_period`,
                 `current_interval`, `workspace_tab`, `comparison_mode`, `payload_json`, `is_default`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["name"],
                normalized["chart_layout"],
                normalized["active_ticker"],
                normalized["current_period"],
                normalized["current_interval"],
                normalized["workspace_tab"],
                normalized["comparison_mode"],
                _json_dumps(normalized["payload"]),
                1 if normalized["is_default"] else 0,
            ),
        )
        workspace = await self.get_workspace_preset(workspace_id, owner_id=owner_id)
        if not workspace:
            raise RuntimeError("Workspace preset was not persisted")
        return workspace

    async def update_workspace_preset(
        self,
        workspace_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_workspace_preset(workspace_id, owner_id=owner_id)
        if not existing:
            return None

        normalized = _normalize_workspace_payload(payload, existing=existing)
        if normalized["is_default"]:
            await self._execute(
                "UPDATE `workspace_presets` SET `is_default`=0 WHERE `owner_id`=%s AND `id`<>%s",
                (owner_id, workspace_id),
            )

        await self._execute(
            """
            UPDATE `workspace_presets`
            SET `name`=%s,
                `chart_layout`=%s,
                `active_ticker`=%s,
                `current_period`=%s,
                `current_interval`=%s,
                `workspace_tab`=%s,
                `comparison_mode`=%s,
                `payload_json`=%s,
                `is_default`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["name"],
                normalized["chart_layout"],
                normalized["active_ticker"],
                normalized["current_period"],
                normalized["current_interval"],
                normalized["workspace_tab"],
                normalized["comparison_mode"],
                _json_dumps(normalized["payload"]),
                1 if normalized["is_default"] else 0,
                workspace_id,
                owner_id,
            ),
        )
        return await self.get_workspace_preset(workspace_id, owner_id=owner_id)

    async def delete_workspace_preset(
        self,
        workspace_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> bool:
        deleted = await self._execute(
            "DELETE FROM `workspace_presets` WHERE `id`=%s AND `owner_id`=%s",
            (workspace_id, owner_id),
        )
        return deleted > 0

    async def list_alerts(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `alerts`
            WHERE `owner_id`=%s
            ORDER BY `active` DESC, `updated_at` DESC, `id` DESC
            """,
            (owner_id,),
        )
        return [_deserialize_alert(row) for row in rows]

    async def list_active_alerts(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `alerts`
            WHERE `owner_id`=%s AND `active`=1
            ORDER BY `updated_at` ASC, `id` ASC
            """,
            (owner_id,),
        )
        return [_deserialize_alert(row) for row in rows]

    async def get_alert(self, alert_id: int, owner_id: int = DEFAULT_OWNER_ID) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `alerts`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (alert_id, owner_id),
        )
        return _deserialize_alert(row)

    async def create_alert(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_alert_payload(payload)
        alert_id = await self._execute_insert(
            """
            INSERT INTO `alerts`
                (`owner_id`, `name`, `ticker`, `type`, `condition`, `value`, `value2`,
                 `timeframe`, `condition_json`, `notification_title`, `note`,
                 `active`, `triggered`, `triggered_at`, `last_evaluated_at`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["name"],
                normalized["ticker"],
                normalized["type"],
                normalized["condition"],
                normalized["value"],
                normalized["value2"],
                normalized["timeframe"],
                _json_dumps(normalized["condition_payload"]),
                normalized["notification_title"],
                normalized["note"],
                1 if normalized["active"] else 0,
                1 if normalized["triggered"] else 0,
                _parse_datetime_value(normalized.get("triggered_at")),
                _parse_datetime_value(normalized.get("last_evaluated_at")),
            ),
        )
        alert = await self.get_alert(alert_id, owner_id=owner_id)
        if not alert:
            raise RuntimeError("Alert was not persisted")
        return alert

    async def update_alert(
        self,
        alert_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_alert(alert_id, owner_id=owner_id)
        if not existing:
            return None

        normalized = _normalize_alert_payload(payload, existing=existing)
        await self._execute(
            """
            UPDATE `alerts`
            SET `name`=%s,
                `ticker`=%s,
                `type`=%s,
                `condition`=%s,
                `value`=%s,
                `value2`=%s,
                `timeframe`=%s,
                `condition_json`=%s,
                `notification_title`=%s,
                `note`=%s,
                `active`=%s,
                `triggered`=%s,
                `triggered_at`=%s,
                `last_evaluated_at`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["name"],
                normalized["ticker"],
                normalized["type"],
                normalized["condition"],
                normalized["value"],
                normalized["value2"],
                normalized["timeframe"],
                _json_dumps(normalized["condition_payload"]),
                normalized["notification_title"],
                normalized["note"],
                1 if normalized["active"] else 0,
                1 if normalized["triggered"] else 0,
                _parse_datetime_value(normalized.get("triggered_at")),
                _parse_datetime_value(normalized.get("last_evaluated_at")),
                alert_id,
                owner_id,
            ),
        )
        return await self.get_alert(alert_id, owner_id=owner_id)

    async def delete_alert(self, alert_id: int, owner_id: int = DEFAULT_OWNER_ID) -> bool:
        deleted = await self._execute(
            "DELETE FROM `alerts` WHERE `id`=%s AND `owner_id`=%s",
            (alert_id, owner_id),
        )
        return deleted > 0

    async def create_alert_trigger_log(
        self,
        alert_id: int,
        ticker: str,
        payload: Optional[Dict[str, Any]] = None,
        owner_id: int = DEFAULT_OWNER_ID,
        trigger_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
    ) -> Dict[str, Any]:
        record_id = await self._execute_insert(
            """
            INSERT INTO `alert_trigger_logs`
                (`alert_id`, `owner_id`, `ticker`, `trigger_value`, `threshold_value`, `payload_json`)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                alert_id,
                owner_id,
                ticker,
                trigger_value,
                threshold_value,
                _json_dumps(payload or {}),
            ),
        )
        row = await self._fetchone(
            """
            SELECT *
            FROM `alert_trigger_logs`
            WHERE `id`=%s
            LIMIT 1
            """,
            (record_id,),
        )
        return _deserialize_alert_trigger_log(row)

    async def list_alert_trigger_logs(
        self,
        alert_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `alert_trigger_logs`
            WHERE `alert_id`=%s AND `owner_id`=%s
            ORDER BY `created_at` DESC, `id` DESC
            LIMIT %s
            """,
            (alert_id, owner_id, max(1, min(limit, 200))),
        )
        return [_deserialize_alert_trigger_log(row) for row in rows]

    async def create_notification(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_notification_payload(payload)
        notification_id = await self._execute_insert(
            """
            INSERT INTO `notifications`
                (`owner_id`, `category`, `level`, `title`, `message`,
                 `related_entity_type`, `related_entity_id`, `link_url`, `payload_json`, `read_at`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["category"],
                normalized["level"],
                normalized["title"],
                normalized["message"],
                normalized["related_entity_type"],
                normalized["related_entity_id"],
                normalized["link_url"],
                _json_dumps(normalized["payload"]),
                _parse_datetime_value(normalized.get("read_at")),
            ),
        )
        notification = await self.get_notification(notification_id, owner_id=owner_id)
        if not notification:
            raise RuntimeError("Notification was not persisted")
        return notification

    async def get_notification(
        self,
        notification_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `notifications`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (notification_id, owner_id),
        )
        return _deserialize_notification(row)

    async def list_notifications(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 200))
        filters = ["`owner_id`=%s"]
        params: List[Any] = [owner_id]
        if unread_only:
            filters.append("`read_at` IS NULL")

        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `notifications`
            WHERE {' AND '.join(filters)}
            ORDER BY `created_at` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_notification(row) for row in rows]

    async def mark_notification_read(
        self,
        notification_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        return await self.set_notification_read_state(notification_id, True, owner_id=owner_id)

    async def create_backtest_run(
        self,
        payload: Dict[str, Any],
        trades: List[Dict[str, Any]],
        equity_points: List[Dict[str, Any]],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_backtest_run_payload(payload)

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO `backtest_runs`
                            (`owner_id`, `ticker`, `strategy_key`, `strategy_name`, `interval`,
                             `start_date`, `end_date`, `initial_capital`, `final_equity`,
                             `total_return_pct`, `max_drawdown_pct`, `sharpe_ratio`, `trade_count`,
                             `win_rate_pct`, `bars_count`, `fee_rate`, `slippage_rate`,
                             `stop_loss_pct`, `take_profit_pct`, `position_sizing`, `summary_json`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            owner_id,
                            normalized["ticker"],
                            normalized["strategy_key"],
                            normalized["strategy_name"],
                            normalized["interval"],
                            normalized["start_date"],
                            normalized["end_date"],
                            normalized["initial_capital"],
                            normalized["final_equity"],
                            normalized["total_return_pct"],
                            normalized["max_drawdown_pct"],
                            normalized["sharpe_ratio"],
                            normalized["trade_count"],
                            normalized["win_rate_pct"],
                            normalized["bars_count"],
                            normalized["fee_rate"],
                            normalized["slippage_rate"],
                            normalized["stop_loss_pct"],
                            normalized["take_profit_pct"],
                            normalized["position_sizing"],
                            _json_dumps(normalized["summary"]),
                        ),
                    )
                    run_id = cur.lastrowid

                    if trades:
                        await cur.executemany(
                            """
                            INSERT INTO `backtest_trades`
                                (`backtest_run_id`, `owner_id`, `ticker`, `side`, `entry_date`,
                                 `entry_price`, `exit_date`, `exit_price`, `quantity`, `gross_pnl`,
                                 `net_pnl`, `return_pct`, `fee_amount`, `holding_bars`, `exit_reason`,
                                 `payload_json`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    run_id,
                                    owner_id,
                                    normalized["ticker"],
                                    _optional_string(trade.get("side"), max_length=16) or "long",
                                    _parse_datetime_value(trade.get("entry_date")),
                                    _optional_float(trade.get("entry_price")) or 0.0,
                                    _parse_datetime_value(trade.get("exit_date")),
                                    _optional_float(trade.get("exit_price")) or 0.0,
                                    _optional_float(trade.get("quantity")) or 0.0,
                                    _optional_float(trade.get("gross_pnl")) or 0.0,
                                    _optional_float(trade.get("net_pnl")) or 0.0,
                                    _optional_float(trade.get("return_pct")) or 0.0,
                                    _optional_float(trade.get("fee_amount")) or 0.0,
                                    _optional_int(trade.get("holding_bars")) or 0,
                                    _optional_string(trade.get("exit_reason"), max_length=64),
                                    _json_dumps(trade.get("payload") or {}),
                                )
                                for trade in trades
                            ],
                        )

                    if equity_points:
                        await cur.executemany(
                            """
                            INSERT INTO `backtest_equity_points`
                                (`backtest_run_id`, `owner_id`, `point_date`, `equity`, `cash`,
                                 `position_qty`, `close_price`, `payload_json`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    run_id,
                                    owner_id,
                                    _parse_datetime_value(point.get("date")),
                                    _optional_float(point.get("equity")) or 0.0,
                                    _optional_float(point.get("cash")) or 0.0,
                                    _optional_float(point.get("position_qty")) or 0.0,
                                    _optional_float(point.get("close_price")),
                                    _json_dumps(point.get("payload") or {}),
                                )
                                for point in equity_points
                            ],
                        )

        run = await self.get_backtest_run(run_id, owner_id=owner_id)
        if not run:
            raise RuntimeError("Backtest run was not persisted")
        return run

    async def list_backtest_runs(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 200))
        filters = ["`owner_id`=%s"]
        params: List[Any] = [owner_id]
        if ticker:
            filters.append("`ticker`=%s")
            params.append(ticker)

        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `backtest_runs`
            WHERE {' AND '.join(filters)}
            ORDER BY `created_at` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_backtest_run(row) for row in rows]

    async def get_backtest_run(
        self,
        run_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `backtest_runs`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (run_id, owner_id),
        )
        run = _deserialize_backtest_run(row)
        if not run:
            return None

        trade_rows = await self._fetchall(
            """
            SELECT *
            FROM `backtest_trades`
            WHERE `backtest_run_id`=%s AND `owner_id`=%s
            ORDER BY `entry_date` ASC, `id` ASC
            """,
            (run_id, owner_id),
        )
        equity_rows = await self._fetchall(
            """
            SELECT *
            FROM `backtest_equity_points`
            WHERE `backtest_run_id`=%s AND `owner_id`=%s
            ORDER BY `point_date` ASC, `id` ASC
            """,
            (run_id, owner_id),
        )
        run["trades"] = [_deserialize_backtest_trade(item) for item in trade_rows]
        run["equity_curve"] = [_deserialize_backtest_equity_point(item) for item in equity_rows]
        return run

    async def list_trade_journal_entries(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        *,
        ticker: Optional[str] = None,
        market: Optional[str] = None,
        strategy_code: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 200))
        filters = ["e.`owner_id`=%s"]
        params: List[Any] = [owner_id]

        if ticker:
            filters.append("e.`ticker`=%s")
            params.append(ticker)
        if market:
            filters.append("e.`market`=%s")
            params.append(market)
        if strategy_code:
            filters.append("e.`strategy_code`=%s")
            params.append(strategy_code)
        if tag:
            filters.append(
                """
                EXISTS (
                    SELECT 1
                    FROM `trade_journal_tags` AS tjt
                    WHERE tjt.`entry_id` = e.`id` AND tjt.`tag`=%s
                )
                """.strip()
            )
            params.append(tag)
        if search:
            filters.append(
                """
                (
                    e.`ticker` LIKE %s OR
                    e.`entry_reason` LIKE %s OR
                    e.`exit_reason` LIKE %s OR
                    e.`review_notes` LIKE %s
                )
                """.strip()
            )
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern, pattern])

        rows = await self._fetchall(
            f"""
            SELECT e.*
            FROM `trade_journal_entries` AS e
            WHERE {' AND '.join(filters)}
            ORDER BY e.`entry_time` DESC, e.`id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return await self._hydrate_trade_journal_entries(rows)

    async def get_trade_journal_entry(
        self,
        entry_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `trade_journal_entries`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (entry_id, owner_id),
        )
        if not row:
            return None
        hydrated = await self._hydrate_trade_journal_entries([row])
        return hydrated[0] if hydrated else None

    async def create_trade_journal_entry(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_trade_journal_payload(payload)
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO `trade_journal_entries`
                            (`owner_id`, `ticker`, `market`, `direction`, `strategy_code`,
                             `entry_time`, `entry_price`, `exit_time`, `exit_price`, `size`,
                             `stop_loss`, `take_profit`, `entry_reason`, `exit_reason`,
                             `emotion_tag`, `review_notes`, `result_json`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            owner_id,
                            normalized["ticker"],
                            normalized["market"],
                            normalized["direction"],
                            normalized["strategy_code"],
                            _parse_datetime_value(normalized["entry_time"]),
                            normalized["entry_price"],
                            _parse_datetime_value(normalized.get("exit_time")),
                            normalized["exit_price"],
                            normalized["size"],
                            normalized["stop_loss"],
                            normalized["take_profit"],
                            normalized["entry_reason"],
                            normalized["exit_reason"],
                            normalized["emotion_tag"],
                            normalized["review_notes"],
                            _json_dumps(normalized["result"]),
                        ),
                    )
                    entry_id = cur.lastrowid
                await self._replace_trade_journal_children(conn, entry_id, normalized["tags"], normalized["attachments"])

        entry = await self.get_trade_journal_entry(entry_id, owner_id=owner_id)
        if not entry:
            raise RuntimeError("Trade journal entry was not persisted")
        return entry

    async def update_trade_journal_entry(
        self,
        entry_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_trade_journal_entry(entry_id, owner_id=owner_id)
        if not existing:
            return None

        normalized = _normalize_trade_journal_payload(payload, existing=existing)
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE `trade_journal_entries`
                        SET `ticker`=%s,
                            `market`=%s,
                            `direction`=%s,
                            `strategy_code`=%s,
                            `entry_time`=%s,
                            `entry_price`=%s,
                            `exit_time`=%s,
                            `exit_price`=%s,
                            `size`=%s,
                            `stop_loss`=%s,
                            `take_profit`=%s,
                            `entry_reason`=%s,
                            `exit_reason`=%s,
                            `emotion_tag`=%s,
                            `review_notes`=%s,
                            `result_json`=%s
                        WHERE `id`=%s AND `owner_id`=%s
                        """,
                        (
                            normalized["ticker"],
                            normalized["market"],
                            normalized["direction"],
                            normalized["strategy_code"],
                            _parse_datetime_value(normalized["entry_time"]),
                            normalized["entry_price"],
                            _parse_datetime_value(normalized.get("exit_time")),
                            normalized["exit_price"],
                            normalized["size"],
                            normalized["stop_loss"],
                            normalized["take_profit"],
                            normalized["entry_reason"],
                            normalized["exit_reason"],
                            normalized["emotion_tag"],
                            normalized["review_notes"],
                            _json_dumps(normalized["result"]),
                            entry_id,
                            owner_id,
                        ),
                    )
                await self._replace_trade_journal_children(conn, entry_id, normalized["tags"], normalized["attachments"])

        return await self.get_trade_journal_entry(entry_id, owner_id=owner_id)

    async def delete_trade_journal_entry(
        self,
        entry_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> bool:
        deleted = await self._execute(
            "DELETE FROM `trade_journal_entries` WHERE `id`=%s AND `owner_id`=%s",
            (entry_id, owner_id),
        )
        return deleted > 0

    async def get_trade_journal_stats(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        *,
        ticker: Optional[str] = None,
        market: Optional[str] = None,
        strategy_code: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        entries = await self.list_trade_journal_entries(
            owner_id=owner_id,
            ticker=ticker,
            market=market,
            strategy_code=strategy_code,
            tag=tag,
            search=search,
            limit=500,
        )
        return build_journal_stats(entries)

    async def set_notification_read_state(
        self,
        notification_id: int,
        read: bool,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        updated = await self._execute(
            """
            UPDATE `notifications`
            SET `read_at`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                datetime.now(timezone.utc).replace(tzinfo=None) if read else None,
                notification_id,
                owner_id,
            ),
        )
        if not updated:
            return None
        return await self.get_notification(notification_id, owner_id=owner_id)

    async def upsert_market_events(self, events: List[Dict[str, Any]]) -> int:
        if not events:
            return 0
        normalized_events = [_normalize_market_event_payload(item) for item in events]
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        """
                        INSERT INTO `market_events`
                            (`event_type`, `market`, `ticker`, `title`, `description`,
                             `event_date`, `event_time`, `importance`, `source`, `url`, `payload_json`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        AS `incoming`
                        ON DUPLICATE KEY UPDATE
                            `market`=`incoming`.`market`,
                            `description`=`incoming`.`description`,
                            `event_time`=`incoming`.`event_time`,
                            `importance`=`incoming`.`importance`,
                            `source`=`incoming`.`source`,
                            `url`=`incoming`.`url`,
                            `payload_json`=`incoming`.`payload_json`
                        """,
                        [
                            (
                                item["event_type"],
                                item["market"],
                                item["ticker"],
                                item["title"],
                                item["description"],
                                item["event_date"],
                                _parse_datetime_value(item.get("event_time")),
                                item["importance"],
                                item["source"],
                                item["url"],
                                _json_dumps(item.get("payload") or {}),
                            )
                            for item in normalized_events
                        ],
                    )
        return len(normalized_events)

    async def list_market_events(
        self,
        *,
        ticker: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 500))
        filters = ["1=1"]
        params: List[Any] = []
        if ticker:
            filters.append("`ticker`=%s")
            params.append(ticker)
        if date_from:
            filters.append("`event_date`>=%s")
            params.append(date_from)
        if date_to:
            filters.append("`event_date`<=%s")
            params.append(date_to)
        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `market_events`
            WHERE {' AND '.join(filters)}
            ORDER BY `event_date` ASC, `event_time` ASC, `id` ASC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_market_event(item) for item in rows]

    async def upsert_news_articles(self, articles: List[Dict[str, Any]]) -> int:
        if not articles:
            return 0
        normalized_articles = [_normalize_news_article_payload(item) for item in articles]
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        """
                        INSERT INTO `news_articles`
                            (`ticker`, `market`, `title`, `summary`, `published_at`, `source`, `url`, `sentiment`, `payload_json`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        AS `incoming`
                        ON DUPLICATE KEY UPDATE
                            `market`=`incoming`.`market`,
                            `summary`=`incoming`.`summary`,
                            `source`=`incoming`.`source`,
                            `url`=`incoming`.`url`,
                            `sentiment`=`incoming`.`sentiment`,
                            `payload_json`=`incoming`.`payload_json`
                        """,
                        [
                            (
                                item["ticker"],
                                item["market"],
                                item["title"],
                                item["summary"],
                                _parse_datetime_value(item["published_at"]),
                                item["source"],
                                item["url"],
                                item["sentiment"],
                                _json_dumps(item.get("payload") or {}),
                            )
                            for item in normalized_articles
                        ],
                    )
        return len(normalized_articles)

    async def list_news_articles(
        self,
        *,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 200))
        filters = ["1=1"]
        params: List[Any] = []
        if ticker:
            filters.append("`ticker`=%s")
            params.append(ticker)
        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `news_articles`
            WHERE {' AND '.join(filters)}
            ORDER BY `published_at` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_news_article(item) for item in rows]

    async def upsert_macro_snapshots(self, snapshots: List[Dict[str, Any]]) -> int:
        if not snapshots:
            return 0
        normalized_snapshots = [_normalize_macro_snapshot_payload(item) for item in snapshots]
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        """
                        INSERT INTO `macro_snapshots`
                            (`metric_code`, `metric_name`, `value`, `snapshot_date`, `source`, `payload_json`)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        AS `incoming`
                        ON DUPLICATE KEY UPDATE
                            `metric_name`=`incoming`.`metric_name`,
                            `value`=`incoming`.`value`,
                            `source`=`incoming`.`source`,
                            `payload_json`=`incoming`.`payload_json`
                        """,
                        [
                            (
                                item["metric_code"],
                                item["metric_name"],
                                item["value"],
                                item["snapshot_date"],
                                item["source"],
                                _json_dumps(item.get("payload") or {}),
                            )
                            for item in normalized_snapshots
                        ],
                    )
        return len(normalized_snapshots)

    async def list_macro_snapshots(
        self,
        snapshot_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if snapshot_date:
            rows = await self._fetchall(
                """
                SELECT *
                FROM `macro_snapshots`
                WHERE `snapshot_date`=%s
                ORDER BY `metric_code` ASC
                """,
                (snapshot_date,),
            )
        else:
            row = await self._fetchone(
                """
                SELECT MAX(`snapshot_date`) AS `snapshot_date`
                FROM `macro_snapshots`
                """
            )
            latest_date = row.get("snapshot_date") if row else None
            if not latest_date:
                return []
            rows = await self._fetchall(
                """
                SELECT *
                FROM `macro_snapshots`
                WHERE `snapshot_date`=%s
                ORDER BY `metric_code` ASC
                """,
                (_date_to_iso(latest_date),),
            )
        return [_deserialize_macro_snapshot(item) for item in rows]

    async def upsert_taiwan_chip_snapshots(self, snapshots: List[Dict[str, Any]]) -> int:
        if not snapshots:
            return 0
        normalized_snapshots = [_normalize_taiwan_chip_snapshot_payload(item) for item in snapshots]
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        """
                        INSERT INTO `taiwan_chip_snapshots`
                            (`ticker`, `market`, `snapshot_date`, `margin_balance`, `short_balance`,
                             `securities_lending_balance`, `institutional_net_buy_sell`, `source`,
                             `branch_payload_json`, `summary_json`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        AS `incoming`
                        ON DUPLICATE KEY UPDATE
                            `market`=`incoming`.`market`,
                            `margin_balance`=`incoming`.`margin_balance`,
                            `short_balance`=`incoming`.`short_balance`,
                            `securities_lending_balance`=`incoming`.`securities_lending_balance`,
                            `institutional_net_buy_sell`=`incoming`.`institutional_net_buy_sell`,
                            `source`=`incoming`.`source`,
                            `branch_payload_json`=`incoming`.`branch_payload_json`,
                            `summary_json`=`incoming`.`summary_json`
                        """,
                        [
                            (
                                item["ticker"],
                                item["market"],
                                item["snapshot_date"],
                                item["margin_balance"],
                                item["short_balance"],
                                item["securities_lending_balance"],
                                item["institutional_net_buy_sell"],
                                item["source"],
                                _json_dumps(item.get("branch_payload") or {}),
                                _json_dumps(item.get("summary") or {}),
                            )
                            for item in normalized_snapshots
                        ],
                    )
        return len(normalized_snapshots)

    async def get_taiwan_chip_snapshot(
        self,
        ticker: str,
        snapshot_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if snapshot_date:
            row = await self._fetchone(
                """
                SELECT *
                FROM `taiwan_chip_snapshots`
                WHERE `ticker`=%s AND `snapshot_date`=%s
                LIMIT 1
                """,
                (ticker, snapshot_date),
            )
        else:
            row = await self._fetchone(
                """
                SELECT *
                FROM `taiwan_chip_snapshots`
                WHERE `ticker`=%s
                ORDER BY `snapshot_date` DESC, `id` DESC
                LIMIT 1
                """,
                (ticker,),
            )
        return _deserialize_taiwan_chip_snapshot(row)

    async def list_taiwan_chip_snapshots(
        self,
        ticker: Optional[str] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 200))
        filters = ["1=1"]
        params: List[Any] = []
        if ticker:
            filters.append("`ticker`=%s")
            params.append(ticker)
        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `taiwan_chip_snapshots`
            WHERE {' AND '.join(filters)}
            ORDER BY `snapshot_date` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_taiwan_chip_snapshot(item) for item in rows]

    async def list_screener_presets(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `screener_presets`
            WHERE `owner_id`=%s
            ORDER BY `updated_at` DESC, `id` DESC
            """,
            (owner_id,),
        )
        return [_deserialize_screener_preset(row) for row in rows]

    async def get_screener_preset(
        self,
        preset_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `screener_presets`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (preset_id, owner_id),
        )
        return _deserialize_screener_preset(row)

    async def create_screener_preset(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_screener_preset_payload(payload)
        preset_id = await self._execute_insert(
            """
            INSERT INTO `screener_presets` (`owner_id`, `name`, `description`, `filters_json`)
            VALUES (%s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["name"],
                normalized["description"],
                _json_dumps(normalized["filters"]),
            ),
        )
        preset = await self.get_screener_preset(preset_id, owner_id=owner_id)
        if not preset:
            raise RuntimeError("Screener preset was not persisted")
        return preset

    async def update_screener_preset(
        self,
        preset_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_screener_preset(preset_id, owner_id=owner_id)
        if not existing:
            return None
        normalized = _normalize_screener_preset_payload(payload, existing=existing)
        updated = await self._execute(
            """
            UPDATE `screener_presets`
            SET `name`=%s, `description`=%s, `filters_json`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["name"],
                normalized["description"],
                _json_dumps(normalized["filters"]),
                preset_id,
                owner_id,
            ),
        )
        if not updated:
            return None
        return await self.get_screener_preset(preset_id, owner_id=owner_id)

    async def delete_screener_preset(
        self,
        preset_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> bool:
        deleted = await self._execute(
            "DELETE FROM `screener_presets` WHERE `id`=%s AND `owner_id`=%s",
            (preset_id, owner_id),
        )
        return bool(deleted)

    async def list_journal_filter_presets(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `journal_filter_presets`
            WHERE `owner_id`=%s
            ORDER BY COALESCE(`last_used_at`, `updated_at`) DESC, `updated_at` DESC, `id` DESC
            """,
            (owner_id,),
        )
        return [_deserialize_journal_filter_preset(row) for row in rows]

    async def get_journal_filter_preset(
        self,
        preset_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `journal_filter_presets`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (preset_id, owner_id),
        )
        return _deserialize_journal_filter_preset(row)

    async def create_journal_filter_preset(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_journal_filter_preset_payload(payload)
        preset_id = await self._execute_insert(
            """
            INSERT INTO `journal_filter_presets` (`owner_id`, `name`, `description`, `scope`, `filters_json`)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["name"],
                normalized["description"],
                normalized["scope"],
                _json_dumps(normalized["filters"]),
            ),
        )
        preset = await self.get_journal_filter_preset(preset_id, owner_id=owner_id)
        if not preset:
            raise RuntimeError("Journal filter preset was not persisted")
        return preset

    async def update_journal_filter_preset(
        self,
        preset_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_journal_filter_preset(preset_id, owner_id=owner_id)
        if not existing:
            return None
        normalized = _normalize_journal_filter_preset_payload(payload, existing=existing)
        updated = await self._execute(
            """
            UPDATE `journal_filter_presets`
            SET `name`=%s, `description`=%s, `scope`=%s, `filters_json`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["name"],
                normalized["description"],
                normalized["scope"],
                _json_dumps(normalized["filters"]),
                preset_id,
                owner_id,
            ),
        )
        if not updated:
            return None
        return await self.get_journal_filter_preset(preset_id, owner_id=owner_id)

    async def delete_journal_filter_preset(
        self,
        preset_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> bool:
        deleted = await self._execute(
            "DELETE FROM `journal_filter_presets` WHERE `id`=%s AND `owner_id`=%s",
            (preset_id, owner_id),
        )
        return bool(deleted)

    async def mark_journal_filter_preset_used(
        self,
        preset_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        updated = await self._execute(
            """
            UPDATE `journal_filter_presets`
            SET `use_count`=`use_count` + 1, `last_used_at`=UTC_TIMESTAMP()
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (preset_id, owner_id),
        )
        if not updated:
            return None
        return await self.get_journal_filter_preset(preset_id, owner_id=owner_id)

    async def _replace_trade_journal_children(
        self,
        conn,
        entry_id: int,
        tags: List[str],
        attachments: List[Dict[str, Any]],
    ) -> None:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM `trade_journal_tags` WHERE `entry_id`=%s", (entry_id,))
            await cur.execute("DELETE FROM `trade_journal_attachments` WHERE `entry_id`=%s", (entry_id,))

            if tags:
                await cur.executemany(
                    """
                    INSERT INTO `trade_journal_tags` (`entry_id`, `tag`)
                    VALUES (%s, %s)
                    """,
                    [(entry_id, tag) for tag in tags],
                )

            if attachments:
                await cur.executemany(
                    """
                    INSERT INTO `trade_journal_attachments` (`entry_id`, `file_path`, `file_type`)
                    VALUES (%s, %s, %s)
                    """,
                    [
                        (
                            entry_id,
                            attachment["file_path"],
                            attachment.get("file_type"),
                        )
                        for attachment in attachments
                    ],
                )

    async def _hydrate_trade_journal_entries(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        entries = [_deserialize_trade_journal_entry(row) for row in rows]
        entries = [entry for entry in entries if entry]
        if not entries:
            return []

        entry_ids = [entry["id"] for entry in entries]
        placeholders = ", ".join(["%s"] * len(entry_ids))
        tag_rows = await self._fetchall(
            f"""
            SELECT `id`, `entry_id`, `tag`
            FROM `trade_journal_tags`
            WHERE `entry_id` IN ({placeholders})
            ORDER BY `tag` ASC, `id` ASC
            """,
            tuple(entry_ids),
        )
        attachment_rows = await self._fetchall(
            f"""
            SELECT `id`, `entry_id`, `file_path`, `file_type`, `created_at`
            FROM `trade_journal_attachments`
            WHERE `entry_id` IN ({placeholders})
            ORDER BY `created_at` ASC, `id` ASC
            """,
            tuple(entry_ids),
        )

        tags_by_entry: Dict[int, List[str]] = {}
        for row in tag_rows:
            tags_by_entry.setdefault(row["entry_id"], []).append(row["tag"])

        attachments_by_entry: Dict[int, List[Dict[str, Any]]] = {}
        for row in attachment_rows:
            attachments_by_entry.setdefault(row["entry_id"], []).append(
                {
                    "id": row["id"],
                    "file_path": row["file_path"],
                    "file_type": row.get("file_type"),
                    "created_at": _datetime_to_iso(row.get("created_at")),
                }
            )

        for entry in entries:
            entry["tags"] = tags_by_entry.get(entry["id"], [])
            entry["attachments"] = attachments_by_entry.get(entry["id"], [])
        return entries

    async def upsert_market_quote(self, quote: Dict[str, Any]) -> Dict[str, Any]:
        normalized = _normalize_quote_payload(quote)
        await self._execute(
            """
            INSERT INTO `market_quotes_latest`
                (`ticker`, `source`, `quote_type`, `is_delayed`, `name`, `currency`, `price`,
                 `open`, `high`, `low`, `prev_close`, `change_amount`, `change_pct`,
                 `volume`, `market_cap`, `quote_timestamp`, `payload_json`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `source`=`incoming`.`source`,
                `quote_type`=`incoming`.`quote_type`,
                `is_delayed`=`incoming`.`is_delayed`,
                `name`=`incoming`.`name`,
                `currency`=`incoming`.`currency`,
                `price`=`incoming`.`price`,
                `open`=`incoming`.`open`,
                `high`=`incoming`.`high`,
                `low`=`incoming`.`low`,
                `prev_close`=`incoming`.`prev_close`,
                `change_amount`=`incoming`.`change_amount`,
                `change_pct`=`incoming`.`change_pct`,
                `volume`=`incoming`.`volume`,
                `market_cap`=`incoming`.`market_cap`,
                `quote_timestamp`=`incoming`.`quote_timestamp`,
                `payload_json`=`incoming`.`payload_json`
            """,
            (
                normalized["ticker"],
                normalized["source"],
                normalized["quote_type"],
                1 if normalized["is_delayed"] else 0,
                normalized["name"],
                normalized["currency"],
                normalized["price"],
                normalized["open"],
                normalized["high"],
                normalized["low"],
                normalized["prev_close"],
                normalized["change"],
                normalized["change_pct"],
                normalized["volume"],
                normalized["market_cap"],
                _parse_datetime_value(normalized.get("quote_timestamp")),
                _json_dumps(normalized),
            ),
        )
        quote_row = await self.get_market_quote(normalized["ticker"])
        if not quote_row:
            raise RuntimeError("Market quote was not persisted")
        return quote_row

    async def get_market_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `market_quotes_latest`
            WHERE `ticker`=%s
            LIMIT 1
            """,
            (ticker,),
        )
        return _deserialize_market_quote(row)

    async def ensure_default_watchlist(self, tickers: List[str], group_name: str = "我的自選") -> None:
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT COUNT(*) AS `c` FROM `watchlist_groups`")
                    existing = (await cur.fetchone())["c"]
                    if existing:
                        return

                    await cur.execute(
                        """
                        INSERT INTO `watchlist_groups` (`name`, `sort_order`)
                        VALUES (%s, %s)
                        """,
                        (group_name, 0),
                    )
                    group_id = cur.lastrowid

                    for sort_order, ticker in enumerate(tickers):
                        await cur.execute(
                            """
                            INSERT INTO `watchlist_items` (`group_id`, `ticker`, `sort_order`)
                            VALUES (%s, %s, %s)
                            """,
                            (group_id, ticker, sort_order),
                        )

    async def ensure_watchlist_group_items(
        self,
        group_name: str,
        tickers: List[str],
        sort_order: int = 0,
    ) -> Optional[Dict]:
        clean_name = (group_name or "").strip()
        clean_tickers = list(dict.fromkeys((ticker or "").strip() for ticker in tickers if (ticker or "").strip()))
        if not clean_name or not clean_tickers:
            return None

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`, `name`, `sort_order`, `created_at`
                        FROM `watchlist_groups`
                        WHERE `name`=%s
                        LIMIT 1
                        """,
                        (clean_name,),
                    )
                    group = await cur.fetchone()

                async with conn.cursor() as cur:
                    if group:
                        group_id = group["id"]
                        await cur.execute(
                            """
                            UPDATE `watchlist_groups`
                            SET `sort_order`=%s
                            WHERE `id`=%s
                            """,
                            (sort_order, group_id),
                        )
                    else:
                        await cur.execute(
                            """
                            INSERT INTO `watchlist_groups` (`name`, `sort_order`)
                            VALUES (%s, %s)
                            """,
                            (clean_name, sort_order),
                        )
                        group_id = cur.lastrowid

                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`, `ticker`
                        FROM `watchlist_items`
                        WHERE `group_id`=%s
                        ORDER BY `sort_order` ASC, `id` ASC
                        """,
                        (group_id,),
                    )
                    existing_items = list(await cur.fetchall())

                existing_by_ticker = {row["ticker"]: row for row in existing_items}
                expected_set = set(clean_tickers)

                async with conn.cursor() as cur:
                    for index, ticker in enumerate(clean_tickers):
                        existing = existing_by_ticker.get(ticker)
                        if existing:
                            await cur.execute(
                                """
                                UPDATE `watchlist_items`
                                SET `sort_order`=%s
                                WHERE `id`=%s
                                """,
                                (index, existing["id"]),
                            )
                        else:
                            await cur.execute(
                                """
                                INSERT INTO `watchlist_items` (`group_id`, `ticker`, `sort_order`)
                                VALUES (%s, %s, %s)
                                """,
                                (group_id, ticker, index),
                            )

                    stale_ids = [row["id"] for row in existing_items if row["ticker"] not in expected_set]
                    if stale_ids:
                        await cur.executemany(
                            "DELETE FROM `watchlist_items` WHERE `id`=%s",
                            [(item_id,) for item_id in stale_ids],
                        )

        return await self.get_watchlist_group(group_id)

    async def get_watchlist_group(self, group_id: int) -> Optional[Dict]:
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT `id`, `name`, `sort_order`, `created_at`
                    FROM `watchlist_groups`
                    WHERE `id`=%s
                    """,
                    (group_id,),
                )
                return await cur.fetchone()

    async def get_watchlist_groups(self) -> List[Dict]:
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT `id`, `name`, `sort_order`, `created_at`
                    FROM `watchlist_groups`
                    ORDER BY `sort_order` ASC, `id` ASC
                    """
                )
                groups = list(await cur.fetchall())

                await cur.execute(
                    """
                    SELECT `id`, `group_id`, `ticker`, `tags_json`, `sort_order`, `created_at`
                    FROM `watchlist_items`
                    ORDER BY `group_id` ASC, `sort_order` ASC, `id` ASC
                    """
                )
                items = [_deserialize_watchlist_item(row) for row in await cur.fetchall()]

        grouped_items: Dict[int, List[Dict]] = {}
        for item in items:
            grouped_items.setdefault(item["group_id"], []).append(item)

        return [
            {
                **group,
                "items": grouped_items.get(group["id"], []),
            }
            for group in groups
        ]

    async def create_watchlist_group(self, name: str) -> Dict:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Group name is required")

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`
                        FROM `watchlist_groups`
                        WHERE `name`=%s
                        LIMIT 1
                        """,
                        (clean_name,),
                    )
                    duplicate = await cur.fetchone()
                    if duplicate:
                        raise ValueError("Group name already exists")

                    await cur.execute("SELECT COALESCE(MAX(`sort_order`), -1) + 1 AS `next_sort` FROM `watchlist_groups`")
                    next_sort = (await cur.fetchone())["next_sort"]

                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO `watchlist_groups` (`name`, `sort_order`)
                        VALUES (%s, %s)
                        """,
                        (clean_name, next_sort),
                    )
                    group_id = cur.lastrowid

        group = await self.get_watchlist_group(group_id)
        return group or {"id": group_id, "name": clean_name, "sort_order": next_sort, "items": []}

    async def rename_watchlist_group(self, group_id: int, name: str) -> Optional[Dict]:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Group name is required")

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`
                        FROM `watchlist_groups`
                        WHERE `name`=%s AND `id`<>%s
                        LIMIT 1
                        """,
                        (clean_name, group_id),
                    )
                    duplicate = await cur.fetchone()
                    if duplicate:
                        raise ValueError("Group name already exists")

                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE `watchlist_groups`
                        SET `name`=%s
                        WHERE `id`=%s
                        """,
                        (clean_name, group_id),
                    )
                    if cur.rowcount == 0:
                        return None

        return await self.get_watchlist_group(group_id)

    async def delete_watchlist_group(self, group_id: int) -> bool:
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("DELETE FROM `watchlist_groups` WHERE `id`=%s", (group_id,))
                    return cur.rowcount > 0

    async def add_watchlist_item(self, group_id: int, ticker: str, tags: Optional[List[str]] = None) -> Dict:
        normalized_tags = _normalize_watchlist_tags(tags)
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`
                        FROM `watchlist_items`
                        WHERE `group_id`=%s AND `ticker`=%s
                        LIMIT 1
                        """,
                        (group_id, ticker),
                    )
                    duplicate = await cur.fetchone()
                    if duplicate:
                        raise ValueError("Ticker already exists in this group")

                    await cur.execute(
                        "SELECT COALESCE(MAX(`sort_order`), -1) + 1 AS `next_sort` FROM `watchlist_items` WHERE `group_id`=%s",
                        (group_id,),
                    )
                    next_sort = (await cur.fetchone())["next_sort"]

                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO `watchlist_items` (`group_id`, `ticker`, `tags_json`, `sort_order`)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (group_id, ticker, _json_dumps(normalized_tags), next_sort),
                    )
                    item_id = cur.lastrowid

                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`, `group_id`, `ticker`, `tags_json`, `sort_order`, `created_at`
                        FROM `watchlist_items`
                        WHERE `id`=%s
                        """,
                        (item_id,),
                    )
                    return _deserialize_watchlist_item(await cur.fetchone())

    async def delete_watchlist_item(self, item_id: int) -> bool:
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("DELETE FROM `watchlist_items` WHERE `id`=%s", (item_id,))
                    return cur.rowcount > 0

    async def reorder_watchlist_items(self, group_id: int, item_ids: List[int]) -> bool:
        if not item_ids:
            return False

        unique_ids = list(dict.fromkeys(item_ids))
        if len(unique_ids) != len(item_ids):
            raise ValueError("Duplicate item ids are not allowed")

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT `id`
                        FROM `watchlist_items`
                        WHERE `group_id`=%s
                        ORDER BY `sort_order` ASC, `id` ASC
                        """,
                        (group_id,),
                    )
                    rows = await cur.fetchall()
                    existing_ids = [row["id"] for row in rows]

                if not existing_ids:
                    return False

                if set(existing_ids) != set(unique_ids):
                    raise ValueError("Item ids do not match the selected group")

                async with conn.cursor() as cur:
                    await cur.executemany(
                        """
                        UPDATE `watchlist_items`
                        SET `sort_order`=%s
                        WHERE `id`=%s AND `group_id`=%s
                        """,
                        [
                            (sort_order, item_id, group_id)
                            for sort_order, item_id in enumerate(unique_ids)
                        ],
                    )

        return True

    async def search_tickers(self, q: str) -> List[Dict]:
        pattern = f"%{q}%"
        sql = """
            SELECT `ticker`, `name`
            FROM `stock_info`
            WHERE `ticker` LIKE %s OR `name` LIKE %s
            LIMIT 20
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (pattern, pattern))
                rows = await cur.fetchall()
        return list(rows)

    async def upsert_institutional_snapshot(self, payload: Dict[str, Any]) -> None:
        resolved_date = payload.get("resolved_date")
        query_date = payload.get("query_date") or resolved_date
        if not resolved_date or not query_date:
            raise ValueError("Institutional snapshot requires query_date and resolved_date")

        sql = """
            INSERT INTO `institutional_snapshots`
                (`resolved_date`, `query_date`, `payload_json`)
            VALUES (%s, %s, %s)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `query_date` = `incoming`.`query_date`,
                `payload_json` = `incoming`.`payload_json`
        """
        params = (
            resolved_date,
            query_date,
            json.dumps(payload, ensure_ascii=False),
        )

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)

    async def get_institutional_snapshot(self, target_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        if target_date:
            sql = """
                SELECT `resolved_date`, `query_date`, `payload_json`
                FROM `institutional_snapshots`
                WHERE `resolved_date`<=%s
                ORDER BY `resolved_date` DESC
                LIMIT 1
            """
            params = (target_date.isoformat(),)
        else:
            sql = """
                SELECT `resolved_date`, `query_date`, `payload_json`
                FROM `institutional_snapshots`
                ORDER BY `resolved_date` DESC
                LIMIT 1
            """
            params = ()

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                row = await cur.fetchone()
        return self._deserialize_institutional_snapshot(row)

    async def get_institutional_snapshot_exact(self, target_date: date) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT `resolved_date`, `query_date`, `payload_json`
            FROM `institutional_snapshots`
            WHERE `resolved_date`=%s
            LIMIT 1
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (target_date.isoformat(),))
                row = await cur.fetchone()
        return self._deserialize_institutional_snapshot(row)

    async def get_institutional_snapshots(self, target_date: date, limit: int) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []

        sql = """
            SELECT `resolved_date`, `query_date`, `payload_json`
            FROM `institutional_snapshots`
            WHERE `resolved_date`<=%s
            ORDER BY `resolved_date` DESC
            LIMIT %s
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (target_date.isoformat(), limit))
                rows = await cur.fetchall()

        snapshots = [
            snapshot
            for snapshot in (
                self._deserialize_institutional_snapshot(row)
                for row in rows
            )
            if snapshot
        ]
        snapshots.reverse()
        return snapshots

    def _deserialize_institutional_snapshot(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        payload = json.loads(row["payload_json"])
        payload.setdefault("resolved_date", _date_to_iso(row.get("resolved_date")))
        payload.setdefault("query_date", _date_to_iso(row.get("query_date")))
        return payload

    async def get_stats(self) -> Dict:
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT COUNT(*) AS `c` FROM `ohlcv`")
                total_rows = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(DISTINCT `ticker`) AS `c` FROM `ohlcv`")
                total_tickers = (await cur.fetchone())["c"]

                await cur.execute(
                    """
                    SELECT
                        o.`ticker`,
                        COUNT(*) AS `rows`,
                        MAX(si.`name`) AS `info_name`,
                        MAX(mq.`name`) AS `quote_name`
                    FROM `ohlcv` AS o
                    LEFT JOIN `stock_info` AS si ON si.`ticker` = o.`ticker`
                    LEFT JOIN `market_quotes_latest` AS mq ON mq.`ticker` = o.`ticker`
                    GROUP BY o.`ticker`
                    ORDER BY `rows` DESC
                    LIMIT 10
                    """
                )
                top = [
                    {
                        "ticker": row["ticker"],
                        "name": resolve_display_name(
                            row["ticker"],
                            {"name": row.get("info_name")} if row.get("info_name") else None,
                            {"name": row.get("quote_name")} if row.get("quote_name") else None,
                        ),
                        "rows": row["rows"],
                    }
                    for row in await cur.fetchall()
                ]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `institutional_snapshots`")
                institutional_snapshots = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `workspace_presets`")
                workspace_presets = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `alerts`")
                alerts = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `notifications`")
                notifications = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `backtest_runs`")
                backtest_runs = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `backtest_trades`")
                backtest_trades = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `trade_journal_entries`")
                trade_journal_entries = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `market_events`")
                market_events = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `news_articles`")
                news_articles = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `macro_snapshots`")
                macro_snapshots = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `taiwan_chip_snapshots`")
                taiwan_chip_snapshots = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `screener_presets`")
                screener_presets = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(*) AS `c` FROM `journal_filter_presets`")
                journal_filter_presets = (await cur.fetchone())["c"]

        return {
            "total_rows": total_rows,
            "total_tickers": total_tickers,
            "top_tickers": top,
            "institutional_snapshots": institutional_snapshots,
            "workspace_presets": workspace_presets,
            "alerts": alerts,
            "notifications": notifications,
            "backtest_runs": backtest_runs,
            "backtest_trades": backtest_trades,
            "trade_journal_entries": trade_journal_entries,
            "market_events": market_events,
            "news_articles": news_articles,
            "macro_snapshots": macro_snapshots,
            "taiwan_chip_snapshots": taiwan_chip_snapshots,
            "screener_presets": screener_presets,
            "journal_filter_presets": journal_filter_presets,
        }

    async def log_sync(self, ticker: str, status: str, rows: int = 0, msg: str = ""):
        sql = """
            INSERT INTO `sync_log` (`ticker`, `status`, `rows_added`, `message`)
            VALUES (%s, %s, %s, %s)
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (ticker, status, rows, msg))


def _serialize_user_profile(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "username": row.get("username"),
        "display_name": row.get("display_name"),
        "timezone": row.get("timezone"),
        "is_active": bool(row.get("is_active", True)),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }


def _deserialize_workspace_preset(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "name": row.get("name"),
        "chart_layout": row.get("chart_layout"),
        "active_ticker": row.get("active_ticker"),
        "current_period": row.get("current_period"),
        "current_interval": row.get("current_interval"),
        "workspace_tab": row.get("workspace_tab"),
        "comparison_mode": row.get("comparison_mode"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "is_default": bool(row.get("is_default", False)),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }


def _normalize_watchlist_tags(tags: Any) -> List[str]:
    source = tags if isinstance(tags, list) else []
    normalized: List[str] = []
    seen = set()
    for item in source:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value[:48])
    return normalized[:6]


def _deserialize_watchlist_item(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        **row,
        "tags": _normalize_watchlist_tags(_json_loads(row.get("tags_json"), [])),
    }


def _deserialize_alert(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "name": row.get("name"),
        "ticker": row.get("ticker"),
        "type": row.get("type"),
        "condition": row.get("condition"),
        "value": row.get("value"),
        "value2": row.get("value2"),
        "timeframe": row.get("timeframe") or "1d",
        "condition_payload": _json_loads(row.get("condition_json"), {}),
        "notification_title": row.get("notification_title"),
        "note": row.get("note"),
        "active": bool(row.get("active", True)),
        "triggered": bool(row.get("triggered", False)),
        "triggered_at": _datetime_to_iso(row.get("triggered_at")),
        "last_evaluated_at": _datetime_to_iso(row.get("last_evaluated_at")),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }


def _deserialize_notification(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "category": row.get("category"),
        "level": row.get("level"),
        "title": row.get("title"),
        "message": row.get("message"),
        "related_entity_type": row.get("related_entity_type"),
        "related_entity_id": row.get("related_entity_id"),
        "link_url": row.get("link_url"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "read_at": _datetime_to_iso(row.get("read_at")),
        "created_at": _datetime_to_iso(row.get("created_at")),
    }


def _deserialize_alert_trigger_log(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "alert_id": row.get("alert_id"),
        "owner_id": row.get("owner_id"),
        "ticker": row.get("ticker"),
        "trigger_value": row.get("trigger_value"),
        "threshold_value": row.get("threshold_value"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
    }


def _deserialize_market_quote(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    payload = _json_loads(row.get("payload_json"), {})
    payload.update(
        {
            "ticker": row.get("ticker"),
            "source": row.get("source"),
            "quote_type": row.get("quote_type"),
            "is_delayed": bool(row.get("is_delayed", True)),
            "name": row.get("name"),
            "currency": row.get("currency"),
            "price": row.get("price"),
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "prev_close": row.get("prev_close"),
            "change": row.get("change_amount"),
            "change_pct": row.get("change_pct"),
            "volume": row.get("volume"),
            "market_cap": row.get("market_cap"),
            "quote_timestamp": _datetime_to_iso(row.get("quote_timestamp")),
            "synced_at": _datetime_to_iso(row.get("synced_at")),
        }
    )
    return payload


def _deserialize_backtest_run(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    summary = _json_loads(row.get("summary_json"), {})
    summary.update(
        {
            "id": row.get("id"),
            "owner_id": row.get("owner_id"),
            "ticker": row.get("ticker"),
            "strategy_key": row.get("strategy_key"),
            "strategy": row.get("strategy_name"),
            "interval": row.get("interval") or "1d",
            "start": _date_to_iso(row.get("start_date")),
            "end": _date_to_iso(row.get("end_date")),
            "capital": row.get("initial_capital"),
            "finalEquity": row.get("final_equity"),
            "totalReturn": row.get("total_return_pct"),
            "maxDrawdown": row.get("max_drawdown_pct"),
            "sharpe": row.get("sharpe_ratio"),
            "sellTrades": row.get("trade_count"),
            "winRate": row.get("win_rate_pct"),
            "bars": row.get("bars_count"),
            "feeRate": row.get("fee_rate"),
            "slippageRate": row.get("slippage_rate"),
            "stopLoss": row.get("stop_loss_pct"),
            "takeProfit": row.get("take_profit_pct"),
            "positionSizing": row.get("position_sizing"),
            "created_at": _datetime_to_iso(row.get("created_at")),
        }
    )
    return summary


def _deserialize_backtest_trade(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "backtest_run_id": row.get("backtest_run_id"),
        "owner_id": row.get("owner_id"),
        "ticker": row.get("ticker"),
        "side": row.get("side"),
        "entry_date": _datetime_to_iso(row.get("entry_date")),
        "entry_price": row.get("entry_price"),
        "exit_date": _datetime_to_iso(row.get("exit_date")),
        "exit_price": row.get("exit_price"),
        "quantity": row.get("quantity"),
        "gross_pnl": row.get("gross_pnl"),
        "net_pnl": row.get("net_pnl"),
        "return_pct": row.get("return_pct"),
        "fee_amount": row.get("fee_amount"),
        "holding_bars": row.get("holding_bars"),
        "exit_reason": row.get("exit_reason"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
    }


def _deserialize_backtest_equity_point(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "backtest_run_id": row.get("backtest_run_id"),
        "owner_id": row.get("owner_id"),
        "date": _datetime_to_iso(row.get("point_date")),
        "equity": row.get("equity"),
        "cash": row.get("cash"),
        "position_qty": row.get("position_qty"),
        "close_price": row.get("close_price"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
    }


def _deserialize_trade_journal_entry(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "ticker": row.get("ticker"),
        "market": row.get("market"),
        "direction": row.get("direction"),
        "strategy_code": row.get("strategy_code"),
        "entry_time": _datetime_to_iso(row.get("entry_time")),
        "entry_price": row.get("entry_price"),
        "exit_time": _datetime_to_iso(row.get("exit_time")),
        "exit_price": row.get("exit_price"),
        "size": row.get("size"),
        "stop_loss": row.get("stop_loss"),
        "take_profit": row.get("take_profit"),
        "entry_reason": row.get("entry_reason"),
        "exit_reason": row.get("exit_reason"),
        "emotion_tag": row.get("emotion_tag"),
        "review_notes": row.get("review_notes"),
        "result": _json_loads(row.get("result_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
        "tags": [],
        "attachments": [],
    }


def _deserialize_market_event(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "event_type": row.get("event_type"),
        "market": row.get("market"),
        "ticker": row.get("ticker"),
        "title": row.get("title"),
        "description": row.get("description"),
        "event_date": _date_to_iso(row.get("event_date")),
        "event_time": _datetime_to_iso(row.get("event_time")),
        "importance": row.get("importance"),
        "source": row.get("source"),
        "url": row.get("url"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }


def _deserialize_news_article(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "ticker": row.get("ticker"),
        "market": row.get("market"),
        "title": row.get("title"),
        "summary": row.get("summary"),
        "published_at": _datetime_to_iso(row.get("published_at")),
        "source": row.get("source"),
        "url": row.get("url"),
        "sentiment": row.get("sentiment"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }


def _deserialize_macro_snapshot(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    payload = _json_loads(row.get("payload_json"), {})
    payload.update(
        {
            "id": row.get("id"),
            "metric_code": row.get("metric_code"),
            "metric_name": row.get("metric_name"),
            "value": row.get("value"),
            "date": _date_to_iso(row.get("snapshot_date")),
            "source": row.get("source"),
            "created_at": _datetime_to_iso(row.get("created_at")),
            "updated_at": _datetime_to_iso(row.get("updated_at")),
        }
    )
    return payload


def _deserialize_taiwan_chip_snapshot(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "ticker": row.get("ticker"),
        "market": row.get("market"),
        "snapshot_date": _date_to_iso(row.get("snapshot_date")),
        "margin_balance": row.get("margin_balance"),
        "short_balance": row.get("short_balance"),
        "securities_lending_balance": row.get("securities_lending_balance"),
        "institutional_net_buy_sell": row.get("institutional_net_buy_sell"),
        "source": row.get("source"),
        "branch_payload": _json_loads(row.get("branch_payload_json"), {}),
        "summary": _json_loads(row.get("summary_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }


def _deserialize_screener_preset(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "name": row.get("name"),
        "description": row.get("description"),
        "filters": _json_loads(row.get("filters_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }


def _deserialize_journal_filter_preset(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "name": row.get("name"),
        "description": row.get("description"),
        "scope": row.get("scope") or "ticker",
        "filters": _json_loads(row.get("filters_json"), {}),
        "use_count": int(row.get("use_count") or 0),
        "last_used_at": _datetime_to_iso(row.get("last_used_at")),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }


def _normalize_workspace_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})

    name = _required_string(source.get("name"), "Workspace name is required", max_length=128)
    data_payload = source.get("payload")
    if data_payload is None:
        data_payload = (existing or {}).get("payload", {})
    if data_payload is None:
        data_payload = {}
    if not isinstance(data_payload, dict):
        raise ValueError("Workspace payload must be an object")

    return {
        "name": name,
        "chart_layout": _optional_string(source.get("chart_layout"), max_length=32) or "single",
        "active_ticker": _optional_string(source.get("active_ticker"), max_length=32),
        "current_period": _optional_string(source.get("current_period"), max_length=16) or "1y",
        "current_interval": _optional_string(source.get("current_interval"), max_length=16) or "1d",
        "workspace_tab": _optional_string(source.get("workspace_tab"), max_length=32) or "chart",
        "comparison_mode": _optional_string(source.get("comparison_mode"), max_length=32) or "percent",
        "payload": data_payload,
        "is_default": _coerce_bool(source.get("is_default"), False),
    }


def _normalize_alert_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})

    ticker = _required_string(source.get("ticker"), "Alert ticker is required", max_length=32).upper()
    alert_type = _required_string(source.get("type"), "Alert type is required", max_length=32)
    condition = _required_string(source.get("condition"), "Alert condition is required", max_length=32)
    condition_payload = source.get("condition_payload")
    if condition_payload is None:
        condition_payload = (existing or {}).get("condition_payload", {})
    if condition_payload is None:
        condition_payload = {}
    if not isinstance(condition_payload, dict):
        raise ValueError("Alert condition payload must be an object")

    name = _optional_string(source.get("name"), max_length=128)
    notification_title = _optional_string(source.get("notification_title"), max_length=255)

    return {
        "name": name or f"{ticker} {condition}",
        "ticker": ticker,
        "type": alert_type,
        "condition": condition,
        "value": _optional_float(source.get("value")),
        "value2": _optional_float(source.get("value2")),
        "timeframe": _optional_string(source.get("timeframe"), max_length=16) or "1d",
        "condition_payload": condition_payload,
        "notification_title": notification_title or name or f"{ticker} {condition}",
        "note": _optional_string(source.get("note"), max_length=4000),
        "active": _coerce_bool(source.get("active"), True),
        "triggered": _coerce_bool(source.get("triggered"), False),
        "triggered_at": source.get("triggered_at"),
        "last_evaluated_at": source.get("last_evaluated_at"),
    }


def _normalize_notification_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(payload or {})
    title = _required_string(source.get("title"), "Notification title is required", max_length=255)
    message = _required_string(source.get("message"), "Notification message is required", max_length=4000)
    extra_payload = source.get("payload") or {}
    if not isinstance(extra_payload, dict):
        raise ValueError("Notification payload must be an object")

    return {
        "category": _optional_string(source.get("category"), max_length=64) or "system",
        "level": _optional_string(source.get("level"), max_length=32) or "info",
        "title": title,
        "message": message,
        "related_entity_type": _optional_string(source.get("related_entity_type"), max_length=64),
        "related_entity_id": _optional_int(source.get("related_entity_id")),
        "link_url": _optional_string(source.get("link_url"), max_length=255),
        "payload": extra_payload,
        "read_at": source.get("read_at"),
    }


def _normalize_quote_payload(quote: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(quote or {})
    ticker = _required_string(source.get("ticker"), "Quote ticker is required", max_length=32).upper()
    quote_timestamp = source.get("quote_timestamp")
    if quote_timestamp is None and source.get("ts") is not None:
        quote_timestamp = source.get("ts")

    return {
        "ticker": ticker,
        "source": _optional_string(source.get("source"), max_length=64) or "local_cache",
        "quote_type": _optional_string(source.get("quote_type"), max_length=64) or "delayed_snapshot",
        "is_delayed": _coerce_bool(source.get("is_delayed"), True),
        "name": _optional_string(source.get("name"), max_length=255) or ticker,
        "currency": _optional_string(source.get("currency"), max_length=16),
        "price": _optional_float(source.get("price")),
        "open": _optional_float(source.get("open")),
        "high": _optional_float(source.get("high")),
        "low": _optional_float(source.get("low")),
        "prev_close": _optional_float(source.get("prev_close")),
        "change": _optional_float(source.get("change")),
        "change_pct": _optional_float(source.get("change_pct")),
        "volume": _optional_int(source.get("volume")),
        "market_cap": _optional_int(source.get("market_cap")),
        "quote_timestamp": quote_timestamp,
        "ts": _optional_int(source.get("ts")),
    }


def _normalize_backtest_run_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(payload or {})
    summary = source.get("summary") or {}
    if not isinstance(summary, dict):
        raise ValueError("Backtest summary must be an object")

    ticker = _required_string(source.get("ticker"), "Backtest ticker is required", max_length=32).upper()
    strategy_key = _required_string(source.get("strategy_key"), "Backtest strategy key is required", max_length=64)
    strategy_name = _required_string(source.get("strategy_name"), "Backtest strategy name is required", max_length=128)
    start_date = _required_date_string(source.get("start_date"), "Backtest start date is required")
    end_date = _required_date_string(source.get("end_date"), "Backtest end date is required")

    return {
        "ticker": ticker,
        "strategy_key": strategy_key,
        "strategy_name": strategy_name,
        "interval": _optional_string(source.get("interval"), max_length=16) or "1d",
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": _optional_float(source.get("initial_capital")) or 0.0,
        "final_equity": _optional_float(source.get("final_equity")) or 0.0,
        "total_return_pct": _optional_float(source.get("total_return_pct")) or 0.0,
        "max_drawdown_pct": _optional_float(source.get("max_drawdown_pct")) or 0.0,
        "sharpe_ratio": _optional_float(source.get("sharpe_ratio")) or 0.0,
        "trade_count": _optional_int(source.get("trade_count")) or 0,
        "win_rate_pct": _optional_float(source.get("win_rate_pct")) or 0.0,
        "bars_count": _optional_int(source.get("bars_count")) or 0,
        "fee_rate": _optional_float(source.get("fee_rate")) or 0.0,
        "slippage_rate": _optional_float(source.get("slippage_rate")) or 0.0,
        "stop_loss_pct": _optional_float(source.get("stop_loss_pct")),
        "take_profit_pct": _optional_float(source.get("take_profit_pct")),
        "position_sizing": _optional_string(source.get("position_sizing"), max_length=32) or "full_equity",
        "summary": summary,
    }


def _normalize_trade_journal_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})

    tags = source.get("tags")
    if tags is None:
        tags = (existing or {}).get("tags", [])
    attachments = source.get("attachments")
    if attachments is None:
        attachments = (existing or {}).get("attachments", [])

    normalized_tags = [
        tag
        for tag in dict.fromkeys(
            _optional_string(item, max_length=64)
            for item in (tags or [])
        )
        if tag
    ]

    normalized_attachments = []
    for item in attachments or []:
        if not isinstance(item, dict):
            raise ValueError("Trade journal attachments must be objects")
        file_path = _required_string(item.get("file_path"), "Attachment file_path is required", max_length=512)
        normalized_attachments.append(
            {
                "file_path": file_path,
                "file_type": _optional_string(item.get("file_type"), max_length=64),
            }
        )

    ticker = _required_string(source.get("ticker"), "Trade journal ticker is required", max_length=32).upper()
    entry_time = source.get("entry_time") or (existing or {}).get("entry_time")
    entry_price = source.get("entry_price") if "entry_price" in source else (existing or {}).get("entry_price")
    size = source.get("size") if "size" in source else (existing or {}).get("size", 0)
    entry_price_value = _optional_float(entry_price)
    size_value = _optional_float(size)
    if entry_price_value is None or entry_price_value <= 0:
        raise ValueError("Trade journal entry_price must be greater than 0")
    if size_value is None or size_value <= 0:
        raise ValueError("Trade journal size must be greater than 0")

    normalized = {
        "ticker": ticker,
        "market": _optional_string(source.get("market"), max_length=32),
        "direction": _optional_string(source.get("direction"), max_length=16) or "long",
        "strategy_code": _optional_string(source.get("strategy_code"), max_length=64),
        "entry_time": _required_string(entry_time, "Trade journal entry_time is required", max_length=64),
        "entry_price": entry_price_value,
        "exit_time": _optional_string(source.get("exit_time"), max_length=64),
        "exit_price": _optional_float(source.get("exit_price")),
        "size": size_value,
        "stop_loss": _optional_float(source.get("stop_loss")),
        "take_profit": _optional_float(source.get("take_profit")),
        "entry_reason": _optional_string(source.get("entry_reason"), max_length=8000),
        "exit_reason": _optional_string(source.get("exit_reason"), max_length=8000),
        "emotion_tag": _optional_string(source.get("emotion_tag"), max_length=64),
        "review_notes": _optional_string(source.get("review_notes"), max_length=20000),
        "tags": normalized_tags,
        "attachments": normalized_attachments,
    }
    explicit_result = source.get("result")
    if explicit_result is not None and not isinstance(explicit_result, dict):
        raise ValueError("Trade journal result must be an object")
    normalized["result"] = dict(explicit_result or compute_trade_result(normalized))
    return normalized


def _normalize_market_event_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(payload or {})
    return {
        "event_type": _required_string(source.get("event_type"), "Market event type is required", max_length=64),
        "market": _optional_string(source.get("market"), max_length=32),
        "ticker": _optional_string(source.get("ticker"), max_length=32),
        "title": _required_string(source.get("title"), "Market event title is required", max_length=255),
        "description": _optional_string(source.get("description"), max_length=4000),
        "event_date": _required_date_string(source.get("event_date"), "Market event date is required"),
        "event_time": source.get("event_time"),
        "importance": _optional_string(source.get("importance"), max_length=32),
        "source": _optional_string(source.get("source"), max_length=128),
        "url": _optional_string(source.get("url"), max_length=512),
        "payload": source.get("payload") if isinstance(source.get("payload"), dict) else {},
    }


def _normalize_news_article_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(payload or {})
    return {
        "ticker": _optional_string(source.get("ticker"), max_length=32),
        "market": _optional_string(source.get("market"), max_length=32),
        "title": _required_string(source.get("title"), "News article title is required", max_length=255),
        "summary": _optional_string(source.get("summary"), max_length=4000),
        "published_at": _required_string(source.get("published_at"), "News article published_at is required", max_length=64),
        "source": _optional_string(source.get("source"), max_length=128),
        "url": _optional_string(source.get("url"), max_length=512),
        "sentiment": _optional_string(source.get("sentiment"), max_length=32),
        "payload": source.get("payload") if isinstance(source.get("payload"), dict) else {},
    }


def _normalize_macro_snapshot_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(payload or {})
    return {
        "metric_code": _required_string(source.get("metric_code"), "Macro snapshot metric_code is required", max_length=64),
        "metric_name": _required_string(source.get("metric_name"), "Macro snapshot metric_name is required", max_length=128),
        "value": _optional_float(source.get("value")),
        "snapshot_date": _required_date_string(source.get("date") or source.get("snapshot_date"), "Macro snapshot date is required"),
        "source": _optional_string(source.get("source"), max_length=128),
        "payload": source.get("payload") if isinstance(source.get("payload"), dict) else {
            key: value
            for key, value in source.items()
            if key not in {"metric_code", "metric_name", "value", "date", "snapshot_date", "source"}
        },
    }


def _normalize_taiwan_chip_snapshot_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(payload or {})
    return {
        "ticker": _required_string(source.get("ticker"), "Taiwan chip ticker is required", max_length=32).upper(),
        "market": _optional_string(source.get("market"), max_length=32),
        "snapshot_date": _required_date_string(source.get("snapshot_date") or source.get("date"), "Taiwan chip snapshot date is required"),
        "margin_balance": _optional_int(source.get("margin_balance")),
        "short_balance": _optional_int(source.get("short_balance")),
        "securities_lending_balance": _optional_int(source.get("securities_lending_balance")),
        "institutional_net_buy_sell": _optional_int(source.get("institutional_net_buy_sell")),
        "source": _optional_string(source.get("source"), max_length=128),
        "branch_payload": source.get("branch_payload") if isinstance(source.get("branch_payload"), dict) else {},
        "summary": source.get("summary") if isinstance(source.get("summary"), dict) else {},
    }


def _normalize_screener_preset_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})
    filters = source.get("filters")
    if filters is None:
        filters = (existing or {}).get("filters", {})
    if not isinstance(filters, dict):
        raise ValueError("Screener preset filters must be an object")
    return {
        "name": _required_string(source.get("name"), "Screener preset name is required", max_length=128),
        "description": _optional_string(source.get("description"), max_length=512),
        "filters": filters,
    }


def _normalize_journal_filter_preset_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})
    filters = source.get("filters")
    if filters is None:
        filters = (existing or {}).get("filters", {})
    if not isinstance(filters, dict):
        raise ValueError("Journal filter preset filters must be an object")

    normalized_scope = _optional_string(source.get("scope"), max_length=32) or "ticker"
    if normalized_scope not in {"ticker", "all"}:
        raise ValueError("Journal filter preset scope must be ticker or all")

    normalized_filters = {
        key: _optional_string(filters.get(key), max_length=128) or ""
        for key in ["market", "strategy_code", "tag", "search"]
    }

    return {
        "name": _required_string(source.get("name"), "Journal filter preset name is required", max_length=128),
        "description": _optional_string(source.get("description"), max_length=512),
        "scope": normalized_scope,
        "filters": normalized_filters,
    }


def _required_string(value: Any, error_message: str, max_length: Optional[int] = None) -> str:
    normalized = _optional_string(value, max_length=max_length)
    if not normalized:
        raise ValueError(error_message)
    return normalized


def _required_date_string(value: Any, error_message: str) -> str:
    normalized = _optional_date_string(value)
    if not normalized:
        raise ValueError(error_message)
    return normalized


def _optional_date_string(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            return datetime.fromisoformat(normalized).date().isoformat()
        except ValueError:
            try:
                return date.fromisoformat(normalized).isoformat()
            except ValueError:
                return None
    return None


def _optional_string(value: Any, max_length: Optional[int] = None) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if max_length:
        return text[:max_length]
    return text


def _optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Unable to parse float from {value!r}")


def _optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Unable to parse int from {value!r}")


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime_value(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        if value.tzinfo:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
        return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    return None


db = Database()


async def init_db():
    await db.connect()
    await db.create_tables()
    log.info(
        "MySQL initialized: %s@%s:%s/%s",
        MYSQL_USER,
        MYSQL_HOST,
        MYSQL_PORT,
        MYSQL_DATABASE,
    )


def _period_to_date(period: str) -> str:
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    if not period:
        return (now_utc - timedelta(days=365)).strftime("%Y-%m-%d")
    if period == "max":
        return "1900-01-01"
    n, unit = int(period[:-2]) if period[:-2].isdigit() else int(period[:-1]), period[-1]
    if period[:-2].isdigit():
        n, unit = int(period[:-2]), period[-2:]
        if unit == "mo":
            d = now_utc - timedelta(days=n * 30)
        elif unit == "yr" or unit == "y":
            d = now_utc - timedelta(days=n * 365)
        else:
            d = now_utc - timedelta(days=30)
    else:
        n = int(period[:-1])
        unit = period[-1]
        if unit == "y":
            d = now_utc - timedelta(days=n * 365)
        elif unit == "m":
            d = now_utc - timedelta(days=n * 30)
        elif unit == "d":
            d = now_utc - timedelta(days=n)
        else:
            d = now_utc - timedelta(days=365)
    return d.strftime("%Y-%m-%d")


def _build_mysql_error_message(exc: Exception) -> str:
    return (
        "MySQL 連線失敗。\n"
        f"目前設定: host={MYSQL_HOST}, port={MYSQL_PORT}, user={MYSQL_USER}, "
        f"database={MYSQL_DATABASE}, password={'已設定' if MYSQL_PASSWORD else '未設定'}。\n"
        "請在專案根目錄建立 `.env`，至少設定 `MYSQL_USER`、`MYSQL_PASSWORD`，必要時也設定 "
        "`MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_DATABASE`。\n"
        "你可以直接複製 `.env.example` 成 `.env` 再修改。\n"
        f"原始錯誤: {exc}"
    )


def _build_mysql_connection_error_message(exc: Exception) -> str:
    message = str(exc)
    if "cryptography" in message and ("caching_sha2_password" in message or "sha256_password" in message):
        return (
            "MySQL 連線失敗：目前 MySQL 使用 `caching_sha2_password` / `sha256_password` 驗證，"
            "但 Python 環境缺少 `cryptography` 套件。\n"
            "請重新安裝 backend dependencies，或手動執行：\n"
            "`venv\\Scripts\\python.exe -m pip install cryptography`\n"
            f"原始錯誤: {exc}"
        )
    return _build_mysql_error_message(exc)


def _escape_identifier(value: str) -> str:
    return value.replace("`", "``")


def _date_to_iso(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _datetime_to_iso(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).isoformat()
    return str(value)
