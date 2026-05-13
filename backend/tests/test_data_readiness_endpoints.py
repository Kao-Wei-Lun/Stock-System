import main


def test_analysis_kline_coverage_route(client, monkeypatch):
    async def get_tw_analysis_kline_coverage(interval="1d"):
        return {
            "interval": interval,
            "expected_latest_date": "2026-05-13",
            "newest_latest_date": "2026-05-13",
            "universe_count": 2000,
            "latest_covered_count": 1680,
            "latest_coverage_pct": 84.0,
        }

    monkeypatch.setattr(main.db, "get_tw_analysis_kline_coverage", get_tw_analysis_kline_coverage)

    response = client.get("/api/tw/universe/analysis-coverage?interval=1d")

    assert response.status_code == 200
    payload = response.json()
    assert payload["interval"] == "1d"
    assert payload["latest_coverage_pct"] == 84.0


def test_taiwan_chip_coverage_route_precedes_ticker_route(client, monkeypatch):
    async def get_taiwan_chip_coverage(on_or_before=None):
        return {
            "resolved_date": on_or_before,
            "latest_date": on_or_before,
            "universe_count": 2000,
            "latest_covered_count": 1900,
            "coverage_pct": 95.0,
        }

    monkeypatch.setattr(main.db, "get_taiwan_chip_coverage", get_taiwan_chip_coverage)

    response = client.get("/api/tw/chips/coverage?date=2026-05-13")

    assert response.status_code == 200
    payload = response.json()
    assert payload["resolved_date"] == "2026-05-13"
    assert payload["coverage_pct"] == 95.0
