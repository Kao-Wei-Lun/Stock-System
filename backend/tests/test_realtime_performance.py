import pytest

from realtime_performance import RealtimePerformanceMetrics
from routers import system


def test_realtime_metrics_keep_bounded_non_sensitive_summaries():
    metrics = RealtimePerformanceMetrics(max_samples=16)
    for index in range(30):
        metrics.record_ingress("trades", queue_depth=index)
        metrics.record_broadcast(index + 0.5)
    metrics.record_persistence_flush(12.5, coalesced=4, dropped=1)

    snapshot = metrics.snapshot()

    assert snapshot["sample_capacity"] == 16
    assert snapshot["broadcast_latency"]["count"] == 16
    assert snapshot["broadcast_latency"]["p95_ms"] == 29.5
    assert snapshot["queue_depth"]["max_ms"] == 29
    assert snapshot["channels"] == {"trades": 30}
    assert snapshot["counters"]["coalesced"] == 4
    assert snapshot["counters"]["dropped"] == 1
    assert "ticker" not in str(snapshot).lower()


@pytest.mark.anyio
async def test_system_performance_returns_database_and_realtime_status(monkeypatch):
    class FakeDatabase:
        def get_performance_status(self):
            return {
                "configured": True,
                "pool": {"size": 2, "free": 1, "maxsize": 10},
                "wait": {"count": 1, "p95_ms": 0.5},
                "query": {"count": 1, "p95_ms": 2.5},
            }

    monkeypatch.setattr(system, "_DATABASE", FakeDatabase())
    monkeypatch.setattr(system, "_QUOTE_PERSISTENCE_BUFFER", None)
    system.realtime_performance_metrics.reset()
    system.realtime_performance_metrics.record_broadcast(4.25)

    payload = await system.system_performance()

    assert payload["database"]["pool"]["maxsize"] == 10
    assert payload["realtime"]["broadcast_latency"]["p95_ms"] == 4.25
    assert payload["quote_persistence"]["pending"] == 0
    assert payload["time"]
