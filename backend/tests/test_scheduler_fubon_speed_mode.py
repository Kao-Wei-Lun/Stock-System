import asyncio

import pytest

from scheduler import fubon_ws_listener_loop


@pytest.mark.anyio
async def test_fubon_ws_listener_broadcasts_trade_messages_as_quotes():
    messages = []
    stored_quotes = []

    async def broadcast_to_ticker(ticker, payload):
        messages.append((ticker, payload))

    async def store_quote_to_db(payload):
        stored_quotes.append(payload)
        return payload

    class FakeFubonManager:
        def __init__(self):
            self.connected = True
            self.handler = None
            self.unregistered = None

        def register_message_handler(self, handler):
            self.handler = handler

        def unregister_message_handler(self, handler):
            self.unregistered = handler

    manager = FakeFubonManager()
    task = asyncio.create_task(
        fubon_ws_listener_loop(
            fubon_manager=manager,
            broadcast_to_ticker=broadcast_to_ticker,
            store_quote_to_db=store_quote_to_db,
        )
    )

    await asyncio.sleep(3.1)
    manager.handler(
        {
            "event": "data",
            "market_type": "stock",
            "channel": "trades",
            "data": {
                "symbol": "2330",
                "market": "TSE",
                "exchange": "TWSE",
                "bid": 567,
                "ask": 568,
                "price": 568,
                "volume": 54538,
                "time": 1685338200000000,
            },
        }
    )

    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert manager.unregistered is manager.handler
    assert stored_quotes[0]["ticker"] == "2330.TW"
    assert stored_quotes[0]["is_delayed"] is False
    assert stored_quotes[0]["price"] == 568
    assert messages[0][0] == "2330.TW"
    assert messages[0][1]["type"] == "quote"
    assert messages[0][1]["data"]["price"] == 568
    assert messages[0][1]["data"]["bid"] == 567
