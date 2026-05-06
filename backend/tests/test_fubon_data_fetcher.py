from datetime import date

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


class ListingAfterFirstChunkFubonManager(StubFubonManager):
    async def fetch_stock_historical_candles(self, symbol, **kwargs):
        self.history_calls.append({"symbol": symbol, **kwargs})
        if len(self.history_calls) == 1:
            raise RuntimeError(
                "[Fugle API Error] Resource Not Found\n"
                "Status: 404\n"
                "Response: {\"statusCode\":404,\"message\":\"Resource Not Found\"}"
            )
        return {
            "symbol": symbol,
            "data": [
                {"date": "2026-04-09", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 1234},
            ],
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
    assert yahoo.info_calls == []
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
async def test_hybrid_fetcher_blocks_yahoo_for_unsupported_taiwan_intervals(monkeypatch):
    yahoo = StubYahooFetcher()
    manager = StubFubonManager()
    fetcher = HybridDataFetcher(yahoo, manager)
    stored = {}

    async def log_sync(ticker, status, count, message):
        stored["log"] = (ticker, status, count, message)

    monkeypatch.setattr(fubon_data_fetcher.db, "log_sync", log_sync)

    count = await fetcher.fetch_and_store("2330.TW", period="5d", interval="2m", include_info=False)

    assert count == 0
    assert yahoo.fetch_calls == []
    assert manager.history_calls == []
    assert manager.intraday_calls == []
    assert stored["log"][0] == "2330.TW"
    assert stored["log"][1] == "error"


@pytest.mark.anyio
async def test_hybrid_fetcher_uses_fubon_for_taiwan_realtime_quote():
    yahoo = StubYahooFetcher()
    manager = StubFubonManager()
    fetcher = HybridDataFetcher(yahoo, manager)

    quote = await fetcher.fetch_realtime_quote("2330")

    assert quote["ticker"] == "2330.TW"
    assert quote["source"] == "fubon_neo"
    assert yahoo.quote_calls == []


@pytest.mark.anyio
async def test_hybrid_fetcher_does_not_fallback_to_yahoo_for_taiwan_quote_when_fubon_disconnected():
    yahoo = StubYahooFetcher()
    manager = StubFubonManager()
    manager.connected = False
    fetcher = HybridDataFetcher(yahoo, manager)

    quote = await fetcher.fetch_realtime_quote("2330")

    assert quote is None
    assert manager.quote_calls == []
    assert yahoo.quote_calls == []


def test_history_start_from_period_1y_stays_under_fubon_limit():
    start = date.fromisoformat(fubon_data_fetcher._history_start_from_period("1y"))

    assert (date.today() - start).days == fubon_data_fetcher.FUBON_HISTORY_MAX_RANGE_DAYS


@pytest.mark.anyio
async def test_hybrid_fetcher_chunks_fubon_history_for_periods_over_single_call_limit(monkeypatch):
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

    count = await fetcher.fetch_and_store("2330.TW", period="2y", interval="1d", include_info=False)

    assert count == 2
    assert yahoo.fetch_calls == []
    assert len(manager.history_calls) >= 2
    assert {call["symbol"] for call in manager.history_calls} == {"2330"}
    assert stored["upsert"][0] == "2330.TW"
    assert stored["upsert"][1] == "1d"


@pytest.mark.anyio
async def test_hybrid_fetcher_skips_404_history_chunks_for_newer_taiwan_listings(monkeypatch):
    yahoo = StubYahooFetcher()
    manager = ListingAfterFirstChunkFubonManager()
    fetcher = HybridDataFetcher(yahoo, manager)
    stored = {}

    async def delete_ohlcv_range(ticker, interval, start_date, end_date):
        stored["deleted"] = (ticker, interval, start_date, end_date)
        return 0

    async def upsert_ohlcv_batch(ticker, rows, interval):
        stored["upsert"] = (ticker, interval, rows)
        return len(rows)

    async def log_sync(ticker, status, count, message):
        stored["log"] = (ticker, status, count, message)

    monkeypatch.setattr(fubon_data_fetcher.db, "delete_ohlcv_range", delete_ohlcv_range)
    monkeypatch.setattr(fubon_data_fetcher.db, "upsert_ohlcv_batch", upsert_ohlcv_batch)
    monkeypatch.setattr(fubon_data_fetcher.db, "log_sync", log_sync)
    monkeypatch.setattr(fubon_data_fetcher, "FUBON_HISTORY_MAX_RANGE_DAYS", 1)

    count = await fetcher.fetch_and_store("00400A.TW", period="1mo", interval="1d", include_info=False)

    assert count >= 1
    assert len(manager.history_calls) >= 2
    assert stored["upsert"][0] == "00400A.TW"
    assert stored["log"][1] == "ok"
