from typing import Any, Dict, List, Optional
from database.helpers import *
from database.core import DEFAULT_OWNER_ID
# Import common serialization helpers here if needed

OFFICIAL_TAIWAN_CHIP_SOURCES = ("twse_t86", "tpex_3itrade_hedge")
OFFICIAL_TAIWAN_CHIP_SOURCE_PLACEHOLDERS = ", ".join(["%s"] * len(OFFICIAL_TAIWAN_CHIP_SOURCES))
TAIFEX_OVERVIEW_FIELDS = (
    "trade_long_futures_volume",
    "trade_long_options_volume",
    "trade_long_futures_amount",
    "trade_long_options_amount",
    "trade_short_futures_volume",
    "trade_short_options_volume",
    "trade_short_futures_amount",
    "trade_short_options_amount",
    "trade_net_futures_volume",
    "trade_net_options_volume",
    "trade_net_futures_amount",
    "trade_net_options_amount",
    "trade_net_futures_volume_change",
    "trade_net_options_volume_change",
    "trade_net_futures_amount_change",
    "trade_net_options_amount_change",
)
TAIFEX_CONTRACT_FIELDS = (
    "rank",
    "trade_long_volume",
    "trade_long_amount",
    "trade_short_volume",
    "trade_short_amount",
    "trade_net_volume",
    "trade_net_amount",
    "oi_long_volume",
    "oi_long_amount",
    "oi_short_volume",
    "oi_short_amount",
    "oi_net_volume",
    "oi_net_amount",
    "trade_net_volume_change",
    "trade_net_amount_change",
    "oi_net_volume_change",
    "oi_net_amount_change",
)
TAIFEX_CALL_PUT_FIELDS = (
    "rank",
    "trade_buy_volume",
    "trade_buy_amount",
    "trade_sell_volume",
    "trade_sell_amount",
    "trade_net_volume",
    "trade_net_amount",
    "oi_buy_volume",
    "oi_buy_amount",
    "oi_sell_volume",
    "oi_sell_amount",
    "oi_net_volume",
    "oi_net_amount",
    "trade_net_volume_change",
    "trade_net_amount_change",
    "oi_net_volume_change",
    "oi_net_amount_change",
)
TAIFEX_CASH_SUMMARY_FIELDS = (
    "buy_amount",
    "sell_amount",
    "net_amount",
    "net_amount_change",
)
TAIFEX_STRUCTURED_ROW_TABLES = (
    "taifex_overview_daily",
    "taifex_futures_daily",
    "taifex_options_daily",
    "taifex_call_put_daily",
    "taifex_cash_summary_daily",
)


def _normalize_taifex_date(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip() or None


def _normalize_taifex_text(value: Any, max_length: int) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:max_length]


def _normalize_taifex_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0


def _normalize_taifex_meta_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    resolved_date = _normalize_taifex_date(payload.get("resolved_date"))
    query_date = _normalize_taifex_date(payload.get("query_date") or resolved_date)
    if not resolved_date or not query_date:
        raise ValueError("Institutional snapshot requires query_date and resolved_date")
    return {
        "resolved_date": resolved_date,
        "query_date": query_date,
        "previous_date": _normalize_taifex_date(payload.get("previous_date")),
        "default_futures_commodity": _normalize_taifex_text(payload.get("default_futures_commodity"), 64),
        "default_options_commodity": _normalize_taifex_text(payload.get("default_options_commodity"), 64),
        "cash_summary_source": _normalize_taifex_text(payload.get("cash_summary_source"), 64),
        "cash_summary_warning": _normalize_taifex_text(payload.get("cash_summary_warning"), 65535),
    }


def _normalize_taifex_overview_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    resolved_date = _normalize_taifex_date(payload.get("resolved_date"))
    rows: List[Dict[str, Any]] = []
    for item in payload.get("overview") or []:
        if not isinstance(item, dict):
            continue
        institution = _normalize_taifex_text(item.get("institution"), 32)
        if not institution:
            continue
        normalized = {"resolved_date": resolved_date, "institution": institution}
        normalized.update({field: _normalize_taifex_int(item.get(field)) for field in TAIFEX_OVERVIEW_FIELDS})
        rows.append(normalized)
    return rows


