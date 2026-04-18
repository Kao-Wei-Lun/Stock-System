import copy

import pytest

import main


@pytest.fixture
def asset_store(monkeypatch):
    store = {
        "next_account_id": 1,
        "next_cash_id": 1,
        "next_trade_id": 1,
        "accounts": {},
        "cash_entries": {},
        "trade_entries": {},
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

    async def list_asset_cash_ledger_entries(owner_id=1, account_id=None, date_from=None, date_to=None, limit=200):
        items = list(store["cash_entries"].values())
        if account_id is not None:
            items = [item for item in items if item["account_id"] == account_id]
        if date_from:
            items = [item for item in items if item["flow_date"] >= date_from]
        if date_to:
            items = [item for item in items if item["flow_date"] <= date_to]
        items.sort(key=lambda item: (item["flow_date"], item["id"]), reverse=True)
        return clone(items[:limit])

    async def get_asset_cash_ledger_entry(entry_id, owner_id=1):
        item = store["cash_entries"].get(entry_id)
        return clone(item) if item else None

    async def create_asset_cash_ledger_entry(payload, owner_id=1):
        entry_id = store["next_cash_id"]
        store["next_cash_id"] += 1
        item = {
            "id": entry_id,
            "owner_id": owner_id,
            "account_id": payload["account_id"],
            "flow_date": payload["flow_date"],
            "flow_type": payload["flow_type"],
            "amount": payload["amount"],
            "currency": payload.get("currency") or "TWD",
            "fx_rate_to_base": payload.get("fx_rate_to_base") or 1,
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

    async def list_asset_trade_entries(owner_id=1, account_id=None, ticker=None, date_from=None, date_to=None, limit=200):
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
        return clone(items[:limit])

    async def get_asset_trade_entry(entry_id, owner_id=1):
        item = store["trade_entries"].get(entry_id)
        return clone(item) if item else None

    async def create_asset_trade_entry(payload, owner_id=1):
        entry_id = store["next_trade_id"]
        store["next_trade_id"] += 1
        gross_amount = payload.get("gross_amount") or payload["quantity"] * payload["price"]
        fee_amount = payload.get("fee_amount") or 0
        tax_amount = payload.get("tax_amount") or 0
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
            "quantity": payload["quantity"],
            "price": payload["price"],
            "gross_amount": gross_amount,
            "fee_amount": fee_amount,
            "tax_amount": tax_amount,
            "net_amount": payload.get("net_amount") or (gross_amount + fee_amount + tax_amount),
            "fx_rate_to_base": payload.get("fx_rate_to_base") or 1,
            "source": payload.get("source") or "manual",
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
        existing["updated_at"] = "2026-04-18T08:35:00+00:00"
        return clone(existing)

    async def delete_asset_trade_entry(entry_id, owner_id=1):
        return store["trade_entries"].pop(entry_id, None) is not None

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
    monkeypatch.setattr(main.db, "list_asset_cash_ledger_entries", list_asset_cash_ledger_entries)
    monkeypatch.setattr(main.db, "get_asset_cash_ledger_entry", get_asset_cash_ledger_entry)
    monkeypatch.setattr(main.db, "create_asset_cash_ledger_entry", create_asset_cash_ledger_entry)
    monkeypatch.setattr(main.db, "update_asset_cash_ledger_entry", update_asset_cash_ledger_entry)
    monkeypatch.setattr(main.db, "delete_asset_cash_ledger_entry", delete_asset_cash_ledger_entry)
    monkeypatch.setattr(main.db, "list_asset_trade_entries", list_asset_trade_entries)
    monkeypatch.setattr(main.db, "get_asset_trade_entry", get_asset_trade_entry)
    monkeypatch.setattr(main.db, "create_asset_trade_entry", create_asset_trade_entry)
    monkeypatch.setattr(main.db, "update_asset_trade_entry", update_asset_trade_entry)
    monkeypatch.setattr(main.db, "delete_asset_trade_entry", delete_asset_trade_entry)
    monkeypatch.setattr(main.db, "get_market_quote", get_market_quote)
    monkeypatch.setattr(main.db, "replace_asset_positions_current", replace_asset_positions_current)
    monkeypatch.setattr(main.db, "replace_asset_valuations_current", replace_asset_valuations_current)
    monkeypatch.setattr(main.assets, "_fetch_and_store_quote_snapshot", None)

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
