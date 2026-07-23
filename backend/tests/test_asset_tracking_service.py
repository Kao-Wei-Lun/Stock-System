import asyncio

from asset_tracking_service import (
    _build_daily_nav_change_metadata,
    build_asset_alerts,
    build_asset_performance_report,
    build_asset_portfolio_snapshot,
)


def test_daily_nav_change_metadata_handles_empty_or_single_series():
    empty_metadata, empty_warnings, empty_flags = _build_daily_nav_change_metadata([])

    assert empty_metadata["daily_nav_change_base"] is None
    assert empty_metadata["daily_nav_change_pct"] is None
    assert empty_metadata["daily_metric_type"] == "unavailable"
    assert empty_warnings
    assert "insufficient_performance_series" in empty_flags

    one_point_metadata, _, one_point_flags = _build_daily_nav_change_metadata([
        {"date": "2026-04-18", "total_asset_value_base": 1000},
    ])

    assert one_point_metadata["daily_nav_change_base"] is None
    assert one_point_metadata["daily_nav_change_pct"] is None
    assert one_point_metadata["daily_metric_type"] == "unavailable"
    assert "insufficient_performance_series" in one_point_flags


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
    assert snapshot["summary"]["current_position_cost_base"] == 1010
    assert snapshot["summary"]["unrealized_total_base"] == 190
    assert snapshot["summary"]["quote_gap_count"] == 0
    assert snapshot["summary"]["account_count"] == 2
    assert snapshot["summary"]["reconciliation_account_count"] == 1
    assert snapshot["summary"]["reconciliation_gap_count"] == 1
    assert snapshot["summary"]["reconciliation_difference_total_base"] == 110
    assert "reconciliation_gaps_present" in snapshot["data_quality_flags"]
    assert snapshot["data_quality_summary"]["severity"] == "warning"
    assert "reconciliation_gaps_present" in snapshot["data_quality_summary"]["debug_flags"]
    assert snapshot["data_quality_summary"]["user_visible_messages"]
    assert snapshot["holdings"][0]["ticker"] == "2330.TW"
    assert snapshot["holdings"][0]["market_value_base"] == 1200
    assert snapshot["holdings"][0]["unrealized_pnl_base"] == 190
    assert snapshot["allocation"]["items"][0]["key"] == "Main Broker"
    assert snapshot["allocation"]["items"][0]["value_base"] == 100190
    assert snapshot["reconciliation"]["items"][0]["account_name"] == "Main Broker"
    assert snapshot["reconciliation"]["items"][0]["cash_difference"] == 10
    assert snapshot["reconciliation"]["items"][0]["market_value_difference"] == 100
    assert snapshot["reconciliation"]["items"][0]["total_difference"] == 110


def test_build_asset_portfolio_snapshot_returns_zero_position_cost_without_holdings():
    accounts = [
        {
            "id": 1,
            "name": "Cash Account",
            "account_type": "bank",
            "base_currency": "TWD",
            "include_in_total": True,
            "sort_order": 0,
        }
    ]

    snapshot = asyncio.run(build_asset_portfolio_snapshot(accounts, [], [], fetch_quote=None))

    assert snapshot["summary"]["current_position_cost_base"] == 0
    assert snapshot["currency_allocation"] == []
    assert snapshot["calculation_metadata"]["current_position_cost"]["status"] == "computed"
    assert snapshot["calculation_metadata"]["currency_allocation"]["status"] == "empty"


