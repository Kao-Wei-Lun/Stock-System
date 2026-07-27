from __future__ import annotations

import asyncio

import pytest

import check_runtime_environment
import main
from env_validation import validate_runtime_environment


VALID_ENV = {
    "MYSQL_HOST": "127.0.0.1",
    "MYSQL_PORT": "3306",
    "MYSQL_USER": "root",
    "MYSQL_PASSWORD": "super-secret",
    "MYSQL_DATABASE": "quantvision",
    "MYSQL_CHARSET": "utf8mb4",
    "APP_PORT": "8001",
    "APP_ENCRYPT_KEY": "unit-test-encrypt-key",
    "STARTUP_DOWNLOAD_ENABLED": "false",
    "INSTITUTIONAL_AUTO_SYNC_ENABLED": "true",
    "LATEST_DATA_SYNC_ON_STARTUP": "true",
    "TW_FULL_HISTORY_SYNC_ENABLED": "false",
    "TW_FULL_HISTORY_SYNC_START": "15:30",
    "TW_FULL_HISTORY_SYNC_STOP": "08:00",
    "TW_FULL_HISTORY_DELAY_SECONDS": "0.8",
    "TW_FULL_HISTORY_TICKER_DELAY_SECONDS": "2.0",
    "TW_FULL_HISTORY_INCLUDE_ETF": "true",
    "ALERT_EVALUATOR_ENABLED": "true",
    "ALERT_POLL_INTERVAL_SECONDS": "30",
    "MARKET_INTELLIGENCE_SYNC_ENABLED": "true",
    "MARKET_INTELLIGENCE_STARTUP_SYNC": "true",
    "APP_TIMEZONE": "Asia/Taipei",
    "DAILY_LATEST_SYNC_TIME": "18:10",
    "FRONTEND_DEV_URL": "http://localhost:5173",
    "FUBON_MAINTENANCE_RESTART_ENABLED": "false",
    "FUBON_MAINTENANCE_RESTART_TIME": "08:00",
    "FUBON_WS_UNHEALTHY_GRACE_SECONDS": "300",
    "FUBON_WS_HEALTH_CHECK_INTERVAL_SECONDS": "30",
    "FUBON_MAINTENANCE_RESTART_WEEKDAYS_ONLY": "true",
}


def apply_env(monkeypatch, **overrides):
    payload = {**VALID_ENV, **overrides}
    for key, value in payload.items():
        monkeypatch.setenv(key, value)


def test_validate_runtime_environment_accepts_valid_settings(monkeypatch):
    apply_env(monkeypatch)

    validated = validate_runtime_environment()

    assert validated["MYSQL_PORT"] == 3306
    assert validated["APP_PORT"] == 8001
    assert validated["APP_BIND_HOST"] == "127.0.0.1"
    assert validated["FRONTEND_DEV_URL"] == "http://localhost:5173"
    assert validated["DAILY_LATEST_SYNC_TIME"] == "18:10"
    assert validated["TW_FULL_HISTORY_SYNC_START"] == "15:30"
    assert validated["TW_FULL_HISTORY_DELAY_SECONDS"] == 0.8
    assert validated["TW_FULL_HISTORY_TICKER_DELAY_SECONDS"] == 2.0
    assert validated["FUBON_MAINTENANCE_RESTART_ENABLED"] is False
    assert validated["FUBON_MAINTENANCE_RESTART_TIME"] == "08:00"
    assert validated["FUBON_WS_UNHEALTHY_GRACE_SECONDS"] == 300
    assert validated["FUBON_WS_HEALTH_CHECK_INTERVAL_SECONDS"] == 30
    assert validated["APP_ENCRYPT_KEY"] == "unit-test-encrypt-key"


def test_validate_runtime_environment_rejects_placeholder_password(monkeypatch):
    apply_env(monkeypatch, MYSQL_PASSWORD="your_mysql_password_here")

    with pytest.raises(RuntimeError, match="MYSQL_PASSWORD"):
        validate_runtime_environment()


def test_validate_runtime_environment_rejects_invalid_frontend_url(monkeypatch):
    apply_env(monkeypatch, FRONTEND_DEV_URL="localhost:5173")

    with pytest.raises(RuntimeError, match="FRONTEND_DEV_URL"):
        validate_runtime_environment()


def test_validate_runtime_environment_requires_encrypt_key(monkeypatch):
    apply_env(monkeypatch, APP_ENCRYPT_KEY="")

    with pytest.raises(RuntimeError, match="APP_ENCRYPT_KEY"):
        validate_runtime_environment()


