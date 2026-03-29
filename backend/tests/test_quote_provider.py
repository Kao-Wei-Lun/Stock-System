import pytest

from quote_provider import YahooFinanceQuoteProvider


class StubFetcher:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def fetch_realtime_quote(self, ticker):
        self.calls.append(ticker)
        return self.payload


@pytest.mark.anyio
async def test_yahoo_quote_provider_normalizes_provider_metadata():
    fetcher = StubFetcher(
        {
            "ticker": "AAPL",
            "price": 210.5,
            "quote_timestamp": "2026-03-29T04:00:00+00:00",
        }
    )
    provider = YahooFinanceQuoteProvider(fetcher)

    quote = await provider.fetch_quote("aapl")

    assert fetcher.calls == ["AAPL"]
    assert quote["ticker"] == "AAPL"
    assert quote["source"] == "yahoo_finance"
    assert quote["quote_type"] == "delayed_snapshot"
    assert quote["is_delayed"] is True


@pytest.mark.anyio
async def test_yahoo_quote_provider_returns_none_when_fetcher_has_no_quote():
    fetcher = StubFetcher(None)
    provider = YahooFinanceQuoteProvider(fetcher)

    quote = await provider.fetch_quote("2330")

    assert fetcher.calls == ["2330.TW"]
    assert quote is None
