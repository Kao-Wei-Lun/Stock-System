import asyncio

import main


def test_hydrate_watchlist_item_prefers_local_quote_metadata(monkeypatch):
    async def fake_get_latest_ohlcv(ticker):
        assert ticker == "AAPL"
        return {
            "ticker": ticker,
            "date": "2026-04-01",
            "open": 205.0,
            "high": 208.0,
            "low": 203.5,
            "close": 206.0,
            "volume": 1000000,
            "source": "yahoo_finance",
            "updated_at": "2026-04-02T01:15:05+00:00",
        }

    async def fake_get_market_quote(ticker):
        assert ticker == "AAPL"
        return {
            "ticker": ticker,
            "price": 210.5,
            "open": 208.0,
            "high": 212.0,
            "low": 207.2,
            "prev_close": 205.0,
            "volume": 1234567,
            "source": "yahoo_finance",
            "quote_type": "delayed_snapshot",
            "is_delayed": True,
            "quote_timestamp": "2026-04-02T01:15:00+00:00",
            "synced_at": "2026-04-02T01:15:05+00:00",
        }

    async def fake_get_stock_info(ticker):
        return {"name": "Apple Inc."}

    async def fake_get_prev_close(ticker):
        return 204.0

    monkeypatch.setattr(main.db, "get_latest_ohlcv", fake_get_latest_ohlcv)
    monkeypatch.setattr(main.db, "get_market_quote", fake_get_market_quote)
    monkeypatch.setattr(main.db, "get_stock_info", fake_get_stock_info)
    monkeypatch.setattr(main.db, "get_prev_close", fake_get_prev_close)

    result = asyncio.run(main.hydrate_watchlist_item("AAPL", {"id": 3, "name": "Core"}))

    assert result["ticker"] == "AAPL"
    assert result["close"] == 210.5
    assert result["change_pct"] == 2.68
    assert result["source"] == "yahoo_finance"
    assert result["quote_type"] == "delayed_snapshot"
    assert result["is_delayed"] is True
    assert result["quote_timestamp"] == "2026-04-02T01:15:00+00:00"
    assert result["synced_at"] == "2026-04-02T01:15:05+00:00"
    assert result["group_id"] == 3
    assert result["group_name"] == "Core"
