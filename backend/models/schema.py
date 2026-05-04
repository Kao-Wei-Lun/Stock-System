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
            KEY `idx_ohlcv_ticker_interval_date` (`ticker`, `interval`, `date`),
            KEY `idx_ohlcv_ticker_date_lookup` (`ticker`, `date`)
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
            KEY `idx_market_quotes_latest_synced_at` (`synced_at`),
            KEY `idx_market_quotes_latest_quote_recency` (`quote_timestamp`, `synced_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "fubon_api_accounts": """
        CREATE TABLE `fubon_api_accounts` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `label` VARCHAR(100) NOT NULL,
            `user_id` VARCHAR(50) NOT NULL,
            `password_enc` TEXT NOT NULL,
            `cert_path` VARCHAR(500) NULL,
            `cert_password_enc` TEXT NULL,
            `api_key_enc` TEXT NOT NULL,
            `ws_mode` VARCHAR(10) NOT NULL DEFAULT 'Speed',
            `is_active` TINYINT NOT NULL DEFAULT 0,
            `is_enabled` TINYINT NOT NULL DEFAULT 1,
            `connection_status` VARCHAR(20) NOT NULL DEFAULT 'disconnected',
            `connection_error` TEXT NULL,
            `last_connected_at` DATETIME NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_fubon_api_accounts_active` (`is_active`, `is_enabled`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        COMMENT='Fubon Neo API account settings'
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
            `color` VARCHAR(32) NULL,
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
    "taifex_institutional_meta": """
        CREATE TABLE `taifex_institutional_meta` (
            `resolved_date` DATE NOT NULL,
            `query_date` DATE NOT NULL,
            `previous_date` DATE NULL,
            `default_futures_commodity` VARCHAR(64) NULL,
            `default_options_commodity` VARCHAR(64) NULL,
            `cash_summary_source` VARCHAR(64) NULL,
            `cash_summary_warning` TEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`resolved_date`),
            KEY `idx_taifex_institutional_meta_query_date` (`query_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "taifex_overview_daily": """
        CREATE TABLE `taifex_overview_daily` (
            `resolved_date` DATE NOT NULL,
            `institution` VARCHAR(32) NOT NULL,
            `trade_long_futures_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_long_options_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_long_futures_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_long_options_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_short_futures_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_short_options_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_short_futures_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_short_options_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_net_futures_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_net_options_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_net_futures_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_net_options_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_net_futures_volume_change` BIGINT NOT NULL DEFAULT 0,
            `trade_net_options_volume_change` BIGINT NOT NULL DEFAULT 0,
            `trade_net_futures_amount_change` BIGINT NOT NULL DEFAULT 0,
            `trade_net_options_amount_change` BIGINT NOT NULL DEFAULT 0,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`resolved_date`, `institution`),
            KEY `idx_taifex_overview_daily_institution_date` (`institution`, `resolved_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "taifex_futures_daily": """
        CREATE TABLE `taifex_futures_daily` (
            `resolved_date` DATE NOT NULL,
            `commodity` VARCHAR(64) NOT NULL,
            `institution` VARCHAR(32) NOT NULL,
            `rank` INT NOT NULL DEFAULT 0,
            `trade_long_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_long_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_short_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_short_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_net_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_net_amount` BIGINT NOT NULL DEFAULT 0,
            `oi_long_volume` BIGINT NOT NULL DEFAULT 0,
            `oi_long_amount` BIGINT NOT NULL DEFAULT 0,
            `oi_short_volume` BIGINT NOT NULL DEFAULT 0,
            `oi_short_amount` BIGINT NOT NULL DEFAULT 0,
            `oi_net_volume` BIGINT NOT NULL DEFAULT 0,
            `oi_net_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_net_volume_change` BIGINT NOT NULL DEFAULT 0,
            `trade_net_amount_change` BIGINT NOT NULL DEFAULT 0,
            `oi_net_volume_change` BIGINT NOT NULL DEFAULT 0,
            `oi_net_amount_change` BIGINT NOT NULL DEFAULT 0,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`resolved_date`, `commodity`, `institution`),
            KEY `idx_taifex_futures_daily_commodity_date` (`commodity`, `resolved_date`),
            KEY `idx_taifex_futures_daily_institution_date` (`institution`, `resolved_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "taifex_options_daily": """
        CREATE TABLE `taifex_options_daily` (
            `resolved_date` DATE NOT NULL,
            `commodity` VARCHAR(64) NOT NULL,
            `institution` VARCHAR(32) NOT NULL,
            `rank` INT NOT NULL DEFAULT 0,
            `trade_long_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_long_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_short_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_short_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_net_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_net_amount` BIGINT NOT NULL DEFAULT 0,
            `oi_long_volume` BIGINT NOT NULL DEFAULT 0,
            `oi_long_amount` BIGINT NOT NULL DEFAULT 0,
            `oi_short_volume` BIGINT NOT NULL DEFAULT 0,
            `oi_short_amount` BIGINT NOT NULL DEFAULT 0,
            `oi_net_volume` BIGINT NOT NULL DEFAULT 0,
            `oi_net_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_net_volume_change` BIGINT NOT NULL DEFAULT 0,
            `trade_net_amount_change` BIGINT NOT NULL DEFAULT 0,
            `oi_net_volume_change` BIGINT NOT NULL DEFAULT 0,
            `oi_net_amount_change` BIGINT NOT NULL DEFAULT 0,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`resolved_date`, `commodity`, `institution`),
            KEY `idx_taifex_options_daily_commodity_date` (`commodity`, `resolved_date`),
            KEY `idx_taifex_options_daily_institution_date` (`institution`, `resolved_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "taifex_call_put_daily": """
        CREATE TABLE `taifex_call_put_daily` (
            `resolved_date` DATE NOT NULL,
            `commodity` VARCHAR(64) NOT NULL,
            `option_side` VARCHAR(16) NOT NULL,
            `institution` VARCHAR(32) NOT NULL,
            `rank` INT NOT NULL DEFAULT 0,
            `trade_buy_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_buy_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_sell_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_sell_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_net_volume` BIGINT NOT NULL DEFAULT 0,
            `trade_net_amount` BIGINT NOT NULL DEFAULT 0,
            `oi_buy_volume` BIGINT NOT NULL DEFAULT 0,
            `oi_buy_amount` BIGINT NOT NULL DEFAULT 0,
            `oi_sell_volume` BIGINT NOT NULL DEFAULT 0,
            `oi_sell_amount` BIGINT NOT NULL DEFAULT 0,
            `oi_net_volume` BIGINT NOT NULL DEFAULT 0,
            `oi_net_amount` BIGINT NOT NULL DEFAULT 0,
            `trade_net_volume_change` BIGINT NOT NULL DEFAULT 0,
            `trade_net_amount_change` BIGINT NOT NULL DEFAULT 0,
            `oi_net_volume_change` BIGINT NOT NULL DEFAULT 0,
            `oi_net_amount_change` BIGINT NOT NULL DEFAULT 0,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`resolved_date`, `commodity`, `option_side`, `institution`),
            KEY `idx_taifex_call_put_daily_commodity_date` (`commodity`, `resolved_date`),
            KEY `idx_taifex_call_put_daily_institution_date` (`institution`, `resolved_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "taifex_cash_summary_daily": """
        CREATE TABLE `taifex_cash_summary_daily` (
            `resolved_date` DATE NOT NULL,
            `institution` VARCHAR(64) NOT NULL,
            `buy_amount` BIGINT NOT NULL DEFAULT 0,
            `sell_amount` BIGINT NOT NULL DEFAULT 0,
            `net_amount` BIGINT NOT NULL DEFAULT 0,
            `net_amount_change` BIGINT NOT NULL DEFAULT 0,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`resolved_date`, `institution`),
            KEY `idx_taifex_cash_summary_daily_institution_date` (`institution`, `resolved_date`)
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
            `foreign_net_buy_sell` BIGINT NULL,
            `investment_trust_net_buy_sell` BIGINT NULL,
            `dealer_net_buy_sell` BIGINT NULL,
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
    "fubon_market_snapshots": """
        CREATE TABLE `fubon_market_snapshots` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `market` VARCHAR(32) NOT NULL,
            `snapshot_date` DATE NOT NULL,
            `payload_json` LONGTEXT NOT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_fubon_market_snapshots_market_date` (`market`, `snapshot_date`),
            KEY `idx_fubon_market_snapshots_date` (`snapshot_date`, `market`)
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
    "asset_accounts": """
        CREATE TABLE `asset_accounts` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `name` VARCHAR(128) NOT NULL,
            `institution` VARCHAR(128) NULL,
            `account_type` VARCHAR(64) NOT NULL DEFAULT 'brokerage',
            `base_currency` VARCHAR(16) NOT NULL DEFAULT 'TWD',
            `settlement_account_id` BIGINT NULL,
            `auto_sync_trade_settlement` TINYINT NOT NULL DEFAULT 0,
            `include_in_total` TINYINT NOT NULL DEFAULT 1,
            `sort_order` INT NOT NULL DEFAULT 0,
            `notes` TEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_asset_accounts_owner_name` (`owner_id`, `name`),
            KEY `idx_asset_accounts_owner_sort` (`owner_id`, `sort_order`, `id`),
            KEY `idx_asset_accounts_settlement` (`settlement_account_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "asset_cash_ledger": """
        CREATE TABLE `asset_cash_ledger` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NOT NULL,
            `flow_date` DATETIME NOT NULL,
            `flow_type` VARCHAR(32) NOT NULL,
            `amount` DOUBLE NOT NULL,
            `currency` VARCHAR(16) NOT NULL DEFAULT 'TWD',
            `fx_rate_to_base` DOUBLE NOT NULL DEFAULT 1,
            `is_initial_balance` TINYINT NOT NULL DEFAULT 0,
            `source` VARCHAR(64) NOT NULL DEFAULT 'manual',
            `linked_trade_id` BIGINT NULL,
            `linked_trade_role` VARCHAR(32) NULL,
            `counterparty` VARCHAR(128) NULL,
            `note` TEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_asset_cash_ledger_owner_date` (`owner_id`, `flow_date`, `id`),
            KEY `idx_asset_cash_ledger_account_date` (`account_id`, `flow_date`, `id`),
            KEY `idx_asset_cash_ledger_linked_trade` (`linked_trade_id`, `linked_trade_role`, `id`),
            CONSTRAINT `fk_asset_cash_ledger_account`
                FOREIGN KEY (`account_id`) REFERENCES `asset_accounts` (`id`)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "asset_trade_ledger": """
        CREATE TABLE `asset_trade_ledger` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NOT NULL,
            `trade_date` DATETIME NOT NULL,
            `ticker` VARCHAR(32) NOT NULL,
            `display_name` VARCHAR(255) NULL,
            `market` VARCHAR(32) NULL,
            `asset_type` VARCHAR(32) NOT NULL DEFAULT 'stock',
            `currency` VARCHAR(16) NOT NULL DEFAULT 'TWD',
            `side` VARCHAR(16) NOT NULL,
            `quantity` DOUBLE NOT NULL,
            `price` DOUBLE NOT NULL,
            `gross_amount` DOUBLE NOT NULL,
            `fee_amount` DOUBLE NOT NULL DEFAULT 0,
            `tax_amount` DOUBLE NOT NULL DEFAULT 0,
            `net_amount` DOUBLE NOT NULL,
            `fx_rate_to_base` DOUBLE NOT NULL DEFAULT 1,
            `is_initial_balance` TINYINT NOT NULL DEFAULT 0,
            `source` VARCHAR(64) NOT NULL DEFAULT 'manual',
            `note` TEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_asset_trade_ledger_owner_date` (`owner_id`, `trade_date`, `id`),
            KEY `idx_asset_trade_ledger_account_ticker` (`account_id`, `ticker`, `trade_date`),
            CONSTRAINT `fk_asset_trade_ledger_account`
                FOREIGN KEY (`account_id`) REFERENCES `asset_accounts` (`id`)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "asset_positions_current": """
        CREATE TABLE `asset_positions_current` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NOT NULL,
            `ticker` VARCHAR(32) NOT NULL,
            `display_name` VARCHAR(255) NULL,
            `market` VARCHAR(32) NULL,
            `asset_type` VARCHAR(32) NOT NULL DEFAULT 'stock',
            `currency` VARCHAR(16) NOT NULL DEFAULT 'TWD',
            `quantity` DOUBLE NOT NULL DEFAULT 0,
            `avg_cost` DOUBLE NOT NULL DEFAULT 0,
            `cost_basis` DOUBLE NOT NULL DEFAULT 0,
            `realized_pnl` DOUBLE NOT NULL DEFAULT 0,
            `trade_count` INT NOT NULL DEFAULT 0,
            `last_trade_at` DATETIME NULL,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_asset_positions_current_owner_account_ticker` (`owner_id`, `account_id`, `ticker`),
            KEY `idx_asset_positions_current_owner_account` (`owner_id`, `account_id`, `ticker`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "asset_valuations_current": """
        CREATE TABLE `asset_valuations_current` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NOT NULL,
            `ticker` VARCHAR(32) NOT NULL,
            `quote_source` VARCHAR(64) NULL,
            `quote_type` VARCHAR(64) NULL,
            `is_delayed` TINYINT NOT NULL DEFAULT 1,
            `quote_timestamp` DATETIME NULL,
            `last_price` DOUBLE NULL,
            `market_value` DOUBLE NULL,
            `market_value_base` DOUBLE NULL,
            `unrealized_pnl` DOUBLE NULL,
            `unrealized_pnl_base` DOUBLE NULL,
            `fx_rate_to_base` DOUBLE NULL,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_asset_valuations_current_owner_account_ticker` (`owner_id`, `account_id`, `ticker`),
            KEY `idx_asset_valuations_current_owner_account` (`owner_id`, `account_id`, `ticker`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "asset_reconciliation_snapshots": """
        CREATE TABLE `asset_reconciliation_snapshots` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NOT NULL,
            `snapshot_date` DATETIME NOT NULL,
            `cash_actual` DOUBLE NULL,
            `cash_system` DOUBLE NULL,
            `market_value_actual` DOUBLE NULL,
            `market_value_system` DOUBLE NULL,
            `positions_payload_json` LONGTEXT NULL,
            `note` TEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_asset_reconciliation_snapshots_owner_date` (`owner_id`, `snapshot_date`, `id`),
            KEY `idx_asset_reconciliation_snapshots_account_date` (`account_id`, `snapshot_date`, `id`),
            CONSTRAINT `fk_asset_reconciliation_snapshots_account`
                FOREIGN KEY (`account_id`) REFERENCES `asset_accounts` (`id`)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "asset_price_overrides": """
        CREATE TABLE `asset_price_overrides` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NULL,
            `ticker` VARCHAR(32) NOT NULL,
            `effective_at` DATETIME NOT NULL,
            `price` DOUBLE NOT NULL,
            `currency` VARCHAR(16) NOT NULL DEFAULT 'TWD',
            `fx_rate_to_base` DOUBLE NULL,
            `force_override` TINYINT NOT NULL DEFAULT 0,
            `note` TEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_asset_price_overrides_owner_ticker_date` (`owner_id`, `ticker`, `effective_at`, `id`),
            KEY `idx_asset_price_overrides_account_ticker_date` (`account_id`, `ticker`, `effective_at`, `id`),
            CONSTRAINT `fk_asset_price_overrides_account`
                FOREIGN KEY (`account_id`) REFERENCES `asset_accounts` (`id`)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "asset_fx_rates_daily": """
        CREATE TABLE `asset_fx_rates_daily` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `snapshot_date` DATE NOT NULL,
            `from_currency` VARCHAR(16) NOT NULL,
            `to_currency` VARCHAR(16) NOT NULL,
            `rate` DOUBLE NOT NULL,
            `source` VARCHAR(64) NOT NULL DEFAULT 'manual',
            `note` TEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_asset_fx_rates_daily_owner_pair_date` (`owner_id`, `snapshot_date`, `from_currency`, `to_currency`),
            KEY `idx_asset_fx_rates_daily_owner_date` (`owner_id`, `snapshot_date`, `id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "asset_position_adjustments": """
        CREATE TABLE `asset_position_adjustments` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NOT NULL,
            `event_date` DATETIME NOT NULL,
            `ticker` VARCHAR(32) NOT NULL,
            `event_type` VARCHAR(32) NOT NULL DEFAULT 'adjustment',
            `quantity_delta` DOUBLE NULL,
            `cost_basis_delta` DOUBLE NULL,
            `cash_delta` DOUBLE NULL,
            `currency` VARCHAR(16) NULL,
            `split_ratio` DOUBLE NULL,
            `target_ticker` VARCHAR(32) NULL,
            `target_display_name` VARCHAR(255) NULL,
            `target_market` VARCHAR(32) NULL,
            `target_asset_type` VARCHAR(32) NULL,
            `note` TEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_asset_position_adjustments_owner_date` (`owner_id`, `event_date`, `id`),
            KEY `idx_asset_position_adjustments_account_ticker_date` (`account_id`, `ticker`, `event_date`, `id`),
            CONSTRAINT `fk_asset_position_adjustments_account`
                FOREIGN KEY (`account_id`) REFERENCES `asset_accounts` (`id`)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "paper_trading_accounts": """
        CREATE TABLE `paper_trading_accounts` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `name` VARCHAR(128) NOT NULL,
            `product_symbol` VARCHAR(32) NOT NULL DEFAULT 'TMF',
            `starting_equity` DOUBLE NOT NULL DEFAULT 100000,
            `initial_margin_per_contract` DOUBLE NOT NULL DEFAULT 26300,
            `margin_source` VARCHAR(64) NOT NULL DEFAULT 'manual',
            `margin_reference_symbol` VARCHAR(32) NULL,
            `margin_currency` VARCHAR(16) NULL,
            `margin_synced_at` DATETIME NULL,
            `margin_sync_error` TEXT NULL,
            `risk_config_json` LONGTEXT NOT NULL,
            `cost_model_json` LONGTEXT NOT NULL,
            `strategy_config_json` LONGTEXT NULL,
            `is_active` TINYINT NOT NULL DEFAULT 1,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_paper_trading_accounts_owner` (`owner_id`, `is_active`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "paper_trading_bots": """
        CREATE TABLE `paper_trading_bots` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NOT NULL,
            `name` VARCHAR(128) NOT NULL,
            `mode` VARCHAR(32) NOT NULL DEFAULT 'realtime',
            `product_symbol` VARCHAR(32) NOT NULL DEFAULT 'TMF',
            `direction_symbol` VARCHAR(32) NOT NULL DEFAULT 'TXF',
            `session_mode` VARCHAR(32) NOT NULL DEFAULT 'day_session_only',
            `holding_policy` VARCHAR(32) NOT NULL DEFAULT 'day_only',
            `status` VARCHAR(32) NOT NULL DEFAULT 'idle',
            `strategy_config_json` LONGTEXT NULL,
            `started_at` DATETIME NULL,
            `stopped_at` DATETIME NULL,
            `last_signal_at` DATETIME NULL,
            `bar_count` INT NOT NULL DEFAULT 0,
            `error_message` TEXT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_paper_trading_bots_owner_status` (`owner_id`, `status`),
            KEY `idx_paper_trading_bots_account` (`account_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "paper_trading_positions": """
        CREATE TABLE `paper_trading_positions` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NOT NULL,
            `bot_id` BIGINT NULL,
            `symbol` VARCHAR(32) NOT NULL,
            `requested_symbol` VARCHAR(32) NULL,
            `resolved_symbol` VARCHAR(32) NULL,
            `side` VARCHAR(16) NOT NULL,
            `qty` INT NOT NULL DEFAULT 0,
            `avg_entry_price` DOUBLE NOT NULL DEFAULT 0,
            `unrealized_pnl` DOUBLE NOT NULL DEFAULT 0,
            `realized_pnl` DOUBLE NOT NULL DEFAULT 0,
            `last_price` DOUBLE NULL,
            `entry_time` DATETIME NULL,
            `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_paper_trading_positions_account` (`account_id`, `symbol`),
            KEY `idx_paper_trading_positions_bot` (`bot_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "paper_trading_orders": """
        CREATE TABLE `paper_trading_orders` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NOT NULL,
            `bot_id` BIGINT NULL,
            `order_id` VARCHAR(64) NOT NULL,
            `symbol` VARCHAR(32) NOT NULL,
            `requested_symbol` VARCHAR(32) NULL,
            `resolved_symbol` VARCHAR(32) NULL,
            `side` VARCHAR(16) NOT NULL,
            `qty` INT NOT NULL,
            `order_type` VARCHAR(32) NOT NULL,
            `price` DOUBLE NULL,
            `stop_price` DOUBLE NULL,
            `session` VARCHAR(16) NOT NULL DEFAULT 'day',
            `status` VARCHAR(32) NOT NULL DEFAULT 'pending',
            `reason` TEXT NULL,
            `signal_bar_time` DATETIME NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_paper_trading_orders_account_created` (`account_id`, `created_at`),
            KEY `idx_paper_trading_orders_bot` (`bot_id`, `created_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "paper_trading_fills": """
        CREATE TABLE `paper_trading_fills` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NOT NULL,
            `bot_id` BIGINT NULL,
            `order_id` VARCHAR(64) NULL,
            `fill_id` VARCHAR(64) NOT NULL,
            `symbol` VARCHAR(32) NOT NULL,
            `side` VARCHAR(16) NOT NULL,
            `fill_qty` INT NOT NULL,
            `fill_price` DOUBLE NOT NULL,
            `slippage_ticks` DOUBLE NOT NULL DEFAULT 0,
            `fee_amount` DOUBLE NOT NULL DEFAULT 0,
            `fill_reason` VARCHAR(64) NOT NULL,
            `session` VARCHAR(16) NOT NULL DEFAULT 'day',
            `bar_open` DOUBLE NULL,
            `bar_high` DOUBLE NULL,
            `bar_low` DOUBLE NULL,
            `bar_close` DOUBLE NULL,
            `fill_time` DATETIME NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_paper_trading_fills_account_time` (`account_id`, `fill_time`),
            KEY `idx_paper_trading_fills_bot` (`bot_id`, `fill_time`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "paper_trading_equity_snapshots": """
        CREATE TABLE `paper_trading_equity_snapshots` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NOT NULL,
            `bot_id` BIGINT NULL,
            `replay_run_id` BIGINT NULL,
            `snapshot_time` DATETIME NOT NULL,
            `equity` DOUBLE NOT NULL,
            `cash` DOUBLE NOT NULL,
            `margin_used` DOUBLE NOT NULL DEFAULT 0,
            `unrealized_pnl` DOUBLE NOT NULL DEFAULT 0,
            `realized_pnl` DOUBLE NOT NULL DEFAULT 0,
            `position_qty` INT NOT NULL DEFAULT 0,
            `position_side` VARCHAR(16) NULL,
            `close_price` DOUBLE NULL,
            `drawdown_pct` DOUBLE NOT NULL DEFAULT 0,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_paper_trading_equity_snapshots_account` (`account_id`, `snapshot_time`),
            KEY `idx_paper_trading_equity_snapshots_replay` (`replay_run_id`, `snapshot_time`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "paper_trading_risk_events": """
        CREATE TABLE `paper_trading_risk_events` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NOT NULL,
            `bot_id` BIGINT NULL,
            `replay_run_id` BIGINT NULL,
            `event_type` VARCHAR(64) NOT NULL,
            `details_json` LONGTEXT NULL,
            `event_time` DATETIME NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_paper_trading_risk_events_account` (`account_id`, `created_at`),
            KEY `idx_paper_trading_risk_events_replay` (`replay_run_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "paper_trading_contract_resolutions": """
        CREATE TABLE `paper_trading_contract_resolutions` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `requested_symbol` VARCHAR(32) NOT NULL,
            `resolved_symbol` VARCHAR(32) NOT NULL,
            `resolution_date` DATE NOT NULL,
            `contract_type` VARCHAR(32) NULL,
            `end_date` DATE NULL,
            `instrument_type` VARCHAR(32) NOT NULL DEFAULT 'future',
            `source` VARCHAR(64) NOT NULL DEFAULT 'fubon_neo',
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_paper_trading_contract_res` (`requested_symbol`, `resolution_date`),
            KEY `idx_paper_trading_contract_res_date` (`resolution_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "paper_trading_cost_models": """
        CREATE TABLE `paper_trading_cost_models` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `version` VARCHAR(32) NOT NULL,
            `product_symbol` VARCHAR(32) NOT NULL DEFAULT 'TMF',
            `broker_fee_per_side` DOUBLE NOT NULL DEFAULT 20,
            `exchange_fee_per_side` DOUBLE NOT NULL DEFAULT 2,
            `futures_tax_per_side` DOUBLE NOT NULL DEFAULT 0,
            `slippage_ticks_day` DOUBLE NOT NULL DEFAULT 1,
            `slippage_ticks_night` DOUBLE NOT NULL DEFAULT 2,
            `is_active` TINYINT NOT NULL DEFAULT 1,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_paper_trading_cost_models_owner` (`owner_id`, `is_active`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "paper_trading_replay_runs": """
        CREATE TABLE `paper_trading_replay_runs` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `account_id` BIGINT NULL,
            `bot_id` BIGINT NULL,
            `product_symbol` VARCHAR(32) NOT NULL DEFAULT 'TMF',
            `direction_symbol` VARCHAR(32) NOT NULL DEFAULT 'TXF',
            `start_date` DATE NOT NULL,
            `end_date` DATE NOT NULL,
            `bar_count` INT NOT NULL DEFAULT 0,
            `trade_count` INT NOT NULL DEFAULT 0,
            `starting_equity` DOUBLE NOT NULL,
            `final_equity` DOUBLE NOT NULL,
            `total_return_pct` DOUBLE NOT NULL DEFAULT 0,
            `max_drawdown_pct` DOUBLE NOT NULL DEFAULT 0,
            `win_rate_pct` DOUBLE NOT NULL DEFAULT 0,
            `profit_factor` DOUBLE NOT NULL DEFAULT 0,
            `total_pnl` DOUBLE NOT NULL DEFAULT 0,
            `total_fees` DOUBLE NOT NULL DEFAULT 0,
            `risk_config_json` LONGTEXT NOT NULL,
            `strategy_config_json` LONGTEXT NOT NULL,
            `cost_model_json` LONGTEXT NOT NULL,
            `summary_json` LONGTEXT NOT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_paper_trading_replay_runs_owner` (`owner_id`, `created_at`),
            KEY `idx_paper_trading_replay_runs_account` (`account_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "paper_trading_continuous_rolls": """
        CREATE TABLE `paper_trading_continuous_rolls` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `owner_id` BIGINT NOT NULL DEFAULT 1,
            `from_symbol` VARCHAR(32) NOT NULL,
            `to_symbol` VARCHAR(32) NOT NULL,
            `roll_timestamp` DATETIME NOT NULL,
            `roll_reason` VARCHAR(64) NOT NULL DEFAULT 'volume_shift',
            `product_base` VARCHAR(16) NOT NULL DEFAULT 'TMF',
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_paper_trading_continuous_rolls_product` (`product_base`, `roll_timestamp`)
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
        "color": """
            ALTER TABLE `watchlist_groups`
            ADD COLUMN `color` VARCHAR(32) NULL AFTER `name`
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
    "taiwan_chip_snapshots": {
        "foreign_net_buy_sell": """
            ALTER TABLE `taiwan_chip_snapshots`
            ADD COLUMN `foreign_net_buy_sell` BIGINT NULL AFTER `securities_lending_balance`
        """,
        "investment_trust_net_buy_sell": """
            ALTER TABLE `taiwan_chip_snapshots`
            ADD COLUMN `investment_trust_net_buy_sell` BIGINT NULL AFTER `foreign_net_buy_sell`
        """,
        "dealer_net_buy_sell": """
            ALTER TABLE `taiwan_chip_snapshots`
            ADD COLUMN `dealer_net_buy_sell` BIGINT NULL AFTER `investment_trust_net_buy_sell`
        """,
    },
    "asset_accounts": {
        "settlement_account_id": """
            ALTER TABLE `asset_accounts`
            ADD COLUMN `settlement_account_id` BIGINT NULL AFTER `base_currency`
        """,
        "auto_sync_trade_settlement": """
            ALTER TABLE `asset_accounts`
            ADD COLUMN `auto_sync_trade_settlement` TINYINT NOT NULL DEFAULT 0 AFTER `settlement_account_id`
        """,
    },
    "asset_cash_ledger": {
        "is_initial_balance": """
            ALTER TABLE `asset_cash_ledger`
            ADD COLUMN `is_initial_balance` TINYINT NOT NULL DEFAULT 0 AFTER `fx_rate_to_base`
        """,
        "source": """
            ALTER TABLE `asset_cash_ledger`
            ADD COLUMN `source` VARCHAR(64) NOT NULL DEFAULT 'manual' AFTER `is_initial_balance`
        """,
        "linked_trade_id": """
            ALTER TABLE `asset_cash_ledger`
            ADD COLUMN `linked_trade_id` BIGINT NULL AFTER `source`
        """,
        "linked_trade_role": """
            ALTER TABLE `asset_cash_ledger`
            ADD COLUMN `linked_trade_role` VARCHAR(32) NULL AFTER `linked_trade_id`
        """,
    },
    "asset_trade_ledger": {
        "is_initial_balance": """
            ALTER TABLE `asset_trade_ledger`
            ADD COLUMN `is_initial_balance` TINYINT NOT NULL DEFAULT 0 AFTER `fx_rate_to_base`
        """,
    },
    "paper_trading_accounts": {
        "margin_source": """
            ALTER TABLE `paper_trading_accounts`
            ADD COLUMN `margin_source` VARCHAR(64) NOT NULL DEFAULT 'manual'
            AFTER `initial_margin_per_contract`
        """,
        "margin_reference_symbol": """
            ALTER TABLE `paper_trading_accounts`
            ADD COLUMN `margin_reference_symbol` VARCHAR(32) NULL
            AFTER `margin_source`
        """,
        "margin_currency": """
            ALTER TABLE `paper_trading_accounts`
            ADD COLUMN `margin_currency` VARCHAR(16) NULL
            AFTER `margin_reference_symbol`
        """,
        "margin_synced_at": """
            ALTER TABLE `paper_trading_accounts`
            ADD COLUMN `margin_synced_at` DATETIME NULL
            AFTER `margin_currency`
        """,
        "margin_sync_error": """
            ALTER TABLE `paper_trading_accounts`
            ADD COLUMN `margin_sync_error` TEXT NULL
            AFTER `margin_synced_at`
        """,
    },
}


REQUIRED_INDEX_MIGRATIONS = {
    "ohlcv": {
        "idx_ohlcv_ticker_date_lookup": """
            ALTER TABLE `ohlcv`
            ADD INDEX `idx_ohlcv_ticker_date_lookup` (`ticker`, `date`)
        """,
    },
    "asset_accounts": {
        "idx_asset_accounts_settlement": """
            ALTER TABLE `asset_accounts`
            ADD INDEX `idx_asset_accounts_settlement` (`settlement_account_id`)
        """,
    },
    "asset_cash_ledger": {
        "idx_asset_cash_ledger_linked_trade": """
            ALTER TABLE `asset_cash_ledger`
            ADD INDEX `idx_asset_cash_ledger_linked_trade` (`linked_trade_id`, `linked_trade_role`, `id`)
        """,
    },
    "market_quotes_latest": {
        "idx_market_quotes_latest_quote_recency": """
            ALTER TABLE `market_quotes_latest`
            ADD INDEX `idx_market_quotes_latest_quote_recency` (`quote_timestamp`, `synced_at`)
        """,
    },
    "taiwan_chip_snapshots": {
        "idx_taiwan_chip_snapshots_source": """
            ALTER TABLE `taiwan_chip_snapshots`
            ADD INDEX `idx_taiwan_chip_snapshots_source` (`source`)
        """,
        "idx_taiwan_chip_snapshots_snapshot_date_source": """
            ALTER TABLE `taiwan_chip_snapshots`
            ADD INDEX `idx_taiwan_chip_snapshots_snapshot_date_source` (`snapshot_date`, `source`)
        """,
    },
}


def build_schema_plan(
    existing_tables: Set[str],
    existing_columns: Dict[str, Set[str]],
    existing_indexes: Dict[str, Set[str]] | None = None,
) -> List[str]:
    plan: List[str] = []
    normalized_indexes = existing_indexes or {}
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

    for table_name, index_statements in REQUIRED_INDEX_MIGRATIONS.items():
        if table_name not in existing_tables:
            continue
        present_indexes = normalized_indexes.get(table_name, set())
        for index_name, statement in index_statements.items():
            if index_name not in present_indexes:
                plan.append(statement.strip())

    return plan
