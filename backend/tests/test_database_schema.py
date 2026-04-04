from database import (
    CREATE_TABLE_STATEMENTS,
    REQUIRED_COLUMN_MIGRATIONS,
    REQUIRED_INDEX_MIGRATIONS,
    build_schema_plan,
)


def test_build_schema_plan_adds_missing_tables_and_columns():
    existing_tables = {"ohlcv", "watchlist_groups", "watchlist_items", "alerts"}
    existing_columns = {
        "ohlcv": {
            "id",
            "ticker",
            "date",
            "interval",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "adj_close",
            "created_at",
        },
        "watchlist_groups": {"id", "name", "sort_order", "created_at"},
        "watchlist_items": {"id", "group_id", "ticker", "sort_order", "created_at"},
        "alerts": {
            "id",
            "ticker",
            "type",
            "condition",
            "value",
            "value2",
            "active",
            "triggered",
            "triggered_at",
            "created_at",
        },
    }

    plan = build_schema_plan(existing_tables, existing_columns, {})

    assert any("CREATE TABLE `workspace_presets`" in statement for statement in plan)
    assert any("CREATE TABLE `market_quotes_latest`" in statement for statement in plan)
    assert any("CREATE TABLE `notifications`" in statement for statement in plan)
    assert any("CREATE TABLE `backtest_runs`" in statement for statement in plan)
    assert any("CREATE TABLE `backtest_trades`" in statement for statement in plan)
    assert any("CREATE TABLE `backtest_equity_points`" in statement for statement in plan)
    assert any("CREATE TABLE `trade_journal_entries`" in statement for statement in plan)
    assert any("CREATE TABLE `trade_journal_tags`" in statement for statement in plan)
    assert any("CREATE TABLE `trade_journal_attachments`" in statement for statement in plan)
    assert any("CREATE TABLE `market_events`" in statement for statement in plan)
    assert any("CREATE TABLE `news_articles`" in statement for statement in plan)
    assert any("CREATE TABLE `macro_snapshots`" in statement for statement in plan)
    assert any("CREATE TABLE `taiwan_chip_snapshots`" in statement for statement in plan)
    assert any("CREATE TABLE `screener_presets`" in statement for statement in plan)
    assert any("ALTER TABLE `ohlcv`" in statement and "`source`" in statement for statement in plan)
    assert any("ALTER TABLE `ohlcv`" in statement and "idx_ohlcv_ticker_date_lookup" in statement for statement in plan)
    assert any("ALTER TABLE `watchlist_groups`" in statement and "`owner_id`" in statement for statement in plan)
    assert any("ALTER TABLE `watchlist_items`" in statement and "`tags_json`" in statement for statement in plan)
    assert any("ALTER TABLE `alerts`" in statement and "`condition_json`" in statement for statement in plan)
    assert any(
        "CREATE TABLE `market_quotes_latest`" in statement and "idx_market_quotes_latest_quote_recency" in statement
        for statement in plan
    )


def test_build_schema_plan_noops_when_schema_is_complete():
    existing_tables = set(CREATE_TABLE_STATEMENTS)
    existing_columns = {
        table_name: set(column_map.keys())
        for table_name, column_map in REQUIRED_COLUMN_MIGRATIONS.items()
    }
    existing_indexes = {
        table_name: set(index_map.keys())
        for table_name, index_map in REQUIRED_INDEX_MIGRATIONS.items()
    }

    plan = build_schema_plan(existing_tables, existing_columns, existing_indexes)

    assert plan == []
