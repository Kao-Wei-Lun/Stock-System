import copy
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest

import main


@pytest.mark.anyio
async def test_complete_asset_loader_reads_records_beyond_legacy_snapshot_limit():
    source_rows = [{"id": index} for index in range(5107)]
    requested_offsets = []

    async def fetch_page(*, owner_id, limit, offset):
        assert owner_id == 1
        requested_offsets.append(offset)
        return source_rows[offset:offset + limit]

    rows = await main.assets._load_all_asset_rows(fetch_page)

    assert len(rows) == 5107
    assert rows[-1]["id"] == 5106
    assert requested_offsets == [0, 1000, 2000, 3000, 4000, 5000]


@pytest.fixture
def asset_store(monkeypatch):
    store = {
        "next_account_id": 1,
        "next_cash_id": 1,
        "next_trade_id": 1,
        "next_reconciliation_id": 1,
        "next_price_override_id": 1,
        "next_fx_rate_id": 1,
        "next_adjustment_id": 1,
        "next_import_batch_id": 1,
        "accounts": {},
        "cash_entries": {},
        "trade_entries": {},
        "reconciliation_entries": {},
        "price_overrides": {},
        "fx_rates": {},
        "adjustments": {},
        "import_batches": {},
        "price_histories": {},
        "journal_entries": [],
        "quotes": {
            "2330.TW": {
                "ticker": "2330.TW",
                "source": "cache",
                "quote_type": "delayed_snapshot",
                "is_delayed": True,
                "currency": "TWD",
                "price": 120,
                "quote_timestamp": "2026-04-18T09:00:00+00:00",
            }
        },
        "positions_current": [],
        "valuations_current": [],
    }

    def clone(value):
        return copy.deepcopy(value)

    async def list_asset_accounts(owner_id=1):
        items = list(store["accounts"].values())
        items.sort(key=lambda item: (item.get("sort_order", 0), item["id"]))
        return clone(items)

    async def get_asset_account(account_id, owner_id=1):
        item = store["accounts"].get(account_id)
        return clone(item) if item else None

    async def create_asset_account(payload, owner_id=1):
        account_id = store["next_account_id"]
        store["next_account_id"] += 1
        item = {
            "id": account_id,
            "owner_id": owner_id,
            "name": payload["name"],
            "institution": payload.get("institution"),
            "account_type": payload.get("account_type") or "brokerage",
            "base_currency": payload.get("base_currency") or "TWD",
            "settlement_account_id": payload.get("settlement_account_id"),
            "auto_sync_trade_settlement": bool(payload.get("auto_sync_trade_settlement", False)),
            "include_in_total": bool(payload.get("include_in_total", True)),
            "sort_order": int(payload.get("sort_order") or 0),
            "notes": payload.get("notes"),
            "created_at": "2026-04-18T08:00:00+00:00",
            "updated_at": "2026-04-18T08:00:00+00:00",
        }
        store["accounts"][account_id] = item
        return clone(item)

    async def update_asset_account(account_id, payload, owner_id=1):
        existing = store["accounts"].get(account_id)
        if not existing:
            return None
        existing.update(payload)
        existing["updated_at"] = "2026-04-18T08:10:00+00:00"
        return clone(existing)

    async def delete_asset_account(account_id, owner_id=1):
        return store["accounts"].pop(account_id, None) is not None

    async def find_asset_trade_import_keys(import_keys, owner_id=1):
        requested = set(import_keys)
        return {
            item["import_key"]: item["id"]
            for item in store["trade_entries"].values()
            if item.get("import_key") in requested
        }

    async def find_asset_cash_import_keys(import_keys, owner_id=1):
        requested = set(import_keys)
        return {
            item["import_key"]: item["id"]
            for item in store["cash_entries"].values()
            if item.get("import_key") in requested
        }

    async def create_asset_import_batch(payload, owner_id=1):
        batch_id = store["next_import_batch_id"]
        store["next_import_batch_id"] += 1
        item = {
            "id": batch_id,
            "owner_id": owner_id,
            "import_type": payload.get("import_type"),
            "source_name": payload.get("source_name"),
            "status": payload.get("status") or "pending",
            "row_count": int(payload.get("row_count") or 0),
            "created_count": int(payload.get("created_count") or 0),
            "skipped_count": int(payload.get("skipped_count") or 0),
            "error_count": int(payload.get("error_count") or 0),
            "metadata": clone(payload.get("metadata") or {}),
            "error_message": payload.get("error_message"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "committed_at": None,
            "rolled_back_at": None,
        }
        store["import_batches"][batch_id] = item
        return clone(item)

    async def get_asset_import_batch(batch_id, owner_id=1):
        item = store["import_batches"].get(batch_id)
        return clone(item) if item and item.get("owner_id") == owner_id else None

    async def list_asset_import_batches(owner_id=1, limit=50, offset=0):
        items = [item for item in store["import_batches"].values() if item.get("owner_id") == owner_id]
        items.sort(key=lambda item: item["id"], reverse=True)
        return clone(items[offset:offset + limit])

    async def finalize_asset_import_batch(batch_id, payload, owner_id=1):
        item = store["import_batches"].get(batch_id)
        if not item or item.get("owner_id") != owner_id:
            return None
        for key in ("status", "row_count", "created_count", "skipped_count", "error_count", "metadata", "error_message"):
            if key in payload:
                item[key] = clone(payload[key])
        if item.get("status") == "committed":
            item["committed_at"] = datetime.now(timezone.utc).isoformat()
        if item.get("status") == "rolled_back":
            item["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        return clone(item)

    async def delete_asset_import_batch_entries(batch_id, owner_id=1):
        cash_ids = [key for key, item in store["cash_entries"].items() if item.get("owner_id") == owner_id and item.get("import_batch_id") == batch_id]
        trade_ids = [key for key, item in store["trade_entries"].items() if item.get("owner_id") == owner_id and item.get("import_batch_id") == batch_id]
        for key in cash_ids:
            del store["cash_entries"][key]
        for key in trade_ids:
            del store["trade_entries"][key]
        return {"cash_count": len(cash_ids), "trade_count": len(trade_ids)}

    @asynccontextmanager
    async def transaction():
        before = clone(store)
        try:
            yield
        except BaseException:
            store.clear()
            store.update(before)
            raise

    async def list_asset_cash_ledger_entries(owner_id=1, account_id=None, date_from=None, date_to=None, limit=200, offset=0):
        items = list(store["cash_entries"].values())
        if account_id is not None:
            items = [item for item in items if item["account_id"] == account_id]
        if date_from:
            items = [item for item in items if item["flow_date"] >= date_from]
        if date_to:
            items = [item for item in items if item["flow_date"] <= date_to]
        items.sort(key=lambda item: (item["flow_date"], item["id"]), reverse=True)
        return clone(items[offset:offset + limit])

    async def get_asset_cash_ledger_entry(entry_id, owner_id=1):
        item = store["cash_entries"].get(entry_id)
        return clone(item) if item else None

    async def create_asset_cash_ledger_entry(payload, owner_id=1):
        entry_id = store["next_cash_id"]
        store["next_cash_id"] += 1
        amount = float(payload["amount"])
        fx_rate_to_base = float(payload.get("fx_rate_to_base") or 1)
        item = {
            "id": entry_id,
            "owner_id": owner_id,
            "account_id": payload["account_id"],
            "flow_date": payload["flow_date"],
            "flow_type": payload["flow_type"],
            "amount": amount,
            "currency": payload.get("currency") or "TWD",
            "fx_rate_to_base": fx_rate_to_base,
            "is_initial_balance": bool(payload.get("is_initial_balance", False)),
            "source": payload.get("source") or "manual",
            "import_key": payload.get("import_key"),
            "import_batch_id": payload.get("import_batch_id"),
            "linked_trade_id": payload.get("linked_trade_id"),
            "linked_trade_role": payload.get("linked_trade_role"),
            "counterparty": payload.get("counterparty"),
            "note": payload.get("note"),
            "created_at": "2026-04-18T08:20:00+00:00",
            "updated_at": "2026-04-18T08:20:00+00:00",
        }
        store["cash_entries"][entry_id] = item
        return clone(item)

    async def update_asset_cash_ledger_entry(entry_id, payload, owner_id=1):
        existing = store["cash_entries"].get(entry_id)
        if not existing:
            return None
        existing.update(payload)
        existing["updated_at"] = "2026-04-18T08:25:00+00:00"
        return clone(existing)

    async def delete_asset_cash_ledger_entry(entry_id, owner_id=1):
        return store["cash_entries"].pop(entry_id, None) is not None

    async def list_asset_cash_ledger_entries_by_linked_trade(linked_trade_id, owner_id=1):
        items = [
            item
            for item in store["cash_entries"].values()
            if int(item.get("linked_trade_id") or 0) == int(linked_trade_id)
        ]
        items.sort(key=lambda item: item["id"])
        return clone(items)

    async def list_asset_trade_entries(owner_id=1, account_id=None, ticker=None, date_from=None, date_to=None, limit=200, offset=0):
        items = list(store["trade_entries"].values())
        if account_id is not None:
            items = [item for item in items if item["account_id"] == account_id]
        if ticker:
            items = [item for item in items if item["ticker"] == ticker]
        if date_from:
            items = [item for item in items if item["trade_date"] >= date_from]
        if date_to:
            items = [item for item in items if item["trade_date"] <= date_to]
        items.sort(key=lambda item: (item["trade_date"], item["id"]), reverse=True)
        return clone(items[offset:offset + limit])

    async def get_asset_trade_entry(entry_id, owner_id=1):
        item = store["trade_entries"].get(entry_id)
        return clone(item) if item else None

    async def create_asset_trade_entry(payload, owner_id=1):
        entry_id = store["next_trade_id"]
        store["next_trade_id"] += 1
        quantity = float(payload["quantity"])
        price = float(payload["price"])
        gross_amount = float(payload["gross_amount"]) if payload.get("gross_amount") not in (None, "") else quantity * price
        fee_amount = float(payload.get("fee_amount") or 0)
        tax_amount = float(payload.get("tax_amount") or 0)
        fx_rate_to_base = float(payload.get("fx_rate_to_base") or 1)
        item = {
            "id": entry_id,
            "owner_id": owner_id,
            "account_id": payload["account_id"],
            "trade_date": payload["trade_date"],
            "ticker": payload["ticker"],
            "display_name": payload.get("display_name"),
            "market": payload.get("market"),
            "asset_type": payload.get("asset_type") or "stock",
            "currency": payload.get("currency") or "TWD",
            "side": payload["side"],
            "quantity": quantity,
            "price": price,
            "gross_amount": gross_amount,
            "fee_amount": fee_amount,
            "tax_amount": tax_amount,
            "net_amount": float(payload["net_amount"]) if payload.get("net_amount") not in (None, "") else (gross_amount + fee_amount + tax_amount),
            "fx_rate_to_base": fx_rate_to_base,
            "is_initial_balance": bool(payload.get("is_initial_balance", False)),
            "source": payload.get("source") or "manual",
            "import_key": payload.get("import_key"),
            "import_batch_id": payload.get("import_batch_id"),
            "note": payload.get("note"),
            "created_at": "2026-04-18T08:30:00+00:00",
            "updated_at": "2026-04-18T08:30:00+00:00",
        }
        store["trade_entries"][entry_id] = item
        return clone(item)

    async def update_asset_trade_entry(entry_id, payload, owner_id=1):
        existing = store["trade_entries"].get(entry_id)
        if not existing:
            return None
        existing.update(payload)
        quantity = float(existing["quantity"])
        price = float(existing["price"])
        gross_amount = quantity * price
        fee_amount = float(existing.get("fee_amount") or 0)
        tax_amount = float(existing.get("tax_amount") or 0)
        side = existing.get("side") or "buy"
        existing["gross_amount"] = gross_amount
        existing["net_amount"] = gross_amount + fee_amount + tax_amount if side == "buy" else gross_amount - fee_amount - tax_amount
        existing["updated_at"] = "2026-04-18T08:35:00+00:00"
        return clone(existing)

    async def delete_asset_trade_entry(entry_id, owner_id=1):
        return store["trade_entries"].pop(entry_id, None) is not None

    async def list_asset_reconciliation_snapshots(owner_id=1, account_id=None, limit=200, offset=0):
        items = list(store["reconciliation_entries"].values())
        if account_id is not None:
            items = [item for item in items if item["account_id"] == account_id]
        items.sort(key=lambda item: (item["snapshot_date"], item["id"]), reverse=True)
        return clone(items[offset:offset + limit])

    async def get_asset_reconciliation_snapshot(snapshot_id, owner_id=1):
        item = store["reconciliation_entries"].get(snapshot_id)
        return clone(item) if item else None

    async def create_asset_reconciliation_snapshot(payload, owner_id=1):
        snapshot_id = store["next_reconciliation_id"]
        store["next_reconciliation_id"] += 1
        item = {
            "id": snapshot_id,
            "owner_id": owner_id,
            "account_id": payload["account_id"],
            "snapshot_date": payload["snapshot_date"],
            "cash_actual": payload.get("cash_actual"),
            "cash_system": payload.get("cash_system"),
            "market_value_actual": payload.get("market_value_actual"),
            "market_value_system": payload.get("market_value_system"),
            "positions_payload": clone(payload.get("positions_payload") or []),
            "note": payload.get("note"),
            "created_at": "2026-04-18T08:40:00+00:00",
        }
        store["reconciliation_entries"][snapshot_id] = item
        return clone(item)

    async def delete_asset_reconciliation_snapshot(snapshot_id, owner_id=1):
        return store["reconciliation_entries"].pop(snapshot_id, None) is not None

    async def list_asset_price_overrides(owner_id=1, account_id=None, ticker=None, limit=200, offset=0):
        items = list(store["price_overrides"].values())
        if account_id is not None:
            items = [item for item in items if item["account_id"] == account_id]
        if ticker:
            items = [item for item in items if item["ticker"] == ticker]
        items.sort(key=lambda item: (item["effective_at"], item["id"]), reverse=True)
        return clone(items[offset:offset + limit])

    async def get_asset_price_override(override_id, owner_id=1):
        item = store["price_overrides"].get(override_id)
        return clone(item) if item else None

    async def create_asset_price_override(payload, owner_id=1):
        override_id = store["next_price_override_id"]
        store["next_price_override_id"] += 1
        item = {
            "id": override_id,
            "owner_id": owner_id,
            "account_id": payload.get("account_id"),
            "ticker": payload["ticker"],
            "effective_at": payload["effective_at"],
            "price": payload["price"],
            "currency": payload.get("currency") or "TWD",
            "fx_rate_to_base": payload.get("fx_rate_to_base"),
            "force_override": bool(payload.get("force_override", False)),
            "note": payload.get("note"),
            "created_at": "2026-04-18T08:42:00+00:00",
            "updated_at": "2026-04-18T08:42:00+00:00",
        }
        store["price_overrides"][override_id] = item
        return clone(item)

    async def update_asset_price_override(override_id, payload, owner_id=1):
        existing = store["price_overrides"].get(override_id)
        if not existing:
            return None
        existing.update(payload)
        existing["updated_at"] = "2026-04-18T08:43:00+00:00"
        return clone(existing)

    async def delete_asset_price_override(override_id, owner_id=1):
        return store["price_overrides"].pop(override_id, None) is not None

    async def list_asset_fx_rates(owner_id=1, date_from=None, date_to=None, from_currency=None, to_currency=None, limit=365, offset=0):
        items = list(store["fx_rates"].values())
        if date_from:
            items = [item for item in items if item["snapshot_date"] >= date_from]
        if date_to:
            items = [item for item in items if item["snapshot_date"] <= date_to]
        if from_currency:
            items = [item for item in items if item["from_currency"] == from_currency]
        if to_currency:
            items = [item for item in items if item["to_currency"] == to_currency]
        items.sort(key=lambda item: (item["snapshot_date"], item["id"]), reverse=True)
        return clone(items[offset:offset + limit])

    async def get_asset_fx_rate(fx_rate_id, owner_id=1):
        item = store["fx_rates"].get(fx_rate_id)
        return clone(item) if item else None

    async def create_asset_fx_rate(payload, owner_id=1):
        fx_rate_id = store["next_fx_rate_id"]
        store["next_fx_rate_id"] += 1
        item = {
            "id": fx_rate_id,
            "owner_id": owner_id,
            "snapshot_date": payload["snapshot_date"],
            "from_currency": payload["from_currency"],
            "to_currency": payload["to_currency"],
            "rate": payload["rate"],
            "source": payload.get("source") or "manual",
            "note": payload.get("note"),
            "created_at": "2026-04-18T08:44:00+00:00",
            "updated_at": "2026-04-18T08:44:00+00:00",
        }
        store["fx_rates"][fx_rate_id] = item
        return clone(item)

    async def update_asset_fx_rate(fx_rate_id, payload, owner_id=1):
        existing = store["fx_rates"].get(fx_rate_id)
        if not existing:
            return None
        existing.update(payload)
        existing["updated_at"] = "2026-04-18T08:45:00+00:00"
        return clone(existing)

    async def delete_asset_fx_rate(fx_rate_id, owner_id=1):
        return store["fx_rates"].pop(fx_rate_id, None) is not None

    async def list_asset_position_adjustments(owner_id=1, account_id=None, ticker=None, date_from=None, date_to=None, limit=200, offset=0):
        items = list(store["adjustments"].values())
        if account_id is not None:
            items = [item for item in items if item["account_id"] == account_id]
        if ticker:
            items = [item for item in items if item["ticker"] == ticker]
        if date_from:
            items = [item for item in items if item["event_date"] >= date_from]
        if date_to:
            items = [item for item in items if item["event_date"] <= date_to]
        items.sort(key=lambda item: (item["event_date"], item["id"]), reverse=True)
        return clone(items[offset:offset + limit])

    async def get_asset_position_adjustment(adjustment_id, owner_id=1):
        item = store["adjustments"].get(adjustment_id)
        return clone(item) if item else None

    async def create_asset_position_adjustment(payload, owner_id=1):
        adjustment_id = store["next_adjustment_id"]
        store["next_adjustment_id"] += 1
        item = {
            "id": adjustment_id,
            "owner_id": owner_id,
            "account_id": payload["account_id"],
            "event_date": payload["event_date"],
            "ticker": payload["ticker"],
            "event_type": payload.get("event_type") or "adjustment",
            "quantity_delta": payload.get("quantity_delta"),
            "cost_basis_delta": payload.get("cost_basis_delta"),
            "cash_delta": payload.get("cash_delta"),
            "currency": payload.get("currency"),
            "split_ratio": payload.get("split_ratio"),
            "target_ticker": payload.get("target_ticker"),
            "target_display_name": payload.get("target_display_name"),
            "target_market": payload.get("target_market"),
            "target_asset_type": payload.get("target_asset_type"),
            "note": payload.get("note"),
            "created_at": "2026-04-18T08:46:00+00:00",
            "updated_at": "2026-04-18T08:46:00+00:00",
        }
        store["adjustments"][adjustment_id] = item
        return clone(item)

    async def update_asset_position_adjustment(adjustment_id, payload, owner_id=1):
        existing = store["adjustments"].get(adjustment_id)
        if not existing:
            return None
        existing.update(payload)
        existing["updated_at"] = "2026-04-18T08:47:00+00:00"
        return clone(existing)

    async def delete_asset_position_adjustment(adjustment_id, owner_id=1):
        return store["adjustments"].pop(adjustment_id, None) is not None

    async def get_ohlcv_range(ticker, start_date, end_date, interval="1d"):
        items = list(store["price_histories"].get(ticker, []))
        filtered = [
            item
            for item in items
            if (not start_date or str(item.get("date") or "") >= str(start_date))
            and (not end_date or str(item.get("date") or "") <= str(end_date))
        ]
        return clone(filtered)

    async def list_trade_journal_entries(owner_id=1, ticker=None, market=None, strategy_code=None, tag=None, search=None, limit=50):
        items = list(store["journal_entries"])
        if ticker:
            items = [item for item in items if item.get("ticker") == ticker]
        if market:
            items = [item for item in items if item.get("market") == market]
        if strategy_code:
            items = [item for item in items if item.get("strategy_code") == strategy_code]
        if tag:
            items = [item for item in items if tag in (item.get("tags") or [])]
        if search:
            needle = str(search).lower()
            items = [
                item
                for item in items
                if needle in str(item.get("ticker") or "").lower()
                or needle in str(item.get("note") or "").lower()
            ]
        items.sort(key=lambda item: (item.get("entry_time") or "", item.get("id") or 0), reverse=True)
        return clone(items[:limit])

    async def get_market_quote(ticker):
        return clone(store["quotes"].get(ticker))

    async def replace_asset_positions_current(owner_id, positions):
        store["positions_current"] = clone(positions)

    async def replace_asset_valuations_current(owner_id, valuations):
        store["valuations_current"] = clone(valuations)

    monkeypatch.setattr(main.db, "list_asset_accounts", list_asset_accounts)
    monkeypatch.setattr(main.db, "get_asset_account", get_asset_account)
    monkeypatch.setattr(main.db, "create_asset_account", create_asset_account)
    monkeypatch.setattr(main.db, "update_asset_account", update_asset_account)
    monkeypatch.setattr(main.db, "delete_asset_account", delete_asset_account)
    monkeypatch.setattr(main.db, "find_asset_trade_import_keys", find_asset_trade_import_keys)
    monkeypatch.setattr(main.db, "find_asset_cash_import_keys", find_asset_cash_import_keys)
    monkeypatch.setattr(main.db, "create_asset_import_batch", create_asset_import_batch)
    monkeypatch.setattr(main.db, "get_asset_import_batch", get_asset_import_batch)
    monkeypatch.setattr(main.db, "list_asset_import_batches", list_asset_import_batches)
    monkeypatch.setattr(main.db, "finalize_asset_import_batch", finalize_asset_import_batch)
    monkeypatch.setattr(main.db, "delete_asset_import_batch_entries", delete_asset_import_batch_entries)
    monkeypatch.setattr(main.db, "transaction", transaction)
    monkeypatch.setattr(main.db, "list_asset_cash_ledger_entries", list_asset_cash_ledger_entries)
    monkeypatch.setattr(main.db, "get_asset_cash_ledger_entry", get_asset_cash_ledger_entry)
    monkeypatch.setattr(main.db, "create_asset_cash_ledger_entry", create_asset_cash_ledger_entry)
    monkeypatch.setattr(main.db, "update_asset_cash_ledger_entry", update_asset_cash_ledger_entry)
    monkeypatch.setattr(main.db, "delete_asset_cash_ledger_entry", delete_asset_cash_ledger_entry)
    monkeypatch.setattr(main.db, "list_asset_cash_ledger_entries_by_linked_trade", list_asset_cash_ledger_entries_by_linked_trade)
    monkeypatch.setattr(main.db, "list_asset_trade_entries", list_asset_trade_entries)
    monkeypatch.setattr(main.db, "get_asset_trade_entry", get_asset_trade_entry)
    monkeypatch.setattr(main.db, "create_asset_trade_entry", create_asset_trade_entry)
    monkeypatch.setattr(main.db, "update_asset_trade_entry", update_asset_trade_entry)
    monkeypatch.setattr(main.db, "delete_asset_trade_entry", delete_asset_trade_entry)
    monkeypatch.setattr(main.db, "list_asset_reconciliation_snapshots", list_asset_reconciliation_snapshots)
    monkeypatch.setattr(main.db, "get_asset_reconciliation_snapshot", get_asset_reconciliation_snapshot)
    monkeypatch.setattr(main.db, "create_asset_reconciliation_snapshot", create_asset_reconciliation_snapshot)
    monkeypatch.setattr(main.db, "delete_asset_reconciliation_snapshot", delete_asset_reconciliation_snapshot)
    monkeypatch.setattr(main.db, "list_asset_price_overrides", list_asset_price_overrides)
    monkeypatch.setattr(main.db, "get_asset_price_override", get_asset_price_override)
    monkeypatch.setattr(main.db, "create_asset_price_override", create_asset_price_override)
    monkeypatch.setattr(main.db, "update_asset_price_override", update_asset_price_override)
    monkeypatch.setattr(main.db, "delete_asset_price_override", delete_asset_price_override)
    monkeypatch.setattr(main.db, "list_asset_fx_rates", list_asset_fx_rates)
    monkeypatch.setattr(main.db, "get_asset_fx_rate", get_asset_fx_rate)
    monkeypatch.setattr(main.db, "create_asset_fx_rate", create_asset_fx_rate)
    monkeypatch.setattr(main.db, "update_asset_fx_rate", update_asset_fx_rate)
    monkeypatch.setattr(main.db, "delete_asset_fx_rate", delete_asset_fx_rate)
    monkeypatch.setattr(main.db, "list_asset_position_adjustments", list_asset_position_adjustments)
    monkeypatch.setattr(main.db, "get_asset_position_adjustment", get_asset_position_adjustment)
    monkeypatch.setattr(main.db, "create_asset_position_adjustment", create_asset_position_adjustment)
    monkeypatch.setattr(main.db, "update_asset_position_adjustment", update_asset_position_adjustment)
    monkeypatch.setattr(main.db, "delete_asset_position_adjustment", delete_asset_position_adjustment)
    monkeypatch.setattr(main.db, "get_ohlcv_range", get_ohlcv_range)
    monkeypatch.setattr(main.db, "list_trade_journal_entries", list_trade_journal_entries)
    monkeypatch.setattr(main.db, "get_market_quote", get_market_quote)
    monkeypatch.setattr(main.db, "replace_asset_positions_current", replace_asset_positions_current)
    monkeypatch.setattr(main.db, "replace_asset_valuations_current", replace_asset_valuations_current)
    monkeypatch.setattr(main.assets, "_fetch_and_store_quote_snapshot", None)
    monkeypatch.setattr(main.assets, "_latest_public_fx_provider", None)

    return store


def test_asset_routes_crud_and_summary_snapshot(client, asset_store):
    account_response = client.post(
        "/api/assets/accounts",
        json={
            "name": "Main Broker",
            "institution": "Manual",
            "account_type": "brokerage",
            "base_currency": "TWD",
            "include_in_total": True,
        },
    )
    assert account_response.status_code == 200
    account = account_response.json()

    excluded_account_response = client.post(
        "/api/assets/accounts",
        json={
            "name": "Side Pocket",
            "account_type": "cash",
            "base_currency": "TWD",
            "include_in_total": False,
        },
    )
    assert excluded_account_response.status_code == 200
    excluded_account = excluded_account_response.json()

    cash_response = client.post(
        "/api/assets/cash-ledger",
        json={
            "account_id": account["id"],
            "flow_date": "2026-04-01T09:00:00",
            "flow_type": "deposit",
            "amount": 100000,
            "currency": "TWD",
            "fx_rate_to_base": 1,
        },
    )
    assert cash_response.status_code == 200

    excluded_cash_response = client.post(
        "/api/assets/cash-ledger",
        json={
            "account_id": excluded_account["id"],
            "flow_date": "2026-04-02T09:00:00",
            "flow_type": "deposit",
            "amount": 5000,
            "currency": "TWD",
            "fx_rate_to_base": 1,
        },
    )
    assert excluded_cash_response.status_code == 200

    trade_response = client.post(
        "/api/assets/trades",
        json={
            "account_id": account["id"],
            "trade_date": "2026-04-03T09:00:00",
            "ticker": "2330",
            "display_name": "TSMC",
            "market": "TW",
            "asset_type": "stock",
            "currency": "TWD",
            "side": "buy",
            "quantity": 10,
            "price": 100,
            "fee_amount": 10,
            "tax_amount": 0,
            "fx_rate_to_base": 1,
        },
    )
    assert trade_response.status_code == 200
    assert trade_response.json()["ticker"] == "2330.TW"

    trades_list_response = client.get("/api/assets/trades?ticker=2330")
    assert trades_list_response.status_code == 200
    assert trades_list_response.json()["items"][0]["ticker"] == "2330.TW"

    summary_response = client.get("/api/assets/summary/current?refresh=false")
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["summary"]["cash_total_base"] == 98990
    assert summary_payload["summary"]["market_value_total_base"] == 1200
    assert summary_payload["summary"]["total_asset_value_base"] == 100190
    assert summary_payload["summary"]["quote_gap_count"] == 0

    allocation_response = client.get("/api/assets/allocation/current?refresh=false&group_by=market")
    assert allocation_response.status_code == 200
    assert allocation_response.json()["allocation"]["items"][0]["key"] == "TW"
    assert allocation_response.json()["allocation"]["items"][0]["value_base"] == 1200

    contributors_response = client.get("/api/assets/contributors/current?refresh=false&limit=5")
    assert contributors_response.status_code == 200
    assert contributors_response.json()["top_gainers"][0]["ticker"] == "2330.TW"

    reconciliation_response = client.post(
        "/api/assets/reconciliation?refresh=false",
        json={
            "account_id": account["id"],
            "snapshot_date": "2026-04-18T10:00:00",
            "cash_actual": 99000,
            "market_value_actual": 1300,
            "note": "Broker app close",
        },
    )
    assert reconciliation_response.status_code == 200
    reconciliation_payload = reconciliation_response.json()
    assert reconciliation_payload["cash_system"] == 98990
    assert reconciliation_payload["market_value_system"] == 1200
    assert reconciliation_payload["positions_payload"][0]["ticker"] == "2330.TW"

    reconciliation_list_response = client.get("/api/assets/reconciliation?limit=5")
    assert reconciliation_list_response.status_code == 200
    assert reconciliation_list_response.json()["items"][0]["id"] == reconciliation_payload["id"]

    portfolio_response = client.get("/api/assets/portfolio/current?refresh=false")
    assert portfolio_response.status_code == 200
    portfolio_payload = portfolio_response.json()
    assert portfolio_payload["summary"]["cash_total_base"] == 98990
    assert portfolio_payload["summary"]["current_position_cost_base"] == 1010
    assert portfolio_payload["reconciliation"]["summary"]["gap_account_count"] == 1
    assert portfolio_payload["reconciliation"]["items"][0]["total_difference"] == 110
    assert portfolio_payload["currency_allocation"][0]["currency"] == "TWD"
    assert "reconciliation_gaps_present" in portfolio_payload["data_quality_flags"]
    assert "calculation_warnings" in portfolio_payload
    assert "data_quality_flags" in portfolio_payload
    assert portfolio_payload["calculation_metadata"]["current_position_cost"]["status"] == "computed"
    assert portfolio_payload["calculation_metadata"]["currency_allocation"]["status"] == "computed"
    assert portfolio_payload["data_quality_summary"]["severity"] == "warning"

    performance_response = client.get("/api/assets/performance?refresh=false&range=30d")
    assert performance_response.status_code == 200
    performance_payload = performance_response.json()
    assert "start_value_base" in performance_payload["summary"]
    assert "daily_nav_change_base" in performance_payload["summary"]
    assert "daily_metric_type" in performance_payload["summary"]
    assert "calculation_warnings" in performance_payload
    assert "data_quality_flags" in performance_payload
    assert "calculation_metadata" in performance_payload
    assert "data_quality_summary" in performance_payload
    assert "daily_nav_change" in performance_payload["calculation_metadata"]

    delete_reconciliation_response = client.delete(f"/api/assets/reconciliation/{reconciliation_payload['id']}")
    assert delete_reconciliation_response.status_code == 200

    assert len(asset_store["positions_current"]) == 1
    assert len(asset_store["valuations_current"]) == 1


def test_asset_routes_validate_unknown_account(client, asset_store):
    response = client.post(
        "/api/assets/trades",
        json={
            "account_id": 999,
            "trade_date": "2026-04-03T09:00:00",
            "ticker": "AAPL",
            "currency": "USD",
            "side": "buy",
            "quantity": 1,
            "price": 100,
        },
    )

    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]


def test_asset_routes_auto_sync_trade_settlement_entries(client, asset_store):
    settlement_response = client.post(
        "/api/assets/accounts",
        json={
            "name": "Settlement Bank",
            "account_type": "bank",
            "base_currency": "TWD",
            "include_in_total": True,
        },
    )
    assert settlement_response.status_code == 200
    settlement_account = settlement_response.json()

    broker_response = client.post(
        "/api/assets/accounts",
        json={
            "name": "Main Broker",
            "account_type": "brokerage",
            "base_currency": "TWD",
            "settlement_account_id": settlement_account["id"],
            "auto_sync_trade_settlement": True,
            "include_in_total": True,
        },
    )
    assert broker_response.status_code == 200
    broker_account = broker_response.json()
    assert broker_account["settlement_account_id"] == settlement_account["id"]
    assert broker_account["auto_sync_trade_settlement"] is True

    trade_response = client.post(
        "/api/assets/trades",
        json={
            "account_id": broker_account["id"],
            "trade_date": "2026-04-03T09:00:00",
            "ticker": "2330",
            "display_name": "TSMC",
            "market": "TW",
            "asset_type": "stock",
            "currency": "TWD",
            "side": "buy",
            "quantity": 2,
            "price": 100,
            "fee_amount": 10,
            "tax_amount": 0,
            "fx_rate_to_base": 1,
        },
    )
    assert trade_response.status_code == 200
    trade_payload = trade_response.json()

    linked_cash_entries = [
        item for item in asset_store["cash_entries"].values()
        if int(item.get("linked_trade_id") or 0) == int(trade_payload["id"])
    ]
    assert len(linked_cash_entries) == 2
    linked_roles = {item["linked_trade_role"]: item for item in linked_cash_entries}
    assert linked_roles["settlement_out"]["account_id"] == settlement_account["id"]
    assert linked_roles["settlement_out"]["flow_type"] == "transfer_out"
    assert linked_roles["settlement_out"]["amount"] == 210
    assert linked_roles["settlement_out"]["source"] == "trade_settlement_auto"
    assert linked_roles["broker_in"]["account_id"] == broker_account["id"]
    assert linked_roles["broker_in"]["flow_type"] == "transfer_in"
    assert linked_roles["broker_in"]["amount"] == 210

    update_response = client.patch(
        f"/api/assets/trades/{trade_payload['id']}",
        json={
            "side": "sell",
            "price": 120,
            "fee_amount": 5,
            "tax_amount": 0,
        },
    )
    assert update_response.status_code == 200

    updated_linked_cash_entries = [
        item for item in asset_store["cash_entries"].values()
        if int(item.get("linked_trade_id") or 0) == int(trade_payload["id"])
    ]
    assert len(updated_linked_cash_entries) == 2
    updated_roles = {item["linked_trade_role"]: item for item in updated_linked_cash_entries}
    assert updated_roles["broker_out"]["flow_type"] == "transfer_out"
    assert updated_roles["broker_out"]["account_id"] == broker_account["id"]
    assert updated_roles["broker_out"]["amount"] == 235
    assert updated_roles["settlement_in"]["flow_type"] == "transfer_in"
    assert updated_roles["settlement_in"]["account_id"] == settlement_account["id"]
    assert updated_roles["settlement_in"]["amount"] == 235

    delete_response = client.delete(f"/api/assets/trades/{trade_payload['id']}")
    assert delete_response.status_code == 200
    assert asset_store["trade_entries"] == {}
    assert asset_store["cash_entries"] == {}


def test_asset_routes_require_settlement_account_when_auto_sync_enabled(client, asset_store):
    response = client.post(
        "/api/assets/accounts",
        json={
            "name": "Main Broker",
            "account_type": "brokerage",
            "base_currency": "TWD",
            "auto_sync_trade_settlement": True,
        },
    )

    assert response.status_code == 400
    assert "Settlement account is required" in response.json()["detail"]


def test_asset_routes_support_initial_balance_baseline_entries(client, asset_store):
    account_response = client.post(
        "/api/assets/accounts",
        json={
            "name": "Main Broker",
            "institution": "Manual",
            "account_type": "brokerage",
            "base_currency": "TWD",
            "include_in_total": True,
        },
    )
    assert account_response.status_code == 200
    account = account_response.json()

    asset_store["price_histories"]["2330.TW"] = [
        {"date": "2026-04-10", "close": 100, "source": "unit-test"},
        {"date": "2026-04-18", "close": 110, "source": "unit-test"},
    ]
    asset_store["quotes"]["2330.TW"]["price"] = 110
    asset_store["quotes"]["2330.TW"]["is_delayed"] = False

    cash_response = client.post(
        "/api/assets/cash-ledger",
        json={
            "account_id": account["id"],
            "flow_date": "2026-04-10T09:00:00",
            "flow_type": "deposit",
            "amount": 10000,
            "currency": "TWD",
            "fx_rate_to_base": 1,
            "is_initial_balance": True,
        },
    )
    assert cash_response.status_code == 200
    assert cash_response.json()["is_initial_balance"] is True

    trade_response = client.post(
        "/api/assets/trades",
        json={
            "account_id": account["id"],
            "trade_date": "2026-04-10T10:00:00",
            "ticker": "2330",
            "display_name": "TSMC",
            "market": "TW",
            "asset_type": "stock",
            "currency": "TWD",
            "side": "buy",
            "quantity": 100,
            "price": 100,
            "fee_amount": 0,
            "tax_amount": 0,
            "fx_rate_to_base": 1,
            "is_initial_balance": True,
        },
    )
    assert trade_response.status_code == 200
    assert trade_response.json()["is_initial_balance"] is True

    performance_response = client.get("/api/assets/performance?range=1y&refresh=false")
    assert performance_response.status_code == 200
    performance_payload = performance_response.json()

    assert performance_payload["summary"]["start_value_base"] == 10000
    assert performance_payload["summary"]["end_value_base"] == 11000
    assert performance_payload["summary"]["net_flow_base"] == 0
    assert performance_payload["summary"]["true_performance_base"] == 1000
    assert performance_payload["summary"]["flow_breakdown"]["deposit_base"] == 0
    assert performance_payload["series"][0]["date"] == "2026-04-10"


def test_asset_routes_refresh_use_latest_quote_and_public_fx(client, asset_store, monkeypatch):
    account_response = client.post(
        "/api/assets/accounts",
        json={
            "name": "US Broker",
            "institution": "Manual",
            "account_type": "brokerage",
            "base_currency": "USD",
            "include_in_total": True,
        },
    )
    assert account_response.status_code == 200
    account = account_response.json()

    cash_response = client.post(
        "/api/assets/cash-ledger",
        json={
            "account_id": account["id"],
            "flow_date": "2026-04-01T09:00:00",
            "flow_type": "deposit",
            "amount": 1000,
            "currency": "USD",
            "fx_rate_to_base": 30,
        },
    )
    assert cash_response.status_code == 200

    trade_response = client.post(
        "/api/assets/trades",
        json={
            "account_id": account["id"],
            "trade_date": "2026-04-02T09:30:00",
            "ticker": "AAPL",
            "display_name": "Apple",
            "market": "US",
            "asset_type": "stock",
            "currency": "USD",
            "side": "buy",
            "quantity": 2,
            "price": 100,
            "fee_amount": 0,
            "tax_amount": 0,
            "fx_rate_to_base": 30,
        },
    )
    assert trade_response.status_code == 200

    async def fake_fetch_and_store_quote_snapshot(ticker):
        if ticker != "AAPL":
            return None
        return {
            "ticker": "AAPL",
            "source": "unit-test-live",
            "quote_type": "snapshot",
            "is_delayed": False,
            "currency": "USD",
            "price": 150,
            "quote_timestamp": "2026-04-19T09:00:00+00:00",
        }

    class FakeFxProvider:
        def fetch_latest_rates(self):
            return {
                "snapshot_date": "2026-04-19",
                "source": "taifex_daily_reference",
                "rates": [
                    {
                        "from_currency": "USD",
                        "to_currency": "TWD",
                        "rate": 32.5,
                        "source": "taifex_daily_reference",
                    }
                ],
            }

    monkeypatch.setattr(main.assets, "_fetch_and_store_quote_snapshot", fake_fetch_and_store_quote_snapshot)
    monkeypatch.setattr(main.assets, "_latest_public_fx_provider", FakeFxProvider())

    portfolio_response = client.get("/api/assets/portfolio/current?refresh=true")
    assert portfolio_response.status_code == 200
    portfolio_payload = portfolio_response.json()

    assert portfolio_payload["summary"]["cash_total_base"] == 26000
    assert portfolio_payload["summary"]["market_value_total_base"] == 9750
    assert portfolio_payload["summary"]["total_asset_value_base"] == 35750
    assert portfolio_payload["holdings"][0]["ticker"] == "AAPL"
    assert portfolio_payload["holdings"][0]["last_price"] == 150
    assert portfolio_payload["holdings"][0]["quote_source"] == "unit-test-live"
    assert portfolio_payload["holdings"][0]["fx_rate_to_base"] == 32.5

    synced_rates = list(asset_store["fx_rates"].values())
    assert len(synced_rates) == 1
    assert synced_rates[0]["snapshot_date"] == "2026-04-19"
    assert synced_rates[0]["rate"] == 32.5
    assert synced_rates[0]["source"] == "taifex_daily_reference"


def test_asset_routes_support_advanced_tracking_workflows(client, asset_store):
    account_response = client.post(
        "/api/assets/accounts",
        json={
            "name": "Main Broker",
            "institution": "Manual",
            "account_type": "brokerage",
            "base_currency": "TWD",
            "include_in_total": True,
        },
    )
    assert account_response.status_code == 200
    account = account_response.json()

    asset_store["price_histories"]["2330.TW"] = [
        {"date": "2026-04-01", "close": 100, "source": "unit-test"},
        {"date": "2026-04-10", "close": 110, "source": "unit-test"},
    ]
    asset_store["quotes"]["2330.TW"]["price"] = 70
    asset_store["quotes"]["2330.TW"]["is_delayed"] = False
    asset_store["quotes"]["2330.TW"]["quote_type"] = "snapshot"

    cash_response = client.post(
        "/api/assets/cash-ledger",
        json={
            "account_id": account["id"],
            "flow_date": "2026-04-01T09:00:00",
            "flow_type": "deposit",
            "amount": 100000,
            "currency": "TWD",
            "fx_rate_to_base": 1,
        },
    )
    assert cash_response.status_code == 200

    buy_response = client.post(
        "/api/assets/trades",
        json={
            "account_id": account["id"],
            "trade_date": "2026-04-01T10:00:00",
            "ticker": "2330",
            "display_name": "TSMC",
            "market": "TW",
            "asset_type": "stock",
            "currency": "TWD",
            "side": "buy",
            "quantity": 900,
            "price": 100,
            "fee_amount": 0,
            "tax_amount": 0,
            "fx_rate_to_base": 1,
        },
    )
    assert buy_response.status_code == 200

    sell_response = client.post(
        "/api/assets/trades",
        json={
            "account_id": account["id"],
            "trade_date": "2026-04-10T10:00:00",
            "ticker": "2330",
            "display_name": "TSMC",
            "market": "TW",
            "asset_type": "stock",
            "currency": "TWD",
            "side": "sell",
            "quantity": 300,
            "price": 110,
            "fee_amount": 0,
            "tax_amount": 0,
            "fx_rate_to_base": 1,
        },
    )
    assert sell_response.status_code == 200

    price_override_response = client.post(
        "/api/assets/price-overrides",
        json={
            "account_id": account["id"],
            "ticker": "2330",
            "effective_at": "2026-04-18T09:00:00",
            "price": 70,
            "currency": "TWD",
            "force_override": True,
            "note": "Manual close",
        },
    )
    assert price_override_response.status_code == 200
    override_payload = price_override_response.json()
    assert override_payload["ticker"] == "2330.TW"

    fx_rate_response = client.post(
        "/api/assets/fx-rates",
        json={
            "snapshot_date": "2026-04-19",
            "from_currency": "USD",
            "to_currency": "TWD",
            "rate": 32,
            "source": "manual",
            "note": "Daily spot",
        },
    )
    assert fx_rate_response.status_code == 200
    fx_rate_payload = fx_rate_response.json()

    performance_response = client.get("/api/assets/performance?range=all&refresh=false")
    assert performance_response.status_code == 200
    performance_payload = performance_response.json()
    assert performance_payload["summary"]["true_performance_base"] == -15000
    assert performance_payload["summary"]["realized_end_base"] == 3000
    assert performance_payload["summary"]["unrealized_end_base"] == -18000
    assert performance_payload["summary"]["net_flow_base"] == 100000
    assert performance_payload["summary"]["flow_breakdown"]["deposit_base"] == 100000
    assert performance_payload["summary"]["performance_breakdown"]["realized_change_base"] == 3000
    assert performance_payload["summary"]["performance_breakdown"]["unrealized_change_base"] == -18000

    portfolio_response = client.get("/api/assets/portfolio/current?refresh=false")
    assert portfolio_response.status_code == 200
    portfolio_payload = portfolio_response.json()
    assert portfolio_payload["summary"]["manual_override_count"] == 1
    assert portfolio_payload["summary"]["total_asset_value_base"] == 85000
    assert portfolio_payload["holdings"][0]["manual_price_override_id"] == override_payload["id"]

    alerts_response = client.get("/api/assets/alerts/current?refresh=false&performance_range=all")
    assert alerts_response.status_code == 200
    alert_codes = {item["code"] for item in alerts_response.json()["items"]}
    assert {"concentration", "holding_drawdown", "portfolio_drawdown"} <= alert_codes

    recompute_response = client.post(
        "/api/assets/recompute",
        json={"refresh": False, "performance_range": "all"},
    )
    assert recompute_response.status_code == 200
    assert recompute_response.json()["performance_summary"]["true_performance_base"] == -15000

    adjustment_response = client.post(
        "/api/assets/adjustments",
        json={
            "account_id": account["id"],
            "event_date": "2026-04-19T12:00:00",
            "ticker": "ABC",
            "event_type": "adjustment",
            "quantity_delta": 2,
            "cost_basis_delta": 200,
            "currency": "TWD",
            "note": "Manual carry-in",
        },
    )
    assert adjustment_response.status_code == 200
    adjustment_payload = adjustment_response.json()

    adjustments_list_response = client.get("/api/assets/adjustments?ticker=ABC")
    assert adjustments_list_response.status_code == 200
    assert adjustments_list_response.json()["items"][0]["ticker"] == "ABC"

    update_fx_response = client.patch(
        f"/api/assets/fx-rates/{fx_rate_payload['id']}",
        json={"rate": 31.8, "note": "Adjusted"},
    )
    assert update_fx_response.status_code == 200
    assert update_fx_response.json()["rate"] == 31.8

    delete_adjustment_response = client.delete(f"/api/assets/adjustments/{adjustment_payload['id']}")
    assert delete_adjustment_response.status_code == 200
    delete_fx_response = client.delete(f"/api/assets/fx-rates/{fx_rate_payload['id']}")
    assert delete_fx_response.status_code == 200
    delete_override_response = client.delete(f"/api/assets/price-overrides/{override_payload['id']}")
    assert delete_override_response.status_code == 200


def test_asset_csv_preview_validates_rows_and_marks_file_duplicates(client, asset_store):
    account_response = client.post(
        "/api/assets/accounts",
        json={"name": "CSV Validation", "account_type": "brokerage", "base_currency": "TWD"},
    )
    account = account_response.json()
    csv_text = "\n".join(
        [
            "trade_date,ticker,market,side,quantity,price,external_id",
            "2026-04-01T09:00:00,2330,TW,buy,10,100,TX-001",
            "2026-04-01T09:00:00,2330,TW,buy,10,100,TX-001",
            "2026-04-02T09:00:00,2330,TW,buy,-1,100,TX-002",
            "not-a-date,2330,TW,buy,5,100,TX-003",
        ]
    )

    preview = client.post(
        "/api/assets/import/trades-csv",
        json={"csv_text": csv_text, "default_account_id": account["id"], "dry_run": True},
    )

    assert preview.status_code == 200
    payload = preview.json()
    assert payload["summary"] == {
        "input_count": 4,
        "row_count": 2,
        "valid_count": 2,
        "importable_count": 1,
        "duplicate_count": 1,
        "file_duplicate_count": 1,
        "database_duplicate_count": 0,
        "error_count": 2,
    }
    assert payload["duplicates"][0]["import_status"] == "duplicate_in_file"
    assert payload["duplicates"][0]["duplicate_of_row"] == 2
    assert {item["row"] for item in payload["errors"]} == {4, 5}

    imported = client.post(
        "/api/assets/import/trades-csv",
        json={"csv_text": csv_text, "default_account_id": account["id"], "dry_run": False},
    )
    assert imported.status_code == 200
    assert imported.json()["summary"]["created_count"] == 0
    assert imported.json()["summary"]["skipped_count"] == 1
    assert imported.json()["summary"]["error_count"] == 2
    assert imported.json()["batch"]["status"] == "failed"
    assert len(asset_store["trade_entries"]) == 0


def test_asset_routes_support_csv_and_journal_import_workflows(client, asset_store):
    account_response = client.post(
        "/api/assets/accounts",
        json={
            "name": "Import Account",
            "account_type": "brokerage",
            "base_currency": "TWD",
            "include_in_total": True,
        },
    )
    assert account_response.status_code == 200
    account = account_response.json()

    trades_csv = "\n".join(
        [
            "trade_date,ticker,market,currency,side,quantity,price,fee_amount,tax_amount",
            "2026-04-01T09:00:00,AAPL,US,USD,buy,5,100,1,0",
        ]
    )
    dry_run_trades_response = client.post(
        "/api/assets/import/trades-csv",
        json={"csv_text": trades_csv, "default_account_id": account["id"], "dry_run": True},
    )
    assert dry_run_trades_response.status_code == 200
    assert dry_run_trades_response.json()["summary"]["row_count"] == 1

    import_trades_response = client.post(
        "/api/assets/import/trades-csv",
        json={"csv_text": trades_csv, "default_account_id": account["id"], "dry_run": False},
    )
    assert import_trades_response.status_code == 200
    imported_trades_payload = import_trades_response.json()
    assert imported_trades_payload["summary"]["created_count"] == 1
    assert imported_trades_payload["items"][0]["ticker"] == "AAPL"
    assert imported_trades_payload["items"][0]["import_key"]

    repeated_trade_preview = client.post(
        "/api/assets/import/trades-csv",
        json={"csv_text": trades_csv, "default_account_id": account["id"], "dry_run": True},
    )
    assert repeated_trade_preview.status_code == 200
    assert repeated_trade_preview.json()["summary"]["importable_count"] == 0
    assert repeated_trade_preview.json()["summary"]["database_duplicate_count"] == 1
    assert repeated_trade_preview.json()["duplicates"][0]["existing_id"] == imported_trades_payload["items"][0]["id"]

    repeated_trade_import = client.post(
        "/api/assets/import/trades-csv",
        json={"csv_text": trades_csv, "default_account_id": account["id"], "dry_run": False},
    )
    assert repeated_trade_import.status_code == 200
    assert repeated_trade_import.json()["summary"]["created_count"] == 0
    assert repeated_trade_import.json()["summary"]["skipped_count"] == 1
    assert len(asset_store["trade_entries"]) == 1

    cash_csv = "\n".join(
        [
            "flow_date,flow_type,amount,currency,counterparty",
            "2026-04-01T08:00:00,deposit,5000,TWD,Bank",
        ]
    )
    dry_run_cash_response = client.post(
        "/api/assets/import/cash-csv",
        json={"csv_text": cash_csv, "default_account_id": account["id"], "dry_run": True},
    )
    assert dry_run_cash_response.status_code == 200
    assert dry_run_cash_response.json()["summary"]["row_count"] == 1

    import_cash_response = client.post(
        "/api/assets/import/cash-csv",
        json={"csv_text": cash_csv, "default_account_id": account["id"], "dry_run": False},
    )
    assert import_cash_response.status_code == 200
    assert import_cash_response.json()["summary"]["created_count"] == 1

    repeated_cash_preview = client.post(
        "/api/assets/import/cash-csv",
        json={"csv_text": cash_csv, "default_account_id": account["id"], "dry_run": True},
    )
    assert repeated_cash_preview.status_code == 200
    assert repeated_cash_preview.json()["summary"]["database_duplicate_count"] == 1
    assert repeated_cash_preview.json()["summary"]["importable_count"] == 0

    asset_store["journal_entries"] = [
        {
            "id": 501,
            "ticker": "MSFT",
            "market": "US",
            "direction": "long",
            "entry_time": "2026-04-02T09:30:00",
            "exit_time": "2026-04-04T09:30:00",
            "entry_price": 100,
            "exit_price": 105,
            "size": 5,
            "strategy_code": "swing",
            "tags": ["growth"],
            "note": "Long setup",
        },
        {
            "id": 502,
            "ticker": "TSLA",
            "market": "US",
            "direction": "short",
            "entry_time": "2026-04-03T09:30:00",
            "entry_price": 200,
            "size": 2,
            "strategy_code": "fade",
            "tags": ["short"],
            "note": "Short setup",
        },
    ]

    preview_response = client.post(
        "/api/assets/journal-import/preview",
        json={"account_id": account["id"], "limit": 10},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["summary"]["entry_count"] == 2
    assert preview_payload["summary"]["importable_count"] == 1
    assert preview_payload["items"][0]["importable"] is False
    assert preview_payload["items"][1]["importable"] is True
    assert len(preview_payload["items"][1]["payloads"]) == 2

    import_journal_response = client.post(
        "/api/assets/journal-import",
        json={"account_id": account["id"], "limit": 10},
    )
    assert import_journal_response.status_code == 200
    import_journal_payload = import_journal_response.json()
    assert import_journal_payload["summary"]["created_count"] == 2
    assert import_journal_payload["summary"]["error_count"] == 0

    preview_after_response = client.post(
        "/api/assets/journal-import/preview",
        json={"account_id": account["id"], "limit": 10},
    )
    assert preview_after_response.status_code == 200
    preview_after_payload = preview_after_response.json()
    assert preview_after_payload["summary"]["importable_count"] == 0
    assert preview_after_payload["summary"]["skipped_count"] == 2


def test_asset_csv_import_rolls_back_every_row_when_one_insert_fails(client, asset_store, monkeypatch):
    account = client.post(
        "/api/assets/accounts",
        json={"name": "Atomic Import", "account_type": "brokerage", "base_currency": "TWD"},
    ).json()
    original_create = main.db.create_asset_trade_entry
    attempts = 0

    async def fail_second_insert(payload, owner_id=1):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise RuntimeError("simulated second-row failure")
        return await original_create(payload, owner_id=owner_id)

    monkeypatch.setattr(main.db, "create_asset_trade_entry", fail_second_insert)
    csv_text = "\n".join(
        [
            "trade_date,ticker,side,quantity,price,external_id",
            "2026-04-01T09:00:00,2330,buy,1,100,A-1",
            "2026-04-02T09:00:00,2317,buy,1,200,A-2",
        ]
    )

    response = client.post(
        "/api/assets/import/trades-csv",
        json={"csv_text": csv_text, "default_account_id": account["id"], "dry_run": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["created_count"] == 0
    assert payload["summary"]["error_count"] == 1
    assert payload["batch"]["status"] == "failed"
    assert asset_store["trade_entries"] == {}


def test_committed_asset_import_batch_can_be_audited_and_rolled_back(client, asset_store):
    account = client.post(
        "/api/assets/accounts",
        json={"name": "Rollback Import", "account_type": "brokerage", "base_currency": "TWD"},
    ).json()
    csv_text = "\n".join(
        [
            "trade_date,ticker,side,quantity,price,external_id",
            "2026-04-01T09:00:00,2330,buy,1,100,R-1",
        ]
    )
    imported = client.post(
        "/api/assets/import/trades-csv",
        json={
            "csv_text": csv_text,
            "default_account_id": account["id"],
            "source_name": "broker-2026.csv",
            "dry_run": False,
        },
    ).json()
    batch_id = imported["batch"]["id"]

    assert imported["batch"]["status"] == "committed"
    assert imported["batch"]["source_name"] == "broker-2026.csv"
    assert len(asset_store["trade_entries"]) == 1
    history = client.get("/api/assets/import-batches").json()["items"]
    assert history[0]["id"] == batch_id

    rolled_back = client.post(f"/api/assets/import-batches/{batch_id}/rollback")

    assert rolled_back.status_code == 200
    assert rolled_back.json()["batch"]["status"] == "rolled_back"
    assert rolled_back.json()["deleted"]["trade_count"] == 1
    assert asset_store["trade_entries"] == {}
    repeated = client.post(f"/api/assets/import-batches/{batch_id}/rollback")
    assert repeated.status_code == 200
    assert repeated.json()["deleted"] == {"trade_count": 0, "cash_count": 0}