def _normalize_taifex_contract_rows(
    payload: Dict[str, Any],
    key: str,
) -> List[Dict[str, Any]]:
    resolved_date = _normalize_taifex_date(payload.get("resolved_date"))
    rows: List[Dict[str, Any]] = []
    for item in payload.get(key) or []:
        if not isinstance(item, dict):
            continue
        commodity = _normalize_taifex_text(item.get("commodity"), 64)
        institution = _normalize_taifex_text(item.get("institution"), 32)
        if not commodity or not institution:
            continue
        normalized = {
            "resolved_date": resolved_date,
            "commodity": commodity,
            "institution": institution,
        }
        normalized.update({field: _normalize_taifex_int(item.get(field)) for field in TAIFEX_CONTRACT_FIELDS})
        rows.append(normalized)
    return rows


def _normalize_taifex_call_put_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    resolved_date = _normalize_taifex_date(payload.get("resolved_date"))
    rows: List[Dict[str, Any]] = []
    for item in payload.get("call_puts") or []:
        if not isinstance(item, dict):
            continue
        commodity = _normalize_taifex_text(item.get("commodity"), 64)
        option_side = _normalize_taifex_text(item.get("option_side"), 16)
        institution = _normalize_taifex_text(item.get("institution"), 32)
        if not commodity or not option_side or not institution:
            continue
        normalized = {
            "resolved_date": resolved_date,
            "commodity": commodity,
            "option_side": option_side,
            "institution": institution,
        }
        normalized.update({field: _normalize_taifex_int(item.get(field)) for field in TAIFEX_CALL_PUT_FIELDS})
        rows.append(normalized)
    return rows


def _normalize_taifex_cash_summary_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    resolved_date = _normalize_taifex_date(payload.get("resolved_date"))
    rows: List[Dict[str, Any]] = []
    for item in payload.get("cash_summary") or []:
        if not isinstance(item, dict):
            continue
        institution = _normalize_taifex_text(item.get("institution"), 64)
        if not institution:
            continue
        normalized = {
            "resolved_date": resolved_date,
            "institution": institution,
        }
        normalized.update({field: _normalize_taifex_int(item.get(field)) for field in TAIFEX_CASH_SUMMARY_FIELDS})
        rows.append(normalized)
    return rows


def _build_taifex_structured_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "meta": _normalize_taifex_meta_payload(payload),
        "overview_rows": _normalize_taifex_overview_rows(payload),
        "futures_rows": _normalize_taifex_contract_rows(payload, "futures"),
        "options_rows": _normalize_taifex_contract_rows(payload, "options"),
        "call_put_rows": _normalize_taifex_call_put_rows(payload),
        "cash_summary_rows": _normalize_taifex_cash_summary_rows(payload),
    }


