from __future__ import annotations

from datetime import datetime, timedelta

from paper_trading.cost_model import CostModel, OrderSide, SessionType
from paper_trading.replay_engine import ReplayEngine
from paper_trading.risk_engine import RiskConfig
from paper_trading.simulation_broker import Bar
from paper_trading.strategy_engine import SessionProfile, SignalAction, SignalDirection, StrategyConfig
from paper_trading.strategy_v2 import StrategyEngineV2


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


def _v2_engine(max_qty: int = 5, total_position_risk_pct: float = 1.0) -> ReplayEngine:
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
        total_position_risk_pct=total_position_risk_pct,
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
    assert reduce_signals[0]["qty"] >= 1
    assert any(fill["fill_qty"] == reduce_signals[0]["qty"] for fill in sell_fills)


def test_v2_blocks_entry_when_size_exceeds_total_position_risk() -> None:
    start = datetime(2026, 4, 20, 8, 45)
    tmf_bars = []
    for index in range(30):
        tmf_bars.append(_bar(start + timedelta(minutes=index), 100 + index * 0.01))
    for offset, close in enumerate([101.0, 101.7, 102.4], start=30):
        tmf_bars.append(
            _bar(
                start + timedelta(minutes=offset),
                close,
                open_=close - 0.6,
                high=close + 0.2,
                low=close - 0.2,
            )
        )

    result = _v2_engine(max_qty=5, total_position_risk_pct=0.1).run(
        _tx_bars(len(tmf_bars)),
        tmf_bars,
        equity_snapshot_interval=1,
    )

    assert any(signal["action"] == "buy" for signal in result.signals)
    assert [fill for fill in result.fills if fill["side"] == "buy"] == []
    assert any(event["event_type"] == "order_size_denied" for event in result.risk_events)


def test_v2_trailing_stop_uses_confirmed_prior_extreme_not_current_bar_high() -> None:
    start = datetime(2026, 4, 20, 8, 45)
    strategy = StrategyEngineV2(StrategyConfig(strategy_type="v2"))

    for index in range(14):
        strategy.warmup_tmf_bar(
            Bar(
                time=start + timedelta(minutes=index),
                open=100,
                high=102.5,
                low=97.5,
                close=100,
                volume=100,
                symbol="TMF",
            ),
            SessionType.DAY,
        )

    strategy.set_position_info(100, OrderSide.BUY)

    first_signal = strategy.update_tmf_bar(
        Bar(
            time=start + timedelta(minutes=14),
            open=100,
            high=113,
            low=105,
            close=111,
            volume=100,
            symbol="TMF",
        ),
        SessionType.DAY,
        has_position=True,
        position_side=OrderSide.BUY,
        position_entry_price=100,
        position_qty=1,
    )

    assert first_signal is None
    assert strategy._highest_price_since_entry == 113

    second_signal = strategy.update_tmf_bar(
        Bar(
            time=start + timedelta(minutes=15),
            open=111,
            high=111,
            low=100,
            close=100.5,
            volume=100,
            symbol="TMF",
        ),
        SessionType.DAY,
        has_position=True,
        position_side=OrderSide.BUY,
        position_entry_price=100,
        position_qty=1,
    )

    assert second_signal is not None
    assert second_signal.reason.startswith("v2_atr_stop")


def test_v2_dynamic_stop_distances_scale_with_index_level_and_recent_noise() -> None:
    start = datetime(2026, 4, 20, 9, 31)
    strategy = StrategyEngineV2(StrategyConfig(strategy_type="v2"))

    for index in range(60):
        close = 40_000 + index
        strategy.warmup_tmf_bar(
            Bar(
                time=start + timedelta(minutes=index),
                open=close,
                high=close + 10,
                low=close - 10,
                close=close,
                volume=100,
                symbol="TMF",
            ),
            SessionType.DAY,
        )

    distances = strategy.get_effective_stop_distances(
        Bar(
            time=start + timedelta(minutes=60),
            open=40_060,
            high=40_070,
            low=40_050,
            close=40_060,
            volume=100,
            symbol="TMF",
        ),
        SessionType.DAY,
    )

    assert distances.initial_stop >= 80
    assert distances.trailing_stop >= 60
    assert distances.overheat_trailing_stop >= 48
    assert distances.trailing_activation >= 80
    assert distances.pyramid_distance >= 48


