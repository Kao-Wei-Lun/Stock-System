from __future__ import annotations

from datetime import datetime, timedelta

from paper_trading.cost_model import CostModel
from paper_trading.replay_engine import ReplayEngine
from paper_trading.risk_engine import RiskConfig
from paper_trading.strategy_engine import SessionProfile, StrategyConfig


def _bar(ts: datetime, close: float, *, open_: float | None = None, high: float | None = None, low: float | None = None) -> dict:
    open_price = close if open_ is None else open_
    return {
        "time": ts.isoformat(),
        "open": open_price,
        "high": close + 0.2 if high is None else high,
        "low": close - 0.2 if low is None else low,
        "close": close,
        "volume": 100,
    }


def _tx_bars(count: int) -> list[dict]:
    start = datetime(2026, 4, 20, 8, 45)
    return [
        _bar(start + timedelta(minutes=index), 100 + index * 0.05, open_=100 + index * 0.05 - 0.02)
        for index in range(count)
    ]


def _v2_engine(max_qty: int = 5) -> ReplayEngine:
    profile = SessionProfile(
        stop_loss_points=60,
        take_profit_points=120,
        max_qty=max_qty,
        breakout_lookback=3,
    )
    strategy_config = StrategyConfig(
        strategy_type="v2",
        day_open_profile=profile,
        day_regular_profile=SessionProfile(
            stop_loss_points=60,
            take_profit_points=120,
            max_qty=max_qty,
            breakout_lookback=3,
        ),
        night_profile=SessionProfile(
            stop_loss_points=60,
            take_profit_points=120,
            max_qty=max_qty,
            breakout_lookback=3,
        ),
    )
    risk_config = RiskConfig(
        starting_equity=100_000,
        initial_margin_per_contract=2_025,
        max_contracts_hard=10,
        max_margin_usage_pct=1.0,
        risk_per_trade_pct=1.0,
        daily_loss_limit_pct=1.0,
        max_drawdown_pct=1.0,
    )
    cost_model = CostModel(
        broker_fee_per_side=0,
        exchange_fee_per_side=0,
        futures_tax_per_side=0,
        slippage_ticks_day=0,
        slippage_ticks_night=0,
    )
    return ReplayEngine(
        risk_config=risk_config,
        strategy_config=strategy_config,
        cost_model=cost_model,
    )


def test_v2_trial_and_pyramid_orders_use_single_contracts() -> None:
    start = datetime(2026, 4, 20, 8, 45)
    tmf_bars = []
    for index in range(30):
        tmf_bars.append(_bar(start + timedelta(minutes=index), 100 + index * 0.01))
    for offset, close in enumerate([101.0, 101.7, 102.4, 103.1, 103.8, 104.5, 105.2], start=30):
        tmf_bars.append(
            _bar(
                start + timedelta(minutes=offset),
                close,
                open_=close - 0.6,
                high=close + 0.2,
                low=close - 0.2,
            )
        )

    result = _v2_engine(max_qty=5).run(_tx_bars(len(tmf_bars)), tmf_bars, equity_snapshot_interval=1)

    buy_fills = [fill for fill in result.fills if fill["side"] == "buy"]

    assert buy_fills
    assert {fill["fill_qty"] for fill in buy_fills} == {1}


def test_v2_time_stop_reduces_position_back_to_one_contract() -> None:
    start = datetime(2026, 4, 20, 8, 45)
    tmf_bars = []
    for index in range(30):
        tmf_bars.append(_bar(start + timedelta(minutes=index), 100 + index * 0.01))

    tmf_bars.extend(
        [
            _bar(start + timedelta(minutes=30), 101.0, open_=100.4, high=101.2, low=100.8),
            _bar(start + timedelta(minutes=31), 101.7, open_=101.0, high=101.9, low=101.5),
            _bar(start + timedelta(minutes=32), 102.4, open_=101.7, high=102.6, low=102.2),
            _bar(start + timedelta(minutes=33), 102.4, open_=102.4, high=102.5, low=102.2),
        ]
    )
    for index in range(34, 68):
        tmf_bars.append(
            _bar(
                start + timedelta(minutes=index),
                101.8,
                open_=101.8,
                high=101.85,
                low=101.75,
            )
        )

    result = _v2_engine(max_qty=5).run(_tx_bars(len(tmf_bars)), tmf_bars, equity_snapshot_interval=1)
    reduce_signals = [signal for signal in result.signals if signal["reason"].startswith("v2_time_stop_reduce")]
    sell_fills = [fill for fill in result.fills if fill["side"] == "sell"]

    assert reduce_signals
    assert reduce_signals[0]["qty"] == 2
    assert any(fill["fill_qty"] == 2 for fill in sell_fills)
