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

    result = asyncio.run(
        main.hydrate_watchlist_item(
            "AAPL",
            {"id": 3, "name": "Core"},
            {"tags": ["優先候選", "Q4"]},
        )
    )

    assert result["ticker"] == "AAPL"
    assert result["close"] == 210.5
    assert result["change_pct"] == 2.68
    assert result["source"] == "yahoo_finance"
    assert result["quote_type"] == "delayed_snapshot"
    assert result["is_delayed"] is True
    assert result["quote_timestamp"] == "2026-04-02T01:15:00+00:00"
    assert result["synced_at"] == "2026-04-02T01:15:05+00:00"
    assert result["tags"] == ["優先候選", "Q4"]
    assert result["group_id"] == 3
    assert result["group_name"] == "Core"


def test_add_watchlist_item_persists_tags_via_api(client, monkeypatch):
    async def fake_get_watchlist_group(group_id):
        assert group_id == 7
        return {"id": 7, "name": "Focus"}

    async def fake_add_watchlist_item(group_id, ticker, tags=None):
        assert group_id == 7
        assert ticker == "AAPL"
        assert tags == ["優先候選", "Q4", "市場:選擇性出手"]
        return {
            "id": 15,
            "group_id": 7,
            "ticker": "AAPL",
            "tags": list(tags or []),
            "sort_order": 2,
        }

    async def fake_fetch_and_store(*args, **kwargs):
        return None

    async def fake_fetch_and_store_info(*args, **kwargs):
        return None

    async def fake_get_latest_ohlcv(ticker):
        return {
            "ticker": ticker,
            "date": "2026-04-02",
            "open": 208.0,
            "high": 212.0,
            "low": 207.0,
            "close": 210.0,
            "volume": 1200000,
            "source": "local_db",
            "updated_at": "2026-04-02T09:00:00+00:00",
        }

    async def fake_get_market_quote(ticker):
        return {
            "ticker": ticker,
            "price": 211.0,
            "prev_close": 205.0,
            "source": "local_db",
            "quote_timestamp": "2026-04-02T09:00:00+00:00",
            "synced_at": "2026-04-02T09:00:05+00:00",
            "is_delayed": True,
        }

    async def fake_get_stock_info(ticker):
        return {"name": "Apple Inc."}

    async def fake_get_prev_close(ticker):
        return 205.0

    monkeypatch.setattr(main.db, "get_watchlist_group", fake_get_watchlist_group)
    monkeypatch.setattr(main.db, "add_watchlist_item", fake_add_watchlist_item)
    monkeypatch.setattr(main.fetcher, "fetch_and_store", fake_fetch_and_store)
    monkeypatch.setattr(main.fetcher, "fetch_and_store_info", fake_fetch_and_store_info)
    monkeypatch.setattr(main.db, "get_latest_ohlcv", fake_get_latest_ohlcv)
    monkeypatch.setattr(main.db, "get_market_quote", fake_get_market_quote)
    monkeypatch.setattr(main.db, "get_stock_info", fake_get_stock_info)
    monkeypatch.setattr(main.db, "get_prev_close", fake_get_prev_close)

    response = client.post(
        "/api/watchlist/items",
        json={
            "group_id": 7,
            "ticker": "AAPL",
            "tags": ["優先候選", "Q4", "市場:選擇性出手"],
        },
    )

    assert response.status_code == 200
    assert response.json()["tags"] == ["優先候選", "Q4", "市場:選擇性出手"]


def test_hydrate_watchlist_item_ignores_quote_older_than_latest_ohlcv(monkeypatch):
    async def fake_get_latest_ohlcv(ticker):
        return {
            "ticker": ticker,
            "date": "2026-07-22",
            "open": 210.0,
            "high": 216.0,
            "low": 209.0,
            "close": 215.0,
            "volume": 2000000,
            "source": "yahoo_finance",
            "updated_at": "2026-07-22T04:05:00+00:00",
        }

    async def fake_get_market_quote(ticker):
        return {
            "ticker": ticker,
            "price": 180.0,
            "prev_close": 179.0,
            "source": "yahoo_finance",
            "quote_type": "delayed_snapshot",
            "is_delayed": True,
            "quote_timestamp": "2026-04-08T04:00:00+00:00",
            "synced_at": "2026-04-08T04:01:00+00:00",
        }

    async def fake_get_stock_info(ticker):
        return {"name": "Apple Inc."}

    async def fake_get_prev_close(ticker):
        return 212.0

    monkeypatch.setattr(main.db, "get_latest_ohlcv", fake_get_latest_ohlcv)
    monkeypatch.setattr(main.db, "get_market_quote", fake_get_market_quote)
    monkeypatch.setattr(main.db, "get_stock_info", fake_get_stock_info)
    monkeypatch.setattr(main.db, "get_prev_close", fake_get_prev_close)

    result = asyncio.run(main.hydrate_watchlist_item("AAPL", {"id": 3, "name": "Core"}))

    assert result["close"] == 215.0
    assert result["change_pct"] == 1.42
    assert result["data_origin"] == "ohlcv"
    assert result["quote_type"] == "historical_close"
    assert result["data_timestamp"].startswith("2026-07-22")
