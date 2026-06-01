"""
QuantVision Pro — Paper Trading Risk Engine

期貨模擬交易風控引擎，負責：
- 開倉前檢查（資金/口數/單日虧損/回撤/時段/結算日/資料新鮮度）
- 可下口數計算
- 強制平倉判斷（收盤前/單日虧損/最大回撤）
- 風控事件紀錄
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as time_of_day, timedelta
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
from paper_trading.futures_risk_sizing import (
    FuturesPositionSizingInput,
    FuturesPositionSizingResult,
    calculate_futures_position_sizing,
)


class HoldingPolicy(str, Enum):
    DAY_ONLY = "day_only"
    OVERNIGHT_ALLOWED = "overnight_allowed"


class RiskDenyReason(str, Enum):
    DAILY_LOSS_LIMIT = "daily_loss_limit_reached"
    MAX_DRAWDOWN = "max_drawdown_reached"
    MAX_CONTRACTS = "max_contracts_reached"
    MARGIN_EXCEEDED = "margin_usage_exceeded"
    NEAR_CLOSE = "too_close_to_session_close"
    NEAR_EXPIRY = "near_expiry_date"
    COOLDOWN = "cooldown_active"
    NO_EQUITY = "insufficient_equity"
    QUOTE_STALE = "quote_data_stale"
    OUTSIDE_SESSION = "outside_trading_session"
    ORDER_SIZE_EXCEEDED = "order_size_exceeded"


# ─── 交易時段定義 ─────────────────────────────────────────────

DAY_SESSION_OPEN = time_of_day(8, 45)
DAY_SESSION_CLOSE = time_of_day(13, 45)
NIGHT_SESSION_OPEN = time_of_day(15, 0)
NIGHT_SESSION_CLOSE = time_of_day(5, 0)   # 次日 05:00

# 到期日日盤收 13:30
EXPIRY_DAY_SESSION_CLOSE = time_of_day(13, 30)


def determine_session(bar_time: datetime) -> Optional[SessionType]:
    """判斷當前時間屬於哪個交易時段"""
    t = bar_time.time()
    if DAY_SESSION_OPEN <= t <= DAY_SESSION_CLOSE:
        return SessionType.DAY
    if t >= NIGHT_SESSION_OPEN or t <= NIGHT_SESSION_CLOSE:
        return SessionType.NIGHT
    return None


def trading_session_key(bar_time: datetime, session: SessionType) -> str:
    """Return a stable key for the trading session containing bar_time."""
    session_date = bar_time.date()
    if session == SessionType.NIGHT and bar_time.time() <= NIGHT_SESSION_CLOSE:
        session_date = (bar_time - timedelta(days=1)).date()
    return f"{session_date.isoformat()}:{session.value}"


def minutes_to_session_close(bar_time: datetime, session: SessionType) -> float:
    """計算距離該時段收盤的分鐘數"""
    t = bar_time.time()
    if session == SessionType.DAY:
        close = DAY_SESSION_CLOSE
        return (close.hour * 60 + close.minute) - (t.hour * 60 + t.minute)
    # 夜盤：跨日計算
    if t >= NIGHT_SESSION_OPEN:
        minutes_until_midnight = (24 * 60) - (t.hour * 60 + t.minute)
        minutes_after_midnight = NIGHT_SESSION_CLOSE.hour * 60 + NIGHT_SESSION_CLOSE.minute
        return minutes_until_midnight + minutes_after_midnight
    # 已在次日 00:00~05:00
    return (NIGHT_SESSION_CLOSE.hour * 60 + NIGHT_SESSION_CLOSE.minute) - (t.hour * 60 + t.minute)


# ─── 風控設定 ─────────────────────────────────────────────────

@dataclass
class RiskConfig:
    """風控參數設定"""

    # 帳戶與資金
    starting_equity: float = 100_000.0          # 模擬帳戶初始權益 (TWD)
    initial_margin_per_contract: float = 28_900.0  # TMF 原始保證金
    maintenance_margin_per_contract: float = 20_150.0  # TMF 維持保證金

    # 口數上限
    max_contracts_hard: int = 10                # 硬上限口數
    max_margin_usage_pct: float = 0.6           # 保證金占用上限比例

    # 單筆風險
    risk_per_trade_pct: float = 0.02            # 單筆交易風險（帳戶比例）
    stress_points: float = 2_000.0              # 壓力測試點數
    total_position_risk_pct: float = 0.2        # 總部位壓力風險（帳戶比例）

    # 單日虧損
    daily_loss_limit_pct: float = 0.05          # 單日虧損上限比例

    # 最大回撤
    max_drawdown_pct: float = 0.15              # 自高點回撤上限

    # 單筆持倉浮虧
    max_open_loss_base: float = 5_000.0         # 單筆持倉浮虧上限 (TWD)

    # 冷卻
    cooldown_bars: int = 3                      # 連續虧損後冷卻 K 棒數

    # 收盤前規則
    flatten_before_close_minutes: int = 5       # 收盤前 N 分鐘強制平倉
    no_new_position_before_close_minutes: int = 15  # 收盤前 N 分鐘禁止新倉

    # 持倉政策
    holding_policy: HoldingPolicy = HoldingPolicy.DAY_ONLY

    # 結算日規則
    no_open_on_expiry_day: bool = True          # 到期日當天不開新倉
    no_open_days_before_expiry: int = 0         # 到期日前 N 天不開新倉

    # 資料新鮮度
    max_quote_age_seconds: float = 30.0         # quote 最大可接受延遲

    def to_dict(self) -> dict:
        return {
            "starting_equity": self.starting_equity,
            "initial_margin_per_contract": self.initial_margin_per_contract,
            "maintenance_margin_per_contract": self.maintenance_margin_per_contract,
            "max_contracts_hard": self.max_contracts_hard,
            "max_margin_usage_pct": self.max_margin_usage_pct,
            "margin_usage_limit": self.max_margin_usage_pct,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "single_trade_risk_pct": self.risk_per_trade_pct,
            "stress_points": self.stress_points,
            "total_position_risk_pct": self.total_position_risk_pct,
            "user_max_contracts": self.max_contracts_hard,
            "daily_loss_limit_pct": self.daily_loss_limit_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_open_loss_base": self.max_open_loss_base,
            "cooldown_bars": self.cooldown_bars,
            "flatten_before_close_minutes": self.flatten_before_close_minutes,
            "no_new_position_before_close_minutes": self.no_new_position_before_close_minutes,
            "holding_policy": self.holding_policy.value,
            "no_open_on_expiry_day": self.no_open_on_expiry_day,
            "no_open_days_before_expiry": self.no_open_days_before_expiry,
            "max_quote_age_seconds": self.max_quote_age_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RiskConfig":
        holding = data.get("holding_policy", "day_only")
        return cls(
            starting_equity=float(data.get("starting_equity", 100_000)),
            initial_margin_per_contract=float(data.get("initial_margin_per_contract", 28_900)),
            maintenance_margin_per_contract=float(data.get("maintenance_margin_per_contract", 20_150)),
            max_contracts_hard=int(data.get("max_contracts_hard", data.get("user_max_contracts", 10))),
            max_margin_usage_pct=float(data.get("max_margin_usage_pct", data.get("margin_usage_limit", 0.6))),
            risk_per_trade_pct=float(data.get("risk_per_trade_pct", data.get("single_trade_risk_pct", 0.02))),
            stress_points=float(data.get("stress_points", 2_000)),
            total_position_risk_pct=float(data.get("total_position_risk_pct", 0.2)),
            daily_loss_limit_pct=float(data.get("daily_loss_limit_pct", 0.05)),
            max_drawdown_pct=float(data.get("max_drawdown_pct", 0.15)),
            max_open_loss_base=float(data.get("max_open_loss_base", 5_000)),
            cooldown_bars=int(data.get("cooldown_bars", 3)),
            flatten_before_close_minutes=int(data.get("flatten_before_close_minutes", 5)),
            no_new_position_before_close_minutes=int(data.get("no_new_position_before_close_minutes", 15)),
            holding_policy=HoldingPolicy(holding) if isinstance(holding, str) else HoldingPolicy.DAY_ONLY,
            no_open_on_expiry_day=bool(data.get("no_open_on_expiry_day", True)),
            no_open_days_before_expiry=int(data.get("no_open_days_before_expiry", 0)),
            max_quote_age_seconds=float(data.get("max_quote_age_seconds", 30.0)),
        )


# ─── 帳戶狀態快照（用於風控判斷） ────────────────────────────

@dataclass
class AccountState:
    """Paper Account 的即時風控狀態快照"""
    equity: float = 0.0
    cash: float = 0.0
    margin_used: float = 0.0
    unrealized_pnl: float = 0.0
    daily_realized_pnl: float = 0.0
    daily_unrealized_pnl: float = 0.0
    peak_equity: float = 0.0
    current_drawdown_pct: float = 0.0
    open_position_qty: int = 0
    open_position_side: Optional[OrderSide] = None
    cooldown_remaining_bars: int = 0
    consecutive_losses: int = 0
    starting_equity: float = 0.0


# ─── 風控引擎 ─────────────────────────────────────────────────

class RiskCheckResult:
    """風控檢查結果"""

    def __init__(
        self,
        allowed: bool,
        deny_reasons: Optional[list[RiskDenyReason]] = None,
        details: Optional[dict] = None,
    ):
        self.allowed = allowed
        self.deny_reasons = deny_reasons or []
        self.details = details or {}

    def __bool__(self) -> bool:
        return self.allowed

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "deny_reasons": [r.value for r in self.deny_reasons],
            "details": self.details,
        }


class RiskEngine:
    """期貨模擬交易風控引擎"""

    def __init__(
        self,
        config: RiskConfig,
        cost_model: CostModel = DEFAULT_COST_MODEL,
        product: FuturesProductSpec = TMF_SPEC,
    ):
        self.config = config
        self.cost_model = cost_model
        self.product = product
        self._risk_events: list[dict] = []

    def check_can_open(
        self,
        account: AccountState,
        bar_time: datetime,
        *,
        is_expiry_day: bool = False,
        days_to_expiry: Optional[int] = None,
    ) -> RiskCheckResult:
        """
        檢查是否允許開新倉。
        回傳 RiskCheckResult，其中 allowed=True 表示可以開倉。
        """
        deny_reasons: list[RiskDenyReason] = []

        # 1. 交易時段檢查
        session = determine_session(bar_time)
        if session is None:
            deny_reasons.append(RiskDenyReason.OUTSIDE_SESSION)
            return RiskCheckResult(False, deny_reasons)

        # 2. 接近收盤禁止新倉
        mins_to_close = minutes_to_session_close(bar_time, session)
        if mins_to_close <= self.config.no_new_position_before_close_minutes:
            deny_reasons.append(RiskDenyReason.NEAR_CLOSE)

        # 3. 結算日規則
        if is_expiry_day and self.config.no_open_on_expiry_day:
            deny_reasons.append(RiskDenyReason.NEAR_EXPIRY)
        if days_to_expiry is not None and days_to_expiry <= self.config.no_open_days_before_expiry:
            deny_reasons.append(RiskDenyReason.NEAR_EXPIRY)

        # 4. 冷卻中
        if account.cooldown_remaining_bars > 0:
            deny_reasons.append(RiskDenyReason.COOLDOWN)

        # 5. 單日虧損上限
        daily_pnl = account.daily_realized_pnl + account.daily_unrealized_pnl
        daily_loss_limit = account.starting_equity * self.config.daily_loss_limit_pct
        if daily_pnl < 0 and abs(daily_pnl) >= daily_loss_limit:
            deny_reasons.append(RiskDenyReason.DAILY_LOSS_LIMIT)

        # 6. 最大回撤
        if account.current_drawdown_pct >= self.config.max_drawdown_pct:
            deny_reasons.append(RiskDenyReason.MAX_DRAWDOWN)

        # 7. 口數上限
        if abs(account.open_position_qty) >= self.config.max_contracts_hard:
            deny_reasons.append(RiskDenyReason.MAX_CONTRACTS)

        # 8. 保證金占用
        available_equity = max(0, account.equity)
        if available_equity <= 0:
            deny_reasons.append(RiskDenyReason.NO_EQUITY)
        else:
            max_margin = available_equity * self.config.max_margin_usage_pct
            if account.margin_used >= max_margin:
                deny_reasons.append(RiskDenyReason.MARGIN_EXCEEDED)

        return RiskCheckResult(len(deny_reasons) == 0, deny_reasons)

    def calculate_position_size(
        self,
        account: AccountState,
        stop_distance_points: float,
        session: SessionType = SessionType.DAY,
    ) -> int:
        """
        計算可下口數，取以下三種上限的最小值：
        1. 硬上限口數
        2. 保證金可承受口數
        3. 停損風險可承受口數
        """
        return self.calculate_position_sizing(
            account,
            stop_distance_points,
            session,
        ).addable_contracts

    def calculate_position_sizing(
        self,
        account: AccountState,
        stop_distance_points: float,
        session: SessionType = SessionType.DAY,
    ) -> FuturesPositionSizingResult:
        initial_margin = float(
            self.config.initial_margin_per_contract
            or self.product.initial_margin
            or 0.0
        )
        maintenance_margin = float(
            self.config.maintenance_margin_per_contract
            or self.product.maintenance_margin
            or 0.0
        )
        params = FuturesPositionSizingInput(
            futures_capital=account.equity,
            point_value=self.product.point_value,
            initial_margin=initial_margin,
            maintenance_margin=maintenance_margin,
            stop_loss_points=stop_distance_points,
            stress_points=self.config.stress_points,
            margin_usage_limit=self.config.max_margin_usage_pct,
            single_trade_risk_pct=self.config.risk_per_trade_pct,
            total_position_risk_pct=self.config.total_position_risk_pct,
            user_max_contracts=self.config.max_contracts_hard,
            open_contracts=abs(account.open_position_qty),
            margin_used=account.margin_used,
        )
        return calculate_futures_position_sizing(params)

    def check_order_size(
        self,
        account: AccountState,
        requested_qty: int,
        stop_distance_points: float,
        session: SessionType = SessionType.DAY,
    ) -> RiskCheckResult:
        sizing = self.calculate_position_sizing(account, stop_distance_points, session)
        normalized_qty = max(0, int(requested_qty or 0))
        allowed = normalized_qty > 0 and normalized_qty <= sizing.addable_contracts
        return RiskCheckResult(
            allowed,
            [] if allowed else [RiskDenyReason.ORDER_SIZE_EXCEEDED],
            {
                "requested_qty": normalized_qty,
                "allowed_qty": sizing.addable_contracts,
                "sizing": sizing.to_dict(),
            },
        )

    def check_must_flatten(
        self,
        bar_time: datetime,
        session: SessionType,
    ) -> bool:
        """
        檢查是否到了必須強制平倉的時間。
        僅在 holding_policy = day_only 時生效。
        """
        if self.config.holding_policy != HoldingPolicy.DAY_ONLY:
            return False
        mins = minutes_to_session_close(bar_time, session)
        return mins <= self.config.flatten_before_close_minutes

    def check_daily_loss_limit(self, account: AccountState) -> bool:
        """檢查是否已達單日虧損上限"""
        daily_pnl = account.daily_realized_pnl + account.daily_unrealized_pnl
        daily_loss_limit = account.starting_equity * self.config.daily_loss_limit_pct
        return daily_pnl < 0 and abs(daily_pnl) >= daily_loss_limit

    def check_drawdown_limit(self, account: AccountState) -> bool:
        """檢查是否已達最大回撤上限"""
        return account.current_drawdown_pct >= self.config.max_drawdown_pct

    def check_open_loss_limit(
        self,
        unrealized_pnl: float,
    ) -> bool:
        """檢查單筆持倉浮虧是否超過上限"""
        return unrealized_pnl < 0 and abs(unrealized_pnl) >= self.config.max_open_loss_base

    def record_risk_event(self, event_type: str, details: dict) -> dict:
        """紀錄風控事件"""
        event = {
            "event_type": event_type,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        }
        self._risk_events.append(event)
        return event

    def get_risk_events(self) -> list[dict]:
        return list(self._risk_events)

    def clear_risk_events(self) -> None:
        self._risk_events.clear()
