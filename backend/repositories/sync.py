from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from database.helpers import *
from database.core import DEFAULT_OWNER_ID
# Import common serialization helpers here if needed

class SyncMixin:
    async def get_stats(self) -> Dict:
        """Return a fast, non-authoritative database size projection.

        Exact COUNT/GROUP BY queries on OHLCV and chip history can scan tens of
        millions of rows and must never run in an interactive request. MySQL's
        INFORMATION_SCHEMA estimates are sufficient for the legacy-compatible
        system summary; offline maintenance tooling can calculate exact counts
        when needed.
        """
        table_names = (
            "ohlcv",
            "institutional_snapshots",
            "workspace_presets",
            "alerts",
            "notifications",
            "backtest_runs",
            "backtest_trades",
            "trade_journal_entries",
            "market_events",
            "news_articles",
            "macro_snapshots",
            "taiwan_chip_snapshots",
            "screener_presets",
            "journal_filter_presets",
        )
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT
                        `TABLE_NAME` AS `table_name`,
                        COALESCE(`TABLE_ROWS`, 0) AS `estimated_rows`
                    FROM `INFORMATION_SCHEMA`.`TABLES`
                    WHERE `TABLE_SCHEMA` = DATABASE()
                      AND `TABLE_NAME` IN (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                      )
                    """,
                    table_names,
                )
                estimated_rows = {
                    str(row.get("table_name") or ""): max(0, int(row.get("estimated_rows") or 0))
                    for row in await cur.fetchall()
                }
                await cur.execute(
                    """
                    SELECT COALESCE(MAX(`CARDINALITY`), 0) AS `estimated_tickers`
                    FROM `INFORMATION_SCHEMA`.`STATISTICS`
                    WHERE `TABLE_SCHEMA` = DATABASE()
                      AND `TABLE_NAME` = 'ohlcv'
                      AND `COLUMN_NAME` = 'ticker'
                      AND `SEQ_IN_INDEX` = 1
                    """
                )
                ticker_row = await cur.fetchone() or {}
                total_tickers = max(0, int(ticker_row.get("estimated_tickers") or 0))

        return {
            "total_rows": estimated_rows.get("ohlcv", 0),
            "total_tickers": total_tickers,
            # Keep the legacy field while avoiding an unbounded GROUP BY.
            "top_tickers": [],
            "institutional_snapshots": estimated_rows.get("institutional_snapshots", 0),
            "workspace_presets": estimated_rows.get("workspace_presets", 0),
            "alerts": estimated_rows.get("alerts", 0),
            "notifications": estimated_rows.get("notifications", 0),
            "backtest_runs": estimated_rows.get("backtest_runs", 0),
            "backtest_trades": estimated_rows.get("backtest_trades", 0),
            "trade_journal_entries": estimated_rows.get("trade_journal_entries", 0),
            "market_events": estimated_rows.get("market_events", 0),
            "news_articles": estimated_rows.get("news_articles", 0),
            "macro_snapshots": estimated_rows.get("macro_snapshots", 0),
            "taiwan_chip_snapshots": estimated_rows.get("taiwan_chip_snapshots", 0),
            "screener_presets": estimated_rows.get("screener_presets", 0),
            "journal_filter_presets": estimated_rows.get("journal_filter_presets", 0),
            "estimated": True,
            "source": "information_schema",
            "as_of": datetime.now(timezone.utc).isoformat(),
            "top_tickers_available": False,
        }

    async def log_sync(self, ticker: str, status: str, rows: int = 0, msg: str = ""):
        sql = """
            INSERT INTO `sync_log` (`ticker`, `status`, `rows_added`, `message`)
            VALUES (%s, %s, %s, %s)
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (ticker, status, rows, msg))

