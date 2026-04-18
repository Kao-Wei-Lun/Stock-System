from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from database.core import DEFAULT_OWNER_ID
from database.helpers import (
    _deserialize_asset_account,
    _deserialize_asset_cash_ledger_entry,
    _deserialize_asset_position_current,
    _deserialize_asset_reconciliation_snapshot,
    _deserialize_asset_trade_entry,
    _deserialize_asset_valuation_current,
    _normalize_asset_account_payload,
    _normalize_asset_cash_ledger_payload,
    _normalize_asset_reconciliation_snapshot_payload,
    _normalize_asset_trade_payload,
    _parse_datetime_value,
)


class AssetMixin:
    async def list_asset_accounts(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `asset_accounts`
            WHERE `owner_id`=%s
            ORDER BY `sort_order` ASC, `id` ASC
            """,
            (owner_id,),
        )
        return [_deserialize_asset_account(row) for row in rows]

    async def get_asset_account(self, account_id: int, owner_id: int = DEFAULT_OWNER_ID) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `asset_accounts`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (account_id, owner_id),
        )
        return _deserialize_asset_account(row)

    async def create_asset_account(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_asset_account_payload(payload)
        account_id = await self._execute_insert(
            """
            INSERT INTO `asset_accounts`
                (`owner_id`, `name`, `institution`, `account_type`, `base_currency`,
                 `include_in_total`, `sort_order`, `notes`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["name"],
                normalized["institution"],
                normalized["account_type"],
                normalized["base_currency"],
                1 if normalized["include_in_total"] else 0,
                normalized["sort_order"],
                normalized["notes"],
            ),
        )
        account = await self.get_asset_account(account_id, owner_id=owner_id)
        if not account:
            raise RuntimeError("Asset account was not persisted")
        return account

    async def update_asset_account(
        self,
        account_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_asset_account(account_id, owner_id=owner_id)
        if not existing:
            return None
        normalized = _normalize_asset_account_payload(payload, existing=existing)
        updated = await self._execute(
            """
            UPDATE `asset_accounts`
            SET `name`=%s,
                `institution`=%s,
                `account_type`=%s,
                `base_currency`=%s,
                `include_in_total`=%s,
                `sort_order`=%s,
                `notes`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["name"],
                normalized["institution"],
                normalized["account_type"],
                normalized["base_currency"],
                1 if normalized["include_in_total"] else 0,
                normalized["sort_order"],
                normalized["notes"],
                account_id,
                owner_id,
            ),
        )
        if not updated:
            return None
        return await self.get_asset_account(account_id, owner_id=owner_id)

    async def delete_asset_account(self, account_id: int, owner_id: int = DEFAULT_OWNER_ID) -> bool:
        deleted = await self._execute(
            "DELETE FROM `asset_accounts` WHERE `id`=%s AND `owner_id`=%s",
            (account_id, owner_id),
        )
        return bool(deleted)

    async def list_asset_cash_ledger_entries(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        *,
        account_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        filters = ["`owner_id`=%s"]
        params: List[Any] = [owner_id]
        if account_id is not None:
            filters.append("`account_id`=%s")
            params.append(account_id)
        if date_from:
            filters.append("`flow_date` >= %s")
            params.append(_parse_datetime_value(date_from))
        if date_to:
            filters.append("`flow_date` <= %s")
            params.append(_parse_datetime_value(date_to))
        clean_limit = max(1, min(int(limit or 200), 5000))
        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `asset_cash_ledger`
            WHERE {' AND '.join(filters)}
            ORDER BY `flow_date` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_asset_cash_ledger_entry(row) for row in rows]

    async def get_asset_cash_ledger_entry(
        self,
        entry_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `asset_cash_ledger`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (entry_id, owner_id),
        )
        return _deserialize_asset_cash_ledger_entry(row)

    async def create_asset_cash_ledger_entry(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_asset_cash_ledger_payload(payload)
        entry_id = await self._execute_insert(
            """
            INSERT INTO `asset_cash_ledger`
                (`owner_id`, `account_id`, `flow_date`, `flow_type`, `amount`, `currency`,
                 `fx_rate_to_base`, `counterparty`, `note`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["account_id"],
                _parse_datetime_value(normalized["flow_date"]),
                normalized["flow_type"],
                normalized["amount"],
                normalized["currency"],
                normalized["fx_rate_to_base"],
                normalized["counterparty"],
                normalized["note"],
            ),
        )
        entry = await self.get_asset_cash_ledger_entry(entry_id, owner_id=owner_id)
        if not entry:
            raise RuntimeError("Asset cash ledger entry was not persisted")
        return entry

    async def update_asset_cash_ledger_entry(
        self,
        entry_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_asset_cash_ledger_entry(entry_id, owner_id=owner_id)
        if not existing:
            return None
        normalized = _normalize_asset_cash_ledger_payload(payload, existing=existing)
        updated = await self._execute(
            """
            UPDATE `asset_cash_ledger`
            SET `account_id`=%s,
                `flow_date`=%s,
                `flow_type`=%s,
                `amount`=%s,
                `currency`=%s,
                `fx_rate_to_base`=%s,
                `counterparty`=%s,
                `note`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["account_id"],
                _parse_datetime_value(normalized["flow_date"]),
                normalized["flow_type"],
                normalized["amount"],
                normalized["currency"],
                normalized["fx_rate_to_base"],
                normalized["counterparty"],
                normalized["note"],
                entry_id,
                owner_id,
            ),
        )
        if not updated:
            return None
        return await self.get_asset_cash_ledger_entry(entry_id, owner_id=owner_id)

    async def delete_asset_cash_ledger_entry(self, entry_id: int, owner_id: int = DEFAULT_OWNER_ID) -> bool:
        deleted = await self._execute(
            "DELETE FROM `asset_cash_ledger` WHERE `id`=%s AND `owner_id`=%s",
            (entry_id, owner_id),
        )
        return bool(deleted)

    async def list_asset_trade_entries(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        *,
        account_id: int | None = None,
        ticker: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        filters = ["`owner_id`=%s"]
        params: List[Any] = [owner_id]
        if account_id is not None:
            filters.append("`account_id`=%s")
            params.append(account_id)
        if ticker:
            filters.append("`ticker`=%s")
            params.append(str(ticker).strip().upper())
        if date_from:
            filters.append("`trade_date` >= %s")
            params.append(_parse_datetime_value(date_from))
        if date_to:
            filters.append("`trade_date` <= %s")
            params.append(_parse_datetime_value(date_to))
        clean_limit = max(1, min(int(limit or 200), 5000))
        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `asset_trade_ledger`
            WHERE {' AND '.join(filters)}
            ORDER BY `trade_date` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_asset_trade_entry(row) for row in rows]

    async def get_asset_trade_entry(
        self,
        entry_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `asset_trade_ledger`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (entry_id, owner_id),
        )
        return _deserialize_asset_trade_entry(row)

    async def create_asset_trade_entry(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_asset_trade_payload(payload)
        entry_id = await self._execute_insert(
            """
            INSERT INTO `asset_trade_ledger`
                (`owner_id`, `account_id`, `trade_date`, `ticker`, `display_name`, `market`,
                 `asset_type`, `currency`, `side`, `quantity`, `price`, `gross_amount`,
                 `fee_amount`, `tax_amount`, `net_amount`, `fx_rate_to_base`, `source`, `note`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["account_id"],
                _parse_datetime_value(normalized["trade_date"]),
                normalized["ticker"],
                normalized["display_name"],
                normalized["market"],
                normalized["asset_type"],
                normalized["currency"],
                normalized["side"],
                normalized["quantity"],
                normalized["price"],
                normalized["gross_amount"],
                normalized["fee_amount"],
                normalized["tax_amount"],
                normalized["net_amount"],
                normalized["fx_rate_to_base"],
                normalized["source"],
                normalized["note"],
            ),
        )
        entry = await self.get_asset_trade_entry(entry_id, owner_id=owner_id)
        if not entry:
            raise RuntimeError("Asset trade entry was not persisted")
        return entry

    async def update_asset_trade_entry(
        self,
        entry_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_asset_trade_entry(entry_id, owner_id=owner_id)
        if not existing:
            return None
        normalized = _normalize_asset_trade_payload(payload, existing=existing)
        updated = await self._execute(
            """
            UPDATE `asset_trade_ledger`
            SET `account_id`=%s,
                `trade_date`=%s,
                `ticker`=%s,
                `display_name`=%s,
                `market`=%s,
                `asset_type`=%s,
                `currency`=%s,
                `side`=%s,
                `quantity`=%s,
                `price`=%s,
                `gross_amount`=%s,
                `fee_amount`=%s,
                `tax_amount`=%s,
                `net_amount`=%s,
                `fx_rate_to_base`=%s,
                `source`=%s,
                `note`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["account_id"],
                _parse_datetime_value(normalized["trade_date"]),
                normalized["ticker"],
                normalized["display_name"],
                normalized["market"],
                normalized["asset_type"],
                normalized["currency"],
                normalized["side"],
                normalized["quantity"],
                normalized["price"],
                normalized["gross_amount"],
                normalized["fee_amount"],
                normalized["tax_amount"],
                normalized["net_amount"],
                normalized["fx_rate_to_base"],
                normalized["source"],
                normalized["note"],
                entry_id,
                owner_id,
            ),
        )
        if not updated:
            return None
        return await self.get_asset_trade_entry(entry_id, owner_id=owner_id)

    async def delete_asset_trade_entry(self, entry_id: int, owner_id: int = DEFAULT_OWNER_ID) -> bool:
        deleted = await self._execute(
            "DELETE FROM `asset_trade_ledger` WHERE `id`=%s AND `owner_id`=%s",
            (entry_id, owner_id),
        )
        return bool(deleted)

    async def list_asset_reconciliation_snapshots(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        *,
        account_id: int | None = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        filters = ["`owner_id`=%s"]
        params: List[Any] = [owner_id]
        if account_id is not None:
            filters.append("`account_id`=%s")
            params.append(account_id)
        clean_limit = max(1, min(int(limit or 200), 5000))
        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `asset_reconciliation_snapshots`
            WHERE {' AND '.join(filters)}
            ORDER BY `snapshot_date` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_asset_reconciliation_snapshot(row) for row in rows]

    async def get_asset_reconciliation_snapshot(
        self,
        snapshot_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `asset_reconciliation_snapshots`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (snapshot_id, owner_id),
        )
        return _deserialize_asset_reconciliation_snapshot(row)

    async def create_asset_reconciliation_snapshot(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_asset_reconciliation_snapshot_payload(payload)
        snapshot_id = await self._execute_insert(
            """
            INSERT INTO `asset_reconciliation_snapshots`
                (`owner_id`, `account_id`, `snapshot_date`, `cash_actual`, `cash_system`,
                 `market_value_actual`, `market_value_system`, `positions_payload_json`, `note`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["account_id"],
                _parse_datetime_value(normalized["snapshot_date"]),
                normalized["cash_actual"],
                normalized["cash_system"],
                normalized["market_value_actual"],
                normalized["market_value_system"],
                json.dumps(normalized["positions_payload"], ensure_ascii=False),
                normalized["note"],
            ),
        )
        snapshot = await self.get_asset_reconciliation_snapshot(snapshot_id, owner_id=owner_id)
        if not snapshot:
            raise RuntimeError("Asset reconciliation snapshot was not persisted")
        return snapshot

    async def delete_asset_reconciliation_snapshot(
        self,
        snapshot_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> bool:
        deleted = await self._execute(
            "DELETE FROM `asset_reconciliation_snapshots` WHERE `id`=%s AND `owner_id`=%s",
            (snapshot_id, owner_id),
        )
        return bool(deleted)

    async def replace_asset_positions_current(
        self,
        owner_id: int,
        positions: List[Dict[str, Any]],
    ) -> None:
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("DELETE FROM `asset_positions_current` WHERE `owner_id`=%s", (owner_id,))
                    if positions:
                        await cur.executemany(
                            """
                            INSERT INTO `asset_positions_current`
                                (`owner_id`, `account_id`, `ticker`, `display_name`, `market`,
                                 `asset_type`, `currency`, `quantity`, `avg_cost`, `cost_basis`,
                                 `realized_pnl`, `trade_count`, `last_trade_at`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    owner_id,
                                    item["account_id"],
                                    item["ticker"],
                                    item.get("display_name"),
                                    item.get("market"),
                                    item.get("asset_type"),
                                    item.get("currency"),
                                    item.get("quantity"),
                                    item.get("avg_cost"),
                                    item.get("cost_basis"),
                                    item.get("realized_pnl"),
                                    item.get("trade_count") or 0,
                                    _parse_datetime_value(item.get("last_trade_at")),
                                )
                                for item in positions
                            ],
                        )

    async def replace_asset_valuations_current(
        self,
        owner_id: int,
        valuations: List[Dict[str, Any]],
    ) -> None:
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("DELETE FROM `asset_valuations_current` WHERE `owner_id`=%s", (owner_id,))
                    if valuations:
                        await cur.executemany(
                            """
                            INSERT INTO `asset_valuations_current`
                                (`owner_id`, `account_id`, `ticker`, `quote_source`, `quote_type`, `is_delayed`,
                                 `quote_timestamp`, `last_price`, `market_value`, `market_value_base`,
                                 `unrealized_pnl`, `unrealized_pnl_base`, `fx_rate_to_base`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    owner_id,
                                    item["account_id"],
                                    item["ticker"],
                                    item.get("quote_source"),
                                    item.get("quote_type"),
                                    1 if item.get("is_delayed") else 0,
                                    _parse_datetime_value(item.get("quote_timestamp")),
                                    item.get("last_price"),
                                    item.get("market_value"),
                                    item.get("market_value_base"),
                                    item.get("unrealized_pnl"),
                                    item.get("unrealized_pnl_base"),
                                    item.get("fx_rate_to_base"),
                                )
                                for item in valuations
                            ],
                        )

    async def list_asset_positions_current(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `asset_positions_current`
            WHERE `owner_id`=%s
            ORDER BY `account_id` ASC, `ticker` ASC
            """,
            (owner_id,),
        )
        return [_deserialize_asset_position_current(row) for row in rows]

    async def list_asset_valuations_current(self, owner_id: int = DEFAULT_OWNER_ID) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT *
            FROM `asset_valuations_current`
            WHERE `owner_id`=%s
            ORDER BY `account_id` ASC, `ticker` ASC
            """,
            (owner_id,),
        )
        return [_deserialize_asset_valuation_current(row) for row in rows]
