import asyncio

import pytest

import main
from repositories.sync import SyncMixin


class AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeStatsCursor:
    def __init__(self):
        self.executed = []
        self.current_sql = ""

    async def execute(self, sql, params=()):
        self.current_sql = " ".join(str(sql).split())
        self.executed.append((self.current_sql, params))

    async def fetchall(self):
        if "INFORMATION_SCHEMA`.`TABLES" in self.current_sql:
            return [
                {"table_name": "ohlcv", "estimated_rows": 8_500_000},
                {"table_name": "taiwan_chip_snapshots", "estimated_rows": 30_000_000},
                {"table_name": "alerts", "estimated_rows": 12},
            ]
        return []

    async def fetchone(self):
        if "INFORMATION_SCHEMA`.`STATISTICS" in self.current_sql:
            return {"estimated_tickers": 1_234}
        return None


class FakeStatsConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, *_args):
        return AsyncContext(self._cursor)


class FakeStatsPool:
    def __init__(self):
        self.cursor = FakeStatsCursor()

    def acquire(self):
        return AsyncContext(FakeStatsConnection(self.cursor))


class StatsRepository(SyncMixin):
    def __init__(self):
        self._pool = FakeStatsPool()


@pytest.mark.anyio
async def test_database_stats_use_metadata_estimates_without_full_table_counts():
    repository = StatsRepository()

    result = await repository.get_stats()

    assert result["total_rows"] == 8_500_000
    assert result["total_tickers"] == 1_234
    assert result["taiwan_chip_snapshots"] == 30_000_000
    assert result["alerts"] == 12
    assert result["top_tickers"] == []
    assert result["estimated"] is True
    sql = "\n".join(item[0] for item in repository._pool.cursor.executed).upper()
    assert "COUNT(*)" not in sql
    assert "COUNT(DISTINCT" not in sql
    assert "GROUP BY" not in sql
    assert "INFORMATION_SCHEMA" in sql


def reset_db_stats_cache():
    asyncio.run(main.market_data._db_stats_cache.clear())
    main.market_data._db_stats_last_success = None
    main.market_data._db_stats_last_success_monotonic = None


def test_database_stats_api_caches_successful_projection(client, monkeypatch):
    reset_db_stats_cache()
    calls = 0

    async def fake_get_stats():
        nonlocal calls
        calls += 1
        return {
            "total_rows": 10,
            "total_tickers": 2,
            "top_tickers": [],
            "estimated": True,
            "source": "test",
        }

    monkeypatch.setattr(main.db, "get_stats", fake_get_stats)

    first = client.get("/api/db/stats")
    second = client.get("/api/db/stats")

    assert first.status_code == second.status_code == 200
    assert first.json()["estimated"] is True
    assert first.json()["stale"] is False
    assert first.json()["as_of"]
    assert second.json()["cache_age_seconds"] is not None
    assert calls == 1


def test_database_stats_api_returns_last_success_when_refresh_fails(client, monkeypatch):
    reset_db_stats_cache()

    async def successful_stats():
        return {"total_rows": 10, "total_tickers": 2, "top_tickers": [], "estimated": True}

    monkeypatch.setattr(main.db, "get_stats", successful_stats)
    assert client.get("/api/db/stats").status_code == 200
    asyncio.run(main.market_data._db_stats_cache.clear())

    async def failing_stats():
        raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(main.db, "get_stats", failing_stats)
    response = client.get("/api/db/stats")

    assert response.status_code == 200
    assert response.json()["stale"] is True
    assert response.json()["total_rows"] == 10


def test_database_stats_api_times_out_without_occupying_request(client, monkeypatch):
    reset_db_stats_cache()
    monkeypatch.setattr(main.market_data, "DB_STATS_TIMEOUT_SECONDS", 0.01)

    async def slow_stats():
        await asyncio.sleep(1)
        return {"total_rows": 10}

    monkeypatch.setattr(main.db, "get_stats", slow_stats)
    response = client.get("/api/db/stats")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database statistics are temporarily unavailable"
