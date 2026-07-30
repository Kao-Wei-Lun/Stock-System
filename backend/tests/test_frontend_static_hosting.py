from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from frontend_static import SPAStaticFiles


def build_static_client(tmp_path: Path) -> TestClient:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><div id='app'>QuantVision</div>", encoding="utf-8")
    (tmp_path / "assets" / "app-AbCd1234.js").write_text("console.log('ok')", encoding="utf-8")
    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    app.mount("/app", SPAStaticFiles(directory=tmp_path), name="frontend")
    return TestClient(app)


def test_spa_entry_and_deep_links_return_uncached_index(tmp_path):
    client = build_static_client(tmp_path)
    paths = [
        "/app/",
        "/app/overview/2330.TW",
        "/app/terminal/*TMFF",
        "/app/institutional/2330.TW",
        "/app/review/journal/2330.TW",
        "/app/assets/2330.TW",
        "/app/settings/2330.TW",
        "/app/paper-trading",
    ]

    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        assert "QuantVision" in response.text
        assert response.headers["cache-control"] == "no-cache"


def test_hashed_assets_are_immutable_and_missing_assets_stay_404(tmp_path):
    client = build_static_client(tmp_path)

    asset = client.get("/app/assets/app-AbCd1234.js")
    missing = client.get("/app/assets/missing-Zz9911.js")

    assert asset.status_code == 200
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert missing.status_code == 404
    assert "QuantVision" not in missing.text


def test_api_routes_are_not_intercepted_by_spa_fallback(tmp_path):
    client = build_static_client(tmp_path)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_production_launcher_does_not_install_dependencies_or_start_node():
    script = (Path(__file__).resolve().parents[2] / "scripts" / "start.bat").read_text(encoding="utf-8").lower()
    assert "npm install" not in script
    assert "pip install" not in script
    assert "npm run dev" not in script
    assert "node.exe" not in script
    assert 'set "backend_url=http://127.0.0.1:%backend_port%"' in script
    assert 'call :wait_for_http "%backend_url%/api/ready" 60' in script
    assert 'call :wait_for_http "%app_url%" 15' in script
    assert 'cmd.exe" /c call "%~f0" backend' in script
    assert 'cmd.exe" /k call "%~f0" backend' not in script
    assert "start-process -filepath '%~1' -erroraction stop" in script
    assert "open this url manually" in script

    dev_script = (Path(__file__).resolve().parents[2] / "scripts" / "start-dev.bat").read_text(encoding="utf-8").lower()
    assert "npm run dev" in dev_script
    assert "npm install" not in dev_script
