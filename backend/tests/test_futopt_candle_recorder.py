from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from futopt_history_service import FutoptCandleRecorder, is_futopt_trading_time


class FakeRealtimePool:
    def __init__(self, *, assignment_ready=True):
        self.handler = None
        self.tracked = []
        self.untracked = []
        self.assignment_ready = assignment_ready

    def register_message_handler(self, handler):
        self.handler = handler

    def unregister_message_handler(self, handler):
        if self.handler is handler:
            self.handler = None

    def track_ticker(self, ticker, *, source="ws"):
        self.tracked.append((ticker, source))

    def untrack_ticker(self, ticker, *, source="ws"):
        self.untracked.append((ticker, source))

    async def ensure_source_tickers(self, source, tickers):
        for ticker in tickers:
            item = (ticker, source)
            if item not in self.tracked:
                self.tracked.append(item)
        return self.get_source_assignment_status(source, tickers)

    async def set_source_tickers(self, source, tickers, *, wait_for_assignments=True):
        if tickers:
            await self.ensure_source_tickers(source, tickers)
            return
        for ticker, tracked_source in self.tracked:
            if tracked_source == source:
                self.untracked.append((ticker, source))

    def get_source_assignment_status(self, source, tickers):
        desired = list(tickers)
        assigned = desired if self.assignment_ready else []
        return {
            "source": source,
            "desired_tickers": desired,
            "assigned_tickers": assigned,
            "healthy_tickers": assigned,
            "missing_tickers": [] if self.assignment_ready else desired,
            "unhealthy_tickers": [],
            "ready": self.assignment_ready,
        }

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


@pytest.mark.anyio
async def test_futopt_candle_recorder_defers_active_state_until_subscriptions_are_ready():
    realtime_pool = FakeRealtimePool(assignment_ready=False)
    recorder = FutoptCandleRecorder(
        provider=None,
        db=FakeDb(),
        realtime_pool=realtime_pool,
        symbols=["TXF", "TMF"],
    )

    assert await recorder.start_ws() is False

    status = recorder.get_status()
    assert status["active"] is False
    assert status["subscription_ready"] is False
    assert status["assignment_status"]["missing_tickers"] == ["TXF", "TMF"]
    assert "subscriptions are not ready" in status["subscription_error"]
    assert realtime_pool.handler is None

    await recorder.stop_ws()
    assert realtime_pool.untracked == [
        ("TXF", "futopt_recorder"),
        ("TMF", "futopt_recorder"),
    ]


def test_futopt_trading_time_covers_day_and_night_sessions():
    tz = ZoneInfo("Asia/Taipei")

    assert is_futopt_trading_time(datetime(2026, 4, 24, 8, 45, tzinfo=tz)) is True
    assert is_futopt_trading_time(datetime(2026, 4, 24, 13, 45, tzinfo=tz)) is True
    assert is_futopt_trading_time(datetime(2026, 4, 24, 14, 30, tzinfo=tz)) is False
    assert is_futopt_trading_time(datetime(2026, 4, 24, 15, 0, tzinfo=tz)) is True
    assert is_futopt_trading_time(datetime(2026, 4, 25, 5, 0, tzinfo=tz)) is True
