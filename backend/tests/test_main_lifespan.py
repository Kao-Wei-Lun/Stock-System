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