def test_validate_runtime_environment_rejects_invalid_maintenance_restart_settings(monkeypatch):
    apply_env(
        monkeypatch,
        FUBON_MAINTENANCE_RESTART_TIME="25:00",
        FUBON_WS_HEALTH_CHECK_INTERVAL_SECONDS="0",
    )

    with pytest.raises(RuntimeError, match="FUBON_MAINTENANCE_RESTART"):
        validate_runtime_environment()


def test_validate_runtime_environment_rejects_external_bind_without_lan_opt_in(monkeypatch):
    apply_env(monkeypatch, APP_BIND_HOST="0.0.0.0", ALLOW_LAN_ACCESS="false")

    with pytest.raises(RuntimeError, match="ALLOW_LAN_ACCESS"):
        validate_runtime_environment()


def test_validate_runtime_environment_accepts_scoped_lan_access(monkeypatch):
    apply_env(
        monkeypatch,
        APP_BIND_HOST="0.0.0.0",
        ALLOW_LAN_ACCESS="true",
        LAN_ALLOWED_NETWORKS="192.168.50.0/24",
        LAN_ALLOWED_ORIGINS="http://192.168.50.10:5173",
        LAN_ACCESS_TOKEN="unit-test-lan-token-0123456789-ABCDEFGHIJ",
    )

    validated = validate_runtime_environment()
    assert validated["ALLOW_LAN_ACCESS"] is True
    assert validated["LAN_ALLOWED_ORIGINS"] == ["http://192.168.50.10:5173"]
    assert "LAN_ACCESS_TOKEN" not in validated


def test_runtime_checker_prints_only_validated_bind_host(monkeypatch, capsys):
    monkeypatch.setattr(check_runtime_environment, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        check_runtime_environment,
        "validate_runtime_environment",
        lambda: {
            "APP_BIND_HOST": "0.0.0.0",
            "ALLOW_LAN_ACCESS": True,
            "LAN_ACCESS_TOKEN": "must-not-be-printed",
        },
    )

    assert check_runtime_environment.main(["--bind-host"]) == 0
    assert capsys.readouterr().out.strip() == "0.0.0.0"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"LAN_ALLOWED_NETWORKS": ""}, "LAN_ALLOWED_NETWORKS"),
        ({"LAN_ALLOWED_ORIGINS": ""}, "LAN_ALLOWED_ORIGINS"),
        ({"LAN_ACCESS_TOKEN": ""}, "LAN_ACCESS_TOKEN"),
        ({"LAN_ACCESS_TOKEN": "changeme"}, "LAN_ACCESS_TOKEN"),
        ({"LAN_ALLOWED_ORIGINS": "*"}, "wildcard"),
    ],
)
def test_validate_runtime_environment_fails_closed_for_incomplete_lan_security(
    monkeypatch,
    overrides,
    message,
):
    settings = {
        "APP_BIND_HOST": "0.0.0.0",
        "ALLOW_LAN_ACCESS": "true",
        "LAN_ALLOWED_NETWORKS": "192.168.50.0/24",
        "LAN_ALLOWED_ORIGINS": "http://192.168.50.10:8001",
        "LAN_ACCESS_TOKEN": "unit-test-lan-token-0123456789-ABCDEFGHIJ",
        **overrides,
    }
    apply_env(monkeypatch, **settings)

    with pytest.raises(RuntimeError, match=message):
        validate_runtime_environment()


def test_lifespan_validates_environment_before_startup(monkeypatch):
    calls: list[str] = []

    async def fake_init_db():
        calls.append("init_db")

    async def fake_ensure_default_watchlist(*_args, **_kwargs):
        calls.append("ensure_default_watchlist")

    async def fake_ensure_watchlist_group_items(*_args, **_kwargs):
        calls.append("ensure_watchlist_group_items")

    async def fake_close():
        calls.append("close")

    async def fake_shutdown():
        calls.append("shutdown")

    monkeypatch.setattr(main, "validate_runtime_environment", lambda: calls.append("validate"))
    monkeypatch.setattr(main, "init_db", fake_init_db)
    monkeypatch.setattr(main.db, "ensure_default_watchlist", fake_ensure_default_watchlist)
    monkeypatch.setattr(main.db, "ensure_watchlist_group_items", fake_ensure_watchlist_group_items)
    monkeypatch.setattr(main.db, "close", fake_close)
    monkeypatch.setattr(main.background_scheduler, "start", lambda: calls.append("start"))
    monkeypatch.setattr(main.background_scheduler, "shutdown", fake_shutdown)

    async def run_lifespan():
        async with main.lifespan(main.app):
            calls.append("inside")

    asyncio.run(run_lifespan())

    assert calls[0] == "validate"
    assert calls[1] == "init_db"
    assert "start" in calls
    assert calls[-2:] == ["shutdown", "close"]
