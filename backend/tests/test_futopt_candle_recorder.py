from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from futopt_history_service import FutoptCandleRecorder, is_futopt_trading_time


class FakeRealtimePool:
    def __init__(self):
        self.handler = None
        self.tracked = []
        self.untracked = []

    def register_message_handler(self, handler):
        self.handler = handler

    def unregister_message_handler(self, handler):
        if self.handler is handler:
            self.handler = None

    def track_ticker(self, ticker, *, source="ws"):
        self.tracked.append((ticker, source))

    def untrack_ticker(self, ticker, *, source="ws"):
        self.untracked.append((ticker, source))

    def resolve_broadcast_tickers(self, ticker):
        if ticker == "TMFE6":
            return ("TMF",)
        if ticker == "TXFE6":
            return ("TXF",)
        return (ticker,)


class FakeDb:
    def __init__(self):
        self.upserts = []

    async def upsert_ohlcv_batch(self, ticker, rows, interval="1d"):
        self.upserts.append({"ticker": ticker, "rows": rows, "interval": interval})
        return len(rows)


@pytest.mark.anyio
async def test_futopt_candle_recorder_stores_alias_and_resolved_ws_candle():
    realtime_pool = FakeRealtimePool()
    db = FakeDb()
    recorder = FutoptCandleRecorder(
        provider=None,
        db=db,
        realtime_pool=realtime_pool,
        symbols=["TMF"],
    )

    await recorder.start_ws()
    realtime_pool.handler(
        {
            "event": "data",
            "channel": "candles",
            "data": {
                "symbol": "TMFE6",
                "date": "2026-04-24T09:01:00+08:00",
                "timeframe": "1",
                "open": 20500,
                "high": 20520,
                "low": 20490,
                "close": 20510,
                "volume": 88,
            },
        }
    )
    await asyncio.sleep(0.05)
    await recorder.stop_ws()

    assert realtime_pool.tracked == [("TMF", "futopt_recorder")]
    assert realtime_pool.untracked == [("TMF", "futopt_recorder")]
    assert [item["ticker"] for item in db.upserts] == ["TMF", "TMFE6"]
    assert all(item["interval"] == "1m" for item in db.upserts)
    assert db.upserts[0]["rows"][0]["source"] == "fubon_neo_ws"


def test_futopt_trading_time_covers_day_and_night_sessions():
    tz = ZoneInfo("Asia/Taipei")

    assert is_futopt_trading_time(datetime(2026, 4, 24, 8, 45, tzinfo=tz)) is True
    assert is_futopt_trading_time(datetime(2026, 4, 24, 13, 45, tzinfo=tz)) is True
    assert is_futopt_trading_time(datetime(2026, 4, 24, 14, 30, tzinfo=tz)) is False
    assert is_futopt_trading_time(datetime(2026, 4, 24, 15, 0, tzinfo=tz)) is True
    assert is_futopt_trading_time(datetime(2026, 4, 25, 5, 0, tzinfo=tz)) is True
