import main
from fubon_provider import FubonMarketdataAuthenticationError


def test_fubon_snapshot_route_returns_provider_payload(client, monkeypatch):
    async def fake_fetch_snapshot(market, *, refresh=False):
        assert market == "TSE"
        assert refresh is True
        return {
            "market": "TSE",
            "date": "2026-04-11",
            "time": "133000",
            "summary": {"count": 2, "advancers": 1, "decliners": 1, "unchanged": 0, "total_trade_value": 30},
            "data": [
                {"ticker": "2330.TW", "name": "TSMC", "change_pct": 1.2},
                {"ticker": "2317.TW", "name": "Hon Hai", "change_pct": -0.8},
            ],
        }

    monkeypatch.setattr(main.market_data.fubon_market_snapshot_provider, "fetch_snapshot", fake_fetch_snapshot)

    response = client.get("/api/fubon/snapshot/TSE?refresh=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "TSE"
    assert payload["summary"]["count"] == 2
    assert payload["data"][0]["ticker"] == "2330.TW"


def test_fubon_movers_route_passes_query_arguments(client, monkeypatch):
    async def fake_fetch_movers(market, *, direction="up", change="percent", limit=10, refresh=False):
        assert market == "OTC"
        assert direction == "down"
        assert change == "percent"
        assert limit == 5
        assert refresh is False
        return {
            "market": "OTC",
            "direction": "down",
            "change": "percent",
            "summary": {"count": 1},
            "data": [{"ticker": "6488.TWO", "name": "GlobalWafers", "change_pct": -6.1}],
        }

    monkeypatch.setattr(main.market_data.fubon_market_snapshot_provider, "fetch_movers", fake_fetch_movers)

    response = client.get("/api/fubon/movers/OTC?direction=down&change=percent&limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["direction"] == "down"
    assert payload["data"][0]["ticker"] == "6488.TWO"


def test_fubon_snapshot_route_rejects_invalid_market(client, monkeypatch):
    async def fake_fetch_snapshot(_market, *, refresh=False):
        raise ValueError("Unsupported market 'US'")

    monkeypatch.setattr(main.market_data.fubon_market_snapshot_provider, "fetch_snapshot", fake_fetch_snapshot)

    response = client.get("/api/fubon/snapshot/US")

    assert response.status_code == 400
    assert "Unsupported market" in response.json()["detail"]


def test_fubon_snapshot_route_returns_503_for_authentication_error(client, monkeypatch):
    async def fake_fetch_snapshot(_market, *, refresh=False):
        raise FubonMarketdataAuthenticationError("Fubon marketdata authentication is invalid or expired")

    monkeypatch.setattr(main.market_data.fubon_market_snapshot_provider, "fetch_snapshot", fake_fetch_snapshot)

    response = client.get("/api/fubon/snapshot/TSE")

    assert response.status_code == 503
    assert "authentication" in response.json()["detail"]
