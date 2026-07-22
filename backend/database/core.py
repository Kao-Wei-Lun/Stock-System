import asyncio
import time
from typing import Any, Dict, List, Optional, Set

import aiomysql
from dotenv import load_dotenv
from pymysql.err import OperationalError

from env_validation import read_int_env, read_text_env, read_timezone_env
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
