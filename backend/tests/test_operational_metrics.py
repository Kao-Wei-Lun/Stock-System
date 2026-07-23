from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from operational_metrics import (
    OperationalMetricStore,
    OperationalMetricsService,
    build_operational_snapshot,
)
from routers import system


def metric_snapshot(at: datetime, *, marker: int = 0) -> dict:
    return {
        "timestamp": at.astimezone(timezone.utc).isoformat(),
        "api": {"count": marker, "p50_ms": 1, "p95_ms": 2, "max_ms": 3},
        "database": {"pool_size": 2, "pool_free": 1, "wait_p95_ms": marker},
        "realtime": {"broadcast_p95_ms": marker, "dropped_count": 0},
        "persistence": {"pending": 0, "failure_count": 0, "error_category": "none"},
        "provider": {"state": "ready", "error_category": "none"},
        "freshness": {"stale_ticker_count": marker, "stale_futures_count": 0},
        "scheduler": {"running": True, "failed_count": 0},
        "process": {"rss_bytes": 100, "private_bytes": 90, "handle_count": 12},
        "background": {"active_task_count": 4},
        "health": {
            "status": "healthy",
            "warning_count": 0,
            "error_count": 0,
            "last_success_at": at.isoformat(),
        },
    }


def test_store_bounds_raw_and_downsampled_history_and_survives_restart(tmp_path):
    path = tmp_path / "metrics" / "operational.json"
    store = OperationalMetricStore(path, raw_retention_hours=24, downsample_retention_days=30)
    now = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)

    store.record(metric_snapshot(now - timedelta(days=31), marker=1))
    store.record(metric_snapshot(now - timedelta(hours=25), marker=2))
    store.record(metric_snapshot(now - timedelta(minutes=14), marker=3))
    store.record(metric_snapshot(now - timedelta(minutes=13), marker=4))
    store.record(metric_snapshot(now, marker=5))

    restarted = OperationalMetricStore(path, raw_retention_hours=24, downsample_retention_days=30)
    raw = restarted.history(hours=24, resolution="raw", now=now)
    downsampled = restarted.history(hours=720, resolution="downsampled", now=now)

    assert raw["resolution"] == "raw"
    assert raw["point_count"] == 3
    assert downsampled["resolution"] == "downsampled"
    assert downsampled["point_count"] == 3
    assert downsampled["points"][-2]["freshness"]["stale_ticker_count"] == 4
    assert all(point["timestamp"] >= (now - timedelta(days=30)).isoformat() for point in downsampled["points"])


def test_store_replaces_same_minute_and_rejects_unbounded_resolution(tmp_path):
    store = OperationalMetricStore(tmp_path / "metrics.json")
    now = datetime(2026, 7, 24, 12, 1, 10, tzinfo=timezone.utc)
    store.record(metric_snapshot(now, marker=1))
    store.record(metric_snapshot(now + timedelta(seconds=30), marker=9))

    payload = store.history(hours=1, resolution="raw", now=now + timedelta(minutes=1))

    assert payload["point_count"] == 1
    assert payload["points"][0]["freshness"]["stale_ticker_count"] == 9
    with pytest.raises(ValueError, match="resolution"):
        store.history(resolution="per_tick")


def test_snapshot_is_strictly_allow_listed_and_excludes_sensitive_payloads():
    secret = "ACCOUNT-KAO5-SECRET"

    class Database:
        def get_performance_status(self):
            return {
                "configured": True,
                "pool": {"size": 2, "free": 1, "maxsize": 5},
                "wait": {"p50_ms": 1, "p95_ms": 2, "max_ms": 3, "sql": secret},
                "query": {"p50_ms": 4, "p95_ms": 5, "max_ms": 6},
            }

    class Scheduler:
        def health_summary(self):
            return {
                "running": True,
                "task_count": 4,
                "active_count": 3,
                "failed_count": 0,
                "unexpected_stopped_count": 0,
                "tasks": [{"name": secret}],
            }

    class Provider:
        connected = True

        def get_warmup_status(self):
            return {
                "state": "ready",
                "configured_account_count": 1,
                "connected_account_count": 1,
                "accounts": {secret: {"password": secret}},
            }

    quality = {
        "status": "warning",
        "generated_at": "2026-07-24T12:00:00+00:00",
        "summary": {"warning_count": 1, "error_count": 0},
        "components": {
            "fubon": {
                "connected": True,
                "account_count": 1,
                "connected_account_count": 1,
                "reconnect_attempts": 2,
                "accounts": {secret: {"credential": secret}},
            },
            "watchlist": {
                "stale_count": 2,
                "stale_items": [{"ticker": "2330.TW", "quote": secret}],
            },
            "futures_recorder": {"stale_symbol_count": 1, "symbols": [secret]},
        },
    }

    payload = build_operational_snapshot(
        database=Database(),
        scheduler=Scheduler(),
        provider_pool=Provider(),
        quality_snapshot=quality,
        now=datetime(2026, 7, 24, 12, tzinfo=timezone.utc),
    )
    serialized = json.dumps(payload)

    assert payload["freshness"] == {"stale_ticker_count": 2, "stale_futures_count": 1}
    assert payload["provider"]["reconnect_attempts"] == 2
    assert secret not in serialized
    assert "2330.tw" not in serialized.lower()
    assert "accounts" not in serialized.lower()


@pytest.mark.anyio
async def test_service_collects_quality_and_exposes_history(tmp_path):
    class Quality:
        calls = 0

        async def build_snapshot(self, *, now=None):
            self.calls += 1
            return {
                "status": "healthy",
                "generated_at": now.isoformat(),
                "summary": {"warning_count": 0, "error_count": 0},
                "components": {
                    "watchlist": {"stale_count": 0},
                    "futures_recorder": {"stale_symbol_count": 0},
                },
            }

    quality = Quality()
    service = OperationalMetricsService(
        OperationalMetricStore(tmp_path / "history.json"),
        data_quality_service=quality,
        interval_seconds=5,
        quality_interval_seconds=60,
        startup_delay_seconds=0,
    )
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    first = await service.collect_once(now=now)
    await service.collect_once(now=now + timedelta(seconds=20))

    assert first["health"]["status"] == "healthy"
    assert quality.calls == 1
    assert service.history(hours=1)["point_count"] == 1
    assert service.status()["last_error_category"] is None


@pytest.mark.anyio
async def test_system_metrics_history_endpoint_uses_configured_service(monkeypatch, tmp_path):
    store = OperationalMetricStore(tmp_path / "history.json")
    now = datetime.now(timezone.utc)
    store.record(metric_snapshot(now))
    service = OperationalMetricsService(store)
    monkeypatch.setattr(system, "_OPERATIONAL_METRICS_SERVICE", service)

    payload = await system.system_metrics_history(hours=24, resolution="auto")

    assert payload["resolution"] == "raw"
    assert payload["point_count"] == 1
