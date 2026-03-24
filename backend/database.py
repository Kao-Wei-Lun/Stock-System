"""
資料庫層 — SQLite + aiosqlite
存放 OHLCV K 線、股票基本資訊、自選股清單
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiosqlite

log = logging.getLogger(__name__)

DB_PATH = "./quantvision.db"


class Database:
    def __init__(self):
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self):
        self._db = await aiosqlite.connect(DB_PATH)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.execute("PRAGMA cache_size=10000")

    async def close(self):
        if self._db:
            await self._db.close()

    # ── Schema ──────────────────────────────────────────────────────────────

    async def create_tables(self):
        await self._db.executescript("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            interval    TEXT    NOT NULL DEFAULT '1d',
            open        REAL    NOT NULL,
            high        REAL    NOT NULL,
            low         REAL    NOT NULL,
            close       REAL    NOT NULL,
            volume      INTEGER NOT NULL,
            adj_close   REAL,
            created_at  TEXT    DEFAULT (datetime('now')),
            UNIQUE(ticker, date, interval)
        );

        CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_date ON ohlcv(ticker, date, interval);

        CREATE TABLE IF NOT EXISTS stock_info (
            ticker          TEXT PRIMARY KEY,
            name            TEXT,
            sector          TEXT,
            industry        TEXT,
            market_cap      INTEGER,
            pe_ratio        REAL,
            dividend_yield  REAL,
            week_52_high    REAL,
            week_52_low     REAL,
            avg_volume      INTEGER,
            description     TEXT,
            currency        TEXT,
            exchange        TEXT,
            country         TEXT,
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sync_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT    NOT NULL,
            status      TEXT    NOT NULL,
            rows_added  INTEGER DEFAULT 0,
            message     TEXT,
            synced_at   TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT    NOT NULL,
            type        TEXT    NOT NULL,
            condition   TEXT    NOT NULL,
            value       REAL,
            value2      REAL,
            active      INTEGER DEFAULT 1,
            triggered   INTEGER DEFAULT 0,
            triggered_at TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );
        """)
        await self._db.commit()

    # ── OHLCV ───────────────────────────────────────────────────────────────

    async def upsert_ohlcv_batch(self, ticker: str, rows: List[Dict], interval: str = "1d") -> int:
        """批次 upsert K 線資料，回傳實際新增筆數"""
        if not rows:
            return 0
        async with self._lock:
            await self._db.executemany(
                """INSERT OR REPLACE INTO ohlcv
                   (ticker, date, interval, open, high, low, close, volume, adj_close)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        ticker,
                        r["date"],
                        interval,
                        r["open"],
                        r["high"],
                        r["low"],
                        r["close"],
                        r.get("volume", 0),
                        r.get("adj_close"),
                    )
                    for r in rows
                ],
            )
            await self._db.commit()
        return len(rows)

    async def get_ohlcv(self, ticker: str, period: str = "1y", interval: str = "1d") -> List[Dict]:
        """從 DB 取得 K 線資料"""
        since = _period_to_date(period)
        async with self._db.execute(
            """SELECT date, open, high, low, close, volume, adj_close
               FROM ohlcv
               WHERE ticker=? AND interval=? AND date>=?
               ORDER BY date ASC""",
            (ticker, interval, since),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_latest_ohlcv(self, ticker: str) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM ohlcv WHERE ticker=? AND interval='1d' ORDER BY date DESC LIMIT 1",
            (ticker,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def get_prev_close(self, ticker: str) -> Optional[float]:
        async with self._db.execute(
            "SELECT close FROM ohlcv WHERE ticker=? AND interval='1d' ORDER BY date DESC LIMIT 1 OFFSET 1",
            (ticker,),
        ) as cur:
            row = await cur.fetchone()
        return row["close"] if row else None

    # ── Stock Info ──────────────────────────────────────────────────────────

    async def upsert_stock_info(self, ticker: str, info: Dict):
        async with self._lock:
            await self._db.execute(
                """INSERT OR REPLACE INTO stock_info
                   (ticker, name, sector, industry, market_cap, pe_ratio,
                    dividend_yield, week_52_high, week_52_low, avg_volume,
                    description, currency, exchange, country, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
                (
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
                ),
            )
            await self._db.commit()

    async def get_stock_info(self, ticker: str) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM stock_info WHERE ticker=?", (ticker,)
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    # ── Search ──────────────────────────────────────────────────────────────

    async def search_tickers(self, q: str) -> List[Dict]:
        pattern = f"%{q}%"
        async with self._db.execute(
            """SELECT ticker, name FROM stock_info
               WHERE ticker LIKE ? OR name LIKE ?
               LIMIT 20""",
            (pattern, pattern),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # ── Stats ───────────────────────────────────────────────────────────────

    async def get_stats(self) -> Dict:
        async with self._db.execute("SELECT COUNT(*) as c FROM ohlcv") as cur:
            total_rows = (await cur.fetchone())["c"]
        async with self._db.execute(
            "SELECT COUNT(DISTINCT ticker) as c FROM ohlcv"
        ) as cur:
            total_tickers = (await cur.fetchone())["c"]
        async with self._db.execute(
            "SELECT ticker, COUNT(*) as rows FROM ohlcv GROUP BY ticker ORDER BY rows DESC LIMIT 10"
        ) as cur:
            top = [dict(r) for r in await cur.fetchall()]
        return {
            "total_rows": total_rows,
            "total_tickers": total_tickers,
            "top_tickers": top,
        }

    # ── Sync Log ─────────────────────────────────────────────────────────────

    async def log_sync(self, ticker: str, status: str, rows: int = 0, msg: str = ""):
        await self._db.execute(
            "INSERT INTO sync_log (ticker, status, rows_added, message) VALUES (?,?,?,?)",
            (ticker, status, rows, msg),
        )
        await self._db.commit()


# ── Singleton ─────────────────────────────────────────────────────────────────
db = Database()


async def init_db():
    await db.connect()
    await db.create_tables()
    log.info(f"✅ SQLite DB 初始化完成: {DB_PATH}")


# ── Helpers ──────────────────────────────────────────────────────────────────
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
