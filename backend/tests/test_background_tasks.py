import pytest

from background_tasks import BackgroundTaskService


class FakeDb:
    def __init__(self):
        self.quotes = {
            "2330.TW": {
                "ticker": "2330.TW",
                "source": "fubon_neo",
                "quote_type": "realtime",
                "is_delayed": False,
                "name": "台積電",
                "currency": "TWD",
                "price": 817.0,
                "open": 815.0,
                "high": 818.0,
                "low": 812.0,
                "prev_close": 810.0,
                "change": 7.0,
                "change_pct": 0.86,
                "volume": 12345,
                "bid": 816.0,
                "ask": 817.0,
                "bid_size": 21,
                "ask_size": 15,
                "bids": [{"price": 816.0, "size": 21}],
                "asks": [{"price": 817.0, "size": 15}],
                "quote_timestamp": "2026-04-17T01:00:00+00:00",
                "synced_at": "2026-04-17T09:00:00+00:00",
            }
        }
        self.last_upsert = None

    async def get_market_quote(self, ticker):
        quote = self.quotes.get(ticker)
        return dict(quote) if quote else None

    async def upsert_market_quote(self, quote):
        self.last_upsert = dict(quote)
        self.quotes[quote["ticker"]] = dict(quote)
        return dict(quote)


@pytest.mark.anyio
async def test_store_realtime_quote_preserves_existing_fields_when_trade_payload_is_partial():
    db = FakeDb()
    service = BackgroundTaskService(
        db=db,
        fetcher=None,
        quote_provider=None,
        macro_snapshot_provider=None,
        market_event_provider=None,
        news_provider=None,
        startup_download_tickers=[],
        startup_download_delay_seconds=0,
        latest_data_sync_period="1d",
        latest_data_sync_interval="1d",
    )

    result = await service.store_realtime_quote(
        {
            "ticker": "2330.TW",
            "source": "fubon_neo",
            "quote_type": "realtime",
            "is_delayed": False,
            "price": 820.0,
            "bid": 819.0,
            "ask": 820.0,
            "volume": 15000,
            "quote_timestamp": "2026-04-17T01:01:00+00:00",
            "bids": [],
            "asks": [],
        }
    )

    assert db.last_upsert["ticker"] == "2330.TW"
    assert db.last_upsert["price"] == 820.0
    assert db.last_upsert["open"] == 815.0
    assert db.last_upsert["high"] == 818.0
    assert db.last_upsert["low"] == 812.0
    assert db.last_upsert["prev_close"] == 810.0
    assert db.last_upsert["quote_timestamp"] == "2026-04-17T01:01:00+00:00"
    assert db.last_upsert["bids"] == [{"price": 816.0, "size": 21}]
    assert db.last_upsert["asks"] == [{"price": 817.0, "size": 15}]
    assert result["price"] == 820.0
