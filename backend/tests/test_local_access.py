from fastapi import FastAPI
from fastapi.testclient import TestClient

from local_access import LocalAccessMiddleware, parse_allowed_networks


def build_client(*, allow_lan=False, networks=""):
    app = FastAPI()
    app.add_middleware(LocalAccessMiddleware, allow_lan=allow_lan, allowed_networks=networks)

    @app.get("/api/settings/fubon-accounts")
    async def probe():
        return {"ok": True}

    return TestClient(app), app


def test_local_guard_rejects_dns_rebinding_host_and_adds_security_headers():
    client, _app = build_client()
    rejected = client.get("/api/settings/fubon-accounts", headers={"Host": "attacker.example"})
    allowed = client.get("/api/settings/fubon-accounts")

    assert rejected.status_code == 403
    assert allowed.status_code == 200
    assert allowed.headers["cache-control"] == "no-store"
    assert allowed.headers["x-content-type-options"] == "nosniff"
    assert allowed.headers["x-frame-options"] == "DENY"


def test_lan_client_must_be_private_and_inside_configured_network():
    _client, app = build_client(allow_lan=True, networks="192.168.50.0/24")
    middleware = LocalAccessMiddleware(app, allow_lan=True, allowed_networks="192.168.50.0/24")

    assert middleware._client_allowed("192.168.50.12") is True
    assert middleware._client_allowed("192.168.51.12") is False
    assert middleware._client_allowed("8.8.8.8") is False


def test_invalid_lan_network_fails_fast():
    try:
        parse_allowed_networks("not-a-network")
    except RuntimeError as exc:
        assert "LAN_ALLOWED_NETWORKS" in str(exc)
    else:
        raise AssertionError("invalid network should fail")
