from typing import Any, Dict, List, Optional
from database.helpers import *
from database.core import DEFAULT_OWNER_ID
# Import common serialization helpers here if needed

class SyncMixin:
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

