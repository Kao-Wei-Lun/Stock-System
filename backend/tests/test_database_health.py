import pytest

from database.core import DatabaseCore


@pytest.mark.anyio
async def test_database_health_reports_uninitialized_pool():
    database = DatabaseCore()

    result = await database.health_check()

    assert result == {
        "connected": False,
        "latency_ms": None,
        "error": "pool_not_initialized",
    }


@pytest.mark.anyio
async def test_database_health_executes_probe(monkeypatch):
    database = DatabaseCore()
    database._pool = object()

    async def fake_fetchone(sql, params=()):
        assert sql == "SELECT 1 AS `ok`"
        assert params == ()
        return {"ok": 1}

    monkeypatch.setattr(database, "_fetchone", fake_fetchone)

    result = await database.health_check()

    assert result["connected"] is True
    assert result["error"] is None
    assert result["latency_ms"] >= 0