class TaiwanChipMixin:
    async def upsert_taiwan_chip_snapshots(self, snapshots: List[Dict[str, Any]]) -> int:
        if not snapshots:
            return 0
        normalized_snapshots = [_normalize_taiwan_chip_snapshot_payload(item) for item in snapshots]
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        """
                        INSERT INTO `taiwan_chip_snapshots`
                            (`ticker`, `market`, `snapshot_date`, `margin_balance`, `short_balance`,
                             `securities_lending_balance`, `foreign_net_buy_sell`,
                             `investment_trust_net_buy_sell`, `dealer_net_buy_sell`,
                             `institutional_net_buy_sell`, `source`, `branch_payload_json`, `summary_json`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        AS `incoming`
                        ON DUPLICATE KEY UPDATE
                            `market`=`incoming`.`market`,
                            `margin_balance`=`incoming`.`margin_balance`,
                            `short_balance`=`incoming`.`short_balance`,
                            `securities_lending_balance`=`incoming`.`securities_lending_balance`,
                            `foreign_net_buy_sell`=`incoming`.`foreign_net_buy_sell`,
                            `investment_trust_net_buy_sell`=`incoming`.`investment_trust_net_buy_sell`,
                            `dealer_net_buy_sell`=`incoming`.`dealer_net_buy_sell`,
                            `institutional_net_buy_sell`=`incoming`.`institutional_net_buy_sell`,
                            `source`=`incoming`.`source`,
                            `branch_payload_json`=`incoming`.`branch_payload_json`,
                            `summary_json`=`incoming`.`summary_json`
                        """,
                        [
                            (
                                item["ticker"],
                                item["market"],
                                item["snapshot_date"],
                                item["margin_balance"],
                                item["short_balance"],
                                item["securities_lending_balance"],
                                item["foreign_net_buy_sell"],
                                item["investment_trust_net_buy_sell"],
                                item["dealer_net_buy_sell"],
                                item["institutional_net_buy_sell"],
                                item["source"],
                                _json_dumps(item.get("branch_payload") or {}),
                                _json_dumps(item.get("summary") or {}),
                            )
                            for item in normalized_snapshots
                        ],
                    )
        return len(normalized_snapshots)

    async def get_taiwan_chip_snapshot(
        self,
        ticker: str,
        snapshot_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if snapshot_date:
            row = await self._fetchone(
                f"""
                SELECT *
                FROM `taiwan_chip_snapshots`
                WHERE `ticker`=%s AND `snapshot_date`=%s
                  AND `source` IN ({OFFICIAL_TAIWAN_CHIP_SOURCE_PLACEHOLDERS})
                LIMIT 1
                """,
                (ticker, snapshot_date, *OFFICIAL_TAIWAN_CHIP_SOURCES),
            )
        else:
            row = await self._fetchone(
                f"""
                SELECT *
                FROM `taiwan_chip_snapshots`
                WHERE `ticker`=%s
                  AND `source` IN ({OFFICIAL_TAIWAN_CHIP_SOURCE_PLACEHOLDERS})
                ORDER BY `snapshot_date` DESC, `id` DESC
                LIMIT 1
                """,
                (ticker, *OFFICIAL_TAIWAN_CHIP_SOURCES),
            )
        return _deserialize_taiwan_chip_snapshot(row)

    async def get_taiwan_chip_snapshot_count(self, snapshot_date: str) -> int:
        row = await self._fetchone(
            f"""
            SELECT COUNT(*) AS `row_count`
            FROM `taiwan_chip_snapshots`
            WHERE `snapshot_date`=%s
              AND `source` IN ({OFFICIAL_TAIWAN_CHIP_SOURCE_PLACEHOLDERS})
            """,
            (snapshot_date, *OFFICIAL_TAIWAN_CHIP_SOURCES),
        )
        return int((row or {}).get("row_count") or 0)

    async def get_taiwan_chip_snapshot_source_counts(self, snapshot_date: str) -> Dict[str, int]:
        rows = await self._fetchall(
            f"""
            SELECT `source`, COUNT(*) AS `row_count`
            FROM `taiwan_chip_snapshots`
            WHERE `snapshot_date`=%s
              AND `source` IN ({OFFICIAL_TAIWAN_CHIP_SOURCE_PLACEHOLDERS})
            GROUP BY `source`
            """,
            (snapshot_date, *OFFICIAL_TAIWAN_CHIP_SOURCES),
        )
        return {
            str(item.get("source") or ""): int(item.get("row_count") or 0)
            for item in rows
            if item.get("source")
        }

    async def get_latest_taiwan_chip_snapshot_date(
        self,
        on_or_before: Optional[str] = None,
    ) -> Optional[str]:
        if on_or_before:
            row = await self._fetchone(
                f"""
                SELECT `snapshot_date`
                FROM `taiwan_chip_snapshots`
                WHERE `snapshot_date`<=%s
                  AND `source` IN ({OFFICIAL_TAIWAN_CHIP_SOURCE_PLACEHOLDERS})
                ORDER BY `snapshot_date` DESC
                LIMIT 1
                """,
                (on_or_before, *OFFICIAL_TAIWAN_CHIP_SOURCES),
            )
        else:
            row = await self._fetchone(
                f"""
                SELECT `snapshot_date`
                FROM `taiwan_chip_snapshots`
                WHERE `source` IN ({OFFICIAL_TAIWAN_CHIP_SOURCE_PLACEHOLDERS})
                ORDER BY `snapshot_date` DESC
                LIMIT 1
                """,
                OFFICIAL_TAIWAN_CHIP_SOURCES,
            )
        if not row or not row.get("snapshot_date"):
            return None
        return _date_to_iso(row.get("snapshot_date"))

    async def list_taiwan_chip_snapshots(
        self,
        ticker: Optional[str] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 200))
        filters = ["1=1"]
        params: List[Any] = []
        if ticker:
            filters.append("`ticker`=%s")
            params.append(ticker)
        filters.append(f"`source` IN ({OFFICIAL_TAIWAN_CHIP_SOURCE_PLACEHOLDERS})")
        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `taiwan_chip_snapshots`
            WHERE {' AND '.join(filters)}
            ORDER BY `snapshot_date` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + list(OFFICIAL_TAIWAN_CHIP_SOURCES) + [clean_limit]),
        )
        return [_deserialize_taiwan_chip_snapshot(item) for item in rows]

    async def upsert_institutional_snapshot(self, payload: Dict[str, Any]) -> None:
        resolved_date = payload.get("resolved_date")
        query_date = payload.get("query_date") or resolved_date
        if not resolved_date or not query_date:
            raise ValueError("Institutional snapshot requires query_date and resolved_date")

        sql = """
            INSERT INTO `institutional_snapshots`
                (`resolved_date`, `query_date`, `payload_json`)
            VALUES (%s, %s, %s)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `query_date` = `incoming`.`query_date`,
                `payload_json` = `incoming`.`payload_json`
        """
        params = (
            resolved_date,
            query_date,
            json.dumps(payload, ensure_ascii=False),
        )

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)

    async def upsert_taifex_structured_snapshot(self, payload: Dict[str, Any]) -> Dict[str, int]:
        normalized = _build_taifex_structured_snapshot(payload)
        meta = normalized["meta"]
        resolved_date = meta["resolved_date"]

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO `taifex_institutional_meta`
                            (`resolved_date`, `query_date`, `previous_date`, `default_futures_commodity`,
                             `default_options_commodity`, `cash_summary_source`, `cash_summary_warning`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        AS `incoming`
                        ON DUPLICATE KEY UPDATE
                            `query_date`=`incoming`.`query_date`,
                            `previous_date`=`incoming`.`previous_date`,
                            `default_futures_commodity`=`incoming`.`default_futures_commodity`,
                            `default_options_commodity`=`incoming`.`default_options_commodity`,
                            `cash_summary_source`=`incoming`.`cash_summary_source`,
                            `cash_summary_warning`=`incoming`.`cash_summary_warning`
                        """,
                        (
                            meta["resolved_date"],
                            meta["query_date"],
                            meta["previous_date"],
                            meta["default_futures_commodity"],
                            meta["default_options_commodity"],
                            meta["cash_summary_source"],
                            meta["cash_summary_warning"],
                        ),
                    )
                    for table_name in TAIFEX_STRUCTURED_ROW_TABLES:
                        await cur.execute(
                            f"DELETE FROM `{table_name}` WHERE `resolved_date`=%s",
                            (resolved_date,),
                        )

                    if normalized["overview_rows"]:
                        await cur.executemany(
                            """
                            INSERT INTO `taifex_overview_daily`
                                (`resolved_date`, `institution`, `trade_long_futures_volume`,
                                 `trade_long_options_volume`, `trade_long_futures_amount`,
                                 `trade_long_options_amount`, `trade_short_futures_volume`,
                                 `trade_short_options_volume`, `trade_short_futures_amount`,
                                 `trade_short_options_amount`, `trade_net_futures_volume`,
                                 `trade_net_options_volume`, `trade_net_futures_amount`,
                                 `trade_net_options_amount`, `trade_net_futures_volume_change`,
                                 `trade_net_options_volume_change`, `trade_net_futures_amount_change`,
                                 `trade_net_options_amount_change`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    item["resolved_date"],
                                    item["institution"],
                                    item["trade_long_futures_volume"],
                                    item["trade_long_options_volume"],
                                    item["trade_long_futures_amount"],
                                    item["trade_long_options_amount"],
                                    item["trade_short_futures_volume"],
                                    item["trade_short_options_volume"],
                                    item["trade_short_futures_amount"],
                                    item["trade_short_options_amount"],
                                    item["trade_net_futures_volume"],
                                    item["trade_net_options_volume"],
                                    item["trade_net_futures_amount"],
                                    item["trade_net_options_amount"],
                                    item["trade_net_futures_volume_change"],
                                    item["trade_net_options_volume_change"],
                                    item["trade_net_futures_amount_change"],
                                    item["trade_net_options_amount_change"],
                                )
                                for item in normalized["overview_rows"]
                            ],
                        )

                    if normalized["futures_rows"]:
                        await cur.executemany(
                            """
                            INSERT INTO `taifex_futures_daily`
                                (`resolved_date`, `commodity`, `institution`, `rank`,
                                 `trade_long_volume`, `trade_long_amount`, `trade_short_volume`,
                                 `trade_short_amount`, `trade_net_volume`, `trade_net_amount`,
                                 `oi_long_volume`, `oi_long_amount`, `oi_short_volume`,
                                 `oi_short_amount`, `oi_net_volume`, `oi_net_amount`,
                                 `trade_net_volume_change`, `trade_net_amount_change`,
                                 `oi_net_volume_change`, `oi_net_amount_change`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    item["resolved_date"],
                                    item["commodity"],
                                    item["institution"],
                                    item["rank"],
                                    item["trade_long_volume"],
                                    item["trade_long_amount"],
                                    item["trade_short_volume"],
                                    item["trade_short_amount"],
                                    item["trade_net_volume"],
                                    item["trade_net_amount"],
                                    item["oi_long_volume"],
                                    item["oi_long_amount"],
                                    item["oi_short_volume"],
                                    item["oi_short_amount"],
                                    item["oi_net_volume"],
                                    item["oi_net_amount"],
                                    item["trade_net_volume_change"],
                                    item["trade_net_amount_change"],
                                    item["oi_net_volume_change"],
                                    item["oi_net_amount_change"],
                                )
                                for item in normalized["futures_rows"]
                            ],
                        )

                    if normalized["options_rows"]:
                        await cur.executemany(
                            """
                            INSERT INTO `taifex_options_daily`
                                (`resolved_date`, `commodity`, `institution`, `rank`,
                                 `trade_long_volume`, `trade_long_amount`, `trade_short_volume`,
                                 `trade_short_amount`, `trade_net_volume`, `trade_net_amount`,
                                 `oi_long_volume`, `oi_long_amount`, `oi_short_volume`,
                                 `oi_short_amount`, `oi_net_volume`, `oi_net_amount`,
                                 `trade_net_volume_change`, `trade_net_amount_change`,
                                 `oi_net_volume_change`, `oi_net_amount_change`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    item["resolved_date"],
                                    item["commodity"],
                                    item["institution"],
                                    item["rank"],
                                    item["trade_long_volume"],
                                    item["trade_long_amount"],
                                    item["trade_short_volume"],
                                    item["trade_short_amount"],
                                    item["trade_net_volume"],
                                    item["trade_net_amount"],
                                    item["oi_long_volume"],
                                    item["oi_long_amount"],
                                    item["oi_short_volume"],
                                    item["oi_short_amount"],
                                    item["oi_net_volume"],
                                    item["oi_net_amount"],
                                    item["trade_net_volume_change"],
                                    item["trade_net_amount_change"],
                                    item["oi_net_volume_change"],
                                    item["oi_net_amount_change"],
                                )
                                for item in normalized["options_rows"]
                            ],
                        )

                    if normalized["call_put_rows"]:
                        await cur.executemany(
                            """
                            INSERT INTO `taifex_call_put_daily`
                                (`resolved_date`, `commodity`, `option_side`, `institution`, `rank`,
                                 `trade_buy_volume`, `trade_buy_amount`, `trade_sell_volume`,
                                 `trade_sell_amount`, `trade_net_volume`, `trade_net_amount`,
                                 `oi_buy_volume`, `oi_buy_amount`, `oi_sell_volume`,
                                 `oi_sell_amount`, `oi_net_volume`, `oi_net_amount`,
                                 `trade_net_volume_change`, `trade_net_amount_change`,
                                 `oi_net_volume_change`, `oi_net_amount_change`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    item["resolved_date"],
                                    item["commodity"],
                                    item["option_side"],
                                    item["institution"],
                                    item["rank"],
                                    item["trade_buy_volume"],
                                    item["trade_buy_amount"],
                                    item["trade_sell_volume"],
                                    item["trade_sell_amount"],
                                    item["trade_net_volume"],
                                    item["trade_net_amount"],
                                    item["oi_buy_volume"],
                                    item["oi_buy_amount"],
                                    item["oi_sell_volume"],
                                    item["oi_sell_amount"],
                                    item["oi_net_volume"],
                                    item["oi_net_amount"],
                                    item["trade_net_volume_change"],
                                    item["trade_net_amount_change"],
                                    item["oi_net_volume_change"],
                                    item["oi_net_amount_change"],
                                )
                                for item in normalized["call_put_rows"]
                            ],
                        )

                    if normalized["cash_summary_rows"]:
                        await cur.executemany(
                            """
                            INSERT INTO `taifex_cash_summary_daily`
                                (`resolved_date`, `institution`, `buy_amount`, `sell_amount`,
                                 `net_amount`, `net_amount_change`)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    item["resolved_date"],
                                    item["institution"],
                                    item["buy_amount"],
                                    item["sell_amount"],
                                    item["net_amount"],
                                    item["net_amount_change"],
                                )
                                for item in normalized["cash_summary_rows"]
                            ],
                        )

        return {
            "overview_rows": len(normalized["overview_rows"]),
            "futures_rows": len(normalized["futures_rows"]),
            "options_rows": len(normalized["options_rows"]),
            "call_put_rows": len(normalized["call_put_rows"]),
            "cash_summary_rows": len(normalized["cash_summary_rows"]),
        }

    async def get_institutional_snapshot(self, target_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        if target_date:
            sql = """
                SELECT `resolved_date`, `query_date`, `payload_json`
                FROM `institutional_snapshots`
                WHERE `resolved_date`<=%s
                ORDER BY `resolved_date` DESC
                LIMIT 1
            """
            params = (target_date.isoformat(),)
        else:
            sql = """
                SELECT `resolved_date`, `query_date`, `payload_json`
                FROM `institutional_snapshots`
                ORDER BY `resolved_date` DESC
                LIMIT 1
            """
            params = ()

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                row = await cur.fetchone()
        return _deserialize_institutional_snapshot(row)

    async def get_institutional_snapshot_exact(self, target_date: date) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT `resolved_date`, `query_date`, `payload_json`
            FROM `institutional_snapshots`
            WHERE `resolved_date`=%s
            LIMIT 1
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (target_date.isoformat(),))
                row = await cur.fetchone()
        return _deserialize_institutional_snapshot(row)

    async def get_institutional_snapshots(self, target_date: date, limit: int) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []

        sql = """
            SELECT `resolved_date`, `query_date`, `payload_json`
            FROM `institutional_snapshots`
            WHERE `resolved_date`<=%s
            ORDER BY `resolved_date` DESC
            LIMIT %s
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (target_date.isoformat(), limit))
                rows = await cur.fetchall()

        snapshots = [
            snapshot
            for snapshot in (
                _deserialize_institutional_snapshot(row)
                for row in rows
            )
            if snapshot
        ]
        snapshots.reverse()
        return snapshots

    async def list_institutional_snapshot_payloads(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        filters = ["1=1"]
        params: List[Any] = []
        normalized_start = _normalize_taifex_date(start_date)
        normalized_end = _normalize_taifex_date(end_date)
        if normalized_start:
            filters.append("`resolved_date`>=%s")
            params.append(normalized_start)
        if normalized_end:
            filters.append("`resolved_date`<=%s")
            params.append(normalized_end)

        sql = f"""
            SELECT `resolved_date`, `query_date`, `payload_json`
            FROM `institutional_snapshots`
            WHERE {' AND '.join(filters)}
            ORDER BY `resolved_date` ASC
        """
        if limit and limit > 0:
            sql += " LIMIT %s"
            params.append(int(limit))

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, tuple(params))
                rows = await cur.fetchall()
        return [
            snapshot
            for snapshot in (_deserialize_institutional_snapshot(row) for row in rows)
            if snapshot
        ]

    async def get_taifex_structured_snapshot_counts(self, resolved_date: str | date) -> Dict[str, int]:
        normalized_date = _normalize_taifex_date(resolved_date)
        if not normalized_date:
            raise ValueError("resolved_date is required")

        counts: Dict[str, int] = {}
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                for table_name in ("taifex_institutional_meta", *TAIFEX_STRUCTURED_ROW_TABLES):
                    await cur.execute(
                        f"SELECT COUNT(*) AS `row_count` FROM `{table_name}` WHERE `resolved_date`=%s",
                        (normalized_date,),
                    )
                    row = await cur.fetchone()
                    counts[table_name] = int((row or {}).get("row_count") or 0)
        return counts

