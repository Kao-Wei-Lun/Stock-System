import re
from uuid import UUID

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from performance_timing import RequestTimingMiddleware, add_server_timing


_TOTAL_RE = re.compile(r"(?:^|, )total;dur=([0-9]+(?:\.[0-9]+)?)")


def _build_app():
    app = FastAPI()
    app.add_middleware(RequestTimingMiddleware)

    @app.get("/ok")
    async def ok(request: Request):
        add_server_timing(request, "db", 1.25)
        return {"ok": True}

    @app.get("/not-found")
    async def not_found():
        raise HTTPException(404, "missing")

    @app.get("/boom")
    async def boom():
        raise RuntimeError("private failure detail")

    return app


@pytest.mark.parametrize(("path", "status"), [("/ok", 200), ("/not-found", 404), ("/boom", 500)])
def test_timing_headers_are_preserved_for_normal_and_error_responses(path, status):
    with TestClient(_build_app(), raise_server_exceptions=False) as client:
        response = client.get(path)

    assert response.status_code == status
    UUID(response.headers["x-request-id"])
    match = _TOTAL_RE.search(response.headers["server-timing"])
    assert match is not None
    assert float(match.group(1)) >= 0


def test_timing_header_includes_safe_component_metrics():
    with TestClient(_build_app()) as client:
        response = client.get("/ok")

    assert "db;dur=1.25" in response.headers["server-timing"]


def test_unhandled_exception_response_does_not_expose_private_detail():
    with TestClient(_build_app(), raise_server_exceptions=False) as client:
        response = client.get("/boom")

    payload = response.json()
    assert payload["detail"] == "Internal Server Error"
    assert "private failure detail" not in response.text
    assert payload["request_id"] == response.headers["x-request-id"]


def test_server_timing_rejects_unsafe_metric_names():
    scope = {"state": {}}

    with pytest.raises(ValueError):
        add_server_timing(scope, "sql SELECT secret", 1)

