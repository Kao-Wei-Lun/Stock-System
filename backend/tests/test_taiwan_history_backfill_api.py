import main


def test_taiwan_full_backfill_route_calls_manual_sync(client, monkeypatch):
    calls = []

    async def fake_sync(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "force_full": kwargs.get("force_full")}

    monkeypatch.setattr(main.market_data, "_sync_taiwan_full_history", fake_sync)

    response = client.post("/api/tw/history/backfill/full?max_tickers=3")

    assert response.status_code == 200
    assert response.json()["force_full"] is True
    assert calls[0]["reason"] == "manual-tw-full-history"
    assert calls[0]["force_full"] is True
    assert calls[0]["force_universe"] is True
    assert calls[0]["max_tickers"] == 3


def test_taiwan_missing_backfill_route_keeps_incremental_mode(client, monkeypatch):
    calls = []

    async def fake_sync(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "force_full": kwargs.get("force_full")}

    monkeypatch.setattr(main.market_data, "_sync_taiwan_full_history", fake_sync)

    response = client.post("/api/tw/history/backfill/missing?force_universe=false")

    assert response.status_code == 200
    assert response.json()["force_full"] is False
    assert calls[0]["force_full"] is False
    assert calls[0]["force_universe"] is False


def test_taiwan_coverage_route_rejects_invalid_interval(client):
    response = client.get("/api/tw/universe/coverage?interval=1h")

    assert response.status_code == 400
    assert "interval" in response.json()["detail"]
