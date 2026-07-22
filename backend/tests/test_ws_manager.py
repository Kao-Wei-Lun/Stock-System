"""Unit tests for ws_manager module."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_manager import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


def _make_ws():
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestConnectionManager:
    @pytest.mark.anyio
    async def test_connect_and_disconnect(self, manager):
        ws = _make_ws()
        await manager.connect(ws)
        assert ws in manager._clients
        manager.disconnect(ws)
        assert ws not in manager._clients

    @pytest.mark.anyio
    async def test_subscribe_adds_ticker(self, manager):
        ws = _make_ws()
        await manager.connect(ws)
        manager.subscribe(ws, "AAPL")
        assert "AAPL" in manager._clients[ws]
        assert ws in manager._ticker_subs["AAPL"]

    @pytest.mark.anyio
    async def test_unsubscribe_removes_ticker(self, manager):
        ws = _make_ws()
        await manager.connect(ws)
        manager.subscribe(ws, "AAPL")
        manager.unsubscribe(ws, "AAPL")
        assert "AAPL" not in manager._clients[ws]
        assert ws not in manager._ticker_subs["AAPL"]

    @pytest.mark.anyio
    async def test_get_subscribed_tickers(self, manager):
        ws1 = _make_ws()
        ws2 = _make_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        manager.subscribe(ws1, "AAPL")
        manager.subscribe(ws2, "TSLA")
        assert manager.get_subscribed_tickers() == {"AAPL", "TSLA"}

    @pytest.mark.anyio
    async def test_get_subscribed_tickers_empty(self, manager):
        assert manager.get_subscribed_tickers() == set()

    @pytest.mark.anyio
    async def test_get_status_summarizes_clients_and_subscriptions(self, manager):
        ws1 = _make_ws()
        ws2 = _make_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        manager.subscribe(ws1, "2330.TW")
        manager.subscribe(ws1, "AAPL")
        manager.subscribe(ws2, "2330.TW")

        assert manager.get_status() == {
            "client_count": 2,
            "subscribed_ticker_count": 2,
            "subscription_count": 3,
            "subscribed_tickers": ["2330.TW", "AAPL"],
        }

    @pytest.mark.anyio
    async def test_disconnect_cleans_subscriptions(self, manager):
        ws = _make_ws()
        await manager.connect(ws)
        manager.subscribe(ws, "AAPL")
        manager.subscribe(ws, "MSFT")
        manager.disconnect(ws)
        assert manager.get_subscribed_tickers() == set()

    @pytest.mark.anyio
    async def test_broadcast_to_ticker(self, manager):
        ws1 = _make_ws()
        ws2 = _make_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        manager.subscribe(ws1, "AAPL")
        # ws2 not subscribed to AAPL
        await manager.broadcast_to_ticker("AAPL", {"price": 150})
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()

    @pytest.mark.anyio
    async def test_broadcast_removes_dead_clients(self, manager):
        ws = _make_ws()
        ws.send_text = AsyncMock(side_effect=Exception("connection closed"))
        await manager.connect(ws)
        manager.subscribe(ws, "AAPL")
        await manager.broadcast_to_ticker("AAPL", {"test": 1})
        assert ws not in manager._clients

    @pytest.mark.anyio
    async def test_broadcast_all(self, manager):
        ws1 = _make_ws()
        ws2 = _make_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.broadcast_all({"type": "ping"})
        assert ws1.send_text.call_count == 1
        assert ws2.send_text.call_count == 1

    @pytest.mark.anyio
    async def test_subscribe_non_connected_ws_is_noop(self, manager):
        ws = _make_ws()
        manager.subscribe(ws, "AAPL")  # not connected
        assert "AAPL" not in manager.get_subscribed_tickers()

    @pytest.mark.anyio
    async def test_market_data_hooks_fire_on_first_and_last_subscriber(self, manager):
        ws1 = _make_ws()
        ws2 = _make_ws()
        first = []
        last = []
        manager.configure_market_data_hooks(
            on_first_subscribe=lambda ticker: first.append(ticker),
            on_last_unsubscribe=lambda ticker: last.append(ticker),
        )

        await manager.connect(ws1)
        await manager.connect(ws2)

        manager.subscribe(ws1, "2330.TW")
        manager.subscribe(ws2, "2330.TW")
        manager.unsubscribe(ws1, "2330.TW")
        manager.unsubscribe(ws2, "2330.TW")

        assert first == ["2330.TW"]
        assert last == ["2330.TW"]

    @pytest.mark.anyio
    async def test_disconnect_triggers_last_unsubscribe_hook_when_final_client_leaves(self, manager):
        ws = _make_ws()
        last = []
        manager.configure_market_data_hooks(on_last_unsubscribe=lambda ticker: last.append(ticker))

        await manager.connect(ws)
        manager.subscribe(ws, "2330.TW")
        manager.disconnect(ws)

        assert last == ["2330.TW"]
