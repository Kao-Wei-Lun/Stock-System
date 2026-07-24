"""Account and ledger commands for the asset subsystem."""

from __future__ import annotations

from typing import Any, Dict, List


AUTO_TRADE_SETTLEMENT_SOURCE = "trade_settlement_auto"


def build_trade_settlement_note(
    trade_entry: Dict[str, Any],
    broker_account: Dict[str, Any],
    settlement_account: Dict[str, Any],
) -> str:
    ticker = str(trade_entry.get("ticker") or "").strip().upper() or "UNKNOWN"
    side = str(trade_entry.get("side") or "").strip().lower()
    action = "buy" if side == "buy" else "sell"
    return (
        f"Auto settlement sync for trade #{trade_entry.get('id')} {ticker} {action} "
        f"between {settlement_account.get('name') or settlement_account.get('id')} "
        f"and {broker_account.get('name') or broker_account.get('id')}."
    )


def build_trade_settlement_payloads(
    trade_entry: Dict[str, Any],
    broker_account: Dict[str, Any],
    settlement_account: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    amount = abs(float(trade_entry.get("net_amount") or 0.0))
    if amount <= 0:
        return {}

    currency = trade_entry.get("currency") or broker_account.get("base_currency") or "TWD"
    side = str(trade_entry.get("side") or "").strip().lower()
    common = {
        "flow_date": trade_entry.get("trade_date"),
        "amount": amount,
        "currency": currency,
        "fx_rate_to_base": float(trade_entry.get("fx_rate_to_base") or 1.0),
        "is_initial_balance": False,
        "source": AUTO_TRADE_SETTLEMENT_SOURCE,
        "import_batch_id": trade_entry.get("import_batch_id"),
        "linked_trade_id": trade_entry.get("id"),
        "note": build_trade_settlement_note(trade_entry, broker_account, settlement_account),
    }
    if side == "buy":
        return {
            "settlement_out": {
                **common,
                "account_id": settlement_account.get("id"),
                "flow_type": "transfer_out",
                "linked_trade_role": "settlement_out",
                "counterparty": broker_account.get("name"),
            },
            "broker_in": {
                **common,
                "account_id": broker_account.get("id"),
                "flow_type": "transfer_in",
                "linked_trade_role": "broker_in",
                "counterparty": settlement_account.get("name"),
            },
        }
    if side == "sell":
        return {
            "broker_out": {
                **common,
                "account_id": broker_account.get("id"),
                "flow_type": "transfer_out",
                "linked_trade_role": "broker_out",
                "counterparty": settlement_account.get("name"),
            },
            "settlement_in": {
                **common,
                "account_id": settlement_account.get("id"),
                "flow_type": "transfer_in",
                "linked_trade_role": "settlement_in",
                "counterparty": broker_account.get("name"),
            },
        }
    return {}


class AssetAccountLedgerCommands:
    """Mutating account/ledger workflows independent of the HTTP layer."""

    def __init__(self, repository: Any, *, owner_id: int) -> None:
        self.repository = repository
        self.owner_id = owner_id

    async def ensure_account_exists(self, account_id: int | None) -> Dict[str, Any] | None:
        if account_id is None:
            return None
        account = await self.repository.get_asset_account(account_id, owner_id=self.owner_id)
        if not account:
            raise ValueError(f"Asset account {account_id} does not exist")
        return account

    async def validate_account_settlement_config(
        self,
        payload: Dict[str, Any],
        *,
        account_id: int | None = None,
    ) -> None:
        settlement_account_id = payload.get("settlement_account_id")
        if settlement_account_id in ("", 0):
            settlement_account_id = None
        if settlement_account_id is not None:
            settlement_account_id = int(settlement_account_id)
            if account_id is not None and settlement_account_id == int(account_id):
                raise ValueError("Settlement account cannot point to the same asset account")
            await self.ensure_account_exists(settlement_account_id)
        if payload.get("auto_sync_trade_settlement") and settlement_account_id is None:
            raise ValueError("Settlement account is required when auto trade settlement sync is enabled")

    async def delete_trade_linked_cash_entries(self, trade_id: int) -> None:
        linked_entries = await self.repository.list_asset_cash_ledger_entries_by_linked_trade(
            trade_id,
            owner_id=self.owner_id,
        )
        for entry in linked_entries:
            await self.repository.delete_asset_cash_ledger_entry(
                int(entry.get("id")),
                owner_id=self.owner_id,
            )

    async def sync_trade_linked_cash_entries(self, trade_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        linked_entries = await self.repository.list_asset_cash_ledger_entries_by_linked_trade(
            int(trade_entry.get("id") or 0),
            owner_id=self.owner_id,
        )
        broker_account = await self.ensure_account_exists(int(trade_entry.get("account_id")))
        auto_enabled = bool(broker_account and broker_account.get("auto_sync_trade_settlement"))
        settlement_account_id = int((broker_account or {}).get("settlement_account_id") or 0)

        if not auto_enabled or not settlement_account_id or bool(trade_entry.get("is_initial_balance")):
            for entry in linked_entries:
                await self.repository.delete_asset_cash_ledger_entry(
                    int(entry.get("id")),
                    owner_id=self.owner_id,
                )
            return []

        settlement_account = await self.ensure_account_exists(settlement_account_id)
        if int(settlement_account.get("id") or 0) == int(broker_account.get("id") or 0):
            raise ValueError("Settlement account cannot point to the same brokerage account")

        payloads = build_trade_settlement_payloads(trade_entry, broker_account, settlement_account)
        expected_roles = set(payloads)
        existing_by_role = {str(item.get("linked_trade_role") or ""): item for item in linked_entries}
        synced_entries: List[Dict[str, Any]] = []
        for role, payload in payloads.items():
            existing = existing_by_role.get(role)
            if existing:
                synced = await self.repository.update_asset_cash_ledger_entry(
                    int(existing.get("id")),
                    payload,
                    owner_id=self.owner_id,
                )
            else:
                synced = await self.repository.create_asset_cash_ledger_entry(
                    payload,
                    owner_id=self.owner_id,
                )
            synced_entries.append(synced)

        for entry in linked_entries:
            if str(entry.get("linked_trade_role") or "") not in expected_roles:
                await self.repository.delete_asset_cash_ledger_entry(
                    int(entry.get("id")),
                    owner_id=self.owner_id,
                )
        return synced_entries

    async def create_trade_entry_with_settlement_sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        trade_entry = await self.repository.create_asset_trade_entry(payload, owner_id=self.owner_id)
        try:
            await self.sync_trade_linked_cash_entries(trade_entry)
        except Exception:  # noqa: BLE001 - remove half-created trade state
            await self.repository.delete_asset_trade_entry(
                int(trade_entry.get("id")),
                owner_id=self.owner_id,
            )
            raise
        return trade_entry
