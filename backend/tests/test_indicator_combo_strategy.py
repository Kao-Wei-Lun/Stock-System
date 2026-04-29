from __future__ import annotations

from datetime import datetime, timedelta

from paper_trading.cost_model import SessionType
from paper_trading.indicator_combo_strategy import IndicatorComboStrategyEngine
from paper_trading.simulation_broker import Bar
from paper_trading.strategy_engine import SignalAction, SignalDirection, StrategyConfig


def _bar(start: datetime, index: int, close: float, *, spread: float = 1.0) -> Bar:
    return Bar(
        time=start + timedelta(minutes=index),
        open=close - 0.2,
        high=close + spread,
        low=close - spread,
        close=close,
        volume=100,
        symbol="TMF",
    )


def _prime_long_trend(strategy: IndicatorComboStrategyEngine) -> None:
    strategy._trend_snapshot = {
        "close": 200.0,
        "ema20": 190.0,
        "ema60": 180.0,
        "ema20_slope3": 5.0,
        "hist": 1.0,
    }
    strategy._current_direction = SignalDirection.LONG


def test_indicator_strategy_presets_resolve_current_candidates() -> None:
    pullback = StrategyConfig.from_dict({"strategy_type": "tmf_pullback_breakout"})
    psar = StrategyConfig.from_dict({"strategy_type": "tmf_psar_flip"})

    assert pullback.to_dict()["indicator_entry_timeframe_minutes"] == 1
    assert pullback.to_dict()["indicator_trend_timeframe_minutes"] == 5
    assert pullback.to_dict()["indicator_entry_type"] == "pullback_breakout"
    assert pullback.to_dict()["indicator_shorts_enabled"] is False
    assert pullback.to_dict()["indicator_atr_stop_mult"] == 1.0
    assert pullback.to_dict()["indicator_atr_target_mult"] == 1.0
    assert pullback.to_dict()["indicator_min_hold_bars"] == 5

    assert psar.to_dict()["indicator_entry_timeframe_minutes"] == 3
    assert psar.to_dict()["indicator_entry_type"] == "psar_flip"
    assert psar.to_dict()["indicator_shorts_enabled"] is True
    assert psar.to_dict()["indicator_kd_short_min"] == 25.0
    assert psar.to_dict()["indicator_atr_stop_mult"] == 1.2
    assert psar.to_dict()["indicator_atr_target_mult"] == 2.0


def test_pullback_breakout_candidate_emits_long_entry() -> None:
    start = datetime(2026, 4, 20, 8, 45)
    strategy = IndicatorComboStrategyEngine(
        StrategyConfig.from_dict({"strategy_type": "tmf_pullback_breakout"})
    )
    _prime_long_trend(strategy)

    prices = [100 + index * 0.5 for index in range(70)]
    prices += [132, 130, 131, 134, 137, 140]

    signal = None
    for index, close in enumerate(prices):
        if index == len(prices) - 3:
            bar = Bar(
                time=start + timedelta(minutes=index),
                open=close - 0.2,
                high=close + 1.0,
                low=close - 6.0,
                close=close,
                volume=100,
                symbol="TMF",
            )
        else:
            bar = _bar(start, index, close)
        signal = strategy.update_tmf_bar(bar, SessionType.DAY)
        if signal:
            break

    assert signal is not None
    assert signal.action == SignalAction.BUY
    assert signal.direction == SignalDirection.LONG
    assert "tmf_pullback_breakout_long_entry" in signal.reason


def test_psar_flip_candidate_emits_long_entry() -> None:
    start = datetime(2026, 4, 20, 8, 45)
    strategy = IndicatorComboStrategyEngine(
        StrategyConfig.from_dict({"strategy_type": "tmf_psar_flip"})
    )
    _prime_long_trend(strategy)

    prices = [140 - index * 0.20 for index in range(130)]
    prices += [114, 115, 116, 118, 120, 122, 124, 126, 128]

    signal = None
    for index, close in enumerate(prices):
        signal = strategy.update_tmf_bar(_bar(start, index, close, spread=1.5), SessionType.DAY)
        if signal:
            break

    assert signal is not None
    assert signal.action == SignalAction.BUY
    assert signal.direction == SignalDirection.LONG
    assert "tmf_psar_flip_long_entry" in signal.reason
