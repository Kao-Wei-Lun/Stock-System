"""Unit tests for tw_symbol_lookup module — using mocked API data."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tw_symbol_lookup
from tw_symbol_lookup import (
    _build_ticker_aliases,
    get_taiwan_ticker_name,
    resolve_taiwan_ticker,
    search_taiwan_tickers,
)

MOCK_FINMIND_RESPONSE = {
    "status": 200,
    "data": [
        {"stock_id": "2330", "stock_name": "台積電", "type": "twse"},
        {"stock_id": "2317", "stock_name": "鴻海", "type": "twse"},
        {"stock_id": "6510", "stock_name": "精測", "type": "tpex"},
        {"stock_id": "2454", "stock_name": "聯發科", "type": "twse"},
    ],
}


def _seed_cache():
    """Seed the module cache directly to avoid HTTP calls."""
    tw_symbol_lookup._lookup_cache["expires_at"] = 9999999999.0
    tw_symbol_lookup._lookup_cache["names"] = {
        "2330": "台積電", "2330.TW": "台積電",
        "2317": "鴻海", "2317.TW": "鴻海",
        "6510": "精測", "6510.TW": "精測", "6510.TWO": "精測",
        "2454": "聯發科", "2454.TW": "聯發科",
    }
    tw_symbol_lookup._lookup_cache["canonical"] = {
        "2330": "2330.TW", "2330.TW": "2330.TW",
        "2317": "2317.TW", "2317.TW": "2317.TW",
        "6510": "6510.TWO", "6510.TW": "6510.TWO", "6510.TWO": "6510.TWO",
        "2454": "2454.TW", "2454.TW": "2454.TW",
    }
    tw_symbol_lookup._lookup_cache["rows"] = [
        {"ticker": "2330.TW", "name": "台積電", "stock_id": "2330", "market_type": "twse"},
        {"ticker": "2317.TW", "name": "鴻海", "stock_id": "2317", "market_type": "twse"},
        {"ticker": "6510.TWO", "name": "精測", "stock_id": "6510", "market_type": "tpex"},
        {"ticker": "2454.TW", "name": "聯發科", "stock_id": "2454", "market_type": "twse"},
    ]


class TestBuildTickerAliases:
    def test_twse_stock(self):
        primary, aliases = _build_ticker_aliases("2330", "twse")
        assert primary == "2330.TW"
        assert "2330" in aliases and "2330.TW" in aliases

    def test_tpex_stock(self):
        primary, aliases = _build_ticker_aliases("6510", "tpex")
        assert primary == "6510.TWO"
        assert "6510.TWO" in aliases

    def test_emerging_stock(self):
        primary, aliases = _build_ticker_aliases("1234", "emerging")
        assert primary == "1234.TWO"


class TestGetTaiwanTickerName:
    def setup_method(self):
        _seed_cache()

    def test_by_ticker(self):
        assert get_taiwan_ticker_name("2330.TW") == "台積電"

    def test_by_stock_id(self):
        assert get_taiwan_ticker_name("2330") == "台積電"

    def test_case_insensitive(self):
        assert get_taiwan_ticker_name("2330.tw") == "台積電"

    def test_unknown_returns_none(self):
        assert get_taiwan_ticker_name("9999.TW") is None

    def test_empty_input(self):
        assert get_taiwan_ticker_name("") is None
        assert get_taiwan_ticker_name(None) is None


class TestResolveTaiwanTicker:
    def setup_method(self):
        _seed_cache()

    def test_resolves_stock_id(self):
        assert resolve_taiwan_ticker("2330") == "2330.TW"

    def test_tpex_resolves_to_two(self):
        assert resolve_taiwan_ticker("6510") == "6510.TWO"

    def test_already_canonical(self):
        assert resolve_taiwan_ticker("2330.TW") == "2330.TW"

    def test_unknown_returns_none(self):
        assert resolve_taiwan_ticker("0000") is None


class TestSearchTaiwanTickers:
    def setup_method(self):
        _seed_cache()

    def test_search_by_id(self):
        results = search_taiwan_tickers("2330")
        assert len(results) >= 1
        assert results[0]["ticker"] == "2330.TW"

    def test_search_by_name(self):
        results = search_taiwan_tickers("台積")
        assert len(results) >= 1
        assert any(r["name"] == "台積電" for r in results)

    def test_search_limit(self):
        results = search_taiwan_tickers("2", limit=2)
        assert len(results) <= 2

    def test_search_empty_query(self):
        assert search_taiwan_tickers("") == []

    def test_search_no_match(self):
        results = search_taiwan_tickers("ZZZZZZZ")
        assert results == []

    def test_exact_match_sorts_first(self):
        results = search_taiwan_tickers("2330")
        assert results[0]["ticker"] == "2330.TW"


class TestLoadLookupFromAPI:
    def test_api_response_parsed_correctly(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_FINMIND_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        # Force cache expiry
        tw_symbol_lookup._lookup_cache["expires_at"] = 0
        tw_symbol_lookup._lookup_cache["names"] = {}

        with patch("tw_symbol_lookup.requests.get", return_value=mock_resp):
            names, canonical, rows = tw_symbol_lookup._load_lookup(force=True)

        assert "2330.TW" in names
        assert names["2330.TW"] == "台積電"
        assert canonical["6510"] == "6510.TWO"
        assert len(rows) == 4

    def test_api_failure_uses_cache(self):
        _seed_cache()
        tw_symbol_lookup._lookup_cache["expires_at"] = 0  # expired but has data

        with patch("tw_symbol_lookup.requests.get", side_effect=Exception("network error")):
            names, _, _ = tw_symbol_lookup._load_lookup()

        assert "2330.TW" in names  # should still have cached data