def test_v2_variant_presets_resolve_candidate_parameters() -> None:
    config = StrategyConfig.from_dict({
        "strategy_type": "v2",
        "v2_variant": "v2_winrate_candidate",
    })

    assert config.v2_setting("v2_entry_breakout_lookback") == 10
    assert config.v2_setting("v2_entry_max_vwap_deviation") == 0.01
    assert config.v2_setting("v2_entry_atr_cap") == 70.0
    assert config.v2_setting("v2_reversal_confirm_5m_bars") == 2
    assert config.v2_setting("v2_initial_stop_cap_points") == 150.0
    assert config.v2_setting("v2_early_fail_bars") == 5
    assert config.v2_setting("v2_vwap_loss_exit_after_early_fail") is True
    assert config.to_dict()["v2_variant"] == "v2_winrate_candidate"


def test_v2_profit_variant_caps_dynamic_stop_distance() -> None:
    start = datetime(2026, 4, 20, 9, 31)
    strategy = StrategyEngineV2(StrategyConfig(strategy_type="v2", v2_variant="v2_profit_candidate"))

    for index in range(60):
        close = 40_000 + index
        strategy.warmup_tmf_bar(
            Bar(
                time=start + timedelta(minutes=index),
                open=close,
                high=close + 120,
                low=close - 120,
                close=close,
                volume=100,
                symbol="TMF",
            ),
            SessionType.DAY,
        )

    distances = strategy.get_effective_stop_distances(
        Bar(
            time=start + timedelta(minutes=60),
            open=40_060,
            high=40_070,
            low=40_050,
            close=40_060,
            volume=100,
            symbol="TMF",
        ),
        SessionType.DAY,
    )

    assert distances.initial_stop == 120.0
    assert distances.trailing_activation == 120.0
    assert distances.trailing_stop <= 96.0


def test_v2_winrate_variant_blocks_entries_when_atr_is_over_cap() -> None:
    start = datetime(2026, 4, 20, 8, 45)
    strategy = StrategyEngineV2(StrategyConfig(strategy_type="v2", v2_variant="v2_winrate_candidate"))

    strategy._tx_vwap.update(
        Bar(
            time=start,
            open=40_000,
            high=40_010,
            low=39_990,
            close=40_000,
            volume=100,
            symbol="TXF",
        )
    )
    strategy._tx_latest_close = 40_020
    strategy._current_direction = SignalDirection.LONG
    strategy._5m_slope = 25

    for index in range(12):
        strategy.warmup_tmf_bar(
            Bar(
                time=start + timedelta(minutes=index),
                open=40_000 + index,
                high=40_100 + index,
                low=39_900 + index,
                close=40_000 + index,
                volume=100,
                symbol="TMF",
            ),
            SessionType.DAY,
        )

    signal = strategy.update_tmf_bar(
        Bar(
            time=start + timedelta(minutes=12),
            open=40_020,
            high=40_250,
            low=39_980,
            close=40_220,
            volume=100,
            symbol="TMF",
        ),
        SessionType.DAY,
    )

    assert strategy.current_atr > 70
    assert signal is None


def test_v2_can_emit_short_entry_when_trend_and_breakdown_align() -> None:
    start = datetime(2026, 4, 20, 8, 45)
    strategy = StrategyEngineV2(StrategyConfig(strategy_type="v2", v2_variant="v2_winrate_candidate"))

    for index in range(35):
        close = 20_000 - index * 1.5
        strategy.update_tx_bar(
            Bar(
                time=start + timedelta(minutes=index),
                open=close + 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1_000,
                symbol="TXF",
            )
        )

    for index in range(12):
        close = 20_000 - index * 0.4
        strategy.update_tmf_bar(
            Bar(
                time=start + timedelta(minutes=index),
                open=close + 0.2,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=1_000,
                symbol="TMF",
            ),
            SessionType.DAY,
        )

    signal = strategy.update_tmf_bar(
        Bar(
            time=start + timedelta(minutes=12),
            open=19_980,
            high=19_981,
            low=19_975,
            close=19_976,
            volume=1_000,
            symbol="TMF",
        ),
        SessionType.DAY,
    )

    assert strategy.current_direction == SignalDirection.SHORT
    assert signal is not None
    assert signal.action == SignalAction.SELL
    assert signal.direction == SignalDirection.SHORT
    assert "v2_short_entry" in signal.reason
