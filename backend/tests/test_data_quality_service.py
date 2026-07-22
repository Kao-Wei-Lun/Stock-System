from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from data_quality_service import DataQualityService


REFERENCE = datetime(2026, 7, 22, 4, 0, tzinfo=timezone.utc)


class HealthyDatabase:
    def __init__(self):
        self.bulk_calls = []

    async def health_check(self):
        return {"connected": True, "latency_ms": 1.2, "error": None}

    async def get_migration_status(self):
        return {
            "current_version": "20260722_0002",
            "applied_versions": ["20260722_0001", "20260722_0002"],
            "unknown_applied_versions": [],
            "pending": [],
            "pending_count": 0,
            "up_to_date": True,
        }

    async def get_watchlist_groups(self):
        return [{"items": [{"ticker": "2330.TW"}]}]

    async def get_market_quote(self, ticker):
        assert ticker == "2330.TW"
        return {
            "ticker": ticker,
            "quote_timestamp": "2026-07-22T03:59:00+00:00",
            "source": "fubon_neo_ws",
        }

    async def get_market_quotes(self, tickers):
        self.bulk_calls.append(("quotes", tuple(tickers)))
        return {ticker: await self.get_market_quote(ticker) for ticker in tickers}

    async def get_latest_ohlcv(self, ticker, interval="1d"):
        if interval == "1m":
            return {"ticker": ticker, "date": "2026-07-22T03:58:00+00:00", "source": "futopt_recorder"}
        return {"ticker": ticker, "date": "2026-07-21T05:30:00+00:00", "source": "yahoo_finance"}

    async def get_latest_ohlcv_many(self, tickers, interval="1d"):
        self.bulk_calls.append(("ohlcv", tuple(tickers)))
        return {ticker: await self.get_latest_ohlcv(ticker, interval) for ticker in tickers}


class HealthyScheduler:
    def health_summary(self):
        return {
            "running": True,
            "task_count": 2,
            "active_count": 2,
            "tasks": [{"name": "realtime-poll", "done": False, "cancelled": False}],
        }


class HealthyFubonPool:
    connected = True

    def get_account_runtime_statuses(self):
        return {
            1: {
                "realtime_connected": True,
                "realtime_reconnect": {"stock": {"attempts": 0}},
            }
        }


class HealthyWebsocketManager:
    def get_status(self):
        return {
            "client_count": 1,
            "subscribed_ticker_count": 1,
            "subscription_count": 1,
            "subscribed_tickers": ["2330.TW"],
        }


class HealthyFuturesRecorder:
    def get_status(self):
        return {
            "active": True,
            "symbols": ["TXF", "TMF"],
            "interval": "1m",
            "queue_size": 0,
            "queue_capacity": 2000,
            "dropped_messages": 0,
            "last_error": None,
        }


def healthy_backup_status():
    return {
        "healthy": True,
        "status": "healthy",
        "scope": "full",
        "backup_id": "20260722T010000Z",
        "created_at": "2026-07-22T01:00:00+00:00",
        "age_hours": 3.0,
        "size_bytes": 1024,
        "checksum_recorded": True,
        "error": None,
    }


@pytest.mark.anyio
async def test_build_snapshot_reports_all_healthy_components():
    database = HealthyDatabase()
    service = DataQualityService(
        db=database,
        scheduler=HealthyScheduler(),
        fubon_pool=HealthyFubonPool(),
        ws_manager=HealthyWebsocketManager(),
        futopt_recorder=HealthyFuturesRecorder(),
        backup_status_provider=healthy_backup_status,
    )

    snapshot = await service.build_snapshot(now=REFERENCE)

    assert snapshot["status"] == "healthy"
    assert snapshot["summary"] == {
        "component_count": 8,
        "healthy_count": 8,
        "idle_count": 0,
        "warning_count": 0,
        "error_count": 0,
    }
    assert snapshot["components"]["watchlist"]["source_counts"] == {"fubon_neo_ws": 1}
    assert snapshot["components"]["futures_recorder"]["stale_symbol_count"] == 0
    assert snapshot["components"]["backups"]["backup_id"] == "20260722T010000Z"
    assert database.bulk_calls == [("quotes", ("2330.TW",)), ("ohlcv", ("2330.TW",))]


class BrokenDatabase:
    async def health_check(self):
        raise RuntimeError("mysql unavailable")

    async def get_migration_status(self):
        raise RuntimeError("migration status unavailable")

    async def get_watchlist_groups(self):
        return [{"items": [{"ticker": "AAPL"}]}]

    async def get_market_quote(self, ticker):
        return None

    async def get_latest_ohlcv(self, ticker, interval="1d"):
        return {"ticker": ticker, "date": "2026-01-01T00:00:00+00:00", "source": "yahoo_finance"}


class BrokenRuntime:
    @property
    def connected(self):
        raise RuntimeError("connection state unavailable")

    def health_summary(self):
        raise RuntimeError("scheduler state unavailable")

    def get_status(self):
        raise RuntimeError("websocket state unavailable")

    def get_account_runtime_statuses(self):
        raise RuntimeError("fubon state unavailable")


@pytest.mark.anyio
async def test_build_snapshot_is_resilient_and_surfaces_stale_data():
    runtime = BrokenRuntime()
    service = DataQualityService(
        db=BrokenDatabase(),
        scheduler=runtime,
        fubon_pool=runtime,
        ws_manager=runtime,
        futopt_recorder=None,
        futopt_enabled=False,
        backup_status_provider=lambda: {"healthy": False, "status": "warning", "error": "stale"},
    )

    snapshot = await service.build_snapshot(now=REFERENCE)

    assert snapshot["status"] == "error"
    assert snapshot["components"]["database"]["error"] == "mysql unavailable"
    assert snapshot["components"]["websocket"]["status"] == "error"
    assert snapshot["components"]["fubon"]["status"] == "error"
    assert snapshot["components"]["watchlist"]["stale_items"][0]["ticker"] == "AAPL"
    assert snapshot["components"]["futures_recorder"]["status"] == "idle"
    assert snapshot["components"]["backups"]["status"] == "warning"


@pytest.mark.anyio
async def test_scheduler_failure_changes_component_to_error():
    class FailedScheduler:
        def health_summary(self):
            return {
                "running": True,
                "task_count": 2,
                "active_count": 1,
                "failed_count": 1,
                "unexpected_stopped_count": 0,
                "tasks": [{"name": "backup", "state": "failed", "last_error": "boom"}],
            }

    service = DataQualityService(
        db=HealthyDatabase(), scheduler=FailedScheduler(), fubon_pool=HealthyFubonPool(),
        ws_manager=HealthyWebsocketManager(), futopt_recorder=HealthyFuturesRecorder(),
        backup_status_provider=healthy_backup_status,
    )
    snapshot = await service.build_snapshot(now=REFERENCE)
    assert snapshot["components"]["scheduler"]["status"] == "error"