def test_build_asset_portfolio_snapshot_groups_currency_allocation_from_cash_and_holdings():
    accounts = [
        {
            "id": 1,
            "name": "Global Broker",
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
        },
        {
            "id": 2,
            "account_id": 1,
            "flow_date": "2026-04-01T09:01:00",
            "flow_type": "deposit",
            "amount": 1000,
            "currency": "USD",
            "fx_rate_to_base": 30,
        },
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
            "quantity": 10,
            "price": 100,
            "fee_amount": 0,
            "tax_amount": 0,
            "fx_rate_to_base": 30,
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

    async def fetch_quote(ticker):
        if ticker == "AAPL":
            return {
                "ticker": ticker,
                "source": "unit-test",
                "quote_type": "snapshot",
                "is_delayed": False,
                "currency": "USD",
                "price": 110,
                "quote_timestamp": "2026-04-18T09:00:00+00:00",
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

    assert snapshot["summary"]["total_asset_value_base"] == 134650
    assert snapshot["summary"]["current_position_cost_base"] == 31500
    assert snapshot["calculation_metadata"]["currency_allocation"]["status"] == "computed"
    allocation_by_currency = {item["currency"]: item for item in snapshot["currency_allocation"]}
    assert allocation_by_currency["TWD"]["value_base"] == 100000
    assert allocation_by_currency["TWD"]["weight_pct"] == 74.2666
    assert allocation_by_currency["USD"]["value_base"] == 34650
    assert allocation_by_currency["USD"]["weight_pct"] == 25.7334


def test_build_asset_portfolio_snapshot_marks_quote_gap_quality_flags():
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
            "amount": 10000,
            "currency": "TWD",
            "fx_rate_to_base": 1,
        }
    ]
    trade_entries = [
        {
            "id": 11,
            "account_id": 1,
            "trade_date": "2026-04-02T10:00:00",
            "ticker": "2330.TW",
            "display_name": "TSMC",
            "market": "TW",
            "asset_type": "stock",
            "currency": "TWD",
            "side": "buy",
            "quantity": 10,
            "price": 100,
            "fee_amount": 0,
            "tax_amount": 0,
            "fx_rate_to_base": 1,
        }
    ]

    snapshot = asyncio.run(build_asset_portfolio_snapshot(accounts, cash_entries, trade_entries, fetch_quote=None))

    assert snapshot["summary"]["quote_gap_count"] == 1
    assert "quote_gaps_present" in snapshot["data_quality_flags"]
    assert "missing_fx_or_price_data" in snapshot["data_quality_flags"]
    assert snapshot["calculation_warnings"]
    assert snapshot["data_quality_summary"]["severity"] == "warning"
    assert "quote_gaps_present" in snapshot["data_quality_summary"]["debug_flags"]
    assert snapshot["data_quality_summary"]["user_visible_messages"]


def test_portfolio_snapshot_fetches_duplicate_ticker_once_across_accounts():
    calls = []
    accounts = [
        {"id": 1, "name": "Broker A", "base_currency": "TWD", "include_in_total": True},
        {"id": 2, "name": "Broker B", "base_currency": "TWD", "include_in_total": True},
    ]
    trades = [
        {
            "id": 1,
            "account_id": 1,
            "ticker": "2330.TW",
            "side": "buy",
            "quantity": 1,
            "price": 100,
            "trade_date": "2026-01-01T00:00:00+00:00",
            "currency": "TWD",
        },
        {
            "id": 2,
            "account_id": 2,
            "ticker": "2330.TW",
            "side": "buy",
            "quantity": 2,
            "price": 100,
            "trade_date": "2026-01-01T00:00:00+00:00",
            "currency": "TWD",
        },
    ]

    async def fetch_quote(ticker):
        calls.append(ticker)
        return {"ticker": ticker, "price": 120, "currency": "TWD"}

    snapshot = asyncio.run(
        build_asset_portfolio_snapshot(accounts, [], trades, fetch_quote=fetch_quote)
    )

    assert calls == ["2330.TW"]
    assert len(snapshot["holdings"]) == 2


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
    assert snapshot["calculation_metadata"]["current_position_cost"]["status"] == "computed"
    assert snapshot["calculation_metadata"]["current_position_cost"]["is_estimated"] is False
    assert snapshot["calculation_metadata"]["currency_allocation"]["status"] == "computed"
    assert snapshot["data_quality_summary"]["severity"] == "ok"
    assert snapshot["calculation_warnings"] == []
    assert snapshot["data_quality_flags"] == []
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
    assert report["summary"]["daily_nav_change_base"] == -24000
    assert report["summary"]["daily_nav_change_pct"] == -22.0183
    assert report["summary"]["daily_metric_type"] == "daily_nav_change"
    assert report["calculation_metadata"]["daily_nav_change"]["status"] == "estimated"
    assert report["calculation_metadata"]["daily_nav_change"]["method"] == "latest_two_snapshots"
    assert report["calculation_metadata"]["daily_nav_change"]["is_estimated"] is True
    assert report["data_quality_summary"]["severity"] == "info"
    assert report["data_quality_summary"]["user_visible_messages"]
    assert report["summary"]["realized_end_base"] == 3000
    assert report["summary"]["unrealized_end_base"] == -18000
    assert report["summary"]["max_drawdown_pct"] == -22.0183
    assert report["summary"]["flow_breakdown"] == {
        "deposit_base": 0.0,
        "withdraw_base": 0.0,
        "dividend_interest_base": 0.0,
        "fee_tax_base": 0.0,
        "transfer_in_base": 0.0,
        "transfer_out_base": 0.0,
        "other_flow_base": 0.0,
        "net_flow_base": 0.0,
    }
    assert report["summary"]["performance_breakdown"] == {
        "realized_change_base": 3000.0,
        "unrealized_change_base": -18000.0,
        "other_change_base": 0.0,
        "total_change_base": -15000.0,
    }
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
    assert report["series"][-1]["flow_breakdown"]["deposit_base"] == 0.0
    assert report["series"][-1]["performance_breakdown"] == {
        "realized_change_base": 3000.0,
        "unrealized_change_base": -18000.0,
        "other_change_base": 0.0,
        "total_change_base": -15000.0,
    }
    assert {"concentration", "holding_drawdown", "portfolio_drawdown"} <= alert_codes


