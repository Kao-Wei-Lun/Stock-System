"""
QuantVision Pro — Paper Trading Account

管理模擬帳戶的：
- 可用權益、已實現損益、未實現損益、保證金占用
- 部位管理（開倉、加碼、平倉）
- 權益快照
- 支援多空方向

設計原則：期貨看的是「權益 / 保證金 / 可動用資金」，不套用股票的持倉估值模型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from paper_trading.cost_model import (
    CostModel,
    FuturesProductSpec,
    OrderSide,
    SessionType,
    TMF_SPEC,
    DEFAULT_COST_MODEL,
)
from paper_trading.simulation_broker import Fill, FillReason
from paper_trading.risk_engine import AccountState


# ─── 持倉 ─────────────────────────────────────────────────────

@dataclass
class Position:
    """期貨持倉"""
    symbol: str
    side: OrderSide
    qty: int
    avg_entry_price: float
    entry_time: Optional[datetime] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    last_price: float = 0.0
    entry_reason: str = ""

    @property
    def is_long(self) -> bool:
        return self.side == OrderSide.BUY

    @property
    def is_short(self) -> bool:
        return self.side == OrderSide.SELL

    @property
    def signed_qty(self) -> int:
        return self.qty if self.is_long else -self.qty

    def update_unrealized(self, current_price: float, point_value: float) -> float:
        """更新未平倉損益"""
        self.last_price = current_price
        if self.is_long:
            self.unrealized_pnl = (current_price - self.avg_entry_price) * self.qty * point_value
        else:
            self.unrealized_pnl = (self.avg_entry_price - current_price) * self.qty * point_value
        return self.unrealized_pnl

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "qty": self.qty,
            "avg_entry_price": self.avg_entry_price,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "last_price": self.last_price,
            "entry_reason": self.entry_reason,
        }


# ─── 交易紀錄 ─────────────────────────────────────────────────

@dataclass
class TradeRecord:
    """完整的交易紀錄（開 → 平）"""
    trade_id: str
    symbol: str
    side: OrderSide
    entry_price: float
    entry_time: datetime
    exit_price: float
    exit_time: datetime
    qty: int
    gross_pnl: float
    fee_total: float
    net_pnl: float
    entry_reason: str = ""
    exit_reason: str = ""
    holding_bars: int = 0

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat(),
            "qty": self.qty,
            "gross_pnl": round(self.gross_pnl, 2),
            "fee_total": round(self.fee_total, 2),
            "net_pnl": round(self.net_pnl, 2),
            "entry_reason": self.entry_reason,
            "exit_reason": self.exit_reason,
            "holding_bars": self.holding_bars,
        }


# ─── 權益快照 ─────────────────────────────────────────────────

@dataclass
class EquitySnapshot:
    """權益快照"""
    timestamp: datetime
    equity: float
    cash: float
    margin_used: float
    unrealized_pnl: float
    realized_pnl: float
    position_qty: int = 0
    position_side: str = ""
    close_price: float = 0.0
    drawdown_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "equity": round(self.equity, 2),
            "cash": round(self.cash, 2),
            "margin_used": round(self.margin_used, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "position_qty": self.position_qty,
            "position_side": self.position_side,
            "close_price": self.close_price,
            "drawdown_pct": round(self.drawdown_pct, 4),
        }


# ─── Paper Account ────────────────────────────────────────────

class PaperAccount:
    """
    期貨模擬帳戶。

    管理：可用權益、保證金占用、持倉、損益追蹤、權益快照。
    """

    def __init__(
        self,
        starting_equity: float = 100_000.0,
        cost_model: CostModel = DEFAULT_COST_MODEL,
        product: FuturesProductSpec = TMF_SPEC,
        margin_per_contract: float = 28_900.0,
    ):
        self.starting_equity = starting_equity
        self.cost_model = cost_model
        self.product = product
        self.margin_per_contract = margin_per_contract

        # 資金狀態
        self.cash = starting_equity
        self.margin_used = 0.0
        self.total_realized_pnl = 0.0
        self.total_fees = 0.0

        # 當日損益追蹤
        self.daily_realized_pnl = 0.0
        self.daily_start_equity = starting_equity

        # 權益追蹤
        self.peak_equity = starting_equity
        self.current_drawdown_pct = 0.0

        # 持倉
        self.position: Optional[Position] = None

        # 紀錄
        self.trades: list[TradeRecord] = []
        self.equity_snapshots: list[EquitySnapshot] = []

        # 冷卻
        self.cooldown_remaining_bars = 0
        self.consecutive_losses = 0

        # 計數
        self._next_trade_id = 1
        self._bar_count = 0
        self._entry_fill_fee = 0.0  # 暫存開倉 fill 的手續費

    @property
    def equity(self) -> float:
        """帳戶總權益 = 現金 + 未平倉損益"""
        unrealized = self.position.unrealized_pnl if self.position else 0.0
        return self.cash + unrealized

    @property
    def unrealized_pnl(self) -> float:
        return self.position.unrealized_pnl if self.position else 0.0

    @property
    def daily_total_pnl(self) -> float:
        return self.daily_realized_pnl + self.unrealized_pnl

    def on_fill(self, fill: Fill) -> Optional[TradeRecord]:
        """
        處理成交回報。

        開倉 fill → 建立/加碼持倉
        平倉 fill → 計算損益、紀錄交易
        """
        self._bar_count += 1

        # 扣除手續費
        self.cash -= fill.fee_amount
        self.total_fees += fill.fee_amount

        if self.position is None:
            # 無持倉 → 開倉
            return self._open_position(fill)

        if self.position.side == fill.side:
            # 同方向 → 加碼
            return self._add_to_position(fill)

        # 反方向 → 平倉
        return self._close_position(fill)

    def on_bar(
        self,
        current_price: float,
        bar_time: Optional[datetime] = None,
        *,
        advance_bar: bool = True,
    ) -> None:
        """更新未平倉損益與權益追蹤"""
        if self.position:
            self.position.update_unrealized(current_price, self.product.point_value)

        # 更新回撤
        current_equity = self.equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        if self.peak_equity > 0:
            self.current_drawdown_pct = max(0, (self.peak_equity - current_equity) / self.peak_equity)

        # 冷卻倒數
        if advance_bar and self.cooldown_remaining_bars > 0:
            self.cooldown_remaining_bars -= 1

    def take_equity_snapshot(self, bar_time: datetime, close_price: float = 0.0) -> EquitySnapshot:
        """產生權益快照"""
        snapshot = EquitySnapshot(
            timestamp=bar_time,
            equity=self.equity,
            cash=self.cash,
            margin_used=self.margin_used,
            unrealized_pnl=self.unrealized_pnl,
            realized_pnl=self.total_realized_pnl,
            position_qty=self.position.qty if self.position else 0,
            position_side=self.position.side.value if self.position else "",
            close_price=close_price,
            drawdown_pct=self.current_drawdown_pct,
        )
        self.equity_snapshots.append(snapshot)
        return snapshot

    def reset_daily(self) -> None:
        """重置當日損益追蹤（新交易日開始時呼叫）"""
        self.daily_realized_pnl = 0.0
        self.daily_start_equity = self.equity

    def get_account_state(self) -> AccountState:
        """取得風控用的帳戶狀態快照"""
        return AccountState(
            equity=self.equity,
            cash=self.cash,
            margin_used=self.margin_used,
            unrealized_pnl=self.unrealized_pnl,
            daily_realized_pnl=self.daily_realized_pnl,
            daily_unrealized_pnl=self.unrealized_pnl,
            peak_equity=self.peak_equity,
            current_drawdown_pct=self.current_drawdown_pct,
            open_position_qty=self.position.qty if self.position else 0,
            open_position_side=self.position.side if self.position else None,
            cooldown_remaining_bars=self.cooldown_remaining_bars,
            consecutive_losses=self.consecutive_losses,
            starting_equity=self.starting_equity,
        )

    def to_dict(self) -> dict:
        return {
            "starting_equity": self.starting_equity,
            "equity": round(self.equity, 2),
            "cash": round(self.cash, 2),
            "margin_used": round(self.margin_used, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "total_realized_pnl": round(self.total_realized_pnl, 2),
            "total_fees": round(self.total_fees, 2),
            "daily_realized_pnl": round(self.daily_realized_pnl, 2),
            "peak_equity": round(self.peak_equity, 2),
            "current_drawdown_pct": round(self.current_drawdown_pct, 4),
            "position": self.position.to_dict() if self.position else None,
            "trade_count": len(self.trades),
            "cooldown_remaining_bars": self.cooldown_remaining_bars,
        }

    # ─── Private ──────────────────────────────────────────────

    def _open_position(self, fill: Fill) -> None:
        """建立新持倉"""
        self.position = Position(
            symbol=fill.symbol,
            side=fill.side,
            qty=fill.fill_qty,
            avg_entry_price=fill.fill_price,
            entry_time=fill.fill_time,
            entry_reason=fill.order_reason or fill.fill_reason.value,
        )
        self.margin_used = fill.fill_qty * self.margin_per_contract
        self._entry_fill_fee = fill.fee_amount
        return None

    def _add_to_position(self, fill: Fill) -> None:
        """加碼（同方向）"""
        pos = self.position
        total_qty = pos.qty + fill.fill_qty
        pos.avg_entry_price = (
            (pos.avg_entry_price * pos.qty + fill.fill_price * fill.fill_qty)
            / total_qty
        )
        pos.qty = total_qty
        self.margin_used = total_qty * self.margin_per_contract
        self._entry_fill_fee += fill.fee_amount
        return None

    def _close_position(self, fill: Fill) -> Optional[TradeRecord]:
        """平倉（反方向）"""
        pos = self.position
        close_qty = min(fill.fill_qty, pos.qty)

        # 計算損益
        if pos.is_long:
            gross_pnl = (fill.fill_price - pos.avg_entry_price) * close_qty * self.product.point_value
        else:
            gross_pnl = (pos.avg_entry_price - fill.fill_price) * close_qty * self.product.point_value

        # 手續費 = 開倉 + 平倉（按比例分攤）
        entry_fee_share = self._entry_fill_fee * (close_qty / pos.qty) if pos.qty > 0 else 0
        total_fee = entry_fee_share + fill.fee_amount
        net_pnl = gross_pnl - total_fee

        # 更新帳戶
        self.cash += gross_pnl
        self.total_realized_pnl += net_pnl
        self.daily_realized_pnl += net_pnl

        # 紀錄交易
        trade = TradeRecord(
            trade_id=f"T-{self._next_trade_id:06d}",
            symbol=pos.symbol,
            side=pos.side,
            entry_price=pos.avg_entry_price,
            entry_time=pos.entry_time or fill.fill_time,
            exit_price=fill.fill_price,
            exit_time=fill.fill_time,
            qty=close_qty,
            gross_pnl=gross_pnl,
            fee_total=total_fee,
            net_pnl=net_pnl,
            entry_reason=pos.entry_reason,
            exit_reason=fill.order_reason or fill.fill_reason.value,
            holding_bars=self._bar_count,
        )
        self._next_trade_id += 1
        self.trades.append(trade)

        # 更新冷卻
        if net_pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        # 連續虧損觸發冷卻
        if net_pnl < 0:
            from paper_trading.risk_engine import RiskConfig
            self.cooldown_remaining_bars = RiskConfig().cooldown_bars

        # 更新持倉
        remaining_qty = pos.qty - close_qty
        if remaining_qty <= 0:
            self.position = None
            self.margin_used = 0.0
            self._entry_fill_fee = 0.0
            self._bar_count = 0
        else:
            pos.qty = remaining_qty
            self.margin_used = remaining_qty * self.margin_per_contract
            self._entry_fill_fee *= (remaining_qty / (remaining_qty + close_qty))

        return trade

    def get_summary(self) -> dict:
        """取得績效摘要"""
        if not self.trades:
            return {
                "trade_count": 0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
                "max_win": 0.0,
                "max_loss": 0.0,
                "profit_factor": 0.0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
            }

        wins = [t for t in self.trades if t.net_pnl > 0]
        losses = [t for t in self.trades if t.net_pnl <= 0]
        total_pnl = sum(t.net_pnl for t in self.trades)
        gross_profit = sum(t.net_pnl for t in wins) if wins else 0
        gross_loss = abs(sum(t.net_pnl for t in losses)) if losses else 0

        return {
            "trade_count": len(self.trades),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": round(len(wins) / len(self.trades) * 100, 2) if self.trades else 0.0,
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(total_pnl / len(self.trades), 2),
            "max_win": round(max((t.net_pnl for t in self.trades), default=0), 2),
            "max_loss": round(min((t.net_pnl for t in self.trades), default=0), 2),
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf"),
            "total_return_pct": round(total_pnl / self.starting_equity * 100, 2),
            "max_drawdown_pct": round(self.current_drawdown_pct * 100, 2),
        }
