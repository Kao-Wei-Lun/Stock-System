import asyncio

import pytest

from realtime_quote_persistence import RealtimeQuotePersistenceBuffer, merge_quote_updates


class FakeMetrics:
    def __init__(self):
        self.flushes = []

    def record_persistence_flush(self, queue_age_ms, *, coalesced=0, dropped=0):
        self.flushes.append((queue_age_ms, coalesced, dropped))


def test_merge_quote_updates_protects_latest_fields_and_session_extrema():
    current = {
        "ticker": "TXF",
        "price": 22100,
        "high": 22120,
        "low": 22020,
        "volume": 100,
        "name": "臺指期",
        "quote_timestamp": "2026-07-23T01:02:00+00:00",
    }

    merged = merge_quote_updates(
        current,
        {
            "ticker": "TXF",
            "price": 22090,
            "high": 22130,
            "low": 22010,
            "volume": 90,
            "name": "",
            "quote_timestamp": "2026-07-23T01:01:00+00:00",
        },
    )

    assert merged["price"] == 22100
    assert merged["volume"] == 100
    assert merged["name"] == "臺指期"
    assert merged["high"] == 22130
    assert merged["low"] == 22010
    assert merged["quote_timestamp"] == "2026-07-23T01:02:00+00:00"


@pytest.mark.anyio
async def test_buffer_coalesces_one_hundred_updates_into_one_write():
    persisted = []
    metrics = FakeMetrics()

    async def persist(payload):
        persisted.append(payload)

    buffer = RealtimeQuotePersistenceBuffer(persist, performance_metrics=metrics)
    for price in range(100):
        await buffer.enqueue(
            {
                "ticker": "2330.tw",
                "price": price,
                "volume": price * 10,
                "quote_timestamp": f"2026-07-23T01:{price // 60:02d}:{price % 60:02d}+00:00",
            }
        )

    assert buffer.pending_count == 1
    assert await buffer.flush_once() == 1
    assert len(persisted) == 1
    assert persisted[0]["ticker"] == "2330.TW"
    assert persisted[0]["price"] == 99
    assert persisted[0]["volume"] == 990
    assert metrics.flushes[0][1] == 99
    await buffer.shutdown()


@pytest.mark.anyio
async def test_buffer_requeues_failed_write_and_recovers():
    attempts = 0
    persisted = []

    async def persist(payload):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary database failure")
        persisted.append(payload)

    buffer = RealtimeQuotePersistenceBuffer(persist)
    await buffer.enqueue({"ticker": "TXF", "price": 22100})

    assert await buffer.flush_once() == 0
    assert buffer.pending_count == 1
    assert await buffer.flush_once() == 1
    assert persisted[0]["price"] == 22100
    assert buffer.status()["failures"] == 1
    await buffer.shutdown()


@pytest.mark.anyio
async def test_buffer_is_bounded_and_reports_dropped_ticker():
    persisted = []
    metrics = FakeMetrics()

    async def persist(payload):
        persisted.append(payload)

    buffer = RealtimeQuotePersistenceBuffer(persist, capacity=2, performance_metrics=metrics)
    await buffer.enqueue({"ticker": "AAPL", "price": 1})
    await buffer.enqueue({"ticker": "MSFT", "price": 2})
    await buffer.enqueue({"ticker": "NVDA", "price": 3})

    assert buffer.pending_count == 2
    await buffer.flush_once()
    assert [item["ticker"] for item in persisted] == ["MSFT", "NVDA"]
    assert metrics.flushes[0][2] == 1
    await buffer.shutdown()


@pytest.mark.anyio
async def test_shutdown_drains_pending_quotes():
    persisted = []

    async def persist(payload):
        persisted.append(payload)

    buffer = RealtimeQuotePersistenceBuffer(persist)
    await buffer.enqueue({"ticker": "TMF", "price": 45000})
    await buffer.shutdown()

    assert persisted == [{"ticker": "TMF", "price": 45000}]
    assert buffer.pending_count == 0
    assert buffer.status()["running"] is False
