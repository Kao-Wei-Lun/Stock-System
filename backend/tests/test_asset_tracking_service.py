import asyncio

from asset_tracking_service import build_asset_portfolio_snapshot


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
            fetch_quote=fetch_quote,
        )
    )

    assert snapshot["summary"]["cash_total_base"] == 98990
    assert snapshot["summary"]["market_value_total_base"] == 1200
    assert snapshot["summary"]["total_asset_value_base"] == 100190
    assert snapshot["summary"]["unrealized_total_base"] == 190
    assert snapshot["summary"]["quote_gap_count"] == 0
    assert snapshot["summary"]["account_count"] == 2
    assert snapshot["holdings"][0]["ticker"] == "2330.TW"
    assert snapshot["holdings"][0]["market_value_base"] == 1200
    assert snapshot["holdings"][0]["unrealized_pnl_base"] == 190
    assert snapshot["allocation"]["items"][0]["key"] == "Main Broker"
    assert snapshot["allocation"]["items"][0]["value_base"] == 100190
