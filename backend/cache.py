"""Small bounded async TTL cache for non-authoritative API projections."""

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any


class AsyncTTLCache:
    """Cache successful loader results and collapse concurrent cache misses."""

    def __init__(self, *, ttl_seconds: float, max_entries: int = 128):
        self.ttl_seconds = max(0.0, float(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._inflight: dict[Any, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def get_or_load(self, key: Any, loader: Callable[[], Awaitable[Any]]) -> Any:
        now = time.monotonic()
        async with self._lock:
            cached = self._entries.get(key)
            if cached and cached[0] > now:
                self._entries.move_to_end(key)
                return cached[1]
            if cached:
                self._entries.pop(key, None)
            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(loader())
                self._inflight[key] = task

        try:
            value = await asyncio.shield(task)
        except BaseException:
            async with self._lock:
                if self._inflight.get(key) is task:
                    self._inflight.pop(key, None)
            raise

        async with self._lock:
            if self._inflight.get(key) is task:
                self._inflight.pop(key, None)
                self._entries[key] = (time.monotonic() + self.ttl_seconds, value)
                self._entries.move_to_end(key)
                while len(self._entries) > self.max_entries:
                    self._entries.popitem(last=False)
        return value

    async def invalidate(self, key: Any | None = None) -> None:
        async with self._lock:
            if key is None:
                self._entries.clear()
            else:
                self._entries.pop(key, None)

    async def clear(self) -> None:
        await self.invalidate()

