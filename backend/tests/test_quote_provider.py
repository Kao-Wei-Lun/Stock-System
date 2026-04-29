import pytest

import fubon_symbols
from fubon_quote_provider import (
    FubonQuoteProvider,
    HybridQuoteProvider,
    build_fubon_quote_payload,
    tw_ticker_to_fubon,
)
from quote_provider import YahooFinanceQuoteProvider


class StubFetcher:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def fetch_realtime_quote(self, ticker):
        self.calls.append(ticker)
        return self.payload


class StubFubonManager:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def fetch_stock_quote(self, symbol):
        self.calls.append(symbol)
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


@pytest.mark.anyio
async def test_fubon_quote_provider_fetches_taiwan_stock_quote():
    manager = StubFubonManager(
        {
            "symbol": "2330",
            "market": "TSE",
            "exchange": "TWSE",
            "name": "台積電",
            "previousClose": 812,
            "openPrice": 820,
            "highPrice": 825,
            "lowPrice": 818,
            "closePrice": 823,
            "change": 11,
            "changePercent": 1.35,
            "lastUpdated": 1712805300000000,
            "bids": [{"price": 822, "size": 81}],
            "asks": [{"price": 823, "size": 42}],
            "total": {"tradeVolume": 87654},
        }
    )
    provider = FubonQuoteProvider(manager)

    quote = await provider.fetch_quote("2330")

    assert manager.calls == ["2330"]
    assert quote["ticker"] == "2330.TW"
    assert quote["source"] == "fubon_neo"
    assert quote["quote_type"] == "realtime"
    assert quote["is_delayed"] is False
    assert quote["bid"] == 822
    assert quote["ask"] == 823
    assert quote["bid_size"] == 81
    assert quote["ask_size"] == 42
    assert quote["volume"] == 87654


@pytest.mark.anyio
async def test_hybrid_quote_provider_does_not_fallback_to_yahoo_for_taiwan_quote():
    fubon_manager = StubFubonManager(None)
    fubon_provider = FubonQuoteProvider(fubon_manager)
    yahoo_fetcher = StubFetcher(
        {
            "ticker": "2330.TW",
            "price": 811,
            "source": "yahoo_finance",
            "quote_timestamp": "2026-04-11T01:00:00+00:00",
        }
    )
    yahoo_provider = YahooFinanceQuoteProvider(yahoo_fetcher)
    provider = HybridQuoteProvider(fubon_provider, yahoo_provider)

    quote = await provider.fetch_quote("2330")

    assert fubon_manager.calls == ["2330"]
    assert yahoo_fetcher.calls == []
    assert quote is None


@pytest.mark.anyio
async def test_hybrid_quote_provider_uses_yahoo_for_us_quote():
    fubon_manager = StubFubonManager(None)
    fubon_provider = FubonQuoteProvider(fubon_manager)
    yahoo_fetcher = StubFetcher(
        {
            "ticker": "AAPL",
            "price": 210.5,
            "source": "yahoo_finance",
            "quote_timestamp": "2026-04-11T20:00:00+00:00",
        }
    )
    yahoo_provider = YahooFinanceQuoteProvider(yahoo_fetcher)
    provider = HybridQuoteProvider(fubon_provider, yahoo_provider)

    quote = await provider.fetch_quote("AAPL")

    assert fubon_manager.calls == []
    assert yahoo_fetcher.calls == ["AAPL"]
    assert quote["source"] == "yahoo_finance"
    assert quote["is_delayed"] is True


def test_tw_ticker_to_fubon_converts_supported_taiwan_tickers(monkeypatch):
    mapping = {
        "2330": "2330.TW",
        "2330.TW": "2330.TW",
        "2646": "2646.TWO",
        "2646.TWO": "2646.TWO",
    }
    monkeypatch.setattr(
        fubon_symbols,
        "resolve_taiwan_ticker",
        lambda ticker: mapping.get(str(ticker or "").strip().upper()),
    )

    assert tw_ticker_to_fubon("2330") == "2330"
    assert tw_ticker_to_fubon("2330.TW") == "2330"
    assert tw_ticker_to_fubon("2646.TWO") == "2646"
    assert tw_ticker_to_fubon("AAPL") is None


def test_build_fubon_quote_payload_accepts_speed_mode_trade_messages():
    payload = build_fubon_quote_payload(
        "2330.TW",
        {
            "symbol": "2330",
            "market": "TSE",
            "exchange": "TWSE",
            "price": 568,
            "bid": 567,
            "ask": 568,
            "volume": 54538,
            "time": 1685338200000000,
        },
    )

    assert payload["ticker"] == "2330.TW"
    assert payload["price"] == 568
    assert payload["bid"] == 567
    assert payload["ask"] == 568
    assert payload["volume"] == 54538
    assert payload["quote_timestamp"] is not None


def test_build_fubon_quote_payload_ignores_non_positive_price_fields():
    payload = build_fubon_quote_payload(
        "2330.TW",
        {
            "symbol": "2330",
            "market": "TSE",
            "exchange": "TWSE",
            "previousClose": 560,
            "openPrice": 0,
            "highPrice": 571,
            "lowPrice": 0,
            "closePrice": 568,
            "changePercent": 1.42,
            "lastUpdated": 1712805300000000,
        },
    )

    assert payload["price"] == 568
    assert payload["open"] is None
    assert payload["high"] == 571
    assert payload["low"] is None
    assert payload["prev_close"] == 560
    assert payload["change_pct"] == pytest.approx(1.42)
