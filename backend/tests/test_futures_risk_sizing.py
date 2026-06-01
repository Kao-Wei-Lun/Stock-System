from __future__ import annotations

from paper_trading.futures_risk_sizing import (
    FuturesPositionSizingInput,
    calculate_futures_position_sizing,
)


def test_tmf_position_sizing_uses_most_conservative_limit() -> None:
    result = calculate_futures_position_sizing(
        FuturesPositionSizingInput(
            futures_capital=100_000,
            point_value=10,
            initial_margin=28_900,
            maintenance_margin=20_150,
            stop_loss_points=60,
            stress_points=2_000,
            margin_usage_limit=0.6,
            single_trade_risk_pct=0.02,
            total_position_risk_pct=0.2,
            user_max_contracts=10,
        )
    )

    assert result.margin_contracts == 2
    assert result.stress_contracts == 1
    assert result.risk_contracts == 3
    assert result.suggested_contracts == 1
    assert result.addable_contracts == 1


def test_existing_position_reduces_addable_contracts() -> None:
    result = calculate_futures_position_sizing(
        FuturesPositionSizingInput(
            futures_capital=300_000,
            point_value=10,
            initial_margin=28_900,
            stop_loss_points=60,
            stress_points=2_000,
            margin_usage_limit=0.6,
            single_trade_risk_pct=0.02,
            total_position_risk_pct=0.2,
            user_max_contracts=10,
            open_contracts=2,
            margin_used=52_600,
        )
    )

    assert result.suggested_contracts == 3
    assert result.remaining_margin_contracts == 4
    assert result.addable_contracts == 1


def test_zero_stop_loss_blocks_risk_contracts() -> None:
    result = calculate_futures_position_sizing(
        FuturesPositionSizingInput(
            futures_capital=100_000,
            point_value=10,
            initial_margin=28_900,
            stop_loss_points=0,
            stress_points=2_000,
            margin_usage_limit=0.6,
            single_trade_risk_pct=0.02,
            total_position_risk_pct=0.2,
            user_max_contracts=10,
        )
    )

    assert result.risk_contracts == 0
    assert result.suggested_contracts == 0
    assert result.addable_contracts == 0
