import pytest

import fubon_data_fetcher
from fubon_data_fetcher import HybridDataFetcher


class StubYahooFetcher:
    def __init__(self):
        self.fetch_calls = []
        self.info_calls = []
        self.quote_calls = []

    async def fetch_and_store(self, ticker, period="2y", interval="1d", include_info=False):
        self.fetch_calls.append(
            {"ticker": ticker, "period": period, "interval": interval, "include_info": include_info}
        )
        return 77

    async def fetch_and_store_info(self, ticker):
        self.info_calls.append(ticker)
        return {"ticker": ticker}

    async def fetch_realtime_quote(self, ticker):
        self.quote_calls.append(ticker)
        return {"ticker": ticker, "source": "yahoo_finance", "price": 100}


class StubFubonManager:
    def __init__(self):
        self.connected = True
        self.history_calls = []
        self.intraday_calls = []
        self.quote_calls = []

    async def fetch_stock_historical_candles(self, symbol, **kwargs):
        self.history_calls.append({"symbol": symbol, **kwargs})
        return {
            "symbol": symbol,
            "data": [
                {"date": "2026-04-09", "open": 810, "high": 820, "low": 805, "close": 818, "volume": 1234},
                {"date": "2026-04-10", "open": 818, "high": 825, "low": 812, "close": 823, "volume": 2345},
            ],
        }

    async def fetch_stock_intraday_candles(self, symbol, **kwargs):
        self.intraday_calls.append({"symbol": symbol, **kwargs})
        return {
            "symbol": symbol,
            "data": [
                {
                    "date": "2026-04-11T09:00:00.000+08:00",
                    "open": 820,
                    "high": 821,
                    "low": 819,
                    "close": 820,
                    "volume": 100,
                },
            ],
        }

    async def fetch_stock_quote(self, symbol):
        self.quote_calls.append(symbol)
        return {
            "symbol": symbol,
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


@pytest.mark.anyio
async def test_hybrid_fetcher_uses_fubon_for_taiwan_daily_history(monkeypatch):
    yahoo = StubYahooFetcher()
    manager = StubFubonManager()
    fetcher = HybridDataFetcher(yahoo, manager)
    stored = {}

    async def delete_ohlcv_range(ticker, interval, start_date, end_date):
        stored["deleted"] = (ticker, interval, start_date, end_date)
        return 2

    async def upsert_ohlcv_batch(ticker, rows, interval):
        stored["upsert"] = (ticker, interval, rows)
        return len(rows)

    async def log_sync(ticker, status, count, message):
        stored["log"] = (ticker, status, count, message)

    monkeypatch.setattr(fubon_data_fetcher.db, "delete_ohlcv_range", delete_ohlcv_range)
    monkeypatch.setattr(fubon_data_fetcher.db, "upsert_ohlcv_batch", upsert_ohlcv_batch)
    monkeypatch.setattr(fubon_data_fetcher.db, "log_sync", log_sync)

    count = await fetcher.fetch_and_store("2330.TW", period="1y", interval="1d", include_info=True)

    assert count == 2
    assert manager.history_calls[0]["symbol"] == "2330"
    assert stored["upsert"][0] == "2330.TW"
    assert stored["upsert"][1] == "1d"
    assert stored["upsert"][2][0]["source"] == "fubon_neo"
    assert yahoo.info_calls == ["2330.TW"]
    assert yahoo.fetch_calls == []


@pytest.mark.anyio
async def test_hybrid_fetcher_uses_fubon_for_taiwan_intraday_history(monkeypatch):
    yahoo = StubYahooFetcher()
    manager = StubFubonManager()
    fetcher = HybridDataFetcher(yahoo, manager)

    async def upsert_ohlcv_batch(_ticker, rows, _interval):
        return len(rows)

    async def log_sync(*_args, **_kwargs):
        return None

    monkeypatch.setattr(fubon_data_fetcher.db, "upsert_ohlcv_batch", upsert_ohlcv_batch)
    monkeypatch.setattr(fubon_data_fetcher.db, "log_sync", log_sync)

    count = await fetcher.fetch_and_store("2330", period="1d", interval="1m", include_info=False)

    assert count == 1
    assert manager.intraday_calls[0]["symbol"] == "2330"
    assert manager.intraday_calls[0]["timeframe"] == "1"
    assert yahoo.fetch_calls == []


@pytest.mark.anyio
async def test_hybrid_fetcher_falls_back_to_yahoo_for_unsupported_intervals():
    yahoo = StubYahooFetcher()
    manager = StubFubonManager()
    fetcher = HybridDataFetcher(yahoo, manager)

    count = await fetcher.fetch_and_store("2330.TW", period="5d", interval="2m", include_info=False)

    assert count == 77
    assert yahoo.fetch_calls[0]["ticker"] == "2330.TW"
    assert manager.history_calls == []
    assert manager.intraday_calls == []


@pytest.mark.anyio
async def test_hybrid_fetcher_uses_fubon_for_taiwan_realtime_quote():
    yahoo = StubYahooFetcher()
    manager = StubFubonManager()
    fetcher = HybridDataFetcher(yahoo, manager)

    quote = await fetcher.fetch_realtime_quote("2330")

    assert quote["ticker"] == "2330.TW"
    assert quote["source"] == "fubon_neo"
    assert yahoo.quote_calls == []
