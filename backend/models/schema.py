from typing import Dict, List, Set

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
