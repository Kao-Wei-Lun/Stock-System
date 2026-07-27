from __future__ import annotations

import asyncio

import pytest

from routers import paper_trading


class WarmupPool:
    def __init__(self, result: bool = True):
        self.result = result
        self.timeouts = []

    async def wait_for_warmup(self, timeout=None):
        self.timeouts.append(timeout)
        return self.result


@pytest.mark.anyio
async def test_autostart_waits_for_provider_and_completes(monkeypatch):
    pool = WarmupPool()
    calls = []

    async def start_all(**kwargs):
        calls.append(kwargs)
        return {
            "status": "started",
            "total_count": 2,
            "started_count": 2,
            "already_running_count": 0,
            "failed_count": 0,
            "items": [],
        }

    monkeypatch.setattr(paper_trading, "_start_all_paper_trading_bots", start_all)

    result = await paper_trading._run_paper_trading_bot_autostart(
        pool,
        warmup_timeout_seconds=45,
        max_attempts=3,
        retry_delay_seconds=0,
    )

    assert pool.timeouts == [45]
    assert calls == [{"realtime_only": True, "realtime_pool": pool}]
    assert result["started_count"] == 2
    state = paper_trading.get_paper_trading_bot_autostart_state()
    assert state["state"] == "completed"
    assert state["started_count"] == 2
    assert state["failed_count"] == 0


@pytest.mark.anyio
async def test_autostart_retries_only_failed_start_attempts(monkeypatch):
    pool = WarmupPool(result=False)
    attempts = []
    sleeps = []

    async def start_all(**_kwargs):
        attempts.append(len(attempts) + 1)
        failed = 1 if len(attempts) == 1 else 0
        return {
            "status": "completed_with_errors" if failed else "already_running",
            "total_count": 2,
            "started_count": 1 if failed else 0,
            "already_running_count": 0 if failed else 2,
            "failed_count": failed,
            "items": [],
        }

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(paper_trading, "_start_all_paper_trading_bots", start_all)

    result = await paper_trading._run_paper_trading_bot_autostart(
        pool,
        warmup_timeout_seconds=10,
        max_attempts=3,
        retry_delay_seconds=7,
        sleep=fake_sleep,
    )

    assert attempts == [1, 2]
    assert sleeps == [7]
    assert result["failed_count"] == 0
    state = paper_trading.get_paper_trading_bot_autostart_state()
    assert state["state"] == "completed"
    assert state["attempt"] == 2


@pytest.mark.anyio
async def test_shutdown_cancels_autostart_and_detaches_active_bots(monkeypatch):
    gate = asyncio.Event()

    class BlockingPool:
        async def wait_for_warmup(self, timeout=None):
            await gate.wait()
            return True

    class Bot:
        def __init__(self):
            self.stopped_with = []

        def stop(self, pool):
            self.stopped_with.append(pool)

    pool = BlockingPool()
    bot = Bot()
    paper_trading._active_bots.clear()
    paper_trading._active_bots[9] = bot

    task = paper_trading.schedule_paper_trading_bot_autostart(pool, enabled=True)
    duplicate = paper_trading.schedule_paper_trading_bot_autostart(pool, enabled=True)
    await asyncio.sleep(0)

    assert task is duplicate

    await paper_trading.shutdown_paper_trading_runtime(pool)

    assert task.cancelled()
    assert bot.stopped_with == [pool]
    assert paper_trading._active_bots == {}
    assert paper_trading.get_paper_trading_bot_autostart_state()["state"] == "cancelled"


@pytest.mark.anyio
async def test_startup_bulk_start_skips_replay_bots(monkeypatch):
    class Db:
        async def list_paper_trading_bots(self, owner_id=1, account_id=None):
            return [
                {"id": 1, "mode": "realtime"},
                {"id": 2, "mode": "replay"},
                {"id": 3, "mode": "realtime"},
            ]

    started = []

    async def start_one(bot_id, *, realtime_pool):
        started.append((bot_id, realtime_pool))
        return {"status": "started", "bot": {"bot_id": bot_id}}

    pool = object()
    monkeypatch.setattr(paper_trading, "db", Db())
    monkeypatch.setattr(paper_trading, "_start_paper_trading_bot_by_id", start_one)

    result = await paper_trading._start_all_paper_trading_bots(
        realtime_only=True,
        realtime_pool=pool,
    )

    assert started == [(1, pool), (3, pool)]
    assert result["total_count"] == 2
    assert result["started_count"] == 2
