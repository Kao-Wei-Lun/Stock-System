"""
Database layer backed by MySQL.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiomysql
from dotenv import load_dotenv
from pymysql.err import OperationalError

log = logging.getLogger(__name__)

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "quantvision")
MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4")


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
        try:
            async with server_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                        f"CHARACTER SET {MYSQL_CHARSET} COLLATE {MYSQL_CHARSET}_unicode_ci"
                    )
        finally:
            server_pool.close()
            await server_pool.wait_closed()

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

    async def close(self):
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()

    async def create_tables(self):
        statements = [
            """
            CREATE TABLE IF NOT EXISTS `ohlcv` (
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
                `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_ohlcv_ticker_date_interval` (`ticker`, `date`, `interval`),
                KEY `idx_ohlcv_ticker_date` (`ticker`, `interval`, `date`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS `stock_info` (
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
            """
            CREATE TABLE IF NOT EXISTS `sync_log` (
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
            """
            CREATE TABLE IF NOT EXISTS `alerts` (
                `id` BIGINT NOT NULL AUTO_INCREMENT,
                `ticker` VARCHAR(32) NOT NULL,
                `type` VARCHAR(32) NOT NULL,
                `condition` VARCHAR(32) NOT NULL,
                `value` DOUBLE NULL,
                `value2` DOUBLE NULL,
                `active` TINYINT(1) NOT NULL DEFAULT 1,
                `triggered` TINYINT(1) NOT NULL DEFAULT 0,
                `triggered_at` DATETIME NULL,
                `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]

        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                for statement in statements:
                    await cur.execute(statement)

    async def upsert_ohlcv_batch(self, ticker: str, rows: List[Dict], interval: str = "1d") -> int:
        if not rows:
            return 0

        sql = """
            INSERT INTO `ohlcv`
                (`ticker`, `date`, `interval`, `open`, `high`, `low`, `close`, `volume`, `adj_close`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                `open` = VALUES(`open`),
                `high` = VALUES(`high`),
                `low` = VALUES(`low`),
                `close` = VALUES(`close`),
                `volume` = VALUES(`volume`),
                `adj_close` = VALUES(`adj_close`)
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
            )
            for row in rows
        ]

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(sql, params)
        return len(rows)

    async def get_ohlcv(self, ticker: str, period: str = "1y", interval: str = "1d") -> List[Dict]:
        since = _period_to_date(period)
        sql = """
            SELECT `date`, `open`, `high`, `low`, `close`, `volume`, `adj_close`
            FROM `ohlcv`
            WHERE `ticker`=%s AND `interval`=%s AND `date`>=%s
            ORDER BY `date` ASC
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (ticker, interval, since))
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
            ON DUPLICATE KEY UPDATE
                `name` = VALUES(`name`),
                `sector` = VALUES(`sector`),
                `industry` = VALUES(`industry`),
                `market_cap` = VALUES(`market_cap`),
                `pe_ratio` = VALUES(`pe_ratio`),
                `dividend_yield` = VALUES(`dividend_yield`),
                `week_52_high` = VALUES(`week_52_high`),
                `week_52_low` = VALUES(`week_52_low`),
                `avg_volume` = VALUES(`avg_volume`),
                `description` = VALUES(`description`),
                `currency` = VALUES(`currency`),
                `exchange` = VALUES(`exchange`),
                `country` = VALUES(`country`)
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

    async def get_stats(self) -> Dict:
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT COUNT(*) AS `c` FROM `ohlcv`")
                total_rows = (await cur.fetchone())["c"]

                await cur.execute("SELECT COUNT(DISTINCT `ticker`) AS `c` FROM `ohlcv`")
                total_tickers = (await cur.fetchone())["c"]

                await cur.execute(
                    """
                    SELECT `ticker`, COUNT(*) AS `rows`
                    FROM `ohlcv`
                    GROUP BY `ticker`
                    ORDER BY `rows` DESC
                    LIMIT 10
                    """
                )
                top = list(await cur.fetchall())

        return {
            "total_rows": total_rows,
            "total_tickers": total_tickers,
            "top_tickers": top,
        }

    async def log_sync(self, ticker: str, status: str, rows: int = 0, msg: str = ""):
        sql = """
            INSERT INTO `sync_log` (`ticker`, `status`, `rows_added`, `message`)
            VALUES (%s, %s, %s, %s)
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (ticker, status, rows, msg))


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
    n, unit = int(period[:-2]) if period[:-2].isdigit() else int(period[:-1]), period[-1]
    if period[:-2].isdigit():
        n, unit = int(period[:-2]), period[-2:]
        if unit == "mo":
            d = datetime.utcnow() - timedelta(days=n * 30)
        elif unit == "yr" or unit == "y":
            d = datetime.utcnow() - timedelta(days=n * 365)
        else:
            d = datetime.utcnow() - timedelta(days=30)
    else:
        n = int(period[:-1])
        unit = period[-1]
        if unit == "y":
            d = datetime.utcnow() - timedelta(days=n * 365)
        elif unit == "m":
            d = datetime.utcnow() - timedelta(days=n * 30)
        elif unit == "d":
            d = datetime.utcnow() - timedelta(days=n)
        else:
            d = datetime.utcnow() - timedelta(days=365)
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
