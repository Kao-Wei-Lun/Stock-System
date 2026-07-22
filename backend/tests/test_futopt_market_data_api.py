import main


def test_search_dynamic_futures_alias_returns_resolved_near_month(client, monkeypatch):
    async def fake_search_tickers(_query):
        return []

    async def fake_resolve_contract(symbol):
        assert symbol == "*TXFF"
        return {"requested_symbol": symbol, "resolved_symbol": "TXFE6"}

    async def fake_search_contracts(_query, limit=20):
        return []

    monkeypatch.setattr(main.market_data.db, "search_tickers", fake_search_tickers)
    monkeypatch.setattr(main.market_data.fubon_futopt_provider, "resolve_contract", fake_resolve_contract)
    monkeypatch.setattr(main.market_data.fubon_futopt_provider, "search_contracts", fake_search_contracts)

    response = client.get("/api/search?q=%2ATXFF")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["ticker"] == "*TXFF"
    assert payload[0]["resolved_symbol"] == "TXFE6"
    assert "目前 TXFE6" in payload[0]["name"]


def test_futopt_history_status_exposes_recorder_health(client):
    response = client.get("/api/futopt/history/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["interval"] == "1m"
    assert {"TXF", "TMF"} <= set(payload["symbols"])
    assert payload["queue_capacity"] >= 10


def test_futopt_ohlc_route_returns_persisted_rows_when_provider_raises(client, monkeypatch):
    async def fake_fetch_intraday_ohlc(_symbol, *, period="1d", interval="1m"):
        raise RuntimeError("upstream futopt failure")

    async def fake_get_ohlcv(ticker, period="1d", interval="1m"):
        assert ticker == "MXFE6"
        return [
            {
                "date": "2026-04-11T09:00:00+08:00",
                "open": 20550,
                "high": 20580,
                "low": 20540,
                "close": 20570,
                "volume": 1200,
                "source": "fubon_neo_ws",
            }
        ]

    monkeypatch.setattr(main.market_data.fubon_futopt_provider, "fetch_intraday_ohlc", fake_fetch_intraday_ohlc)
    monkeypatch.setattr(main.market_data.db, "get_ohlcv", fake_get_ohlcv)

    response = client.get("/api/futopt/ohlc/MXFE6?period=1d&interval=1m")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_source"] == "database"
    assert payload["sync_status"] == "failed"
    assert payload["row_count"] == 1
    assert "upstream futopt failure" in payload["sync_error"]


def test_futopt_ohlc_route_returns_502_when_provider_and_database_have_no_data(client, monkeypatch):
    async def fake_fetch_intraday_ohlc(_symbol, *, period="1d", interval="1m"):
        raise RuntimeError("upstream futopt failure")

    async def fake_get_ohlcv(_ticker, period="1d", interval="1m"):
        return []

    monkeypatch.setattr(main.market_data.fubon_futopt_provider, "fetch_intraday_ohlc", fake_fetch_intraday_ohlc)
    monkeypatch.setattr(main.market_data.db, "get_ohlcv", fake_get_ohlcv)

    response = client.get("/api/futopt/ohlc/MXFE6?period=1d&interval=1m")

    assert response.status_code == 502
    assert "upstream futopt failure" in response.json()["detail"]


def test_futopt_sync_route_persists_alias_and_resolved_contract(client, monkeypatch):
    upserts = []
    resolutions = []

    async def fake_fetch_intraday_ohlc(symbol, *, period="1d", interval="1m"):
        assert symbol == "TMF"
        assert period == "1d"
        assert interval == "1m"
        return {
            "ticker": "TMFE6",
            "requested_symbol": "TMF",
            "resolved_symbol": "TMFE6",
            "contract_type": "I",
            "end_date": "2026-05-20",
            "instrument_type": "future",
            "interval": "1m",
            "data": [
                {
                    "date": "2026-04-11T09:00:00+08:00",
                    "open": 20550,
                    "high": 20580,
                    "low": 20540,
                    "close": 20570,
                    "volume": 1200,
                    "adj_close": 20570,
                    "source": "fubon_neo",
                }
            ],
        }

    async def fake_upsert_ohlcv_batch(ticker, rows, interval="1d"):
        upserts.append({"ticker": ticker, "rows": rows, "interval": interval})
        return len(rows)

    async def fake_save_contract_resolution(data):
        resolutions.append(data)
        return len(resolutions)

    monkeypatch.setattr(main.market_data.fubon_futopt_provider, "fetch_intraday_ohlc", fake_fetch_intraday_ohlc)
    monkeypatch.setattr(main.market_data.db, "upsert_ohlcv_batch", fake_upsert_ohlcv_batch)
    monkeypatch.setattr(main.market_data.db, "save_paper_trading_contract_resolution", fake_save_contract_resolution)

    response = client.post("/api/futopt/sync/TMF?period=1d&interval=1m")

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_symbol"] == "TMF"
    assert payload["resolved_symbol"] == "TMFE6"
    assert payload["stored_tickers"] == ["TMF", "TMFE6"]
    assert [item["ticker"] for item in upserts] == ["TMF", "TMFE6"]
    assert all(item["interval"] == "1m" for item in upserts)
    assert {item["requested_symbol"] for item in resolutions} == {"TMF", "TMFE6"}
