from __future__ import annotations

from datetime import date, timedelta

import pytest

import main
from backtest_engine import list_backtest_strategies, run_backtest


def build_rows(closes, opens=None):
    rows = []
    base_date = date(2024, 1, 1)
    for index, close in enumerate(closes):
        open_price = opens[index] if opens else closes[index - 1] if index else close
        high = max(open_price, close) * 1.02
        low = min(open_price, close) * 0.98
        rows.append(
            {
                "ticker": "AAPL",
                "date": (base_date + timedelta(days=index)).isoformat(),
                "open": round(open_price, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": 1_000_000 + index * 100,
            }
        )
    return rows


MA_CLOSES = [100.0] * 55 + [101, 102, 103, 104, 106, 108, 111, 114, 118, 121, 124, 128, 132, 136, 140]
RSI_CLOSES = [100.0] * 14 + [98, 95, 92, 89, 86, 84, 82, 80, 78, 79, 81, 84, 88, 92, 96, 101, 105, 109]
MACD_CLOSES = [100.0] * 35 + [101, 103, 106, 110, 115, 121, 128, 136, 145, 155, 166]
BOLLINGER_CLOSES = [100, 100.2, 99.8, 100.1, 99.9, 100.0, 100.1, 99.8, 100.0, 100.2, 99.9, 100.1, 100.0, 99.8, 100.1,
                    99.9, 100.0, 100.1, 99.8, 100.0, 102.0, 104.0, 107.0, 111.0, 114.0, 118.0, 121.0, 124.0, 127.0, 130.0]
KD_CLOSES = [100, 98, 96, 94, 92, 90, 88, 86, 85, 84, 83, 84, 86, 88, 90, 93, 96, 99, 102, 105, 108, 110, 112]


@pytest.mark.parametrize(
    ("strategy", "closes"),
    [
        ("MA 黃金/死亡交叉", MA_CLOSES),
        ("RSI 超買超賣", RSI_CLOSES),
        ("MACD 交叉", MACD_CLOSES),
        ("布林通道突破", BOLLINGER_CLOSES),
        ("KD 交叉", KD_CLOSES),
    ],
)
def test_backtest_engine_supports_all_official_strategies(strategy, closes):
    result = run_backtest(
        build_rows(closes),
        {
            "ticker": "AAPL",
            "strategy": strategy,
            "start": "2024-01-01",
            "end": "2024-12-31",
            "capital": 100_000,
            "fee_rate": 0.001,
            "slippage_rate": 0.0,
            "take_profit_pct": 0.05,
        },
    )

    assert result["strategy"] == strategy
    assert result["bars"] == len(closes)
    assert result["sellTrades"] >= 1
    assert result["equity_curve"]


def test_backtest_engine_uses_next_bar_execution_without_lookahead():
    closes = [100.0] * 55 + [100.0, 100.0, 120.0, 121.0, 123.0, 126.0, 130.0]
    opens = closes[:-1] + [131.0]
    opens[58] = 128.0
    rows = build_rows(closes, opens=opens)

    result = run_backtest(
        rows,
        {
            "ticker": "AAPL",
            "strategy": "MA 黃金/死亡交叉",
            "start": "2024-01-01",
            "end": "2024-12-31",
            "capital": 100_000,
            "fee_rate": 0.0,
            "slippage_rate": 0.0,
            "take_profit_pct": 0.01,
        },
    )

    first_trade = result["trades"][0]
    assert first_trade["entry_date"] == rows[58]["date"]
    assert first_trade["entry_price"] == rows[58]["open"]
    assert first_trade["entry_price"] != rows[57]["close"]


def test_list_backtest_strategies_includes_phase_four_registry():
    strategies = list_backtest_strategies()

    assert len(strategies) == 5
    assert strategies[0]["key"] == "ma_cross"
    assert {item["name"] for item in strategies} >= {
        "MA 黃金/死亡交叉",
        "RSI 超買超賣",
        "MACD 交叉",
        "布林通道突破",
        "KD 交叉",
    }


def test_backtest_api_persists_runs(client, monkeypatch):
    stored_runs = {}

    async def get_ohlcv_range(ticker, start_date, end_date, interval="1d"):
        assert ticker == "AAPL"
        assert start_date == "2024-01-01"
        assert end_date == "2024-12-31"
        assert interval == "1d"
        return build_rows(MA_CLOSES)

    async def create_backtest_run(payload, trades, equity_points, owner_id=1):
        run_id = 21
        stored_runs[run_id] = {
            "id": run_id,
            "ticker": payload["ticker"],
            "strategy_key": payload["strategy_key"],
            "strategy": payload["strategy_name"],
            "start": payload["start_date"],
            "end": payload["end_date"],
            "capital": payload["initial_capital"],
            "finalEquity": payload["final_equity"],
            "totalReturn": payload["total_return_pct"],
            "sellTrades": payload["trade_count"],
            "winRate": payload["win_rate_pct"],
            "maxDrawdown": payload["max_drawdown_pct"],
            "sharpe": payload["sharpe_ratio"],
            "bars": payload["bars_count"],
            "feeRate": payload["fee_rate"],
            "slippageRate": payload["slippage_rate"],
            "stopLoss": payload["stop_loss_pct"],
            "takeProfit": payload["take_profit_pct"],
            "positionSizing": payload["position_sizing"],
            "trades": trades,
            "equity_curve": equity_points,
            "created_at": "2026-04-01T08:00:00+00:00",
        }
        return stored_runs[run_id]

    async def list_backtest_runs(owner_id=1, ticker=None, limit=20):
        return list(stored_runs.values())[:limit]

    async def get_backtest_run(run_id, owner_id=1):
        return stored_runs.get(run_id)

    monkeypatch.setattr(main.db, "get_ohlcv_range", get_ohlcv_range)
    monkeypatch.setattr(main.db, "create_backtest_run", create_backtest_run)
    monkeypatch.setattr(main.db, "list_backtest_runs", list_backtest_runs)
    monkeypatch.setattr(main.db, "get_backtest_run", get_backtest_run)

    create_response = client.post(
        "/api/backtests/runs",
        json={
            "ticker": "AAPL",
            "strategy": "MA 黃金/死亡交叉",
            "start": "2024-01-01",
            "end": "2024-12-31",
            "capital": 100000,
            "fee": 0.1,
            "sl": 5,
            "tp": 10,
            "slippage": 0.0,
            "interval": "1d",
        },
    )

    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["strategy_key"] == "ma_cross"
    assert payload["trades"]

    list_response = client.get("/api/backtests/runs?limit=10")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == 21

    get_response = client.get("/api/backtests/runs/21")
    assert get_response.status_code == 200
    assert get_response.json()["ticker"] == "AAPL"
