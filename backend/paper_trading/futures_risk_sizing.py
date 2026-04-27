"""
Futures position sizing utilities.

The functions in this module are intentionally pure so replay, realtime paper
trading, API previews, and future live-order gateways can share the same
contract-sizing rules.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class FuturesPositionSizingInput:
    futures_capital: float
    point_value: float
    initial_margin: float
    stop_loss_points: float
    stress_points: float = 2000.0
    margin_usage_limit: float = 0.6
    single_trade_risk_pct: float = 0.02
    total_position_risk_pct: float = 0.2
    user_max_contracts: int = 10
    maintenance_margin: float = 0.0
    open_contracts: int = 0
    margin_used: float = 0.0


@dataclass(frozen=True)
class FuturesPositionSizingResult:
    futures_capital: float
    point_value: float
    initial_margin: float
    maintenance_margin: float
    stop_loss_points: float
    stress_points: float
    margin_usage_limit: float
    single_trade_risk_pct: float
    total_position_risk_pct: float
    user_max_contracts: int
    open_contracts: int
    margin_used: float
    margin_budget: float
    remaining_margin_budget: float
    max_position_loss: float
    max_single_trade_loss: float
    loss_per_contract_under_stress: float
    loss_per_contract_at_stop: float
    margin_contracts: int
    remaining_margin_contracts: int
    stress_contracts: int
    risk_contracts: int
    suggested_contracts: int
    addable_contracts: int

    def to_dict(self) -> dict:
        return {
            "futures_capital": self.futures_capital,
            "point_value": self.point_value,
            "initial_margin": self.initial_margin,
            "maintenance_margin": self.maintenance_margin,
            "stop_loss_points": self.stop_loss_points,
            "stress_points": self.stress_points,
            "margin_usage_limit": self.margin_usage_limit,
            "single_trade_risk_pct": self.single_trade_risk_pct,
            "total_position_risk_pct": self.total_position_risk_pct,
            "user_max_contracts": self.user_max_contracts,
            "open_contracts": self.open_contracts,
            "margin_used": self.margin_used,
            "margin_budget": self.margin_budget,
            "remaining_margin_budget": self.remaining_margin_budget,
            "max_position_loss": self.max_position_loss,
            "max_single_trade_loss": self.max_single_trade_loss,
            "loss_per_contract_under_stress": self.loss_per_contract_under_stress,
            "loss_per_contract_at_stop": self.loss_per_contract_at_stop,
            "margin_contracts": self.margin_contracts,
            "remaining_margin_contracts": self.remaining_margin_contracts,
            "stress_contracts": self.stress_contracts,
            "risk_contracts": self.risk_contracts,
            "suggested_contracts": self.suggested_contracts,
            "addable_contracts": self.addable_contracts,
        }


def _floor_contracts(value: float, divisor: float) -> int:
    if value <= 0 or divisor <= 0:
        return 0
    return max(0, math.floor(value / divisor))


def calculate_futures_position_sizing(
    params: FuturesPositionSizingInput,
) -> FuturesPositionSizingResult:
    futures_capital = max(0.0, float(params.futures_capital or 0.0))
    point_value = max(0.0, float(params.point_value or 0.0))
    initial_margin = max(0.0, float(params.initial_margin or 0.0))
    maintenance_margin = max(0.0, float(params.maintenance_margin or 0.0))
    stop_loss_points = max(0.0, float(params.stop_loss_points or 0.0))
    stress_points = max(0.0, float(params.stress_points or 0.0))
    margin_usage_limit = max(0.0, float(params.margin_usage_limit or 0.0))
    single_trade_risk_pct = max(0.0, float(params.single_trade_risk_pct or 0.0))
    total_position_risk_pct = max(0.0, float(params.total_position_risk_pct or 0.0))
    user_max_contracts = max(0, int(params.user_max_contracts or 0))
    open_contracts = max(0, int(params.open_contracts or 0))
    margin_used = max(0.0, float(params.margin_used or 0.0))

    margin_budget = futures_capital * margin_usage_limit
    remaining_margin_budget = max(0.0, margin_budget - margin_used)
    max_position_loss = futures_capital * total_position_risk_pct
    max_single_trade_loss = futures_capital * single_trade_risk_pct
    loss_per_contract_under_stress = stress_points * point_value
    loss_per_contract_at_stop = stop_loss_points * point_value

    margin_contracts = _floor_contracts(margin_budget, initial_margin)
    remaining_margin_contracts = _floor_contracts(remaining_margin_budget, initial_margin)
    stress_contracts = _floor_contracts(max_position_loss, loss_per_contract_under_stress)
    risk_contracts = _floor_contracts(max_single_trade_loss, loss_per_contract_at_stop)

    suggested_contracts = max(
        0,
        min(
            margin_contracts,
            stress_contracts,
            risk_contracts,
            user_max_contracts,
        ),
    )

    addable_contracts = max(
        0,
        min(
            remaining_margin_contracts,
            max(0, stress_contracts - open_contracts),
            risk_contracts,
            max(0, user_max_contracts - open_contracts),
            max(0, suggested_contracts - open_contracts),
        ),
    )

    return FuturesPositionSizingResult(
        futures_capital=futures_capital,
        point_value=point_value,
        initial_margin=initial_margin,
        maintenance_margin=maintenance_margin,
        stop_loss_points=stop_loss_points,
        stress_points=stress_points,
        margin_usage_limit=margin_usage_limit,
        single_trade_risk_pct=single_trade_risk_pct,
        total_position_risk_pct=total_position_risk_pct,
        user_max_contracts=user_max_contracts,
        open_contracts=open_contracts,
        margin_used=margin_used,
        margin_budget=margin_budget,
        remaining_margin_budget=remaining_margin_budget,
        max_position_loss=max_position_loss,
        max_single_trade_loss=max_single_trade_loss,
        loss_per_contract_under_stress=loss_per_contract_under_stress,
        loss_per_contract_at_stop=loss_per_contract_at_stop,
        margin_contracts=margin_contracts,
        remaining_margin_contracts=remaining_margin_contracts,
        stress_contracts=stress_contracts,
        risk_contracts=risk_contracts,
        suggested_contracts=suggested_contracts,
        addable_contracts=addable_contracts,
    )
