from __future__ import annotations

import asyncio
import inspect
from datetime import date

import pytest

from asset_use_cases import (
    account_ledger_commands,
    csv_imports,
    market_hydration,
    reconciliation,
    valuation_queries,
)
from asset_use_cases.reconciliation import build_reconciliation_positions_payload
from asset_use_cases.valuation_queries import (
    InvalidAllocationGroup,
    build_allocation,
    build_contributors,
    resolve_performance_start,
)
from routers import assets


def test_asset_use_cases_do_not_depend_on_fastapi():
    modules = (
        account_ledger_commands,
        csv_imports,
        market_hydration,
        reconciliation,
        valuation_queries,
    )
    assert all("fastapi" not in inspect.getsource(module) for module in modules)


def test_asset_router_keeps_legacy_private_facades():
    expected = (
        "_ensure_account_exists",
        "_fetch_latest_quote",
        "_load_asset_fx_rates",
        "_build_snapshot",
        "_build_performance",
        "_run_csv_import",
        "_run_atomic_asset_import",
    )
    assert all(callable(getattr(assets, name, None)) for name in expected)


def test_trade_settlement_payloads_preserve_double_entry_roles():
    payloads = account_ledger_commands.build_trade_settlement_payloads(
        {
            "id": 9,
            "trade_date": "2026-07-24",
            "ticker": "2330.TW",
            "side": "buy",
            "net_amount": -1000,
            "currency": "TWD",
        },
        {"id": 2, "name": "證券帳戶"},
        {"id": 1, "name": "交割帳戶"},
    )

    assert set(payloads) == {"settlement_out", "broker_in"}
    assert payloads["settlement_out"]["amount"] == payloads["broker_in"]["amount"] == 1000
    assert payloads["settlement_out"]["linked_trade_role"] == "settlement_out"
    assert payloads["broker_in"]["linked_trade_role"] == "broker_in"


def test_market_hydration_loads_every_page():
    calls = []

    async def fetcher(*, owner_id, limit, offset):
        calls.append((owner_id, limit, offset))
        rows = [{"id": index} for index in range(5)]
        return rows[offset : offset + limit]

    rows = asyncio.run(
        market_hydration.load_all_asset_rows(
            fetcher,
            owner_id=7,
            page_size=2,
        )
    )

    assert [row["id"] for row in rows] == [0, 1, 2, 3, 4]
    assert calls == [(7, 2, 0), (7, 2, 2), (7, 2, 4)]


def test_market_hydration_cache_and_wait_policy():
    cache = {"2330.TW": (110.0, 123, {"price": 1000})}
    assert market_hydration.read_fresh_quote_cache(
        cache,
        "2330.TW",
        provider_identity=123,
        now=100.0,
    ) == {"price": 1000}
    assert market_hydration.provider_wait_budget(
        has_persisted_value=True,
        timeout_seconds=8,
    ) == 1.5
    assert market_hydration.provider_wait_budget(
        has_persisted_value=False,
        timeout_seconds=8,
    ) == 8


def test_csv_import_key_is_stable_and_reference_scoped():
    item = {
        "account_id": 1,
        "trade_date": "2026-07-24T09:00:00+08:00",
        "ticker": "2330.TW",
        "side": "buy",
        "quantity": 10,
        "price": 1000,
        "fee_amount": 1,
        "tax_amount": 0,
        "currency": "TWD",
    }
    assert csv_imports.build_asset_import_key("trade", item) == csv_imports.build_asset_import_key(
        "trade",
        dict(item),
    )
    assert csv_imports.build_asset_import_key(
        "trade",
        item,
        reference="broker-1",
    ) != csv_imports.build_asset_import_key("trade", item, reference="broker-2")


def test_valuation_projections_and_reconciliation_are_pure():
    snapshot = {
        "holdings": [
            {
                "account_id": 1,
                "ticker": "2330.TW",
                "market": "TW",
                "market_value_base": 60,
                "unrealized_pnl_base": 10,
            },
            {
                "account_id": 2,
                "ticker": "AAPL",
                "market": "US",
                "market_value_base": 40,
                "unrealized_pnl_base": -5,
            },
        ]
    }

    allocation = build_allocation(snapshot, "market")
    assert allocation["items"] == [
        {"key": "TW", "value_base": 60.0, "weight_pct": 60.0},
        {"key": "US", "value_base": 40.0, "weight_pct": 40.0},
    ]
    assert build_contributors(snapshot, 1)["top_gainers"][0]["ticker"] == "2330.TW"
    assert build_reconciliation_positions_payload(snapshot, 1)[0]["ticker"] == "2330.TW"
    assert resolve_performance_start("ytd", today=date(2026, 7, 24)) == "2026-01-01"
    with pytest.raises(InvalidAllocationGroup):
        build_allocation(snapshot, "currency")
