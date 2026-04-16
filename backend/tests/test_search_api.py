import main


def test_search_route_includes_futopt_results(client, monkeypatch):
    async def fake_search_tickers(_query):
        return []

    async def fake_search_contracts(query, limit=20, session="REGULAR"):
        assert query == "TXO"
        assert limit == 20
        assert session == "REGULAR"
        return [
            {
                "ticker": "TXO20000E4",
                "name": "臺指選擇權20000買權04",
                "asset_class": "futopt",
                "instrument_type": "option",
                "exchange": "TAIFEX",
                "market": "FUTOPT",
                "source": "fubon_neo",
            }
        ]

    monkeypatch.setattr(main.market_data.db, "search_tickers", fake_search_tickers)
    monkeypatch.setattr(main.market_data, "search_taiwan_tickers", lambda _query: [])
    monkeypatch.setattr(main.market_data.fubon_futopt_provider, "search_contracts", fake_search_contracts)

    response = client.get("/api/search?q=TXO")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["ticker"] == "TXO20000E4"
    assert payload[0]["asset_class"] == "futopt"
    assert payload[0]["instrument_type"] == "option"
