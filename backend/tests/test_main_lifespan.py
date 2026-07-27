from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest

import main


@asynccontextmanager
async def _noop_lifespan_context(_app):
    yield


@asynccontextmanager
async def _failing_lifespan_context(_app):
    raise RuntimeError("boom")
    yield


def test_router_lifespan_treats_shutdown_cancellation_as_complete(monkeypatch):
    sent_messages: list[str] = []
    receive_calls = 0

    async def receive():
        nonlocal receive_calls
        receive_calls += 1
        if receive_calls == 1:
            return {"type": "lifespan.startup"}
        raise asyncio.CancelledError()

    async def send(message):
        sent_messages.append(message["type"])

    monkeypatch.setattr(main.app.router, "lifespan_context", _noop_lifespan_context)

    asyncio.run(main.app.router.lifespan({"type": "lifespan", "app": main.app, "state": {}}, receive, send))

    assert sent_messages == ["lifespan.startup.complete", "lifespan.shutdown.complete"]


def test_router_lifespan_preserves_startup_failures(monkeypatch):
    sent_messages: list[dict[str, str]] = []

    async def receive():
        return {"type": "lifespan.startup"}

    async def send(message):
        sent_messages.append(message)

    monkeypatch.setattr(main.app.router, "lifespan_context", _failing_lifespan_context)

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(main.app.router.lifespan({"type": "lifespan", "app": main.app, "state": {}}, receive, send))

    assert sent_messages[0]["type"] == "lifespan.startup.failed"
    assert "RuntimeError: boom" in sent_messages[0]["message"]


def test_application_lifespan_schedules_provider_warmup_without_awaiting(monkeypatch):
    calls = []

    async def async_call(name):
        calls.append(name)

    async def fake_init_db():
        calls.append("init_db")

    monkeypatch.setattr(main, "validate_runtime_environment", lambda: calls.append("validate"))
    monkeypatch.setattr(main, "init_db", fake_init_db)
    monkeypatch.setattr(main.backtest_workload_executor, "startup", lambda: calls.append("backtest_start"))
    monkeypatch.setattr(main.futopt_refresh_coordinator, "startup", lambda: calls.append("refresh_start"))
    monkeypatch.setattr(main.db, "_pool", object())
    monkeypatch.setattr(
        main.db,
        "ensure_default_watchlist",
        lambda *_args, **_kwargs: async_call("default_watchlist"),
    )
    monkeypatch.setattr(
        main.db,
        "ensure_watchlist_group_items",
        lambda *_args, **_kwargs: async_call("market_watchlist"),
    )
    monkeypatch.setattr(
        main.fubon_realtime_pool,
        "start_background_warmup",
        lambda _db: calls.append("warmup_scheduled"),
    )
    monkeypatch.setattr(
        main.paper_trading,
        "schedule_paper_trading_bot_autostart",
        lambda *_args, **_kwargs: calls.append("bot_autostart_scheduled"),
    )
    monkeypatch.setattr(main.background_scheduler, "start", lambda: calls.append("scheduler_start"))
    monkeypatch.setattr(main.operational_metrics_service, "start", lambda: calls.append("metrics_start"))
    monkeypatch.setattr(main.operational_metrics_service, "shutdown", lambda: async_call("metrics_stop"))
    monkeypatch.setattr(main.background_scheduler, "shutdown", lambda: async_call("scheduler_stop"))
    monkeypatch.setattr(main.quote_persistence_buffer, "shutdown", lambda: async_call("quote_stop"))
    monkeypatch.setattr(main.futopt_refresh_coordinator, "shutdown", lambda: async_call("refresh_stop"))
    monkeypatch.setattr(main.assets, "shutdown", lambda: async_call("assets_stop"))
    monkeypatch.setattr(main.backtest_workload_executor, "shutdown", lambda: async_call("backtest_stop"))
    monkeypatch.setattr(
        main.paper_trading,
        "shutdown_paper_trading_runtime",
        lambda _pool: async_call("bot_runtime_stop"),
    )
    monkeypatch.setattr(main.fubon_realtime_pool, "shutdown_async", lambda: async_call("warmup_stop"))
    monkeypatch.setattr(main.fubon_manager, "shutdown", lambda: calls.append("manager_stop"))
    monkeypatch.setattr(main.db, "close", lambda: async_call("db_stop"))

    async def run():
        async with main.lifespan(main.app):
            calls.append("inside")

    asyncio.run(run())

    assert (
        calls.index("warmup_scheduled")
        < calls.index("bot_autostart_scheduled")
        < calls.index("scheduler_start")
        < calls.index("metrics_start")
    )
    assert calls.index("metrics_start") < calls.index("inside")
    assert calls.index("bot_runtime_stop") < calls.index("warmup_stop")
    assert calls[-3:] == ["warmup_stop", "manager_stop", "db_stop"]
