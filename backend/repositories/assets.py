from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from database.core import DEFAULT_OWNER_ID
from database.helpers import (
    _deserialize_asset_account,
    _deserialize_asset_cash_ledger_entry,
    _deserialize_asset_fx_rate,
    _deserialize_asset_position_current,
    _deserialize_asset_position_adjustment,
    _deserialize_asset_price_override,
    _deserialize_asset_reconciliation_snapshot,
    _deserialize_asset_trade_entry,
    _deserialize_asset_valuation_current,
    _normalize_asset_account_payload,
    _normalize_asset_cash_ledger_payload,
    _normalize_asset_fx_rate_payload,
    _normalize_asset_position_adjustment_payload,
    _normalize_asset_price_override_payload,
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
                 `fx_rate_to_base`, `is_initial_balance`, `counterparty`, `note`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["account_id"],
                _parse_datetime_value(normalized["flow_date"]),
                normalized["flow_type"],
                normalized["amount"],
                normalized["currency"],
                normalized["fx_rate_to_base"],
                normalized["is_initial_balance"],
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
                `is_initial_balance`=%s,
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
                normalized["is_initial_balance"],
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
                 `fee_amount`, `tax_amount`, `net_amount`, `fx_rate_to_base`,
                 `is_initial_balance`, `source`, `note`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                normalized["is_initial_balance"],
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
                `is_initial_balance`=%s,
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
                normalized["is_initial_balance"],
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

    async def list_asset_price_overrides(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        *,
        account_id: int | None = None,
        ticker: str | None = None,
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
        clean_limit = max(1, min(int(limit or 200), 5000))
        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `asset_price_overrides`
            WHERE {' AND '.join(filters)}
            ORDER BY `effective_at` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_asset_price_override(row) for row in rows]

    async def get_asset_price_override(
        self,
        override_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `asset_price_overrides`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (override_id, owner_id),
        )
        return _deserialize_asset_price_override(row)

    async def create_asset_price_override(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_asset_price_override_payload(payload)
        override_id = await self._execute_insert(
            """
            INSERT INTO `asset_price_overrides`
                (`owner_id`, `account_id`, `ticker`, `effective_at`, `price`, `currency`,
                 `fx_rate_to_base`, `force_override`, `note`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["account_id"],
                normalized["ticker"],
                _parse_datetime_value(normalized["effective_at"]),
                normalized["price"],
                normalized["currency"],
                normalized["fx_rate_to_base"],
                1 if normalized["force_override"] else 0,
                normalized["note"],
            ),
        )
        override = await self.get_asset_price_override(override_id, owner_id=owner_id)
        if not override:
            raise RuntimeError("Asset price override was not persisted")
        return override

    async def update_asset_price_override(
        self,
        override_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_asset_price_override(override_id, owner_id=owner_id)
        if not existing:
            return None
        normalized = _normalize_asset_price_override_payload(payload, existing=existing)
        updated = await self._execute(
            """
            UPDATE `asset_price_overrides`
            SET `account_id`=%s,
                `ticker`=%s,
                `effective_at`=%s,
                `price`=%s,
                `currency`=%s,
                `fx_rate_to_base`=%s,
                `force_override`=%s,
                `note`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["account_id"],
                normalized["ticker"],
                _parse_datetime_value(normalized["effective_at"]),
                normalized["price"],
                normalized["currency"],
                normalized["fx_rate_to_base"],
                1 if normalized["force_override"] else 0,
                normalized["note"],
                override_id,
                owner_id,
            ),
        )
        if not updated:
            return None
        return await self.get_asset_price_override(override_id, owner_id=owner_id)

    async def delete_asset_price_override(
        self,
        override_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> bool:
        deleted = await self._execute(
            "DELETE FROM `asset_price_overrides` WHERE `id`=%s AND `owner_id`=%s",
            (override_id, owner_id),
        )
        return bool(deleted)

    async def list_asset_fx_rates(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        from_currency: str | None = None,
        to_currency: str | None = None,
        limit: int = 365,
    ) -> List[Dict[str, Any]]:
        filters = ["`owner_id`=%s"]
        params: List[Any] = [owner_id]
        if date_from:
            filters.append("`snapshot_date` >= %s")
            params.append(date_from)
        if date_to:
            filters.append("`snapshot_date` <= %s")
            params.append(date_to)
        if from_currency:
            filters.append("`from_currency`=%s")
            params.append(str(from_currency).strip().upper())
        if to_currency:
            filters.append("`to_currency`=%s")
            params.append(str(to_currency).strip().upper())
        clean_limit = max(1, min(int(limit or 365), 5000))
        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `asset_fx_rates_daily`
            WHERE {' AND '.join(filters)}
            ORDER BY `snapshot_date` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_asset_fx_rate(row) for row in rows]

    async def get_asset_fx_rate(
        self,
        fx_rate_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `asset_fx_rates_daily`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (fx_rate_id, owner_id),
        )
        return _deserialize_asset_fx_rate(row)

    async def create_asset_fx_rate(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_asset_fx_rate_payload(payload)
        fx_rate_id = await self._execute_insert(
            """
            INSERT INTO `asset_fx_rates_daily`
                (`owner_id`, `snapshot_date`, `from_currency`, `to_currency`, `rate`, `source`, `note`)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                `rate`=VALUES(`rate`),
                `source`=VALUES(`source`),
                `note`=VALUES(`note`)
            """,
            (
                owner_id,
                normalized["snapshot_date"],
                normalized["from_currency"],
                normalized["to_currency"],
                normalized["rate"],
                normalized["source"],
                normalized["note"],
            ),
        )
        if not fx_rate_id:
            row = await self._fetchone(
                """
                SELECT *
                FROM `asset_fx_rates_daily`
                WHERE `owner_id`=%s AND `snapshot_date`=%s
                  AND `from_currency`=%s AND `to_currency`=%s
                LIMIT 1
                """,
                (
                    owner_id,
                    normalized["snapshot_date"],
                    normalized["from_currency"],
                    normalized["to_currency"],
                ),
            )
            return _deserialize_asset_fx_rate(row)
        fx_rate = await self.get_asset_fx_rate(fx_rate_id, owner_id=owner_id)
        if not fx_rate:
            raise RuntimeError("Asset FX rate was not persisted")
        return fx_rate

    async def update_asset_fx_rate(
        self,
        fx_rate_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_asset_fx_rate(fx_rate_id, owner_id=owner_id)
        if not existing:
            return None
        normalized = _normalize_asset_fx_rate_payload(payload, existing=existing)
        updated = await self._execute(
            """
            UPDATE `asset_fx_rates_daily`
            SET `snapshot_date`=%s,
                `from_currency`=%s,
                `to_currency`=%s,
                `rate`=%s,
                `source`=%s,
                `note`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["snapshot_date"],
                normalized["from_currency"],
                normalized["to_currency"],
                normalized["rate"],
                normalized["source"],
                normalized["note"],
                fx_rate_id,
                owner_id,
            ),
        )
        if not updated:
            return None
        return await self.get_asset_fx_rate(fx_rate_id, owner_id=owner_id)

    async def delete_asset_fx_rate(
        self,
        fx_rate_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> bool:
        deleted = await self._execute(
            "DELETE FROM `asset_fx_rates_daily` WHERE `id`=%s AND `owner_id`=%s",
            (fx_rate_id, owner_id),
        )
        return bool(deleted)

    async def list_asset_position_adjustments(
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
            filters.append("`event_date` >= %s")
            params.append(_parse_datetime_value(date_from))
        if date_to:
            filters.append("`event_date` <= %s")
            params.append(_parse_datetime_value(date_to))
        clean_limit = max(1, min(int(limit or 200), 5000))
        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `asset_position_adjustments`
            WHERE {' AND '.join(filters)}
            ORDER BY `event_date` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_asset_position_adjustment(row) for row in rows]

    async def get_asset_position_adjustment(
        self,
        adjustment_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `asset_position_adjustments`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (adjustment_id, owner_id),
        )
        return _deserialize_asset_position_adjustment(row)

    async def create_asset_position_adjustment(
        self,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_asset_position_adjustment_payload(payload)
        adjustment_id = await self._execute_insert(
            """
            INSERT INTO `asset_position_adjustments`
                (`owner_id`, `account_id`, `event_date`, `ticker`, `event_type`, `quantity_delta`,
                 `cost_basis_delta`, `cash_delta`, `currency`, `split_ratio`, `target_ticker`,
                 `target_display_name`, `target_market`, `target_asset_type`, `note`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                normalized["account_id"],
                _parse_datetime_value(normalized["event_date"]),
                normalized["ticker"],
                normalized["event_type"],
                normalized["quantity_delta"],
                normalized["cost_basis_delta"],
                normalized["cash_delta"],
                normalized["currency"],
                normalized["split_ratio"],
                normalized["target_ticker"],
                normalized["target_display_name"],
                normalized["target_market"],
                normalized["target_asset_type"],
                normalized["note"],
            ),
        )
        adjustment = await self.get_asset_position_adjustment(adjustment_id, owner_id=owner_id)
        if not adjustment:
            raise RuntimeError("Asset position adjustment was not persisted")
        return adjustment

    async def update_asset_position_adjustment(
        self,
        adjustment_id: int,
        payload: Dict[str, Any],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        existing = await self.get_asset_position_adjustment(adjustment_id, owner_id=owner_id)
        if not existing:
            return None
        normalized = _normalize_asset_position_adjustment_payload(payload, existing=existing)
        updated = await self._execute(
            """
            UPDATE `asset_position_adjustments`
            SET `account_id`=%s,
                `event_date`=%s,
                `ticker`=%s,
                `event_type`=%s,
                `quantity_delta`=%s,
                `cost_basis_delta`=%s,
                `cash_delta`=%s,
                `currency`=%s,
                `split_ratio`=%s,
                `target_ticker`=%s,
                `target_display_name`=%s,
                `target_market`=%s,
                `target_asset_type`=%s,
                `note`=%s
            WHERE `id`=%s AND `owner_id`=%s
            """,
            (
                normalized["account_id"],
                _parse_datetime_value(normalized["event_date"]),
                normalized["ticker"],
                normalized["event_type"],
                normalized["quantity_delta"],
                normalized["cost_basis_delta"],
                normalized["cash_delta"],
                normalized["currency"],
                normalized["split_ratio"],
                normalized["target_ticker"],
                normalized["target_display_name"],
                normalized["target_market"],
                normalized["target_asset_type"],
                normalized["note"],
                adjustment_id,
                owner_id,
            ),
        )
        if not updated:
            return None
        return await self.get_asset_position_adjustment(adjustment_id, owner_id=owner_id)

    async def delete_asset_position_adjustment(
        self,
        adjustment_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> bool:
        deleted = await self._execute(
            "DELETE FROM `asset_position_adjustments` WHERE `id`=%s AND `owner_id`=%s",
            (adjustment_id, owner_id),
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
