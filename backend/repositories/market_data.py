from typing import Any, Dict, List, Optional
from database.helpers import *
from database.core import DEFAULT_OWNER_ID
# Import common serialization helpers here if needed

class MarketDataMixin:
    @staticmethod
    def _normalized_tickers(tickers) -> List[str]:
        return list(dict.fromkeys(
            str(ticker or "").strip().upper()
            for ticker in tickers or []
            if str(ticker or "").strip()
        ))

    async def upsert_ohlcv_batch(self, ticker: str, rows: List[Dict], interval: str = "1d") -> int:
        if not rows:
            return 0

        sql = """
            INSERT INTO `ohlcv`
                (`ticker`, `date`, `interval`, `open`, `high`, `low`, `close`, `volume`, `adj_close`, `source`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `open` = `incoming`.`open`,
                `high` = `incoming`.`high`,
                `low` = `incoming`.`low`,
                `close` = `incoming`.`close`,
                `volume` = `incoming`.`volume`,
                `adj_close` = `incoming`.`adj_close`,
                `source` = `incoming`.`source`
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
                row.get("source", "yahoo_finance"),
            )
            for row in rows
        ]

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(sql, params)
        return len(rows)

    async def delete_ohlcv_range(
        self,
        ticker: str,
        interval: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> int:
        conditions = ["`ticker`=%s", "`interval`=%s"]
        params: List = [ticker, interval]

        if start_date:
            conditions.append("`date`>=%s")
            params.append(start_date)
        if end_date:
            conditions.append("`date`<=%s")
            params.append(end_date)

        sql = f"DELETE FROM `ohlcv` WHERE {' AND '.join(conditions)}"
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, tuple(params))
                    return cur.rowcount

    async def get_ohlcv(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
        *,
        since: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        period_start = _period_to_date(period)
        lower_bound = since or period_start
        select_sql = """
            SELECT `date`, `open`, `high`, `low`, `close`, `volume`, `adj_close`, `source`, `updated_at`
            FROM `ohlcv`
            WHERE `ticker`=%s AND `interval`=%s AND `date`>=%s
        """
        params: tuple = (ticker, interval, lower_bound)
        if limit is not None:
            clean_limit = max(1, min(int(limit), 5000))
            sql = f"""
                SELECT * FROM ({select_sql} ORDER BY `date` DESC LIMIT %s) AS `bounded`
                ORDER BY `date` ASC
            """
            params = (*params, clean_limit)
        else:
            sql = f"{select_sql} ORDER BY `date` ASC"
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()
        return list(rows)

    async def get_ohlcv_range(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> List[Dict]:
        sql = """
            SELECT `date`, `open`, `high`, `low`, `close`, `volume`, `adj_close`, `source`, `updated_at`
            FROM `ohlcv`
            WHERE `ticker`=%s AND `interval`=%s AND `date`>=%s AND `date`<=%s
            ORDER BY `date` ASC
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (ticker, interval, start_date, end_date))
                rows = await cur.fetchall()
        return list(rows)

    async def get_latest_ohlcv(self, ticker: str, interval: str = "1d") -> Optional[Dict]:
        sql = """
            SELECT *
            FROM `ohlcv`
            WHERE `ticker`=%s AND `interval`=%s
            ORDER BY `date` DESC
            LIMIT 1
        """
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, (ticker, interval))
                return await cur.fetchone()

    async def get_recent_ohlcv_many(
        self,
        tickers,
        interval: str = "1d",
        per_ticker_limit: int = 2,
    ) -> Dict[str, List[Dict]]:
        normalized = self._normalized_tickers(tickers)
        if not normalized:
            return {}
        clean_limit = max(1, min(int(per_ticker_limit), 10))
        # A window function over the 1-minute OHLCV table scans too many rows.
        # Each UNION branch can use the ticker/interval/date index and still
        # returns the whole watchlist in one database round trip.
        rows = []
        for start in range(0, len(normalized), 100):
            batch = normalized[start:start + 100]
            branches = [
                "(SELECT * FROM `ohlcv` WHERE `ticker`=%s AND `interval`=%s ORDER BY `date` DESC LIMIT %s)"
                for _ in batch
            ]
            params = tuple(
                value
                for ticker in batch
                for value in (ticker, interval, clean_limit)
            )
            rows.extend(await self._fetchall(
                f"""
                SELECT *
                FROM ({' UNION ALL '.join(branches)}) AS `recent`
                ORDER BY `ticker`, `date` DESC
                """,
                params,
            ))
        grouped: Dict[str, List[Dict]] = {ticker: [] for ticker in normalized}
        for row in rows:
            item = dict(row)
            grouped.setdefault(str(item.get("ticker") or "").upper(), []).append(item)
        return grouped

    async def get_latest_ohlcv_many(self, tickers, interval: str = "1d") -> Dict[str, Dict]:
        grouped = await self.get_recent_ohlcv_many(tickers, interval=interval, per_ticker_limit=1)
        return {ticker: rows[0] for ticker, rows in grouped.items() if rows}

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
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `name` = `incoming`.`name`,
                `sector` = `incoming`.`sector`,
                `industry` = `incoming`.`industry`,
                `market_cap` = `incoming`.`market_cap`,
                `pe_ratio` = `incoming`.`pe_ratio`,
                `dividend_yield` = `incoming`.`dividend_yield`,
                `week_52_high` = `incoming`.`week_52_high`,
                `week_52_low` = `incoming`.`week_52_low`,
                `avg_volume` = `incoming`.`avg_volume`,
                `description` = `incoming`.`description`,
                `currency` = `incoming`.`currency`,
                `exchange` = `incoming`.`exchange`,
                `country` = `incoming`.`country`
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

    async def get_stock_info_many(self, tickers) -> Dict[str, Dict]:
        normalized = self._normalized_tickers(tickers)
        if not normalized:
            return {}
        placeholders = ", ".join(["%s"] * len(normalized))
        rows = await self._fetchall(
            f"SELECT * FROM `stock_info` WHERE `ticker` IN ({placeholders})",
            tuple(normalized),
        )
        return {str(row["ticker"]).upper(): row for row in rows}

    async def upsert_tw_equity_universe(self, rows: List[Dict[str, Any]]) -> int:
        if not rows:
            return 0

        sql = """
            INSERT INTO `tw_equity_universe`
                (`ticker`, `symbol`, `market`, `name`, `sector`, `security_type`, `is_etf`,
                 `is_active`, `source`, `latest_snapshot_date`, `last_seen_at`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `symbol`=`incoming`.`symbol`,
                `market`=`incoming`.`market`,
                `name`=`incoming`.`name`,
                `sector`=`incoming`.`sector`,
                `security_type`=`incoming`.`security_type`,
                `is_etf`=`incoming`.`is_etf`,
                `is_active`=`incoming`.`is_active`,
                `source`=`incoming`.`source`,
                `latest_snapshot_date`=`incoming`.`latest_snapshot_date`,
                `last_seen_at`=NOW()
        """
        params = [
            (
                row["ticker"],
                row.get("symbol") or str(row["ticker"]).split(".", 1)[0],
                row.get("market") or "TSE",
                row.get("name"),
                row.get("sector"),
                row.get("security_type"),
                1 if row.get("is_etf") else 0,
                1 if row.get("is_active", True) else 0,
                row.get("source") or "fubon_neo",
                row.get("latest_snapshot_date"),
            )
            for row in rows
            if row.get("ticker")
        ]
        if not params:
            return 0
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(sql, params)
        return len(params)

    async def deactivate_stale_tw_equities(self, snapshot_date: str) -> int:
        return await self._execute(
            """
            UPDATE `tw_equity_universe`
            SET `is_active`=0
            WHERE `source`='fubon_neo'
              AND (`latest_snapshot_date` IS NULL OR `latest_snapshot_date`<>%s)
            """,
            (snapshot_date,),
        )

    async def list_tw_equity_universe(
        self,
        *,
        active_only: bool = True,
        include_etf: bool = True,
        markets: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        conditions: List[str] = []
        params: List[Any] = []
        if active_only:
            conditions.append("`is_active`=1")
        if not include_etf:
            conditions.append("`is_etf`=0")
        if markets:
            clean_markets = [str(item).strip().upper() for item in markets if str(item or "").strip()]
            if clean_markets:
                placeholders = ", ".join(["%s"] * len(clean_markets))
                conditions.append(f"`market` IN ({placeholders})")
                params.extend(clean_markets)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        limit_clause = ""
        if limit is not None:
            limit_clause = "LIMIT %s"
            params.append(max(1, min(int(limit), 10000)))
        return await self._fetchall(
            f"""
            SELECT *
            FROM `tw_equity_universe`
            {where_clause}
            ORDER BY `market` ASC, `ticker` ASC
            {limit_clause}
            """,
            tuple(params),
        )

    async def record_tw_history_sync_status(
        self,
        *,
        ticker: str,
        interval: str,
        status: str,
        requested_start_date: Optional[str] = None,
        requested_end_date: Optional[str] = None,
        last_success_date: Optional[str] = None,
        rows_synced: int = 0,
        error: Optional[str] = None,
        source: str = "fubon_neo",
    ) -> Dict[str, Any]:
        await self._execute(
            """
            INSERT INTO `tw_history_sync_status`
                (`ticker`, `interval`, `status`, `requested_start_date`, `requested_end_date`,
                 `last_success_date`, `last_attempt_at`, `last_success_at`, `rows_synced_total`,
                 `last_rows_synced`, `attempts`, `last_error`, `source`)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), IF(%s='success', NOW(), NULL), %s, %s, 1, %s, %s)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `status`=`incoming`.`status`,
                `requested_start_date`=`incoming`.`requested_start_date`,
                `requested_end_date`=`incoming`.`requested_end_date`,
                `last_success_date`=IF(
                    `incoming`.`last_success_date` IS NULL,
                    `tw_history_sync_status`.`last_success_date`,
                    `incoming`.`last_success_date`
                ),
                `last_attempt_at`=NOW(),
                `last_success_at`=IF(`incoming`.`status`='success', NOW(), `tw_history_sync_status`.`last_success_at`),
                `rows_synced_total`=`tw_history_sync_status`.`rows_synced_total` + `incoming`.`last_rows_synced`,
                `last_rows_synced`=`incoming`.`last_rows_synced`,
                `attempts`=`tw_history_sync_status`.`attempts` + 1,
                `last_error`=IF(`incoming`.`status`='success', NULL, `incoming`.`last_error`),
                `source`=`incoming`.`source`
            """,
            (
                ticker,
                interval,
                status,
                requested_start_date,
                requested_end_date,
                last_success_date,
                status,
                max(0, int(rows_synced or 0)),
                max(0, int(rows_synced or 0)),
                error[:2000] if error else None,
                source,
            ),
        )
        return await self.get_tw_history_sync_status(ticker, interval) or {
            "ticker": ticker,
            "interval": interval,
            "status": status,
        }

    async def get_tw_history_sync_status(self, ticker: str, interval: str = "1d") -> Optional[Dict[str, Any]]:
        return await self._fetchone(
            """
            SELECT *
            FROM `tw_history_sync_status`
            WHERE `ticker`=%s AND `interval`=%s
            LIMIT 1
            """,
            (ticker, interval),
        )

    async def list_tw_history_sync_status(
        self,
        *,
        interval: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        conditions: List[str] = []
        params: List[Any] = []
        if interval:
            conditions.append("`interval`=%s")
            params.append(interval)
        if status:
            conditions.append("`status`=%s")
            params.append(status)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(max(1, min(int(limit or 500), 5000)))
        return await self._fetchall(
            f"""
            SELECT *
            FROM `tw_history_sync_status`
            {where_clause}
            ORDER BY `updated_at` DESC, `ticker` ASC
            LIMIT %s
            """,
            tuple(params),
        )

    async def get_tw_universe_coverage(self, interval: str = "1d") -> Dict[str, Any]:
        row = await self._fetchone(
            """
            SELECT
                COUNT(*) AS `universe_count`,
                SUM(CASE WHEN latest.`ticker` IS NOT NULL THEN 1 ELSE 0 END) AS `covered_count`,
                MIN(latest.`latest_date`) AS `oldest_latest_date`,
                MAX(latest.`latest_date`) AS `newest_latest_date`,
                SUM(COALESCE(latest.`row_count`, 0)) AS `ohlcv_rows`
            FROM `tw_equity_universe` AS u
            LEFT JOIN (
                SELECT `ticker`, MAX(`date`) AS `latest_date`, COUNT(*) AS `row_count`
                FROM `ohlcv`
                WHERE `interval`=%s
                GROUP BY `ticker`
            ) AS latest ON latest.`ticker` = u.`ticker`
            WHERE u.`is_active`=1
            """,
            (interval,),
        )
        payload = dict(row or {})
        universe_count = int(payload.get("universe_count") or 0)
        covered_count = int(payload.get("covered_count") or 0)
        payload["universe_count"] = universe_count
        payload["covered_count"] = covered_count
        payload["coverage_pct"] = round(covered_count / universe_count * 100.0, 2) if universe_count else 0.0
        payload["interval"] = interval
        return payload

    async def get_tw_analysis_kline_coverage(self, interval: str = "1d") -> Dict[str, Any]:
        row = await self._fetchone(
            """
            SELECT
                COUNT(*) AS `universe_count`,
                SUM(CASE WHEN latest.`ticker` IS NOT NULL THEN 1 ELSE 0 END) AS `covered_count`,
                SUM(CASE WHEN latest.`latest_date` = market_latest.`latest_date` THEN 1 ELSE 0 END)
                    AS `latest_covered_count`,
                MIN(latest.`latest_date`) AS `oldest_latest_date`,
                MAX(latest.`latest_date`) AS `newest_latest_date`,
                MAX(market_latest.`latest_date`) AS `expected_latest_date`,
                SUM(COALESCE(latest.`row_count`, 0)) AS `ohlcv_rows`
            FROM `tw_equity_universe` AS u
            CROSS JOIN (
                SELECT MAX(`date`) AS `latest_date`
                FROM `ohlcv`
                WHERE `interval`=%s
            ) AS market_latest
            LEFT JOIN (
                SELECT `ticker`, MAX(`date`) AS `latest_date`, COUNT(*) AS `row_count`
                FROM `ohlcv`
                WHERE `interval`=%s
                GROUP BY `ticker`
            ) AS latest ON latest.`ticker` = u.`ticker`
            WHERE u.`is_active`=1
              AND u.`is_etf`=0
              AND u.`symbol` REGEXP '^[0-9]{4}$'
            """,
            (interval, interval),
        )
        payload = dict(row or {})
        universe_count = int(payload.get("universe_count") or 0)
        covered_count = int(payload.get("covered_count") or 0)
        latest_covered_count = int(payload.get("latest_covered_count") or 0)
        payload["universe_count"] = universe_count
        payload["covered_count"] = covered_count
        payload["latest_covered_count"] = latest_covered_count
        payload["coverage_pct"] = round(covered_count / universe_count * 100.0, 2) if universe_count else 0.0
        payload["latest_coverage_pct"] = (
            round(latest_covered_count / universe_count * 100.0, 2) if universe_count else 0.0
        )
        payload["interval"] = interval
        return payload

    async def list_screenable_tickers(self, limit: int = 400) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 5000))
        rows = await self._fetchall(
            """
            SELECT
                o.`ticker`,
                o.`date`,
                o.`open`,
                o.`high`,
                o.`low`,
                o.`close`,
                o.`volume`,
                si.`name`,
                si.`sector`,
                si.`industry`,
                si.`market_cap`,
                si.`pe_ratio`,
                si.`dividend_yield`,
                si.`week_52_high`,
                si.`week_52_low`,
                si.`avg_volume`,
                si.`exchange`,
                si.`country`,
                mq.`change_pct` AS `quote_change_pct`,
                mq.`quote_timestamp`,
                mq.`source` AS `quote_source`
            FROM `ohlcv` AS o
            INNER JOIN (
                SELECT `ticker`, MAX(`date`) AS `latest_date`
                FROM `ohlcv`
                WHERE `interval`='1d'
                GROUP BY `ticker`
            ) AS latest
                ON latest.`ticker` = o.`ticker`
               AND latest.`latest_date` = o.`date`
            LEFT JOIN `stock_info` AS si ON si.`ticker` = o.`ticker`
            LEFT JOIN `market_quotes_latest` AS mq ON mq.`ticker` = o.`ticker`
            WHERE o.`interval`='1d'
            ORDER BY o.`date` DESC, o.`ticker` ASC
            LIMIT %s
            """,
            (clean_limit,),
        )
        return list(rows)

    async def get_recent_ohlcv_rows(
        self,
        ticker: str,
        limit: int = 260,
        interval: str = "1d",
    ) -> List[Dict[str, Any]]:
        clean_limit = max(2, min(limit, 1000))
        rows = await self._fetchall(
            """
            SELECT `date`, `open`, `high`, `low`, `close`, `volume`, `adj_close`, `source`, `updated_at`
            FROM `ohlcv`
            WHERE `ticker`=%s AND `interval`=%s
            ORDER BY `date` DESC
            LIMIT %s
            """,
            (ticker, interval, clean_limit),
        )
        return list(reversed(rows))

    async def upsert_market_quote(self, quote: Dict[str, Any]) -> Dict[str, Any]:
        normalized = _normalize_quote_payload(quote)
        await self._execute(
            """
            INSERT INTO `market_quotes_latest`
                (`ticker`, `source`, `quote_type`, `is_delayed`, `name`, `currency`, `price`,
                 `open`, `high`, `low`, `prev_close`, `change_amount`, `change_pct`,
                 `volume`, `market_cap`, `quote_timestamp`, `payload_json`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `source`=`incoming`.`source`,
                `quote_type`=`incoming`.`quote_type`,
                `is_delayed`=`incoming`.`is_delayed`,
                `name`=`incoming`.`name`,
                `currency`=`incoming`.`currency`,
                `price`=`incoming`.`price`,
                `open`=`incoming`.`open`,
                `high`=`incoming`.`high`,
                `low`=`incoming`.`low`,
                `prev_close`=`incoming`.`prev_close`,
                `change_amount`=`incoming`.`change_amount`,
                `change_pct`=`incoming`.`change_pct`,
                `volume`=`incoming`.`volume`,
                `market_cap`=`incoming`.`market_cap`,
                `quote_timestamp`=`incoming`.`quote_timestamp`,
                `payload_json`=`incoming`.`payload_json`
            """,
            (
                normalized["ticker"],
                normalized["source"],
                normalized["quote_type"],
                1 if normalized["is_delayed"] else 0,
                normalized["name"],
                normalized["currency"],
                normalized["price"],
                normalized["open"],
                normalized["high"],
                normalized["low"],
                normalized["prev_close"],
                normalized["change"],
                normalized["change_pct"],
                normalized["volume"],
                normalized["market_cap"],
                _parse_datetime_value(normalized.get("quote_timestamp")),
                _json_dumps(normalized),
            ),
        )
        quote_row = await self.get_market_quote(normalized["ticker"])
        if not quote_row:
            raise RuntimeError("Market quote was not persisted")
        return quote_row

    async def get_market_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `market_quotes_latest`
            WHERE `ticker`=%s
            LIMIT 1
            """,
            (ticker,),
        )
        return _deserialize_market_quote(row)

    async def get_market_quotes(self, tickers) -> Dict[str, Dict[str, Any]]:
        normalized = self._normalized_tickers(tickers)
        if not normalized:
            return {}
        placeholders = ", ".join(["%s"] * len(normalized))
        rows = await self._fetchall(
            f"SELECT * FROM `market_quotes_latest` WHERE `ticker` IN ({placeholders})",
            tuple(normalized),
        )
        return {
            str(row["ticker"]).upper(): _deserialize_market_quote(row)
            for row in rows
        }

