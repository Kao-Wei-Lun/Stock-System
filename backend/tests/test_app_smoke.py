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

    response = client.get("/api/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["components"]["database"]["connected"] is True


def test_readiness_endpoint_returns_503_when_database_is_unavailable(client, monkeypatch):
    async def unhealthy_database():
        return {"connected": False, "latency_ms": None, "error": "pool_not_initialized"}

    monkeypatch.setattr(main.db, "health_check", unhealthy_database)

    response = client.get("/api/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["components"]["database"]["error"] == "pool_not_initialized"
