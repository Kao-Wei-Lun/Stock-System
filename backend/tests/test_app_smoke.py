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


def test_health_endpoint_smoke(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "time" in payload
