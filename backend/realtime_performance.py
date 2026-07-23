"""Bounded, non-sensitive runtime metrics for realtime market-data diagnostics."""

from __future__ import annotations

from collections import Counter, deque
from threading import Lock
from typing import Iterable


def _percentile(values: Iterable[float], ratio: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * ratio + 0.999999)))
    return round(ordered[index], 3)


def _summary(values: deque[float]) -> dict:
    snapshot = list(values)
    return {
        "count": len(snapshot),
        "p50_ms": _percentile(snapshot, 0.50),
        "p95_ms": _percentile(snapshot, 0.95),
        "max_ms": round(max(snapshot), 3) if snapshot else None,
    }


class RealtimePerformanceMetrics:
    """Keep rolling latency samples without retaining ticker or payload content."""

    def __init__(self, max_samples: int = 512) -> None:
        self.max_samples = max(16, int(max_samples))
        self._broadcast_latency_ms: deque[float] = deque(maxlen=self.max_samples)
        self._persistence_queue_age_ms: deque[float] = deque(maxlen=self.max_samples)
        self._queue_depth: deque[float] = deque(maxlen=self.max_samples)
        self._channels: Counter[str] = Counter()
        self._counters: Counter[str] = Counter()
        self._lock = Lock()

    def record_ingress(self, channel: str, queue_depth: int = 0) -> None:
        safe_channel = str(channel or "unknown").strip().lower()[:24] or "unknown"
        with self._lock:
            self._channels[safe_channel] += 1
            self._counters["ingress"] += 1
            self._queue_depth.append(max(0.0, float(queue_depth)))

    def record_broadcast(self, duration_ms: float) -> None:
        with self._lock:
            self._counters["broadcast"] += 1
            self._broadcast_latency_ms.append(max(0.0, float(duration_ms)))

    def record_persistence_flush(self, queue_age_ms: float, *, coalesced: int = 0, dropped: int = 0) -> None:
        with self._lock:
            self._counters["persistence_flush"] += 1
            self._counters["coalesced"] += max(0, int(coalesced))
            self._counters["dropped"] += max(0, int(dropped))
            self._persistence_queue_age_ms.append(max(0.0, float(queue_age_ms)))

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "sample_capacity": self.max_samples,
                "counters": dict(self._counters),
                "channels": dict(self._channels),
                "broadcast_latency": _summary(self._broadcast_latency_ms),
                "persistence_queue_age": _summary(self._persistence_queue_age_ms),
                "queue_depth": _summary(self._queue_depth),
            }

    def reset(self) -> None:
        with self._lock:
            self._broadcast_latency_ms.clear()
            self._persistence_queue_age_ms.clear()
            self._queue_depth.clear()
            self._channels.clear()
            self._counters.clear()


realtime_performance_metrics = RealtimePerformanceMetrics()
