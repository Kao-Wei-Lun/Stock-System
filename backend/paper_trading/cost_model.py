"""
QuantVision Pro — Paper Trading Cost Model

統一管理期貨模擬交易的手續費、期交稅、滑價，
確保計算可下口數、預估風險、已實現損益、回放績效時使用同一套成本模型。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class SessionType(str, Enum):
    DAY = "day"
    NIGHT = "night"


# ─── 商品規格 ────────────────────────────────────────────────

@dataclass(frozen=True)
class FuturesProductSpec:
    """期貨商品規格（不可變）"""
    symbol: str
    name: str
    point_value: float          # 每點價值（TWD）
    tick_size: float = 1.0      # 最小升降單位（點）
    currency: str = "TWD"
    exchange: str = "TAIFEX"

    @property
    def tick_value(self) -> float:
        return self.tick_size * self.point_value


# 預設商品規格
TMF_SPEC = FuturesProductSpec(symbol="TMF", name="微型臺指期貨", point_value=10.0)
TX_SPEC = FuturesProductSpec(symbol="TXF", name="臺股期貨", point_value=200.0)
MTX_SPEC = FuturesProductSpec(symbol="MXF", name="小型臺指期貨", point_value=50.0)

PRODUCT_SPECS = {
    "TMF": TMF_SPEC,
    "TXF": TX_SPEC,
    "MXF": MTX_SPEC,
}


def get_product_spec(symbol: str) -> FuturesProductSpec:
    base = symbol.upper().rstrip("0123456789")
    for key in (symbol.upper(), base):
        if key in PRODUCT_SPECS:
            return PRODUCT_SPECS[key]
    return TMF_SPEC


# ─── 成本模型 ────────────────────────────────────────────────

@dataclass
class CostModel:
    """
    期貨交易成本模型。

    第一版保守原則：
    - 日盤市價單至少預設 1 tick 滑價
    - 夜盤市價單預設比日盤更保守的滑價
    - 停損單應用最不利方向的滑價估算
    """
    broker_fee_per_side: float = 20.0       # 券商手續費（單邊，TWD）
    exchange_fee_per_side: float = 2.0      # 期交所費用（單邊，TWD）
    futures_tax_per_side: float = 0.0       # 期交稅（TMF 免稅，TX 有稅）
    slippage_ticks_day: float = 1.0         # 日盤滑價（tick 數）
    slippage_ticks_night: float = 2.0       # 夜盤滑價（tick 數）
    cost_model_version: str = "v1.0"

    def fee_per_side(self) -> float:
        """單邊總費用（不含滑價）"""
        return self.broker_fee_per_side + self.exchange_fee_per_side + self.futures_tax_per_side

    def fee_round_trip(self) -> float:
        """來回總費用（不含滑價）"""
        return self.fee_per_side() * 2

    def slippage_ticks(self, session: SessionType = SessionType.DAY) -> float:
        if session == SessionType.NIGHT:
            return self.slippage_ticks_night
        return self.slippage_ticks_day

    def apply_slippage(
        self,
        price: float,
        side: OrderSide,
        session: SessionType = SessionType.DAY,
        product: Optional[FuturesProductSpec] = None,
    ) -> float:
        """
        根據買賣方向與日盤/夜盤套用滑價。
        買入：價格往上滑
        賣出：價格往下滑
        """
        spec = product or TMF_SPEC
        ticks = self.slippage_ticks(session)
        slippage_amount = ticks * spec.tick_size
        if side == OrderSide.BUY:
            return price + slippage_amount
        return price - slippage_amount

    def calculate_fill_cost(
        self,
        qty: int,
        product: Optional[FuturesProductSpec] = None,
    ) -> float:
        """
        計算成交的總費用（來回，不含滑價造成的損益影響）。
        qty 為口數。
        """
        return self.fee_round_trip() * abs(qty)

    def estimate_slippage_cost(
        self,
        qty: int,
        session: SessionType = SessionType.DAY,
        product: Optional[FuturesProductSpec] = None,
    ) -> float:
        """估算滑價造成的成本（來回）"""
        spec = product or TMF_SPEC
        ticks = self.slippage_ticks(session)
        return ticks * spec.tick_value * abs(qty) * 2  # 進出各一次

    def total_estimated_cost(
        self,
        qty: int,
        session: SessionType = SessionType.DAY,
        product: Optional[FuturesProductSpec] = None,
    ) -> float:
        """估算總成本（含費用 + 滑價）"""
        return self.calculate_fill_cost(qty, product) + self.estimate_slippage_cost(qty, session, product)

    def to_dict(self) -> dict:
        return {
            "broker_fee_per_side": self.broker_fee_per_side,
            "exchange_fee_per_side": self.exchange_fee_per_side,
            "futures_tax_per_side": self.futures_tax_per_side,
            "slippage_ticks_day": self.slippage_ticks_day,
            "slippage_ticks_night": self.slippage_ticks_night,
            "cost_model_version": self.cost_model_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CostModel":
        return cls(
            broker_fee_per_side=float(data.get("broker_fee_per_side", 20.0)),
            exchange_fee_per_side=float(data.get("exchange_fee_per_side", 2.0)),
            futures_tax_per_side=float(data.get("futures_tax_per_side", 0.0)),
            slippage_ticks_day=float(data.get("slippage_ticks_day", 1.0)),
            slippage_ticks_night=float(data.get("slippage_ticks_night", 2.0)),
            cost_model_version=str(data.get("cost_model_version", "v1.0")),
        )


# 預設成本模型
DEFAULT_COST_MODEL = CostModel()
