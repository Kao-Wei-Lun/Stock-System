"""Verify that the bounded OHLCV read uses an indexed access path.

The output intentionally contains only optimizer metadata. It never prints
credentials, SQL text, parameter values, market rows, or account data.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import warnings
from pathlib import Path

import aiomysql


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database.core import (  # noqa: E402
    MYSQL_CHARSET,
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
)


QUERY = """
    SELECT `date`, `open`, `high`, `low`, `close`, `volume`
    FROM `ohlcv`
    WHERE `ticker`=%s AND `interval`=%s AND `date`>=%s
    ORDER BY `date` DESC
    LIMIT %s
"""


async def inspect_plan(ticker: str, interval: str, limit: int) -> dict:
    connection = await aiomysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DATABASE,
        charset=MYSQL_CHARSET,
        autocommit=True,
    )
    try:
        with warnings.catch_warnings():
            # Some MySQL versions emit the optimizer-rewritten query as a
            # warning. Suppress it so benchmark output never contains SQL
            # values or symbols.
            warnings.simplefilter("ignore")
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    f"EXPLAIN {QUERY}",
                    (ticker, interval, "1970-01-01", limit),
                )
                rows = list(await cursor.fetchall())
                await cursor.execute(
                    """
                    SELECT `INDEX_NAME` AS `index_name`,
                           `SEQ_IN_INDEX` AS `sequence`,
                           `COLUMN_NAME` AS `column_name`
                    FROM `INFORMATION_SCHEMA`.`STATISTICS`
                    WHERE `TABLE_SCHEMA`=%s AND `TABLE_NAME`='ohlcv'
                    ORDER BY `INDEX_NAME`, `SEQ_IN_INDEX`
                    """,
                    (MYSQL_DATABASE,),
                )
                index_rows = list(await cursor.fetchall())
    finally:
        connection.close()

    sanitized = []
    for row in rows:
        sanitized.append(
            {
                "select_type": row.get("select_type"),
                "table": row.get("table"),
                "access_type": row.get("type"),
                "possible_keys": row.get("possible_keys"),
                "selected_key": row.get("key"),
                "estimated_rows": row.get("rows"),
                "extra": row.get("Extra"),
            }
        )
    index_columns: dict[str, list[str]] = {}
    for row in index_rows:
        index_columns.setdefault(str(row["index_name"]), []).append(str(row["column_name"]))
    compatible_indexes = sorted(
        name
        for name, columns in index_columns.items()
        if columns[:3] == ["ticker", "interval", "date"]
    )
    allowed_access = {"const", "eq_ref", "ref", "range", "index"}
    indexed_access = bool(sanitized) and all(
        item["selected_key"]
        and str(item["access_type"] or "").lower() in allowed_access
        for item in sanitized
    )
    optimizer_selected_compatible = bool(sanitized) and all(
        item["selected_key"] in compatible_indexes for item in sanitized
    )
    passed = indexed_access and bool(compatible_indexes)
    return {
        "schema_version": 1,
        "check": "bounded_ohlcv_index_access",
        "passed": passed,
        "compatible_indexes": compatible_indexes,
        "optimizer_selected_compatible": optimizer_selected_compatible,
        "plan": sanitized,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="*TMFF")
    parser.add_argument("--interval", default="1m")
    parser.add_argument("--limit", type=int, default=400)
    args = parser.parse_args()
    result = asyncio.run(
        inspect_plan(
            ticker=str(args.ticker).strip() or "*TMFF",
            interval=str(args.interval).strip() or "1m",
            limit=max(1, min(args.limit, 5000)),
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
