from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main  # noqa: E402


def test_app_import_smoke():
    assert main.app is not None
    assert main.app.title == "QuantVision Pro API"
    assert any(route.path == "/api/health" for route in main.app.routes)
    assert any(route.path == "/api/ready" for route in main.app.routes)
    assert any(route.path == "/api/system/data-quality" for route in main.app.routes)


def test_health_endpoint_smoke(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "time" in payload


def test_readiness_endpoint_reports_database_health(client, monkeypatch):
    async def healthy_database():
        return {"connected": True, "latency_ms": 1.25, "error": None}

    monkeypatch.setattr(main.db, "health_check", healthy_database)
    monkeypatch.setattr(main.system, "_frontend_ready", lambda: True)
    monkeypatch.setattr(
        main.system,
        "_PROVIDER_WARMUP_STATUS_PROVIDER",
        lambda: {"state": "ready", "complete": True, "connected_account_count": 1},
    )

    response = client.get("/api/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["ready"] is True
    assert response.json()["degraded"] is False
    assert response.json()["components"]["database"]["connected"] is True
    assert response.json()["components"]["frontend"]["available"] is True


def test_readiness_endpoint_returns_503_when_database_is_unavailable(client, monkeypatch):
    async def unhealthy_database():
        return {"connected": False, "latency_ms": None, "error": "pool_not_initialized"}

    monkeypatch.setattr(main.db, "health_check", unhealthy_database)
    monkeypatch.setattr(main.system, "_frontend_ready", lambda: True)

    response = client.get("/api/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["components"]["database"]["error"] == "pool_not_initialized"


def test_readiness_is_degraded_but_available_while_provider_warms_up(client, monkeypatch):
    async def healthy_database():
        return {"connected": True, "latency_ms": 1.0, "error": None}

    monkeypatch.setattr(main.db, "health_check", healthy_database)
    monkeypatch.setattr(main.system, "_frontend_ready", lambda: True)
    monkeypatch.setattr(
        main.system,
        "_PROVIDER_WARMUP_STATUS_PROVIDER",
        lambda: {
            "state": "running",
            "complete": False,
            "configured_account_count": 5,
            "connected_account_count": 2,
        },
    )

    response = client.get("/api/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready_degraded"
    assert response.json()["ready"] is True
    assert response.json()["degraded"] is True


def test_readiness_requires_production_frontend_artifact(client, monkeypatch):
    async def healthy_database():
        return {"connected": True, "latency_ms": 1.0, "error": None}

    monkeypatch.setattr(main.db, "health_check", healthy_database)
    monkeypatch.setattr(main.system, "_frontend_ready", lambda: False)

    response = client.get("/api/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["components"]["frontend"]["available"] is False


def test_data_quality_endpoint_returns_unified_snapshot(client, monkeypatch):
    async def snapshot(_self):
        return {
            "status": "warning",
            "summary": {"warning_count": 1},
            "issues": [{"component": "fubon", "status": "warning", "message": "富邦行情未連線"}],
            "components": {},
        }

    monkeypatch.setattr(type(main.data_quality_service), "build_snapshot", snapshot)

    response = client.get("/api/system/data-quality")

    assert response.status_code == 200
    assert response.json()["status"] == "warning"
    assert response.json()["summary"]["warning_count"] == 1
