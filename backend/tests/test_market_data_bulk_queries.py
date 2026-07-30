import pytest

from repositories.market_data import MarketDataMixin


class ProbeRepository(MarketDataMixin):
    def __init__(self):
        self.calls = []

    async def _fetchall(self, sql, params=()):
        self.calls.append((sql, params))
        if "UNION ALL" in sql or "FROM ((SELECT" in " ".join(sql.split()):
            return [
                {"ticker": "AAPL", "date": "2026-07-22", "close": 210, "_row_number": 1},
                {"ticker": "AAPL", "date": "2026-07-21", "close": 208, "_row_number": 2},
            ]
        if "market_quotes_latest" in sql:
            return [{"ticker": "AAPL", "price": 211, "payload_json": "{}"}]
        return [{"ticker": "AAPL", "name": "Apple"}]


@pytest.mark.anyio
async def test_bulk_market_queries_normalize_deduplicate_and_group():
    repository = ProbeRepository()

    recent = await repository.get_recent_ohlcv_many(["aapl", "AAPL", ""], per_ticker_limit=2)
    quotes = await repository.get_market_quotes(["aapl", "AAPL"])
    info = await repository.get_stock_info_many(["aapl"])

    assert [row["close"] for row in recent["AAPL"]] == [210, 208]
    assert quotes["AAPL"]["price"] == 211
    assert info["AAPL"]["name"] == "Apple"
    assert repository.calls[0][1] == ("AAPL", "1d", 2)
    assert repository.calls[1][1] == ("AAPL",)
    assert repository.calls[2][1] == ("AAPL",)


@pytest.mark.anyio
async def test_bulk_market_queries_skip_database_for_empty_input():
    repository = ProbeRepository()

    assert await repository.get_recent_ohlcv_many([]) == {}
    assert await repository.get_market_quotes([]) == {}
    assert await repository.get_stock_info_many([]) == {}
    assert repository.calls == []


@pytest.mark.anyio
async def test_analysis_coverage_uses_indexed_latest_rows_and_excludes_non_stock_symbols():
    class CoverageRepository(MarketDataMixin):
        async def list_tw_equity_universe(self, **_kwargs):
            return [
                {"ticker": "2330.TW", "symbol": "2330"},
                {"ticker": "2317.TW", "symbol": "2317"},
                {"ticker": "006208.TW", "symbol": "006208"},
            ]

        async def get_latest_ohlcv_many(self, tickers, interval="1d"):
            assert tickers == ["2330.TW", "2317.TW"]
            assert interval == "1d"
            return {
                "2330.TW": {"date": "2026-07-30"},
                "2317.TW": {"date": "2026-07-29"},
            }

    coverage = await CoverageRepository().get_tw_analysis_kline_coverage("1d")

    assert coverage == {
        "universe_count": 2,
        "covered_count": 2,
        "latest_covered_count": 1,
        "oldest_latest_date": "2026-07-29",
        "newest_latest_date": "2026-07-30",
        "expected_latest_date": "2026-07-30",
        "ohlcv_rows": None,
        "coverage_pct": 100.0,
        "latest_coverage_pct": 50.0,
        "interval": "1d",
    }
