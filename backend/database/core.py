import asyncio
import time
from collections import deque
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Set

import aiomysql
from dotenv import load_dotenv
from pymysql.err import OperationalError

from env_validation import read_int_env, read_text_env, read_timezone_env
from performance_timing import record_server_timing
from .helpers import _build_mysql_error_message, _build_mysql_connection_error_message, _escape_identifier
from .migrations import (
    CREATE_MIGRATION_TABLE_SQL,
    MIGRATION_TABLE,
    MigrationError,
    SchemaState,
    build_versioned_migration_plan,
)

load_dotenv()

MYSQL_HOST = read_text_env("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = read_int_env("MYSQL_PORT", "3306", minimum=1, maximum=65535)
MYSQL_USER = read_text_env("MYSQL_USER", "root")
MYSQL_PASSWORD = read_text_env("MYSQL_PASSWORD", "")
MYSQL_DATABASE = read_text_env("MYSQL_DATABASE", "quantvision")
MYSQL_CHARSET = read_text_env("MYSQL_CHARSET", "utf8mb4")

DEFAULT_OWNER_ID = 1
DEFAULT_OWNER_USERNAME = "local-owner"
DEFAULT_OWNER_DISPLAY_NAME = "Local Owner"
DEFAULT_OWNER_TIMEZONE = read_timezone_env("APP_TIMEZONE", "Asia/Taipei")

class DatabaseCore:
    def __init__(self):
        self._pool: Optional[aiomysql.Pool] = None
        self._lock = asyncio.Lock()
        self._transaction_connection: ContextVar[Any | None] = ContextVar(
            f"quantvision_db_transaction_{id(self)}",
            default=None,
        )
        self._db_wait_samples: deque[float] = deque(maxlen=512)
        self._db_query_samples: deque[float] = deque(maxlen=512)

    @staticmethod
    def _timing_summary(samples: deque[float]) -> Dict[str, Any]:
        values = sorted(samples)
        if not values:
            return {"count": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}

        def percentile(ratio: float) -> float:
            index = max(0, min(len(values) - 1, int((len(values) - 1) * ratio + 0.999999)))
            return round(values[index], 3)

        return {
            "count": len(values),
            "p50_ms": percentile(0.50),
            "p95_ms": percentile(0.95),
            "max_ms": round(values[-1], 3),
        }

    def _record_db_timing(self, metric: str, duration_ms: float) -> None:
        duration = max(0.0, float(duration_ms))
        if metric == "db_wait":
            self._db_wait_samples.append(duration)
        elif metric == "db_query":
            self._db_query_samples.append(duration)
        record_server_timing(metric, duration)

    def get_performance_status(self) -> Dict[str, Any]:
        pool = self._pool
        return {
            "configured": pool is not None,
            "pool": {
                "size": int(getattr(pool, "size", 0) or 0) if pool is not None else 0,
                "free": int(getattr(pool, "freesize", 0) or 0) if pool is not None else 0,
                "maxsize": int(getattr(pool, "maxsize", 0) or 0) if pool is not None else 0,
            },
            "wait": self._timing_summary(self._db_wait_samples),
            "query": self._timing_summary(self._db_query_samples),
        }

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

    async def health_check(self) -> Dict[str, Any]:
        """Return a non-throwing database readiness snapshot."""
        started = time.perf_counter()
        if self._pool is None:
            return {"connected": False, "latency_ms": None, "error": "pool_not_initialized"}
        try:
            row = await self._fetchone("SELECT 1 AS `ok`")
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            return {
                "connected": bool(row and row.get("ok") == 1),
                "latency_ms": latency_ms,
                "error": None,
            }
        except Exception as exc:
            return {
                "connected": False,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": str(exc)[:300],
            }

    @property
    def in_transaction(self) -> bool:
        return self._transaction_connection.get() is not None

    @asynccontextmanager
    async def transaction(self):
        """Run repository calls atomically on one connection.

        Repository helpers automatically reuse this connection through the
        task-local context, so existing methods remain backward compatible.
        """
        if self._pool is None:
            raise RuntimeError("Database pool is not initialized")
        if self.in_transaction:
            raise RuntimeError("Nested database transactions are not supported")
        async with self._lock:
            wait_started = time.perf_counter()
            async with self._pool.acquire() as conn:
                self._record_db_timing("db_wait", (time.perf_counter() - wait_started) * 1000)
                await conn.begin()
                token = self._transaction_connection.set(conn)
                try:
                    yield conn
                    await conn.commit()
                except BaseException:
                    await conn.rollback()
                    raise
                finally:
                    self._transaction_connection.reset(token)

    async def _inspect_schema(self, cur) -> SchemaState:
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
        await cur.execute(
            """
            SELECT `TABLE_NAME` AS `table_name`, `INDEX_NAME` AS `index_name`
            FROM `INFORMATION_SCHEMA`.`STATISTICS`
            WHERE `TABLE_SCHEMA`=%s
              AND `INDEX_NAME`<>'PRIMARY'
            """,
            (MYSQL_DATABASE,),
        )
        existing_indexes: Dict[str, Set[str]] = {}
        for row in await cur.fetchall():
            existing_indexes.setdefault(row["table_name"], set()).add(row["index_name"])
        return SchemaState(existing_tables, existing_columns, existing_indexes)

    async def _get_applied_migrations(self, cur, state: SchemaState) -> List[Dict[str, Any]]:
        if MIGRATION_TABLE not in state.tables:
            return []
        await cur.execute(
            """
            SELECT `version`, `description`, `checksum`, `statement_count`, `applied_at`
            FROM `schema_migrations`
            ORDER BY `version`
            """
        )
        return list(await cur.fetchall())

    async def get_migration_status(self) -> Dict[str, Any]:
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                state = await self._inspect_schema(cur)
                applied = await self._get_applied_migrations(cur, state)
        return build_versioned_migration_plan(state, applied)

    async def create_tables(self, *, auto_apply: bool = True):
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                state = await self._inspect_schema(cur)
                applied = await self._get_applied_migrations(cur, state)
            plan = build_versioned_migration_plan(state, applied)
            if plan["unknown_applied_versions"]:
                versions = ", ".join(plan["unknown_applied_versions"])
                raise MigrationError(
                    f"Database contains migrations unknown to this application version: {versions}"
                )
            if plan["pending_count"] and not auto_apply:
                versions = ", ".join(item["version"] for item in plan["pending"])
                raise MigrationError(
                    f"Pending database migrations: {versions}. Run database_migrate.py apply or enable DB_AUTO_MIGRATE."
                )
            async with conn.cursor() as cur:
                if plan["pending_count"]:
                    await cur.execute(CREATE_MIGRATION_TABLE_SQL)
                for migration in plan["pending"]:
                    for statement in migration["statements"]:
                        await cur.execute(statement)
                    await cur.execute(
                        """
                        INSERT INTO `schema_migrations`
                            (`version`, `description`, `checksum`, `statement_count`)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            migration["version"],
                            migration["description"],
                            migration["checksum"],
                            migration["statement_count"],
                        ),
                    )
        if hasattr(self, "ensure_default_owner"):
            await self.ensure_default_owner()
        return plan

    async def _fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        transaction_conn = self._transaction_connection.get()
        if transaction_conn is not None:
            async with transaction_conn.cursor(aiomysql.DictCursor) as cur:
                query_started = time.perf_counter()
                try:
                    await cur.execute(sql, params)
                    return await cur.fetchone()
                finally:
                    self._record_db_timing("db_query", (time.perf_counter() - query_started) * 1000)
        wait_started = time.perf_counter()
        async with self._pool.acquire() as conn:
            self._record_db_timing("db_wait", (time.perf_counter() - wait_started) * 1000)
            async with conn.cursor(aiomysql.DictCursor) as cur:
                query_started = time.perf_counter()
                try:
                    await cur.execute(sql, params)
                    return await cur.fetchone()
                finally:
                    self._record_db_timing("db_query", (time.perf_counter() - query_started) * 1000)

    async def _fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        transaction_conn = self._transaction_connection.get()
        if transaction_conn is not None:
            async with transaction_conn.cursor(aiomysql.DictCursor) as cur:
                query_started = time.perf_counter()
                try:
                    await cur.execute(sql, params)
                    return list(await cur.fetchall())
                finally:
                    self._record_db_timing("db_query", (time.perf_counter() - query_started) * 1000)
        wait_started = time.perf_counter()
        async with self._pool.acquire() as conn:
            self._record_db_timing("db_wait", (time.perf_counter() - wait_started) * 1000)
            async with conn.cursor(aiomysql.DictCursor) as cur:
                query_started = time.perf_counter()
                try:
                    await cur.execute(sql, params)
                    rows = await cur.fetchall()
                finally:
                    self._record_db_timing("db_query", (time.perf_counter() - query_started) * 1000)
        return list(rows)

    async def _execute(self, sql: str, params: tuple = ()) -> int:
        transaction_conn = self._transaction_connection.get()
        if transaction_conn is not None:
            async with transaction_conn.cursor() as cur:
                query_started = time.perf_counter()
                try:
                    await cur.execute(sql, params)
                    return cur.rowcount
                finally:
                    self._record_db_timing("db_query", (time.perf_counter() - query_started) * 1000)
        wait_started = time.perf_counter()
        async with self._lock:
            async with self._pool.acquire() as conn:
                self._record_db_timing("db_wait", (time.perf_counter() - wait_started) * 1000)
                async with conn.cursor() as cur:
                    query_started = time.perf_counter()
                    try:
                        await cur.execute(sql, params)
                        return cur.rowcount
                    finally:
                        self._record_db_timing("db_query", (time.perf_counter() - query_started) * 1000)

    async def _execute_insert(self, sql: str, params: tuple = ()) -> int:
        transaction_conn = self._transaction_connection.get()
        if transaction_conn is not None:
            async with transaction_conn.cursor() as cur:
                query_started = time.perf_counter()
                try:
                    await cur.execute(sql, params)
                    return cur.lastrowid
                finally:
                    self._record_db_timing("db_query", (time.perf_counter() - query_started) * 1000)
        wait_started = time.perf_counter()
        async with self._lock:
            async with self._pool.acquire() as conn:
                self._record_db_timing("db_wait", (time.perf_counter() - wait_started) * 1000)
                async with conn.cursor() as cur:
                    query_started = time.perf_counter()
                    try:
                        await cur.execute(sql, params)
                        return cur.lastrowid
                    finally:
                        self._record_db_timing("db_query", (time.perf_counter() - query_started) * 1000)
