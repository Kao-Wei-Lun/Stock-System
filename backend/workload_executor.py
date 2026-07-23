"""Bounded executors for CPU-heavy request work."""

from __future__ import annotations

import asyncio
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial
from typing import Any, Callable


class WorkloadTimeoutError(TimeoutError):
    """Raised when a bounded workload cannot finish within its request budget."""


class BoundedWorkloadExecutor:
    """Run synchronous CPU work away from the event loop with a hard worker cap.

    The semaphore is held until the underlying worker really finishes, including
    after an HTTP request times out. This prevents timed-out work from silently
    exceeding the configured concurrency limit.
    """

    def __init__(
        self,
        *,
        name: str,
        max_workers: int = 1,
        timeout_seconds: float = 30.0,
        enabled: bool = True,
        executor_kind: str = "thread",
    ) -> None:
        self.name = str(name or "workload")
        self.max_workers = max(1, int(max_workers))
        self.timeout_seconds = max(0.01, float(timeout_seconds))
        self.enabled = bool(enabled)
        self.executor_kind = "process" if str(executor_kind).lower() == "process" else "thread"
        self._executor: Executor | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._shutdown = False
        self._active = 0
        self._peak_active = 0

    def startup(self) -> None:
        if not self.enabled or self._executor is not None:
            return
        if self.executor_kind == "process":
            self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        else:
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix=f"qv-{self.name}",
            )
        self._semaphore = asyncio.Semaphore(self.max_workers)
        self._shutdown = False

    async def run(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if not self.enabled:
            return function(*args, **kwargs)
        if self._executor is None:
            # Production starts this in FastAPI lifespan. Lazy startup keeps
            # direct router/unit-test use backward compatible.
            self.startup()
        if self._shutdown or self._executor is None or self._semaphore is None:
            raise RuntimeError(f"{self.name} executor is shut down")

        semaphore = self._semaphore
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=self.timeout_seconds)
        except TimeoutError as exc:
            raise WorkloadTimeoutError(
                f"{self.name} workload timed out while waiting for the worker"
            ) from exc

        loop = asyncio.get_running_loop()
        self._active += 1
        self._peak_active = max(self._peak_active, self._active)
        future = loop.run_in_executor(self._executor, partial(function, *args, **kwargs))
        released = False

        def release_slot(_future: asyncio.Future | None = None) -> None:
            nonlocal released
            if released:
                return
            released = True
            self._active = max(0, self._active - 1)
            semaphore.release()

        try:
            result = await asyncio.wait_for(asyncio.shield(future), timeout=self.timeout_seconds)
        except TimeoutError as exc:
            future.add_done_callback(release_slot)
            raise WorkloadTimeoutError(
                f"{self.name} workload exceeded {self.timeout_seconds:g} seconds"
            ) from exc
        except asyncio.CancelledError:
            if future.done():
                release_slot()
            else:
                future.add_done_callback(release_slot)
            raise
        except BaseException:
            release_slot()
            raise
        else:
            release_slot()
            return result

    async def shutdown(self) -> None:
        executor = self._executor
        self._shutdown = True
        self._executor = None
        self._semaphore = None
        if executor is not None:
            await asyncio.to_thread(executor.shutdown, wait=True, cancel_futures=True)
        self._active = 0

    def metrics(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "max_workers": self.max_workers,
            "executor_kind": self.executor_kind,
            "active": self._active,
            "peak_active": self._peak_active,
            "started": self._executor is not None,
            "shutdown": self._shutdown,
        }
