"""Measure event-loop responsiveness while a large backtest runs."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backtest_engine import run_backtest  # noqa: E402
from workload_executor import BoundedWorkloadExecutor  # noqa: E402


def build_rows(count: int) -> list[dict]:
    return [
        {
            "date": f"{2000 + index // 365:04d}-{index % 12 + 1:02d}-{index % 28 + 1:02d}T{index:06d}",
            "open": 100 + index % 20,
            "high": 102 + index % 20,
            "low": 98 + index % 20,
            "close": 100 + (index * 7) % 20,
            "volume": 1000 + index,
        }
        for index in range(count)
    ]


async def measure(count: int, executor_kind: str) -> dict:
    runner = BoundedWorkloadExecutor(
        name="backtest-benchmark",
        max_workers=1,
        timeout_seconds=30,
        executor_kind=executor_kind,
    )
    lags: list[float] = []

    async def heartbeat() -> None:
        loop = asyncio.get_running_loop()
        previous = loop.time()
        for _ in range(30):
            await asyncio.sleep(0.01)
            current = loop.time()
            lags.append(max(0.0, current - previous - 0.01))
            previous = current

    loop = asyncio.get_running_loop()
    started = loop.time()
    result, _ = await asyncio.gather(
        runner.run(
            run_backtest,
            build_rows(count),
            {"ticker": "LOAD", "strategy": "ma_cross", "capital": 100_000, "interval": "1m"},
        ),
        heartbeat(),
    )
    elapsed_ms = (loop.time() - started) * 1000
    sorted_lags = sorted(lags)
    p95_index = max(0, int(len(sorted_lags) * 0.95) - 1)
    payload = {
        "bars": result["bars"],
        "equity_points": len(result["equity_curve"]),
        "elapsed_ms": round(elapsed_ms, 2),
        "heartbeat_p95_ms": round(sorted_lags[p95_index] * 1000, 2),
        "heartbeat_max_ms": round(max(sorted_lags) * 1000, 2),
        "peak_workers": runner.metrics()["peak_active"],
        "executor_kind": runner.metrics()["executor_kind"],
    }
    await runner.shutdown()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=100_000)
    parser.add_argument("--executor-kind", choices=("thread", "process"), default="process")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(measure(max(60, args.bars), args.executor_kind)), ensure_ascii=False))


if __name__ == "__main__":
    main()
