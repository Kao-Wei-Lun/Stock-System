from __future__ import annotations

import main


class FakeDb:
    def __init__(self):
        self.updated = []
        self.ohlcv = {
            "TXFE6": [
                {
                    "date": "2026-04-24T20:59:00+08:00",
                    "open": 20480,
                    "high": 20500,
                    "low": 20470,
                    "close": 20490,
                    "volume": 80,
                },
                {
                    "date": "2026-04-24T21:00:00+08:00",
                    "open": 20490,
                    "high": 20510,
                    "low": 20480,
                    "close": 20500,
                    "volume": 90,
                },
            ],
            "TMFE6": [
                {
                    "date": "2026-04-24T20:59:00+08:00",
                    "open": 20480,
                    "high": 20500,
                    "low": 20470,
                    "close": 20490,
                    "volume": 80,
                },
                {
                    "date": "2026-04-24T21:00:00+08:00",
                    "open": 20490,
                    "high": 20510,
                    "low": 20480,
                    "close": 20500,
                    "volume": 90,
                },
            ],
        }

    async def get_paper_trading_bot(self, bot_id, owner_id=1):
        return {
            "id": bot_id,
            "account_id": 101,
            "name": "Resolved Contract Bot",
            "product_symbol": "TMF",
            "direction_symbol": "TXF",
            "strategy_config": {},
        }

    async def list_paper_trading_bots(self, owner_id=1, account_id=None):
        return [
            {
                "id": 42,
                "account_id": 101,
                "name": "Resolved Contract Bot",
                "product_symbol": "TMF",
                "direction_symbol": "TXF",
                "strategy_config": {},
                "status": "idle",
            },
            {
                "id": 43,
                "account_id": 101,
                "name": "Second Contract Bot",
                "product_symbol": "TMF",
                "direction_symbol": "TXF",
                "strategy_config": {},
                "status": "idle",
            },
        ]

    async def get_paper_trading_account(self, account_id, owner_id=1):
        return {
            "id": account_id,
            "starting_equity": 100000,
            "initial_margin_per_contract": 26300,
            "risk_config": {},
            "cost_model": {},
            "strategy_config": {},
        }

    async def update_paper_trading_bot(self, bot_id, data, owner_id=1):
        self.updated.append({"bot_id": bot_id, "data": data})
        return {"id": bot_id, **data}

    async def get_ohlcv_range(self, ticker, *, start_date, end_date, interval="1d"):
        return self.ohlcv.get(ticker, [])


class FakeRealtimePool:
    def __init__(self):
        self.handlers = []
        self.tracked = []
        self.untracked = []

    def register_message_handler(self, handler):
        self.handlers.append(handler)

    def unregister_message_handler(self, handler):
        self.handlers = [item for item in self.handlers if item is not handler]

    def track_ticker(self, ticker, *, source="ws"):
        self.tracked.append((ticker, source))

    def untrack_ticker(self, ticker, *, source="ws"):
        self.untracked.append((ticker, source))


async def fake_resolve_contract(symbol, *, session="REGULAR"):
    mapping = {"TMF": "TMFE6", "TXF": "TXFE6"}
    return {
        "requested_symbol": symbol,
        "resolved_symbol": mapping[symbol],
        "instrument_type": "future",
        "contract_type": "I",
        "end_date": "2026-05-20",
    }


def _candle(symbol: str) -> dict:
    return {
        "event": "data",
        "channel": "candles",
        "data": {
            "symbol": symbol,
            "date": "2026-04-24T21:01:00+08:00",
            "open": 20500,
            "high": 20520,
            "low": 20490,
            "close": 20510,
            "volume": 88,
        },
    }


def test_realtime_bot_start_resolves_nearest_fubon_contracts(client, monkeypatch):
    fake_db = FakeDb()
    fake_pool = FakeRealtimePool()
    main.paper_trading._active_bots.clear()
    monkeypatch.setattr(main.paper_trading, "db", fake_db)
    monkeypatch.setattr(main, "fubon_realtime_pool", fake_pool)
    monkeypatch.setattr(
        main.paper_trading.fubon_futopt_provider,
        "resolve_contract",
        fake_resolve_contract,
    )

    try:
        response = client.post("/api/paper-trading/bots/42/start")

        assert response.status_code == 200
        state = response.json()["bot"]
        assert state["data_source"] == "fubon_neo"
        assert state["direction_symbol"] == "TXF"
        assert state["product_symbol"] == "TMF"
        assert state["resolved_direction_symbol"] == "TXFE6"
        assert state["resolved_product_symbol"] == "TMFE6"
        assert state["bar_count"] == 0
        assert state["warmup_bar_count"] == 2
        assert state["total_fills"] == 0
        assert state["trades"] == []
        assert fake_pool.tracked == [
            ("TXFE6", "paper_bot_42"),
            ("TMFE6", "paper_bot_42"),
        ]

        fake_pool.handlers[0](_candle("TXFE6"))
        assert client.get("/api/paper-trading/bots/42/state").json()["bar_count"] == 0

        fake_pool.handlers[0](_candle("TMFE6"))
        assert client.get("/api/paper-trading/bots/42/state").json()["bar_count"] == 1
    finally:
        main.paper_trading._active_bots.clear()


def test_start_all_realtime_bots_starts_each_bot(client, monkeypatch):
    fake_db = FakeDb()
    fake_pool = FakeRealtimePool()
    main.paper_trading._active_bots.clear()
    monkeypatch.setattr(main.paper_trading, "db", fake_db)
    monkeypatch.setattr(main, "fubon_realtime_pool", fake_pool)
    monkeypatch.setattr(
        main.paper_trading.fubon_futopt_provider,
        "resolve_contract",
        fake_resolve_contract,
    )

    try:
        response = client.post("/api/paper-trading/bots/start-all")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "started"
        assert payload["total_count"] == 2
        assert payload["started_count"] == 2
        assert payload["failed_count"] == 0
        assert {item["bot_id"] for item in payload["items"]} == {42, 43}
        assert set(main.paper_trading._active_bots) == {42, 43}
        assert fake_pool.tracked == [
            ("TXFE6", "paper_bot_42"),
            ("TMFE6", "paper_bot_42"),
            ("TXFE6", "paper_bot_43"),
            ("TMFE6", "paper_bot_43"),
        ]
        assert [item["data"]["status"] for item in fake_db.updated] == ["running", "running"]
    finally:
        main.paper_trading._active_bots.clear()
