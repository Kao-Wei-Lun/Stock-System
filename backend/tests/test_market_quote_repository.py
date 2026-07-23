import pytest

from repositories.market_data import MarketDataMixin


class QuoteRepositoryProbe(MarketDataMixin):
    def __init__(self):
        self.executions = []
        self.fetches = 0

    async def _execute(self, sql, params=()):
        self.executions.append((sql, params))
        return 1

    async def get_market_quote(self, _ticker):
        self.fetches += 1
        raise AssertionError("upsert must not issue a read-after-write query")


@pytest.mark.anyio
async def test_market_quote_upsert_is_single_query_and_preserves_partial_fields():
    repository = QuoteRepositoryProbe()

    result = await repository.upsert_market_quote(
        {
            "ticker": "2330.TW",
            "source": "fubon_neo",
            "quote_type": "realtime",
            "is_delayed": False,
            "price": 1000,
            "quote_timestamp": "2026-07-23T01:00:00+00:00",
        }
    )

    assert len(repository.executions) == 1
    assert repository.fetches == 0
    sql, params = repository.executions[0]
    assert "COALESCE(`incoming`.`open`, `market_quotes_latest`.`open`)" in sql
    assert "GREATEST(`market_quotes_latest`.`high`, `incoming`.`high`)" in sql
    assert "JSON_MERGE_PATCH" in sql
    assert result["ticker"] == "2330.TW"
    assert result["price"] == 1000
    assert '"open"' not in params[-1]
