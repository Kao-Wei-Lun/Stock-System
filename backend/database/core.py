import asyncio
import os
from typing import Any, Dict, List, Optional, Set

import aiomysql
from dotenv import load_dotenv
from pymysql.err import OperationalError

from .helpers import _build_mysql_error_message, _build_mysql_connection_error_message, _escape_identifier
from models.schema import build_schema_plan

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
        if hasattr(self, "ensure_default_owner"):
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
