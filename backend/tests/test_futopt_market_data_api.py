import main


def test_futopt_ohlc_route_returns_502_when_provider_raises(client, monkeypatch):
    async def fake_fetch_intraday_ohlc(_symbol, *, period="1d", interval="1m"):
        raise RuntimeError("upstream futopt failure")

    monkeypatch.setattr(main.market_data.fubon_futopt_provider, "fetch_intraday_ohlc", fake_fetch_intraday_ohlc)

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
