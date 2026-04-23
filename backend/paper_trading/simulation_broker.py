"""
QuantVision Pro — Paper Trading Simulation Broker

模擬券商，負責：
- 接收委託（market / marketable_limit / stop_market）
- 用新 K 棒撮合
- 套用保守成交原則
- 每筆 fill 保存 fill_price, fill_qty, slippage_ticks, fill_reason
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from paper_trading.cost_model import (
    CostModel,
    FuturesProductSpec,
    OrderSide,
    SessionType,
    TMF_SPEC,
    DEFAULT_COST_MODEL,
)


class OrderType(str, Enum):
    MARKET = "market"
    MARKETABLE_LIMIT = "marketable_limit"
    STOP_MARKET = "stop_market"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class FillReason(str, Enum):
    MARKET_OPEN = "market_fill_at_open"
    STOP_TRIGGERED = "stop_triggered"
    LIMIT_MATCHED = "limit_matched"
    FORCED_FLATTEN = "forced_flatten"
    SESSION_CLOSE = "session_close_flatten"
    RISK_FLATTEN = "risk_forced_flatten"


# ─── 委託 ─────────────────────────────────────────────────────

@dataclass
class Order:
    """模擬委託"""
    order_id: str
    symbol: str
    side: OrderSide
    qty: int
    order_type: OrderType
    price: Optional[float] = None           # limit / stop price
    stop_price: Optional[float] = None      # stop_market trigger price
    session: SessionType = SessionType.DAY
    status: OrderStatus = OrderStatus.PENDING
    created_at: Optional[datetime] = None
    signal_bar_time: Optional[datetime] = None
    reason: str = ""
    requested_symbol: str = ""
    resolved_symbol: str = ""

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "qty": self.qty,
            "order_type": self.order_type.value,
            "price": self.price,
            "stop_price": self.stop_price,
            "session": self.session.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "signal_bar_time": self.signal_bar_time.isoformat() if self.signal_bar_time else None,
            "reason": self.reason,
            "requested_symbol": self.requested_symbol,
            "resolved_symbol": self.resolved_symbol,
        }


# ─── 成交 ─────────────────────────────────────────────────────

@dataclass
class Fill:
    """模擬成交"""
    fill_id: str
    order_id: str
    symbol: str
    side: OrderSide
    fill_qty: int
    fill_price: float
    slippage_ticks: float
    fee_amount: float
    fill_reason: FillReason
    fill_time: Optional[datetime] = None
    session: SessionType = SessionType.DAY
    bar_open: Optional[float] = None
    bar_high: Optional[float] = None
    bar_low: Optional[float] = None
    bar_close: Optional[float] = None

    @property
    def gross_value(self) -> float:
        """成交金額（點 × 點值 × 口數），不含方向"""
        return self.fill_price * self.fill_qty

    def to_dict(self) -> dict:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "fill_qty": self.fill_qty,
            "fill_price": self.fill_price,
            "slippage_ticks": self.slippage_ticks,
            "fee_amount": self.fee_amount,
            "fill_reason": self.fill_reason.value,
            "fill_time": self.fill_time.isoformat() if self.fill_time else None,
            "session": self.session.value,
            "bar_open": self.bar_open,
            "bar_high": self.bar_high,
            "bar_low": self.bar_low,
            "bar_close": self.bar_close,
        }


# ─── K 棒 ─────────────────────────────────────────────────────

@dataclass
class Bar:
    """K 棒資料"""
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    symbol: str = ""

    def to_dict(self) -> dict:
        return {
            "time": self.time.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "symbol": self.symbol,
        }


# ─── 模擬券商 ─────────────────────────────────────────────────

class SimulationBroker:
    """
    模擬券商。

    第一版僅正式支援：market, marketable_limit, stop_market。
    保守成交原則：
    - market order：下一根 open ± 滑價
    - stop_market：停損價觸發後以最不利方向 + 滑價成交
    - marketable_limit：bar 內明確可成交時才成交
    """

    def __init__(
        self,
        cost_model: CostModel = DEFAULT_COST_MODEL,
        product: FuturesProductSpec = TMF_SPEC,
    ):
        self.cost_model = cost_model
        self.product = product
        self._pending_orders: list[Order] = []
        self._all_orders: list[Order] = []
        self._all_fills: list[Fill] = []
        self._next_order_id = 1
        self._next_fill_id = 1

    def submit_order(self, order: Order) -> Order:
        """提交委託到待成交佇列"""
        if not order.order_id:
            order.order_id = f"ORD-{self._next_order_id:06d}"
            self._next_order_id += 1
        if not order.created_at:
            order.created_at = datetime.now()
        order.status = OrderStatus.PENDING
        self._pending_orders.append(order)
        self._all_orders.append(order)
        return order

    def create_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: int,
        session: SessionType = SessionType.DAY,
        reason: str = "",
        signal_bar_time: Optional[datetime] = None,
        requested_symbol: str = "",
        resolved_symbol: str = "",
    ) -> Order:
        """快捷建立市價委託"""
        order = Order(
            order_id="",
            symbol=symbol,
            side=side,
            qty=qty,
            order_type=OrderType.MARKET,
            session=session,
            reason=reason,
            signal_bar_time=signal_bar_time,
            requested_symbol=requested_symbol or symbol,
            resolved_symbol=resolved_symbol or symbol,
        )
        return self.submit_order(order)

    def create_stop_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: int,
        stop_price: float,
        session: SessionType = SessionType.DAY,
        reason: str = "",
        signal_bar_time: Optional[datetime] = None,
    ) -> Order:
        """快捷建立停損委託"""
        order = Order(
            order_id="",
            symbol=symbol,
            side=side,
            qty=qty,
            order_type=OrderType.STOP_MARKET,
            stop_price=stop_price,
            session=session,
            reason=reason,
            signal_bar_time=signal_bar_time,
        )
        return self.submit_order(order)

    def cancel_pending_orders(self, *, symbol: Optional[str] = None) -> list[Order]:
        """取消所有（或指定商品的）待成交委託"""
        cancelled = []
        remaining = []
        for order in self._pending_orders:
            if symbol and order.symbol != symbol:
                remaining.append(order)
                continue
            order.status = OrderStatus.CANCELLED
            cancelled.append(order)
        self._pending_orders = remaining
        return cancelled

    def process_bar(self, bar: Bar) -> list[Fill]:
        """
        用新 K 棒撮合所有待成交委託。

        保守成交原則：
        - market：成交在 bar.open ± 滑價
        - stop_market：若 bar 價格觸及停損價，以 stop_price ± 滑價成交
        - marketable_limit：limit price 在 bar 範圍內才成交
        """
        fills: list[Fill] = []
        still_pending: list[Order] = []

        for order in self._pending_orders:
            if order.symbol != bar.symbol and order.symbol != "":
                # 不同商品的委託保留
                if bar.symbol and order.symbol != bar.symbol:
                    still_pending.append(order)
                    continue

            fill = self._try_fill_order(order, bar)
            if fill:
                order.status = OrderStatus.FILLED
                fills.append(fill)
                self._all_fills.append(fill)
            else:
                still_pending.append(order)

        self._pending_orders = still_pending
        return fills

    def force_flatten_fill(
        self,
        symbol: str,
        side: OrderSide,
        qty: int,
        bar: Bar,
        reason: FillReason = FillReason.FORCED_FLATTEN,
        session: SessionType = SessionType.DAY,
    ) -> Fill:
        """強制平倉成交（收盤前或風控觸發）"""
        slippage = self.cost_model.slippage_ticks(session)
        fill_price = self.cost_model.apply_slippage(
            bar.close, side, session, self.product,
        )
        fee = self.cost_model.fee_per_side()

        fill = Fill(
            fill_id=f"FILL-{self._next_fill_id:06d}",
            order_id="FORCE",
            symbol=symbol,
            side=side,
            fill_qty=abs(qty),
            fill_price=fill_price,
            slippage_ticks=slippage,
            fee_amount=fee * abs(qty),
            fill_reason=reason,
            fill_time=bar.time,
            session=session,
            bar_open=bar.open,
            bar_high=bar.high,
            bar_low=bar.low,
            bar_close=bar.close,
        )
        self._next_fill_id += 1
        self._all_fills.append(fill)
        return fill

    def _try_fill_order(self, order: Order, bar: Bar) -> Optional[Fill]:
        """嘗試用 bar 撮合單筆委託"""
        session = order.session

        if order.order_type == OrderType.MARKET:
            return self._fill_market(order, bar, session)

        if order.order_type == OrderType.STOP_MARKET:
            return self._fill_stop_market(order, bar, session)

        if order.order_type == OrderType.MARKETABLE_LIMIT:
            return self._fill_marketable_limit(order, bar, session)

        return None

    def _fill_market(self, order: Order, bar: Bar, session: SessionType) -> Fill:
        """市價單：以 bar.open ± 滑價成交"""
        slippage = self.cost_model.slippage_ticks(session)
        fill_price = self.cost_model.apply_slippage(
            bar.open, order.side, session, self.product,
        )
        fee = self.cost_model.fee_per_side()

        fill = Fill(
            fill_id=f"FILL-{self._next_fill_id:06d}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            fill_qty=order.qty,
            fill_price=fill_price,
            slippage_ticks=slippage,
            fee_amount=fee * order.qty,
            fill_reason=FillReason.MARKET_OPEN,
            fill_time=bar.time,
            session=session,
            bar_open=bar.open,
            bar_high=bar.high,
            bar_low=bar.low,
            bar_close=bar.close,
        )
        self._next_fill_id += 1
        return fill

    def _fill_stop_market(self, order: Order, bar: Bar, session: SessionType) -> Optional[Fill]:
        """
        停損單：
        - 買入停損：bar.high >= stop_price 時觸發
        - 賣出停損：bar.low <= stop_price 時觸發
        成交價 = stop_price ± 滑價（最不利方向）
        """
        if order.stop_price is None:
            return None

        triggered = False
        if order.side == OrderSide.BUY and bar.high >= order.stop_price:
            triggered = True
        elif order.side == OrderSide.SELL and bar.low <= order.stop_price:
            triggered = True

        if not triggered:
            return None

        slippage = self.cost_model.slippage_ticks(session)
        fill_price = self.cost_model.apply_slippage(
            order.stop_price, order.side, session, self.product,
        )
        fee = self.cost_model.fee_per_side()

        fill = Fill(
            fill_id=f"FILL-{self._next_fill_id:06d}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            fill_qty=order.qty,
            fill_price=fill_price,
            slippage_ticks=slippage,
            fee_amount=fee * order.qty,
            fill_reason=FillReason.STOP_TRIGGERED,
            fill_time=bar.time,
            session=session,
            bar_open=bar.open,
            bar_high=bar.high,
            bar_low=bar.low,
            bar_close=bar.close,
        )
        self._next_fill_id += 1
        return fill

    def _fill_marketable_limit(self, order: Order, bar: Bar, session: SessionType) -> Optional[Fill]:
        """
        可成交限價單：
        - 買入：limit price >= bar.low → 成交
        - 賣出：limit price <= bar.high → 成交
        成交價 = limit price（不加滑價，因為是限價）
        """
        if order.price is None:
            return None

        can_fill = False
        if order.side == OrderSide.BUY and order.price >= bar.low:
            can_fill = True
        elif order.side == OrderSide.SELL and order.price <= bar.high:
            can_fill = True

        if not can_fill:
            return None

        fee = self.cost_model.fee_per_side()

        fill = Fill(
            fill_id=f"FILL-{self._next_fill_id:06d}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            fill_qty=order.qty,
            fill_price=order.price,
            slippage_ticks=0.0,
            fee_amount=fee * order.qty,
            fill_reason=FillReason.LIMIT_MATCHED,
            fill_time=bar.time,
            session=session,
            bar_open=bar.open,
            bar_high=bar.high,
            bar_low=bar.low,
            bar_close=bar.close,
        )
        self._next_fill_id += 1
        return fill

    @property
    def pending_orders(self) -> list[Order]:
        return list(self._pending_orders)

    @property
    def all_orders(self) -> list[Order]:
        return list(self._all_orders)

    @property
    def all_fills(self) -> list[Fill]:
        return list(self._all_fills)

    def reset(self) -> None:
        """重置所有狀態"""
        self._pending_orders.clear()
        self._all_orders.clear()
        self._all_fills.clear()
        self._next_order_id = 1
        self._next_fill_id = 1
