"""
QuantVision Pro — Paper Trading Strategy Engine V2

實作進階策略邏輯：
- 波動率引擎 (ATR)：取代固定停損停利。
- 動態倉位 (Pyramiding)：試單 1 口，隨趨勢與獲利加碼。
- 移動停損 (Trailing Stop)：鎖定利潤。
- 追加濾網：趨勢斜率、均線乖離等過熱指標。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from paper_trading.cost_model import OrderSide, SessionType
from paper_trading.simulation_broker import Bar
from paper_trading.strategy_engine import (
    StrategyConfig,
    SessionProfile,
    Signal,
    SignalDirection,
    SignalAction,
    VWAPCalculator,
    BarAggregator,
)

class ATRCalculator:
    def __init__(self, period: int = 14):
        self.period = period
        self._trs: list[float] = []
        self._prev_close: Optional[float] = None
        self._value = 0.0

    @property
    def value(self) -> float:
        return self._value

    def update(self, bar: Bar) -> float:
        if self._prev_close is None:
            tr = bar.high - bar.low
        else:
            tr = max(
                bar.high - bar.low,
                abs(bar.high - self._prev_close),
                abs(bar.low - self._prev_close)
            )
        self._prev_close = bar.close
        
        self._trs.append(tr)
        if len(self._trs) > self.period:
            self._trs.pop(0)
            
        if len(self._trs) == self.period:
            self._value = sum(self._trs) / self.period
        else:
            # Not enough data yet, use current average
            self._value = sum(self._trs) / len(self._trs) if self._trs else 1.0
            
        # 確保 ATR 至少為 1
        self._value = max(self._value, 1.0)
        return self._value
        
    def reset(self):
        self._trs.clear()
        self._prev_close = None
        self._value = 0.0


class StrategyEngineV2:
    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()

        self._tx_vwap = VWAPCalculator()
        self._tx_5m = BarAggregator(self.config.direction_5m_periods)
        self._tx_15m = BarAggregator(self.config.direction_15m_periods)
        self._tmf_atr = ATRCalculator(14)
        
        self._tmf_recent_bars: list[Bar] = []
        self._tmf_max_bars = 20

        self._current_direction = SignalDirection.NEUTRAL
        self._tx_latest_close = 0.0
        
        # 趨勢動能濾網（斜率）
        self._5m_slope: float = 0.0

        # 持倉追蹤
        self._entry_price: Optional[float] = None
        self._entry_side: Optional[OrderSide] = None
        self._highest_price_since_entry: float = 0.0
        self._lowest_price_since_entry: float = float('inf')
        self._bars_since_entry: int = 0
        
        # 加碼記錄
        self._last_add_price: Optional[float] = None

        self.signals: list[Signal] = []

    @property
    def current_direction(self) -> SignalDirection:
        return self._current_direction

    @property
    def current_atr(self) -> float:
        return self._tmf_atr.value

    def update_tx_bar(self, bar: Bar) -> None:
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
        position_qty: int = 0,
    ) -> Optional[Signal]:
        self._tmf_recent_bars.append(bar)
        if len(self._tmf_recent_bars) > self._tmf_max_bars:
            self._tmf_recent_bars = self._tmf_recent_bars[-self._tmf_max_bars:]
            
        self._tmf_atr.update(bar)
        profile = self.config.get_profile(bar.time, session)

        if has_position and position_side and position_entry_price is not None:
            self._bars_since_entry += 1
            if bar.high > self._highest_price_since_entry:
                self._highest_price_since_entry = bar.high
            if bar.low < self._lowest_price_since_entry:
                self._lowest_price_since_entry = bar.low
                
            exit_signal = self._check_exit(
                bar, session, profile, position_side, position_entry_price, position_qty
            )
            if exit_signal:
                self.signals.append(exit_signal)
                return exit_signal
                
            # 加碼檢查
            add_signal = self._check_pyramid(
                bar, session, profile, position_side, position_qty
            )
            if add_signal:
                self.signals.append(add_signal)
                return add_signal
        else:
            entry_signal = self._check_entry(bar, session, profile)
            if entry_signal:
                self.signals.append(entry_signal)
                return entry_signal

        return None

    def set_position_info(self, entry_price: float, side: OrderSide) -> None:
        if self._entry_price is None:
            # 首次開倉
            self._entry_price = entry_price
            self._entry_side = side
            self._highest_price_since_entry = entry_price
            self._lowest_price_since_entry = entry_price
            self._bars_since_entry = 0
            self._last_add_price = entry_price
        else:
            # 加碼
            self._last_add_price = entry_price

    def clear_position_info(self) -> None:
        self._entry_price = None
        self._entry_side = None
        self._last_add_price = None
        self._highest_price_since_entry = 0.0
        self._lowest_price_since_entry = float('inf')
        self._bars_since_entry = 0

    def on_position_reduced(self) -> None:
        """部分減碼後保留核心部位，重新計算盤整等待時間。"""
        self._bars_since_entry = 0

    def reset_session(self) -> None:
        self._tx_vwap.reset()
        self._tx_5m.reset()
        self._tx_15m.reset()
        self._tmf_atr.reset()
        self._tmf_recent_bars.clear()
        self._current_direction = SignalDirection.NEUTRAL
        self._tx_latest_close = 0.0
        self._5m_slope = 0.0

    def reset(self) -> None:
        self.reset_session()
        self.clear_position_info()
        self.signals.clear()

    # ─── Private ──────────────────────────────────────────────

    def _update_direction(self, tx_bar: Bar) -> None:
        vwap = self._tx_vwap.value
        if vwap <= 0:
            self._current_direction = SignalDirection.NEUTRAL
            return

        above_vwap = tx_bar.close > vwap
        below_vwap = tx_bar.close < vwap

        last_5m = self._tx_5m.last_completed
        prev_5m = self._tx_5m.prev_completed
        
        trend_5m_up = last_5m and prev_5m and last_5m.close > prev_5m.close
        trend_5m_down = last_5m and prev_5m and last_5m.close < prev_5m.close
        
        if last_5m and prev_5m:
            self._5m_slope = last_5m.close - prev_5m.close

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

    def _check_entry(self, bar: Bar, session: SessionType, profile: SessionProfile) -> Optional[Signal]:
        lookback = profile.breakout_lookback
        if len(self._tmf_recent_bars) < lookback + 1:
            return None

        recent = self._tmf_recent_bars[-(lookback + 1):-1]
        highest = max(b.high for b in recent)
        lowest = min(b.low for b in recent)
        
        atr = self._tmf_atr.value

        # V2 試探倉只下 1 口
        entry_qty = 1

        if self._current_direction == SignalDirection.LONG and self._5m_slope > 0 and bar.close > highest:
            return Signal(
                bar_time=bar.time,
                direction=SignalDirection.LONG,
                action=SignalAction.BUY,
                entry_price=bar.close,
                qty=entry_qty,
                reason=f"v2_long_entry: breakout high {highest}, atr={atr:.1f}",
                session=session,
            )

        if self._current_direction == SignalDirection.SHORT and self._5m_slope < 0 and bar.close < lowest:
            return Signal(
                bar_time=bar.time,
                direction=SignalDirection.SHORT,
                action=SignalAction.SELL,
                entry_price=bar.close,
                qty=entry_qty,
                reason=f"v2_short_entry: breakout low {lowest}, atr={atr:.1f}",
                session=session,
            )
        return None

    def _check_pyramid(self, bar: Bar, session: SessionType, profile: SessionProfile, position_side: OrderSide, current_qty: int) -> Optional[Signal]:
        # 達到上限不加碼
        if current_qty >= profile.max_qty:
            return None
            
        if self._last_add_price is None:
            return None
            
        atr = self._tmf_atr.value
        pyramid_distance = atr * 0.5  # 每獲利 0.5 ATR 加碼一次
        
        # 趨勢強度必須還在
        if position_side == OrderSide.BUY:
            if self._current_direction != SignalDirection.LONG or self._5m_slope <= 0:
                return None
            if bar.close >= self._last_add_price + pyramid_distance:
                return Signal(
                    bar_time=bar.time, direction=SignalDirection.LONG,
                    action=SignalAction.BUY, entry_price=bar.close, qty=1,
                    reason=f"v2_pyramid_long: target reached {bar.close} > {self._last_add_price} + {pyramid_distance:.1f}",
                    session=session
                )
        else:
            if self._current_direction != SignalDirection.SHORT or self._5m_slope >= 0:
                return None
            if bar.close <= self._last_add_price - pyramid_distance:
                return Signal(
                    bar_time=bar.time, direction=SignalDirection.SHORT,
                    action=SignalAction.SELL, entry_price=bar.close, qty=1,
                    reason=f"v2_pyramid_short: target reached {bar.close} < {self._last_add_price} - {pyramid_distance:.1f}",
                    session=session
                )
        return None

    def _check_exit(self, bar: Bar, session: SessionType, profile: SessionProfile, position_side: OrderSide, entry_price: float, current_qty: int) -> Optional[Signal]:
        atr = self._tmf_atr.value
        
        # 乖離過大判斷 (1%)
        vwap = self._tx_vwap.value
        deviation = abs(bar.close - vwap) / vwap if vwap > 0 else 0
        is_overheated = deviation > 0.01

        # 1. 時間停損 / 盤整減碼
        if self._bars_since_entry >= 30:
            if position_side == OrderSide.BUY:
                unrealized = bar.close - entry_price
            else:
                unrealized = entry_price - bar.close
                
            # 若損益在 -0.5 ATR 到 +0.5 ATR 之間，視為盤整
            if -0.5 * atr < unrealized < 0.5 * atr:
                if current_qty > 1:
                    # 退回 1 口
                    reduce_qty = current_qty - 1
                    return Signal(
                        bar_time=bar.time,
                        direction=SignalDirection.LONG if position_side == OrderSide.BUY else SignalDirection.SHORT,
                        action=SignalAction.CLOSE_LONG if position_side == OrderSide.BUY else SignalAction.CLOSE_SHORT,
                        qty=reduce_qty,
                        reason=f"v2_time_stop_reduce: 30 bars flat, reduce {reduce_qty} contracts",
                        session=session
                    )
                else:
                    # 只有 1 口，直接全平
                    return Signal(
                        bar_time=bar.time,
                        direction=SignalDirection.LONG if position_side == OrderSide.BUY else SignalDirection.SHORT,
                        action=SignalAction.CLOSE_LONG if position_side == OrderSide.BUY else SignalAction.CLOSE_SHORT,
                        qty=current_qty,
                        reason=f"v2_time_stop_exit: 30 bars flat, exit 1 contract",
                        session=session
                    )
                    
        # 2. 方向反轉出場 (Reversal Exit)
        if position_side == OrderSide.BUY and self._current_direction == SignalDirection.SHORT:
            return Signal(
                bar_time=bar.time, direction=SignalDirection.LONG, action=SignalAction.CLOSE_LONG,
                qty=current_qty, reason="v2_reversal_exit: trend flipped to SHORT", session=session
            )
        if position_side == OrderSide.SELL and self._current_direction == SignalDirection.LONG:
            return Signal(
                bar_time=bar.time, direction=SignalDirection.SHORT, action=SignalAction.CLOSE_SHORT,
                qty=current_qty, reason="v2_reversal_exit: trend flipped to LONG", session=session
            )

        # 3. ATR 移動停損 / 初始停損
        trailing_dist = 0.5 * atr if is_overheated else 1.0 * atr
        initial_stop_dist = 1.5 * atr
        
        if position_side == OrderSide.BUY:
            # 停損價 = max(初始停損, 最高價 - 移動距離)
            stop_price = max(entry_price - initial_stop_dist, self._highest_price_since_entry - trailing_dist)
            if bar.low <= stop_price:
                return Signal(
                    bar_time=bar.time, direction=SignalDirection.LONG, action=SignalAction.CLOSE_LONG,
                    qty=current_qty, reason=f"v2_atr_stop: low <= {stop_price:.1f} (atr={atr:.1f}, heated={is_overheated})", session=session
                )
        else:
            # 停損價 = min(初始停損, 最低價 + 移動距離)
            stop_price = min(entry_price + initial_stop_dist, self._lowest_price_since_entry + trailing_dist)
            if bar.high >= stop_price:
                return Signal(
                    bar_time=bar.time, direction=SignalDirection.SHORT, action=SignalAction.CLOSE_SHORT,
                    qty=current_qty, reason=f"v2_atr_stop: high >= {stop_price:.1f} (atr={atr:.1f}, heated={is_overheated})", session=session
                )

        return None
