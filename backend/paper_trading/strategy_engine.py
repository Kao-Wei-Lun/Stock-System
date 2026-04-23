"""
QuantVision Pro — Paper Trading Strategy Engine

實作規劃書 §7.2 的最小可用策略：
- Layer 1 方向判斷：TX 5m/15m 趨勢 + session VWAP
- Layer 2 進場觸發：TMF 1m 突破/跌破前 N 根高低點
- Layer 3 禁止條件：冷卻、單日虧損、保證金、收盤前、資料延遲

支援 day_open_profile / day_regular_profile / night_profile 分開參數。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time as time_of_day
from enum import Enum
from typing import Optional

from paper_trading.cost_model import OrderSide, SessionType
from paper_trading.simulation_broker import Bar


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    HOLD = "hold"


# ─── Session Profiles ────────────────────────────────────────

@dataclass
class SessionProfile:
    """時段交易參數"""
    stop_loss_points: float = 60.0
    take_profit_points: float = 120.0
    trail_stop_points: Optional[float] = None   # 移動停損（第一版先用固定停損停利）
    max_qty: int = 5
    volume_threshold: int = 0
    slippage_assumption: float = 1.0
    breakout_lookback: int = 5                   # 突破回看 K 棒數

    def to_dict(self) -> dict:
        return {
            "stop_loss_points": self.stop_loss_points,
            "take_profit_points": self.take_profit_points,
            "trail_stop_points": self.trail_stop_points,
            "max_qty": self.max_qty,
            "volume_threshold": self.volume_threshold,
            "slippage_assumption": self.slippage_assumption,
            "breakout_lookback": self.breakout_lookback,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionProfile":
        return cls(
            stop_loss_points=float(data.get("stop_loss_points", 60.0)),
            take_profit_points=float(data.get("take_profit_points", 120.0)),
            trail_stop_points=data.get("trail_stop_points"),
            max_qty=int(data.get("max_qty", 5)),
            volume_threshold=int(data.get("volume_threshold", 0)),
            slippage_assumption=float(data.get("slippage_assumption", 1.0)),
            breakout_lookback=int(data.get("breakout_lookback", 5)),
        )


# 預設三個時段 profile
DEFAULT_DAY_OPEN_PROFILE = SessionProfile(
    stop_loss_points=60.0,
    take_profit_points=120.0,
    max_qty=3,
    breakout_lookback=5,
)

DEFAULT_DAY_REGULAR_PROFILE = SessionProfile(
    stop_loss_points=60.0,
    take_profit_points=120.0,
    max_qty=5,
    breakout_lookback=5,
)

DEFAULT_NIGHT_PROFILE = SessionProfile(
    stop_loss_points=80.0,
    take_profit_points=100.0,
    max_qty=2,
    breakout_lookback=5,
    slippage_assumption=2.0,
)


# ─── 策略設定 ─────────────────────────────────────────────────

@dataclass
class StrategyConfig:
    """策略參數"""
    day_open_profile: SessionProfile = field(default_factory=lambda: SessionProfile(**DEFAULT_DAY_OPEN_PROFILE.__dict__))
    day_regular_profile: SessionProfile = field(default_factory=lambda: SessionProfile(**DEFAULT_DAY_REGULAR_PROFILE.__dict__))
    night_profile: SessionProfile = field(default_factory=lambda: SessionProfile(**DEFAULT_NIGHT_PROFILE.__dict__))

    # 開盤區間結束時間（日盤開盤後 N 分鐘切換到 regular profile）
    day_open_phase_minutes: int = 30

    # 方向判斷使用的聚合週期
    direction_5m_periods: int = 5    # 5m K 棒用幾根 1m 聚合
    direction_15m_periods: int = 15  # 15m K 棒用幾根 1m 聚合

    def get_profile(self, bar_time: datetime, session: SessionType) -> SessionProfile:
        """根據時間與時段取得對應 profile"""
        if session == SessionType.NIGHT:
            return self.night_profile
        # 日盤：判斷是否還在開盤區間
        t = bar_time.time()
        open_end = time_of_day(
            8 + (45 + self.day_open_phase_minutes) // 60,
            (45 + self.day_open_phase_minutes) % 60,
        )
        if t <= open_end:
            return self.day_open_profile
        return self.day_regular_profile

    def to_dict(self) -> dict:
        return {
            "day_open_profile": self.day_open_profile.to_dict(),
            "day_regular_profile": self.day_regular_profile.to_dict(),
            "night_profile": self.night_profile.to_dict(),
            "day_open_phase_minutes": self.day_open_phase_minutes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyConfig":
        return cls(
            day_open_profile=SessionProfile.from_dict(data.get("day_open_profile", {})),
            day_regular_profile=SessionProfile.from_dict(data.get("day_regular_profile", {})),
            night_profile=SessionProfile.from_dict(data.get("night_profile", {})),
            day_open_phase_minutes=int(data.get("day_open_phase_minutes", 30)),
        )


# ─── 訊號 ─────────────────────────────────────────────────────

@dataclass
class Signal:
    """策略訊號"""
    bar_time: datetime
    direction: SignalDirection
    action: SignalAction
    entry_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    qty: int = 1
    reason: str = ""
    session: SessionType = SessionType.DAY

    # 訊號產生時的資料時間戳
    tmf_quote_ts: Optional[str] = None
    tx_quote_ts: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "bar_time": self.bar_time.isoformat(),
            "direction": self.direction.value,
            "action": self.action.value,
            "entry_price": self.entry_price,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "qty": self.qty,
            "reason": self.reason,
            "session": self.session.value,
            "tmf_quote_ts": self.tmf_quote_ts,
            "tx_quote_ts": self.tx_quote_ts,
        }


# ─── VWAP 計算器 ──────────────────────────────────────────────

class VWAPCalculator:
    """Session VWAP 計算器"""

    def __init__(self):
        self._cumulative_volume_price = 0.0
        self._cumulative_volume = 0
        self._value = 0.0

    @property
    def value(self) -> float:
        return self._value

    def update(self, bar: Bar) -> float:
        typical_price = (bar.high + bar.low + bar.close) / 3
        self._cumulative_volume_price += typical_price * bar.volume
        self._cumulative_volume += bar.volume
        if self._cumulative_volume > 0:
            self._value = self._cumulative_volume_price / self._cumulative_volume
        return self._value

    def reset(self) -> None:
        self._cumulative_volume_price = 0.0
        self._cumulative_volume = 0
        self._value = 0.0


# ─── K 棒聚合器 ───────────────────────────────────────────────

class BarAggregator:
    """將 1m K 棒聚合為 Nm K 棒"""

    def __init__(self, period: int):
        self.period = period
        self._buffer: list[Bar] = []
        self._completed: list[Bar] = []

    @property
    def last_completed(self) -> Optional[Bar]:
        return self._completed[-1] if self._completed else None

    @property
    def prev_completed(self) -> Optional[Bar]:
        return self._completed[-2] if len(self._completed) >= 2 else None

    def update(self, bar: Bar) -> Optional[Bar]:
        """加入新 1m bar，若滿足 period 則回傳聚合後的 bar"""
        self._buffer.append(bar)
        if len(self._buffer) >= self.period:
            aggregated = Bar(
                time=self._buffer[0].time,
                open=self._buffer[0].open,
                high=max(b.high for b in self._buffer),
                low=min(b.low for b in self._buffer),
                close=self._buffer[-1].close,
                volume=sum(b.volume for b in self._buffer),
                symbol=bar.symbol,
            )
            self._completed.append(aggregated)
            self._buffer.clear()
            return aggregated
        return None

    def reset(self) -> None:
        self._buffer.clear()
        self._completed.clear()


# ─── 策略引擎 ─────────────────────────────────────────────────

class StrategyEngine:
    """
    最小可用策略引擎。

    方向判斷（Layer 1）：
    - TX 1m close vs session VWAP
    - TX 5m 趨勢（最新 close vs 前一根 close）
    - TX 15m 趨勢（最新 close vs 前一根 close）

    進場觸發（Layer 2）：
    - TMF 1m close 突破前 N 根最高點 → long entry
    - TMF 1m close 跌破前 N 根最低點 → short entry

    出場：
    - 固定停損 / 固定停利
    - 收盤前強制平倉
    """

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()

        # TX 方向判斷用
        self._tx_vwap = VWAPCalculator()
        self._tx_5m = BarAggregator(self.config.direction_5m_periods)
        self._tx_15m = BarAggregator(self.config.direction_15m_periods)
        self._tx_latest_close = 0.0

        # TMF 進場觸發用
        self._tmf_recent_bars: list[Bar] = []
        self._tmf_max_bars = 20  # 保留最近 N 根

        # 方向狀態
        self._current_direction = SignalDirection.NEUTRAL

        # 持倉追蹤（用於停損/停利計算）
        self._entry_price: Optional[float] = None
        self._entry_side: Optional[OrderSide] = None

        # 訊號日誌
        self.signals: list[Signal] = []

    @property
    def current_direction(self) -> SignalDirection:
        return self._current_direction

    def update_tx_bar(self, bar: Bar) -> None:
        """更新 TX 方向判斷用的 1m bar"""
        self._tx_latest_close = bar.close
        self._tx_vwap.update(bar)
        self._tx_5m.update(bar)
        self._tx_15m.update(bar)
        self._update_direction(bar)

    def update_tmf_bar(
        self,
        bar: Bar,
        session: SessionType,
        *,
        has_position: bool = False,
        position_side: Optional[OrderSide] = None,
        position_entry_price: Optional[float] = None,
    ) -> Optional[Signal]:
        """
        更新 TMF 1m bar，檢查是否產生訊號。

        回傳 Signal 或 None。
        """
        self._tmf_recent_bars.append(bar)
        if len(self._tmf_recent_bars) > self._tmf_max_bars:
            self._tmf_recent_bars = self._tmf_recent_bars[-self._tmf_max_bars:]

        profile = self.config.get_profile(bar.time, session)

        # 有持倉：檢查停損 / 停利
        if has_position and position_side and position_entry_price is not None:
            exit_signal = self._check_exit(
                bar, session, profile, position_side, position_entry_price,
            )
            if exit_signal:
                self.signals.append(exit_signal)
                return exit_signal

        # 無持倉：檢查進場
        if not has_position:
            entry_signal = self._check_entry(bar, session, profile)
            if entry_signal:
                self.signals.append(entry_signal)
                return entry_signal

        return None

    def set_position_info(self, entry_price: float, side: OrderSide) -> None:
        """更新持倉資訊（開倉成功後呼叫）"""
        self._entry_price = entry_price
        self._entry_side = side

    def clear_position_info(self) -> None:
        """清除持倉資訊（平倉成功後呼叫）"""
        self._entry_price = None
        self._entry_side = None

    def reset_session(self) -> None:
        """重置 session（新交易時段開始時呼叫）"""
        self._tx_vwap.reset()
        self._tx_5m.reset()
        self._tx_15m.reset()
        self._tmf_recent_bars.clear()
        self._current_direction = SignalDirection.NEUTRAL
        self._tx_latest_close = 0.0

    def reset(self) -> None:
        """完全重置"""
        self.reset_session()
        self._entry_price = None
        self._entry_side = None
        self.signals.clear()

    # ─── Private ──────────────────────────────────────────────

    def _update_direction(self, tx_bar: Bar) -> None:
        """
        方向判斷：
        - long bias：TX close > VWAP, 5m 向上, 15m 向上
        - short bias：TX close < VWAP, 5m 向下, 15m 向下
        - 否則 neutral
        """
        vwap = self._tx_vwap.value
        if vwap <= 0:
            self._current_direction = SignalDirection.NEUTRAL
            return

        above_vwap = tx_bar.close > vwap
        below_vwap = tx_bar.close < vwap

        # 5m 趨勢
        last_5m = self._tx_5m.last_completed
        prev_5m = self._tx_5m.prev_completed
        trend_5m_up = last_5m and prev_5m and last_5m.close > prev_5m.close
        trend_5m_down = last_5m and prev_5m and last_5m.close < prev_5m.close

        # 15m 趨勢
        last_15m = self._tx_15m.last_completed
        prev_15m = self._tx_15m.prev_completed
        trend_15m_up = last_15m and prev_15m and last_15m.close > prev_15m.close
        trend_15m_down = last_15m and prev_15m and last_15m.close < prev_15m.close

        if above_vwap and trend_5m_up and trend_15m_up:
            self._current_direction = SignalDirection.LONG
        elif below_vwap and trend_5m_down and trend_15m_down:
            self._current_direction = SignalDirection.SHORT
        else:
            self._current_direction = SignalDirection.NEUTRAL

    def _check_entry(
        self,
        bar: Bar,
        session: SessionType,
        profile: SessionProfile,
    ) -> Optional[Signal]:
        """檢查進場條件"""
        lookback = profile.breakout_lookback
        if len(self._tmf_recent_bars) < lookback + 1:
            return None

        # 前 N 根的高低點（不含當前 bar）
        recent = self._tmf_recent_bars[-(lookback + 1):-1]
        highest = max(b.high for b in recent)
        lowest = min(b.low for b in recent)

        # Long entry：方向偏多 + TMF 突破前高
        if self._current_direction == SignalDirection.LONG and bar.close > highest:
            return Signal(
                bar_time=bar.time,
                direction=SignalDirection.LONG,
                action=SignalAction.BUY,
                entry_price=bar.close,
                stop_loss_price=bar.close - profile.stop_loss_points,
                take_profit_price=bar.close + profile.take_profit_points,
                qty=1,
                reason=f"long_breakout: TMF close {bar.close} > prev {lookback} high {highest}",
                session=session,
            )

        # Short entry：方向偏空 + TMF 跌破前低
        if self._current_direction == SignalDirection.SHORT and bar.close < lowest:
            return Signal(
                bar_time=bar.time,
                direction=SignalDirection.SHORT,
                action=SignalAction.SELL,
                entry_price=bar.close,
                stop_loss_price=bar.close + profile.stop_loss_points,
                take_profit_price=bar.close - profile.take_profit_points,
                qty=1,
                reason=f"short_breakout: TMF close {bar.close} < prev {lookback} low {lowest}",
                session=session,
            )

        return None

    def _check_exit(
        self,
        bar: Bar,
        session: SessionType,
        profile: SessionProfile,
        position_side: OrderSide,
        entry_price: float,
    ) -> Optional[Signal]:
        """檢查出場條件（停損/停利）"""
        if position_side == OrderSide.BUY:
            # 多單停損
            stop_price = entry_price - profile.stop_loss_points
            if bar.low <= stop_price:
                return Signal(
                    bar_time=bar.time,
                    direction=SignalDirection.LONG,
                    action=SignalAction.CLOSE_LONG,
                    entry_price=stop_price,
                    reason=f"stop_loss: bar low {bar.low} <= stop {stop_price}",
                    session=session,
                )
            # 多單停利
            tp_price = entry_price + profile.take_profit_points
            if bar.high >= tp_price:
                return Signal(
                    bar_time=bar.time,
                    direction=SignalDirection.LONG,
                    action=SignalAction.CLOSE_LONG,
                    entry_price=tp_price,
                    reason=f"take_profit: bar high {bar.high} >= target {tp_price}",
                    session=session,
                )

        elif position_side == OrderSide.SELL:
            # 空單停損
            stop_price = entry_price + profile.stop_loss_points
            if bar.high >= stop_price:
                return Signal(
                    bar_time=bar.time,
                    direction=SignalDirection.SHORT,
                    action=SignalAction.CLOSE_SHORT,
                    entry_price=stop_price,
                    reason=f"stop_loss: bar high {bar.high} >= stop {stop_price}",
                    session=session,
                )
            # 空單停利
            tp_price = entry_price - profile.take_profit_points
            if bar.low <= tp_price:
                return Signal(
                    bar_time=bar.time,
                    direction=SignalDirection.SHORT,
                    action=SignalAction.CLOSE_SHORT,
                    entry_price=tp_price,
                    reason=f"take_profit: bar low {bar.low} <= target {tp_price}",
                    session=session,
                )

        return None
