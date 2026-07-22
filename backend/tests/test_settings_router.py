from __future__ import annotations

from unittest.mock import AsyncMock

import main
import providers


MOCK_ACCOUNT = {
    "id": 1,
    "label": "測試帳號",
    "user_id": "P123456789",
    "password": "****",
    "cert_path": "C:\\certs\\test.pfx",
    "cert_password": "****",
    "api_key": "****",
    "ws_mode": "Speed",
    "is_active": False,
    "is_enabled": True,
    "connection_status": "disconnected",
    "connection_error": None,
    "last_connected_at": None,
}


class FakeRepo:
    def __init__(self):
        self.list_accounts = AsyncMock(return_value=[])
        self.create_account = AsyncMock(return_value=1)
        self.update_account = AsyncMock(return_value=1)
        self.delete_account = AsyncMock(return_value=1)
        self.activate_account = AsyncMock(return_value=True)
        self.get_account_with_secrets = AsyncMock(return_value=None)
        self.list_statuses = AsyncMock(return_value=[])
        self.update_connection_status = AsyncMock(return_value=None)


def patch_repo(monkeypatch, repo):
    monkeypatch.setattr(main.settings, "FubonAccountRepository", lambda _db: repo)


def test_list_fubon_accounts_returns_repo_payload(client, monkeypatch):
    repo = FakeRepo()
    repo.list_accounts.return_value = [MOCK_ACCOUNT]
    patch_repo(monkeypatch, repo)

    response = client.get("/api/settings/fubon-accounts")

    assert response.status_code == 200
    assert response.json() == {"accounts": [MOCK_ACCOUNT]}
    repo.list_accounts.assert_awaited_once()


def test_create_fubon_account_rejects_short_api_key(client):
    response = client.post(
        "/api/settings/fubon-accounts",
        json={
            "label": "測試帳號",
            "user_id": "P123456789",
            "password": "secret",
            "cert_path": "C:\\certs\\test.pfx",
            "cert_password": "cert-pass",
            "api_key": "short",
            "ws_mode": "Speed",
        },
    )

    assert response.status_code == 422


def test_create_fubon_account_rejects_invalid_ws_mode(client):
    response = client.post(
        "/api/settings/fubon-accounts",
        json={
            "label": "測試帳號",
            "user_id": "P123456789",
            "password": "secret",
            "cert_path": "C:\\certs\\test.pfx",
            "cert_password": "cert-pass",
            "api_key": "A" * 64,
            "ws_mode": "Fast",
        },
    )

    assert response.status_code == 422


def test_update_fubon_account_uses_partial_payload(client, monkeypatch):
    repo = FakeRepo()
    patch_repo(monkeypatch, repo)
    reload_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(providers.fubon_realtime_pool, "reload_from_db", reload_mock)

    response = client.put(
        "/api/settings/fubon-accounts/1",
        json={"label": "新名稱"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "帳號已更新"
    repo.update_account.assert_awaited_once_with(1, {"label": "新名稱"})
    reload_mock.assert_awaited_once()


def test_activate_disabled_account_returns_400(client, monkeypatch):
    repo = FakeRepo()
    repo.get_account_with_secrets.return_value = {
        "id": 1,
        "label": "停用帳號",
        "user_id": "P123456789",
        "password": "secret",
        "cert_path": "C:\\certs\\test.pfx",
        "cert_password": "cert-pass",
        "api_key": "A" * 64,
        "ws_mode": "Speed",
        "is_enabled": False,
    }
    patch_repo(monkeypatch, repo)

    response = client.post("/api/settings/fubon-accounts/1/activate")

    assert response.status_code == 400
    assert response.json()["detail"] == "帳號已停用"
    repo.activate_account.assert_not_awaited()


def test_get_fubon_accounts_status_merges_runtime_state(client, monkeypatch):
    repo = FakeRepo()
    repo.list_statuses.return_value = [
        {
            "id": 1,
            "label": "主帳號",
            "is_active": True,
            "is_enabled": True,
            "connection_status": "connecting",
            "connection_error": None,
            "last_connected_at": None,
        }
    ]
    patch_repo(monkeypatch, repo)
    monkeypatch.setattr(
        providers.fubon_realtime_pool,
        "get_account_runtime_statuses",
        lambda: {
            1: {
                "connection_status": "connected",
                "realtime_assigned_count": 2,
                "realtime_assigned_tickers": ["2330.TW", "2317.TW"],
                "realtime_connected": True,
            }
        },
    )
    monkeypatch.setattr(
        providers.fubon_realtime_pool,
        "get_ws_diagnostics",
        lambda: {"TMFE6": {"last_channel": "books", "channels": {"books": {"count": 1}}}},
    )

    response = client.get("/api/settings/fubon-accounts/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["accounts"][0]["connection_status"] == "connected"
    assert payload["accounts"][0]["realtime_assigned_count"] == 2
    assert payload["accounts"][0]["realtime_connected"] is True
    assert payload["realtime_diagnostics"]["TMFE6"]["last_channel"] == "books"


def test_reconnect_fubon_account_recovers_runtime_without_app_restart(client, monkeypatch):
    repo = FakeRepo()
    repo.get_account_with_secrets.return_value = {
        **MOCK_ACCOUNT,
        "password": "secret",
        "api_key": "A" * 64,
        "is_enabled": True,
    }
    patch_repo(monkeypatch, repo)
    reconnect_mock = AsyncMock(
        return_value={"success": True, "account_id": 1, "market_type": "all"}
    )
    monkeypatch.setattr(providers.fubon_realtime_pool, "reconnect_account", reconnect_mock)

    response = client.post("/api/settings/fubon-accounts/1/reconnect")

    assert response.status_code == 200
    assert response.json()["success"] is True
    reconnect_mock.assert_awaited_once_with(1, market_type=None)


def test_reconnect_fubon_account_can_target_futopt_websocket(client, monkeypatch):
    repo = FakeRepo()
    repo.get_account_with_secrets.return_value = {
        **MOCK_ACCOUNT,
        "password": "secret",
        "api_key": "A" * 64,
        "is_enabled": True,
    }
    patch_repo(monkeypatch, repo)
    reconnect_mock = AsyncMock(
        return_value={"success": True, "account_id": 1, "market_type": "futopt"}
    )
    monkeypatch.setattr(providers.fubon_realtime_pool, "reconnect_account", reconnect_mock)

    response = client.post(
        "/api/settings/fubon-accounts/1/reconnect",
        json={"market_type": "futopt"},
    )

    assert response.status_code == 200
    reconnect_mock.assert_awaited_once_with(1, market_type="futopt")
