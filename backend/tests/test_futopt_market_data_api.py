import main


def test_futopt_ohlc_route_returns_502_when_provider_raises(client, monkeypatch):
    async def fake_fetch_intraday_ohlc(_symbol, *, period="1d", interval="1m"):
        raise RuntimeError("upstream futopt failure")

    monkeypatch.setattr(main.market_data.fubon_futopt_provider, "fetch_intraday_ohlc", fake_fetch_intraday_ohlc)

    response = client.get("/api/futopt/ohlc/MXFE6?period=1d&interval=1m")

    assert response.status_code == 502
    assert "upstream futopt failure" in response.json()["detail"]
