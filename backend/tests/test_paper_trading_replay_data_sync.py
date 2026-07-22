from __future__ import annotations

from datetime import datetime, timedelta

import main


def _intraday_rows(symbol: str) -> list[dict]:
    start = datetime(2026, 4, 11, 8, 45)
    base = 20_000 if symbol.upper().startswith("TX") else 100
    return [
        {
            "date": (start + timedelta(minutes=index)).isoformat(),
            "open": base + index * 0.2,
            "high": base + index * 0.2 + 0.1,
            "low": base + index * 0.2 - 0.1,
            "close": base + index * 0.2,
            "volume": 100 + index,
            "adj_close": base + index * 0.2,
            "source": "fubon_neo",
        }
        for index in range(40)
    ]


def test_paper_replay_auto_syncs_missing_futopt_minute_bars(client, monkeypatch):
    storage = {}
    fetch_calls = []

    async def fake_get_ohlcv_range(ticker, start_date, end_date, interval="1d"):
        rows = storage.get((ticker, interval), [])
        return [
            row
            for row in rows
            if str(row["date"]) > start_date and str(row["date"]) <= end_date
        ]

    async def fake_upsert_ohlcv_batch(ticker, rows, interval="1d"):
        storage[(ticker, interval)] = list(rows)
        return len(rows)

    async def fake_save_contract_resolution(_data):
        return 1

    async def fake_fetch_intraday_ohlc(symbol, *, period="1d", interval="1m"):
        fetch_calls.append({"symbol": symbol, "period": period, "interval": interval})
        resolved = "TXFE6" if symbol == "TXF" else "TMFE6"
        return {
            "ticker": resolved,
            "requested_symbol": symbol,
            "resolved_symbol": resolved,
            "contract_type": "I",
            "end_date": "2026-05-20",
            "instrument_type": "future",
            "interval": interval,
            "data": _intraday_rows(symbol),
        }

    async def fake_save_replay_run(data, owner_id=1):
        return {"id": 77, **data}

    async def fake_get_paper_trading_account(account_id, owner_id=1):
        return {
            "id": account_id,
            "product_symbol": "TMF",
            "starting_equity": 250000,
            "initial_margin_per_contract": 28900,
            "risk_config": {},
            "cost_model": {},
        }

    async def fake_ensure_account_margin_current(_db, _provider, account, **_kwargs):
        return account

    async def fake_save_records(*args, **kwargs):
        return None

    monkeypatch.setattr(main.paper_trading.db, "get_paper_trading_account", fake_get_paper_trading_account)
    monkeypatch.setattr(main.paper_trading.db, "get_ohlcv_range", fake_get_ohlcv_range)
    monkeypatch.setattr(main.paper_trading.db, "upsert_ohlcv_batch", fake_upsert_ohlcv_batch)
    monkeypatch.setattr(main.paper_trading.db, "save_paper_trading_contract_resolution", fake_save_contract_resolution)
    monkeypatch.setattr(main.paper_trading.db, "save_paper_trading_replay_run", fake_save_replay_run)
    monkeypatch.setattr(main.paper_trading.db, "save_paper_trading_fills", fake_save_records)
    monkeypatch.setattr(main.paper_trading.db, "save_paper_trading_equity_snapshots", fake_save_records)
    monkeypatch.setattr(main.paper_trading.db, "save_paper_trading_risk_events", fake_save_records)
    monkeypatch.setattr(main.paper_trading.fubon_futopt_provider, "fetch_intraday_ohlc", fake_fetch_intraday_ohlc)
    monkeypatch.setattr(
        main.paper_trading,
        "ensure_account_margin_current",
        fake_ensure_account_margin_current,
    )

    response = client.post(
        "/api/paper-trading/replay/run",
        json={
            "account_id": 1,
            "product_symbol": "TMF",
            "direction_symbol": "TXF",
            "start_date": "2026-04-11",
            "end_date": "2026-04-11",
            "strategy_config": {"strategy_type": "v2"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["bar_count"] == 40
    assert payload["run"]["starting_equity"] == 250000
    assert fetch_calls == [
        {"symbol": "TMF", "period": "1d", "interval": "1m"},
        {"symbol": "TXF", "period": "1d", "interval": "1m"},
    ]
    assert ("TMF", "1m") in storage
    assert ("TMFE6", "1m") in storage
    assert ("TXF", "1m") in storage
    assert ("TXFE6", "1m") in storage
