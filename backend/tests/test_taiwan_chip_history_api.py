import main


def test_taiwan_chip_history_route_returns_series_stats_and_prices(client, monkeypatch):
    history_rows = [
        {
            "id": 3,
            "ticker": "2330.TW",
            "snapshot_date": "2026-04-02",
            "foreign_net_buy_sell": 16000,
            "investment_trust_net_buy_sell": 1500,
            "dealer_net_buy_sell": 500,
            "institutional_net_buy_sell": 18000,
            "source": "twse_t86",
        },
        {
            "id": 2,
            "ticker": "2330.TW",
            "snapshot_date": "2026-04-01",
            "foreign_net_buy_sell": 12000,
            "investment_trust_net_buy_sell": -500,
            "dealer_net_buy_sell": 1000,
            "institutional_net_buy_sell": 12500,
            "source": "twse_t86",
        },
        {
            "id": 1,
            "ticker": "2330.TW",
            "snapshot_date": "2026-03-31",
            "foreign_net_buy_sell": -4000,
            "investment_trust_net_buy_sell": 250,
            "dealer_net_buy_sell": -1000,
            "institutional_net_buy_sell": -4750,
            "source": "twse_t86",
        },
    ]
    ohlcv_rows = [
        {"date": "2026-03-31", "close": 946, "volume": 120000},
        {"date": "2026-04-01", "close": 952, "volume": 128000},
        {"date": "2026-04-02", "close": 965, "volume": 131000},
    ]

    async def list_taiwan_chip_snapshots(ticker=None, limit=30):
        items = [item for item in history_rows if not ticker or item["ticker"] == ticker]
        return items[:limit]

    async def get_recent_ohlcv_rows(ticker, limit=260, interval="1d"):
        if ticker != "2330.TW" or interval != "1d":
            return []
        return ohlcv_rows[-limit:]

    monkeypatch.setattr(main.db, "list_taiwan_chip_snapshots", list_taiwan_chip_snapshots)
    monkeypatch.setattr(main.db, "get_recent_ohlcv_rows", get_recent_ohlcv_rows)

    response = client.get("/api/tw/chips/2330/history?days=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "2330.TW"
    assert payload["days"] == 20
    assert payload["resolved_range"] == {"from": "2026-03-31", "to": "2026-04-02"}
    assert [item["snapshot_date"] for item in payload["series"]] == ["2026-03-31", "2026-04-01", "2026-04-02"]
    assert payload["latest"]["snapshot_date"] == "2026-04-02"
    assert payload["latest"]["summary"]["bias"] == "bullish"
    assert payload["stats"]["foreign_5d_sum"] == 24000
    assert payload["stats"]["institutional_20d_sum"] == 25750
    assert payload["stats"]["institutional_streak_days"] == 2
    assert payload["stats"]["institutional_streak_direction"] == "buy"
    assert [item["date"] for item in payload["price_series"]] == ["2026-03-31", "2026-04-01", "2026-04-02"]
    assert payload["price_series"][-1]["close"] == 965


def test_taiwan_chip_history_route_returns_404_when_unavailable(client, monkeypatch):
    async def list_taiwan_chip_snapshots(ticker=None, limit=30):
        return []

    async def sync_ticker_snapshot(ticker, target_date=None, force_refresh=False):
        return None

    async def get_recent_ohlcv_rows(ticker, limit=260, interval="1d"):
        return []

    monkeypatch.setattr(main.db, "list_taiwan_chip_snapshots", list_taiwan_chip_snapshots)
    monkeypatch.setattr(main.db, "get_recent_ohlcv_rows", get_recent_ohlcv_rows)
    monkeypatch.setattr(main.taiwan_chip_provider, "sync_ticker_snapshot", sync_ticker_snapshot)

    response = client.get("/api/tw/chips/2330/history?days=20")

    assert response.status_code == 404
    assert "No Taiwan chip history available" in response.json()["detail"]
