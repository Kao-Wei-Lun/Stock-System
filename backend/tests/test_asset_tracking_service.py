import asyncio

from asset_tracking_service import (
    build_asset_alerts,
    build_asset_performance_report,
    build_asset_portfolio_snapshot,
)


def test_build_asset_portfolio_snapshot_derives_holdings_and_respects_include_in_total():
    accounts = [
        {
            "id": 1,
            "name": "Main Broker",
            "account_type": "brokerage",
            "base_currency": "TWD",
            "include_in_total": True,
            "sort_order": 0,
        },
        {
            "id": 2,
            "name": "Side Pocket",
            "account_type": "cash",
            "base_currency": "TWD",
            "include_in_total": False,
            "sort_order": 1,
        },
    ]
    cash_entries = [
        {
            "id": 1,
            "account_id": 1,
            "flow_date": "2026-04-01T09:00:00",
            "flow_type": "deposit",
            "amount": 100000,
            "currency": "TWD",
            "fx_rate_to_base": 1,
        },
        {
            "id": 2,
            "account_id": 2,
            "flow_date": "2026-04-02T09:00:00",
            "flow_type": "deposit",
            "amount": 5000,
            "currency": "TWD",
            "fx_rate_to_base": 1,
        },
    ]
    trade_entries = [
        {
            "id": 11,
            "account_id": 1,
            "trade_date": "2026-04-03T09:00:00",
            "ticker": "2330.TW",
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
    ]
    reconciliation_snapshots = [
        {
            "id": 31,
            "account_id": 1,
            "snapshot_date": "2026-04-18T10:00:00",
            "cash_actual": 99000,
            "cash_system": 98990,
            "market_value_actual": 1300,
            "market_value_system": 1200,
            "positions_payload": [{"ticker": "2330.TW", "quantity": 10}],
            "note": "Broker app close",
        }
    ]

    async def fetch_quote(ticker):
        if ticker == "2330.TW":
            return {
                "ticker": ticker,
                "source": "unit-test",
                "quote_type": "snapshot",
                "is_delayed": True,
                "currency": "TWD",
                "price": 120,
                "quote_timestamp": "2026-04-18T09:00:00+00:00",
            }
        return None

    snapshot = asyncio.run(
        build_asset_portfolio_snapshot(
            accounts,
            cash_entries,
            trade_entries,
            reconciliation_snapshots=reconciliation_snapshots,
            fetch_quote=fetch_quote,
        )
    )

    assert snapshot["summary"]["cash_total_base"] == 98990
    assert snapshot["summary"]["market_value_total_base"] == 1200
    assert snapshot["summary"]["total_asset_value_base"] == 100190
    assert snapshot["summary"]["unrealized_total_base"] == 190
    assert snapshot["summary"]["quote_gap_count"] == 0
    assert snapshot["summary"]["account_count"] == 2
    assert snapshot["summary"]["reconciliation_account_count"] == 1
    assert snapshot["summary"]["reconciliation_gap_count"] == 1
    assert snapshot["summary"]["reconciliation_difference_total_base"] == 110
    assert snapshot["holdings"][0]["ticker"] == "2330.TW"
    assert snapshot["holdings"][0]["market_value_base"] == 1200
    assert snapshot["holdings"][0]["unrealized_pnl_base"] == 190
    assert snapshot["allocation"]["items"][0]["key"] == "Main Broker"
    assert snapshot["allocation"]["items"][0]["value_base"] == 100190
    assert snapshot["reconciliation"]["items"][0]["account_name"] == "Main Broker"
    assert snapshot["reconciliation"]["items"][0]["cash_difference"] == 10
    assert snapshot["reconciliation"]["items"][0]["market_value_difference"] == 100
    assert snapshot["reconciliation"]["items"][0]["total_difference"] == 110


def test_build_asset_portfolio_snapshot_applies_manual_override_fx_rates_and_splits():
    accounts = [
        {
            "id": 1,
            "name": "US Broker",
            "account_type": "brokerage",
            "base_currency": "USD",
            "include_in_total": True,
            "sort_order": 0,
        }
    ]
    cash_entries = [
        {
            "id": 1,
            "account_id": 1,
            "flow_date": "2026-04-01T09:00:00",
            "flow_type": "deposit",
            "amount": 10000,
            "currency": "USD",
            "fx_rate_to_base": 32,
        }
    ]
    trade_entries = [
        {
            "id": 11,
            "account_id": 1,
            "trade_date": "2026-04-01T10:00:00",
            "ticker": "AAPL",
            "display_name": "Apple",
            "market": "US",
            "asset_type": "stock",
            "currency": "USD",
            "side": "buy",
            "quantity": 10,
            "price": 100,
            "fee_amount": 0,
            "tax_amount": 0,
            "fx_rate_to_base": 32,
        }
    ]
    adjustment_entries = [
        {
            "id": 21,
            "account_id": 1,
            "event_date": "2026-04-15T09:00:00",
            "ticker": "AAPL",
            "event_type": "split",
            "split_ratio": 2,
            "currency": "USD",
        }
    ]
    fx_rate_entries = [
        {
            "id": 31,
            "snapshot_date": "2026-04-18",
            "from_currency": "USD",
            "to_currency": "TWD",
            "rate": 31.5,
            "source": "manual",
        }
    ]
    price_overrides = [
        {
            "id": 41,
            "account_id": 1,
            "ticker": "AAPL",
            "effective_at": "2026-04-18T11:00:00",
            "price": 110,
            "currency": "USD",
            "force_override": True,
            "note": "Manual broker close",
        }
    ]

    async def fetch_quote(ticker):
        if ticker == "AAPL":
            return {
                "ticker": ticker,
                "source": "unit-test",
                "quote_type": "snapshot",
                "is_delayed": False,
                "currency": "USD",
                "price": 105,
                "quote_timestamp": "2026-04-18T09:00:00+00:00",
            }
        return None

    snapshot = asyncio.run(
        build_asset_portfolio_snapshot(
            accounts,
            cash_entries,
            trade_entries,
            adjustment_entries=adjustment_entries,
            price_overrides=price_overrides,
            fx_rate_entries=fx_rate_entries,
            fetch_quote=fetch_quote,
        )
    )

    assert snapshot["summary"]["cash_total_base"] == 283500
    assert snapshot["summary"]["market_value_total_base"] == 69300
    assert snapshot["summary"]["total_asset_value_base"] == 352800
    assert snapshot["summary"]["manual_override_count"] == 1
    assert snapshot["summary"]["quote_gap_count"] == 0
    assert snapshot["holdings"][0]["ticker"] == "AAPL"
    assert snapshot["holdings"][0]["quantity"] == 20
    assert snapshot["holdings"][0]["quote_source"] == "manual_override"
    assert snapshot["holdings"][0]["last_price"] == 110
    assert snapshot["holdings"][0]["market_value_base"] == 69300
    assert snapshot["holdings"][0]["unrealized_pnl_base"] == 37800
    assert snapshot["holdings"][0]["manual_price_override_id"] == 41


def test_build_asset_portfolio_snapshot_prefers_latest_fx_snapshots_for_current_valuation():
    accounts = [
        {
            "id": 1,
            "name": "US Broker",
            "account_type": "brokerage",
            "base_currency": "USD",
            "include_in_total": True,
            "sort_order": 0,
        }
    ]
    cash_entries = [
        {
            "id": 1,
            "account_id": 1,
            "flow_date": "2026-04-01T09:00:00",
            "flow_type": "deposit",
            "amount": 1000,
            "currency": "USD",
            "fx_rate_to_base": 30,
        }
    ]
    trade_entries = [
        {
            "id": 11,
            "account_id": 1,
            "trade_date": "2026-04-02T10:00:00",
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
        }
    ]
    fx_rate_entries = [
        {
            "id": 31,
            "snapshot_date": "2026-04-19",
            "from_currency": "USD",
            "to_currency": "TWD",
            "rate": 32.5,
            "source": "taifex_daily_reference",
        }
    ]

    async def fetch_quote(ticker):
        if ticker == "AAPL":
            return {
                "ticker": ticker,
                "source": "unit-test-live",
                "quote_type": "snapshot",
                "is_delayed": False,
                "currency": "USD",
                "price": 150,
                "quote_timestamp": "2026-04-19T09:00:00+00:00",
            }
        return None

    snapshot = asyncio.run(
        build_asset_portfolio_snapshot(
            accounts,
            cash_entries,
            trade_entries,
            fx_rate_entries=fx_rate_entries,
            fetch_quote=fetch_quote,
        )
    )

    assert snapshot["summary"]["cash_total_base"] == 26000
    assert snapshot["summary"]["market_value_total_base"] == 9750
    assert snapshot["summary"]["total_asset_value_base"] == 35750
    assert snapshot["holdings"][0]["fx_rate_to_base"] == 32.5
    assert snapshot["holdings"][0]["cost_basis_base"] == 6500
    assert snapshot["holdings"][0]["unrealized_pnl_base"] == 3250


def test_build_asset_performance_report_and_alerts_use_start_day_baseline_correctly():
    accounts = [
        {
            "id": 1,
            "name": "Main Broker",
            "account_type": "brokerage",
            "base_currency": "TWD",
            "include_in_total": True,
            "sort_order": 0,
        }
    ]
    cash_entries = [
        {
            "id": 1,
            "account_id": 1,
            "flow_date": "2026-04-01T09:00:00",
            "flow_type": "deposit",
            "amount": 100000,
            "currency": "TWD",
            "fx_rate_to_base": 1,
        }
    ]
    trade_entries = [
        {
            "id": 11,
            "account_id": 1,
            "trade_date": "2026-04-01T10:00:00",
            "ticker": "2330.TW",
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
        {
            "id": 12,
            "account_id": 1,
            "trade_date": "2026-04-10T10:00:00",
            "ticker": "2330.TW",
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
    ]

    async def get_price_history(ticker, start_date, end_date):
        assert ticker == "2330.TW"
        return [
            {"date": "2026-04-01", "close": 100, "source": "unit-test"},
            {"date": "2026-04-10", "close": 110, "source": "unit-test"},
            {"date": "2026-04-18", "close": 70, "source": "unit-test"},
        ]

    report = asyncio.run(
        build_asset_performance_report(
            accounts,
            cash_entries,
            trade_entries,
            start_at="2026-04-01T00:00:00",
            end_at="2026-04-18T23:59:59",
            get_price_history=get_price_history,
        )
    )
    snapshot = asyncio.run(
        build_asset_portfolio_snapshot(
            accounts,
            cash_entries,
            trade_entries,
            fetch_quote=None,
        )
    )
    snapshot["holdings"][0]["market_value_base"] = 42000
    snapshot["holdings"][0]["unrealized_pnl_base"] = -18000
    snapshot["holdings"][0]["unrealized_pnl_pct"] = -30
    snapshot["summary"]["market_value_total_base"] = 42000
    snapshot["summary"]["total_asset_value_base"] = 85000
    snapshot["summary"]["unrealized_total_base"] = -18000

    alerts = build_asset_alerts(snapshot, report)
    alert_codes = {item["code"] for item in alerts}

    assert report["summary"]["start_value_base"] == 100000
    assert report["summary"]["end_value_base"] == 85000
    assert report["summary"]["net_flow_base"] == 0
    assert report["summary"]["true_performance_base"] == -15000
    assert report["summary"]["true_return_pct"] == -15
    assert report["summary"]["realized_end_base"] == 3000
    assert report["summary"]["unrealized_end_base"] == -18000
    assert report["summary"]["max_drawdown_pct"] == -22.0183
    assert report["monthly_heatmap"] == [
        {
            "month": "2026-04",
            "true_performance_base": -15000,
            "return_pct": -15,
        }
    ]
    assert report["realized_vs_unrealized"][-1] == {
        "date": "2026-04-18",
        "realized_total_base": 3000.0,
        "unrealized_total_base": -18000.0,
    }
    assert {"concentration", "holding_drawdown", "portfolio_drawdown"} <= alert_codes