def test_build_asset_performance_report_handles_previous_zero_daily_percentage():
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
            "flow_date": "2026-04-18T09:00:00",
            "flow_type": "deposit",
            "amount": 1000,
            "currency": "TWD",
            "fx_rate_to_base": 1,
        }
    ]

    report = asyncio.run(
        build_asset_performance_report(
            accounts,
            cash_entries,
            [],
            start_at="2026-04-17T00:00:00",
            end_at="2026-04-18T23:59:59",
        )
    )

    assert report["series"][0]["total_asset_value_base"] == 0
    assert report["series"][-1]["total_asset_value_base"] == 1000
    assert report["summary"]["daily_nav_change_base"] == 1000
    assert report["summary"]["daily_nav_change_pct"] is None
    assert report["summary"]["daily_metric_type"] == "daily_nav_change"
    assert "previous_total_asset_zero" in report["data_quality_flags"]
    assert report["calculation_warnings"]
    assert report["data_quality_summary"]["severity"] == "info"
    assert "previous_total_asset_zero" in report["data_quality_summary"]["debug_flags"]


def test_build_asset_performance_report_marks_daily_nav_unavailable_with_one_snapshot():
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

    report = asyncio.run(
        build_asset_performance_report(
            accounts,
            [],
            [],
            start_at="2026-04-18T00:00:00",
            end_at="2026-04-18T23:59:59",
        )
    )

    assert len(report["series"]) == 1
    assert report["summary"]["daily_nav_change_base"] is None
    assert report["summary"]["daily_metric_type"] == "unavailable"
    assert report["calculation_metadata"]["daily_nav_change"]["status"] == "unavailable"
    assert report["calculation_metadata"]["daily_nav_change"]["is_estimated"] is True
    assert "insufficient_performance_series" in report["data_quality_flags"]
    assert report["data_quality_summary"]["severity"] == "info"


def test_build_asset_performance_report_treats_initial_balances_as_baseline():
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
            "flow_date": "2026-04-10T09:00:00",
            "flow_type": "deposit",
            "amount": 10000,
            "currency": "TWD",
            "fx_rate_to_base": 1,
            "is_initial_balance": True,
        }
    ]
    trade_entries = [
        {
            "id": 11,
            "account_id": 1,
            "trade_date": "2026-04-10T10:00:00",
            "ticker": "2330.TW",
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
        }
    ]

    async def get_price_history(ticker, start_date, end_date):
        assert ticker == "2330.TW"
        return [
            {"date": "2026-04-10", "close": 100, "source": "unit-test"},
            {"date": "2026-04-18", "close": 110, "source": "unit-test"},
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

    assert report["summary"]["start_value_base"] == 10000
    assert report["summary"]["end_value_base"] == 11000
    assert report["summary"]["net_flow_base"] == 0
    assert report["summary"]["true_performance_base"] == 1000
    assert report["summary"]["true_return_pct"] == 10
    assert report["summary"]["flow_breakdown"] == {
        "deposit_base": 0.0,
        "withdraw_base": 0.0,
        "dividend_interest_base": 0.0,
        "fee_tax_base": 0.0,
        "transfer_in_base": 0.0,
        "transfer_out_base": 0.0,
        "other_flow_base": 0.0,
        "net_flow_base": 0.0,
    }
    assert report["series"][0]["date"] == "2026-04-10"
    assert report["series"][0]["total_asset_value_base"] == 10000
    assert report["series"][-1]["date"] == "2026-04-18"
    assert report["series"][-1]["total_asset_value_base"] == 11000
    assert report["series"][-1]["true_performance_base"] == 1000
    assert report["series"][-1]["flow_breakdown"]["deposit_base"] == 0.0
    assert report["monthly_heatmap"] == [
        {
            "month": "2026-04",
            "true_performance_base": 1000.0,
            "return_pct": 10.0,
        }
    ]
