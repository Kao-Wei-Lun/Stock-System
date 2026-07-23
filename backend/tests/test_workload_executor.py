import asyncio
import threading
import time

import pytest

from backtest_engine import run_backtest
from workload_executor import BoundedWorkloadExecutor, WorkloadTimeoutError


@pytest.mark.anyio
async def test_bounded_executor_keeps_cpu_work_off_event_loop():
    executor = BoundedWorkloadExecutor(name="heartbeat-test", max_workers=1, timeout_seconds=2)
    heartbeat_lags = []

    def cpu_work():
        deadline = time.perf_counter() + 0.15
        value = 0
        while time.perf_counter() < deadline:
            value += 1
        return value

    async def heartbeat():
        previous = asyncio.get_running_loop().time()
        for _ in range(12):
            await asyncio.sleep(0.01)
            current = asyncio.get_running_loop().time()
            heartbeat_lags.append(max(0.0, current - previous - 0.01))
            previous = current

    result, _ = await asyncio.gather(executor.run(cpu_work), heartbeat())

    assert result > 0
    p95_lag = sorted(heartbeat_lags)[max(0, int(len(heartbeat_lags) * 0.95) - 1)]
    assert p95_lag < 0.03
    await executor.shutdown()


@pytest.mark.anyio
async def test_100k_bar_backtest_preserves_heartbeat_and_result_contract():
    rows = [
        {
            "date": f"{2000 + index // 365:04d}-{index % 12 + 1:02d}-{index % 28 + 1:02d}T{index:06d}",
            "open": 100 + index % 20,
            "high": 102 + index % 20,
            "low": 98 + index % 20,
            "close": 100 + (index * 7) % 20,
            "volume": 1000 + index,
        }
        for index in range(100_000)
    ]
    options = {
        "ticker": "LOAD",
        "strategy": "ma_cross",
        "capital": 100_000,
        "interval": "1m",
    }
    executor = BoundedWorkloadExecutor(
        name="backtest-load",
        max_workers=1,
        timeout_seconds=5,
        executor_kind="process",
    )
    heartbeat_lags = []

    async def heartbeat():
        previous = asyncio.get_running_loop().time()
        for _ in range(20):
            await asyncio.sleep(0.01)
            current = asyncio.get_running_loop().time()
            heartbeat_lags.append(max(0.0, current - previous - 0.01))
            previous = current

    result, _ = await asyncio.gather(executor.run(run_backtest, rows, options), heartbeat())

    assert result["bars"] == 100_000
    assert len(result["equity_curve"]) == 99_999
    p95_lag = sorted(heartbeat_lags)[max(0, int(len(heartbeat_lags) * 0.95) - 1)]
    assert p95_lag < 0.03
    await executor.shutdown()


@pytest.mark.anyio
async def test_executor_result_matches_inline_backtest_fixture():
    rows = [
        {
            "date": f"2026-01-{index % 28 + 1:02d}T{index:04d}",
            "open": 100 + index % 4,
            "high": 105 + index % 4,
            "low": 95 + index % 4,
            "close": 100 + (index * 3) % 8,
            "volume": 1000,
        }
        for index in range(120)
    ]
    options = {"ticker": "FIXTURE", "strategy": "ma_cross", "capital": 100_000}
    expected = run_backtest(rows, options)
    executor = BoundedWorkloadExecutor(
        name="parity-test",
        max_workers=1,
        timeout_seconds=2,
        executor_kind="process",
    )

    actual = await executor.run(run_backtest, rows, options)

    assert actual == expected
    await executor.shutdown()


@pytest.mark.anyio
async def test_bounded_executor_never_exceeds_worker_limit():
    executor = BoundedWorkloadExecutor(name="serial-test", max_workers=1, timeout_seconds=2)
    release = threading.Event()
    started = threading.Event()

    def blocking_work(value):
        started.set()
        release.wait(timeout=1)
        return value

    first = asyncio.create_task(executor.run(blocking_work, 1))
    await asyncio.to_thread(started.wait, 1)
    second = asyncio.create_task(executor.run(blocking_work, 2))
    await asyncio.sleep(0.03)

    assert executor.metrics()["active"] == 1
    assert executor.metrics()["peak_active"] == 1
    release.set()
    assert await asyncio.gather(first, second) == [1, 2]
    await executor.shutdown()


@pytest.mark.anyio
async def test_timeout_holds_slot_until_underlying_thread_finishes():
    executor = BoundedWorkloadExecutor(name="timeout-test", max_workers=1, timeout_seconds=0.02)
    release = threading.Event()

    def blocking_work():
        release.wait(timeout=1)

    with pytest.raises(WorkloadTimeoutError):
        await executor.run(blocking_work)

    assert executor.metrics()["active"] == 1
    release.set()
    for _ in range(20):
        if executor.metrics()["active"] == 0:
            break
        await asyncio.sleep(0.01)
    assert executor.metrics()["active"] == 0
    await executor.shutdown()
