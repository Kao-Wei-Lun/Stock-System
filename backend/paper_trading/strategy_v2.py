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

@dataclass
class V2StopDistances:
    initial_stop: float
    trailing_stop: float
    overheat_trailing_stop: float
    trailing_activation: float
    pyramid_distance: float
    atr: float
    noise_initial: float
    noise_trailing: float
    price_reference: float

    def to_dict(self) -> dict:
        return {
            "initial_stop": round(self.initial_stop, 2),
            "trailing_stop": round(self.trailing_stop, 2),
            "overheat_trailing_stop": round(self.overheat_trailing_stop, 2),
            "trailing_activation": round(self.trailing_activation, 2),
            "pyramid_distance": round(self.pyramid_distance, 2),
            "atr": round(self.atr, 2),
            "noise_initial": round(self.noise_initial, 2),
            "noise_trailing": round(self.noise_trailing, 2),
            "price_reference": round(self.price_reference, 2),
        }


class ATRCalculator:
    def __init__(self, period: int = 30, max_history: int = 120):
        self.period = period
        self.max_history = max(period, max_history)
        self._trs: list[float] = []
        self._prev_close: Optional[float] = None
        self._last_bar_minute: Optional[str] = None
        self._last_prev_close_for_bar: Optional[float] = None
        self._value = 0.0

    @property
    def value(self) -> float:
        return self._value

    @property
    def true_ranges(self) -> list[float]:
        return list(self._trs)

    def update(self, bar: Bar) -> float:
        bar_minute = bar.time.strftime("%Y-%m-%d %H:%M")
        is_same_bar = self._last_bar_minute == bar_minute and bool(self._trs)
        prev_close = self._last_prev_close_for_bar if is_same_bar else self._prev_close

        if prev_close is None:
            tr = bar.high - bar.low
        else:
            tr = max(
                bar.high - bar.low,
                abs(bar.high - prev_close),
                abs(bar.low - prev_close)
            )

        if is_same_bar:
            self._trs[-1] = tr
        else:
            self._last_prev_close_for_bar = self._prev_close
            self._trs.append(tr)
            if len(self._trs) > self.max_history:
                self._trs.pop(0)
            self._last_bar_minute = bar_minute

        self._prev_close = bar.close

        if len(self._trs) >= self.period:
            self._value = sum(self._trs[-self.period:]) / self.period
        else:
            # Not enough data yet, use current average
            self._value = sum(self._trs) / len(self._trs) if self._trs else 1.0
            
        # 確保 ATR 至少為 1
        self._value = max(self._value, 1.0)
        return self._value
        
    def reset(self):
        self._trs.clear()
        self._prev_close = None
        self._last_bar_minute = None
        self._last_prev_close_for_bar = None
        self._value = 0.0


class StrategyEngineV2:
    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()

        self._tx_vwap = VWAPCalculator()
        self._tx_5m = BarAggregator(self.config.direction_5m_periods)
        self._tx_15m = BarAggregator(self.config.direction_15m_periods)
        self._tmf_atr = ATRCalculator(
            self.config.v2_atr_period,
            max_history=max(self.config.v2_noise_lookback_bars * 2, self.config.v2_atr_period),
        )
        
        self._tmf_recent_bars: list[Bar] = []
        self._tmf_max_bars = max(80, self.config.v2_noise_lookback_bars + 5)

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
        self._opposite_reversal_count: int = 0
        self._opposite_reversal_key: Optional[str] = None
        self._opposite_reversal_direction: Optional[SignalDirection] = None

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

    def warmup_tmf_bar(self, bar: Bar, session: SessionType) -> None:
        """Warm up TMF bar history and ATR without emitting signals."""
        self._append_tmf_bar(bar)
        self._tmf_atr.update(bar)

    def get_effective_stop_distances(
        self,
        bar: Bar,
        session: SessionType,
        profile: Optional[SessionProfile] = None,
    ) -> V2StopDistances:
        """Return dynamic V2 distances scaled by ATR, index level, and recent 1m noise."""
        profile = profile or self.config.get_profile(bar.time, session)
        phase = self._resolve_stop_phase(bar, session, profile)
        price = max(1.0, abs(float(bar.close or self._tx_latest_close or 0.0)))
        atr = max(1.0, float(self._tmf_atr.value or 1.0))

        initial_pct = self._phase_pct(phase, "initial_stop")
        trailing_pct = self._phase_pct(phase, "trailing_stop")
        overheat_pct = self._phase_pct(phase, "overheat_trailing")
        activation_pct = self._phase_pct(phase, "activation")
        pyramid_pct = self._phase_pct(phase, "pyramid")

        noise_initial = self._recent_noise_distance(
            self.config.v2_initial_noise_percentile,
            self.config.v2_initial_noise_mult,
        )
        noise_trailing = self._recent_noise_distance(
            self.config.v2_trailing_noise_percentile,
            self.config.v2_trailing_noise_mult,
        )
        noise_overheat = self._recent_noise_distance(
            self.config.v2_overheat_noise_percentile,
            self.config.v2_overheat_noise_mult,
        )
        noise_activation = self._recent_noise_distance(
            self.config.v2_activation_noise_percentile,
            self.config.v2_activation_noise_mult,
        )
        noise_pyramid = self._recent_noise_distance(
            self.config.v2_pyramid_noise_percentile,
            self.config.v2_pyramid_noise_mult,
        )

        initial_stop = max(
            atr * self.config.v2_initial_stop_atr_mult,
            price * initial_pct,
            noise_initial,
        )
        trailing_stop = max(
            atr * self.config.v2_trailing_stop_atr_mult,
            price * trailing_pct,
            noise_trailing,
        )
        overheat_trailing_stop = max(
            atr * self.config.v2_overheat_trailing_atr_mult,
            price * overheat_pct,
            noise_overheat,
        )
        trailing_activation = max(
            atr * self.config.v2_trailing_activation_atr_mult,
            price * activation_pct,
            noise_activation,
        )
        pyramid_distance = max(
            atr * self.config.v2_pyramid_atr_mult,
            price * pyramid_pct,
            noise_pyramid,
        )
        stop_cap = self._v2_setting("v2_initial_stop_cap_points")
        if stop_cap is not None and float(stop_cap) > 0:
            cap = float(stop_cap)
            initial_stop = min(initial_stop, cap)
            trailing_activation = min(trailing_activation, cap)
            trailing_stop = min(trailing_stop, max(40.0, cap * 0.8))
            overheat_trailing_stop = min(overheat_trailing_stop, max(30.0, cap * 0.55))

        return V2StopDistances(
            initial_stop=initial_stop,
            trailing_stop=trailing_stop,
            overheat_trailing_stop=overheat_trailing_stop,
            trailing_activation=trailing_activation,
            pyramid_distance=pyramid_distance,
            atr=atr,
            noise_initial=noise_initial,
            noise_trailing=noise_trailing,
            price_reference=price,
        )

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
        is_new_bar = self._append_tmf_bar(bar)
        self._tmf_atr.update(bar)
        profile = self.config.get_profile(bar.time, session)

        if has_position and position_side and position_entry_price is not None:
            if is_new_bar:
                self._bars_since_entry += 1
            exit_signal = self._check_exit(
                bar, session, profile, position_side, position_entry_price, position_qty
            )
            if exit_signal:
                self.signals.append(exit_signal)
                return exit_signal

            if bar.high > self._highest_price_since_entry:
                self._highest_price_since_entry = bar.high
            if bar.low < self._lowest_price_since_entry:
                self._lowest_price_since_entry = bar.low
                
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

    def _append_tmf_bar(self, bar: Bar) -> bool:
        bar_minute = bar.time.strftime("%Y-%m-%d %H:%M")
        is_new_bar = not (
            self._tmf_recent_bars
            and self._tmf_recent_bars[-1].time.strftime("%Y-%m-%d %H:%M") == bar_minute
        )

        if is_new_bar:
            self._tmf_recent_bars.append(bar)
        else:
            self._tmf_recent_bars[-1] = bar
        if len(self._tmf_recent_bars) > self._tmf_max_bars:
            self._tmf_recent_bars = self._tmf_recent_bars[-self._tmf_max_bars:]
        return is_new_bar

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
        self._reset_reversal_confirmation()

    def reset(self) -> None:
        self.reset_session()
        self.clear_position_info()
        self.signals.clear()

    # ─── Private ──────────────────────────────────────────────

    def _v2_setting(self, name: str):
        getter = getattr(self.config, "v2_setting", None)
        if callable(getter):
            return getter(name)
        return getattr(self.config, name)

    def _reset_reversal_confirmation(self) -> None:
        self._opposite_reversal_count = 0
        self._opposite_reversal_key = None
        self._opposite_reversal_direction = None

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        pct = min(1.0, max(0.0, percentile))
        ordered = sorted(float(value) for value in values)
        index = (len(ordered) - 1) * pct
        lower = math.floor(index)
        upper = math.ceil(index)
        if lower == upper:
            return ordered[int(index)]
        return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)

    def _recent_noise_distance(self, percentile: float, multiplier: float) -> float:
        lookback = max(1, int(self.config.v2_noise_lookback_bars))
        recent = self._tmf_atr.true_ranges[-lookback:]
        return self._percentile(recent, percentile) * max(0.0, multiplier)

    def _resolve_stop_phase(self, bar: Bar, session: SessionType, profile: SessionProfile) -> str:
        if session == SessionType.NIGHT:
            return "night"
        if profile is self.config.day_open_profile:
            return "day_open"
        if self.config.get_profile(bar.time, session) is self.config.day_open_profile:
            return "day_open"
        return "regular"

    def _phase_pct(self, phase: str, name: str) -> float:
        attr = {
            ("day_open", "initial_stop"): "v2_day_open_initial_stop_pct",
            ("day_open", "trailing_stop"): "v2_day_open_trailing_stop_pct",
            ("day_open", "overheat_trailing"): "v2_day_open_overheat_trailing_pct",
            ("day_open", "activation"): "v2_day_open_activation_pct",
            ("day_open", "pyramid"): "v2_day_open_pyramid_pct",
            ("regular", "initial_stop"): "v2_regular_initial_stop_pct",
            ("regular", "trailing_stop"): "v2_regular_trailing_stop_pct",
            ("regular", "overheat_trailing"): "v2_regular_overheat_trailing_pct",
            ("regular", "activation"): "v2_regular_activation_pct",
            ("regular", "pyramid"): "v2_regular_pyramid_pct",
            ("night", "initial_stop"): "v2_night_initial_stop_pct",
            ("night", "trailing_stop"): "v2_night_trailing_stop_pct",
            ("night", "overheat_trailing"): "v2_night_overheat_trailing_pct",
            ("night", "activation"): "v2_night_activation_pct",
            ("night", "pyramid"): "v2_night_pyramid_pct",
        }[(phase, name)]
        return max(0.0, float(getattr(self.config, attr)))

    def _entry_lookback(self, profile: SessionProfile) -> int:
        configured = self._v2_setting("v2_entry_breakout_lookback")
        if configured is not None and int(configured) > 0:
            return int(configured)
        return int(profile.breakout_lookback)

    def _entry_quality_allows(self, side: OrderSide, bar: Bar) -> bool:
        atr_cap = self._v2_setting("v2_entry_atr_cap")
        if atr_cap is not None and float(atr_cap) > 0 and self._tmf_atr.value > float(atr_cap):
            return False

        max_deviation = self._v2_setting("v2_entry_max_vwap_deviation")
        min_deviation = float(self._v2_setting("v2_entry_min_vwap_deviation") or 0.0)
        if max_deviation is None:
            return True

        vwap = self._tx_vwap.value
        tx_price = float(self._tx_latest_close or bar.close or 0.0)
        if vwap <= 0 or tx_price <= 0:
            return False

        if side == OrderSide.BUY:
            deviation = (tx_price - vwap) / vwap
        else:
            deviation = (vwap - tx_price) / vwap
        return min_deviation <= deviation <= float(max_deviation)

    def _opposite_reversal_confirmed(self, position_side: OrderSide) -> bool:
        required = int(self._v2_setting("v2_reversal_confirm_5m_bars") or 0)
        if required <= 0:
            return True

        opposite_direction: Optional[SignalDirection] = None
        if position_side == OrderSide.BUY and self._current_direction == SignalDirection.SHORT:
            opposite_direction = SignalDirection.SHORT
        elif position_side == OrderSide.SELL and self._current_direction == SignalDirection.LONG:
            opposite_direction = SignalDirection.LONG

        if opposite_direction is None:
            self._reset_reversal_confirmation()
            return False

        last_5m = self._tx_5m.last_completed
        opposite_key = last_5m.time.strftime("%Y-%m-%d %H:%M") if last_5m else None
        if opposite_direction != self._opposite_reversal_direction:
            self._opposite_reversal_count = 0
            self._opposite_reversal_key = None
            self._opposite_reversal_direction = opposite_direction
        if opposite_key and opposite_key != self._opposite_reversal_key:
            self._opposite_reversal_key = opposite_key
            self._opposite_reversal_count += 1
        return self._opposite_reversal_count >= required

    def _check_early_failure_exit(
        self,
        bar: Bar,
        session: SessionType,
        position_side: OrderSide,
        entry_price: float,
        current_qty: int,
    ) -> Optional[Signal]:
        early_bars = int(self._v2_setting("v2_early_fail_bars") or 0)
        if early_bars <= 0 or self._bars_since_entry < early_bars:
            return None

        progress_mult = float(self._v2_setting("v2_early_fail_min_progress_atr_mult") or 0.0)
        required_progress = max(1.0, self._tmf_atr.value) * progress_mult
        vwap = self._tx_vwap.value

        if position_side == OrderSide.BUY:
            favorable = self._highest_price_since_entry - entry_price
            unrealized = bar.close - entry_price
            crossed_vwap = vwap > 0 and bar.close < vwap
            direction = SignalDirection.LONG
            action = SignalAction.CLOSE_LONG
        else:
            favorable = entry_price - self._lowest_price_since_entry
            unrealized = entry_price - bar.close
            crossed_vwap = vwap > 0 and bar.close > vwap
            direction = SignalDirection.SHORT
            action = SignalAction.CLOSE_SHORT

        if favorable < required_progress and unrealized <= 0:
            return Signal(
                bar_time=bar.time,
                direction=direction,
                action=action,
                qty=current_qty,
                reason=(
                    f"v2_early_fail_exit: {early_bars} bars no progress "
                    f"favorable={favorable:.1f}, need={required_progress:.1f}"
                ),
                session=session,
            )

        if bool(self._v2_setting("v2_vwap_loss_exit_after_early_fail")) and crossed_vwap and unrealized < 0:
            return Signal(
                bar_time=bar.time,
                direction=direction,
                action=action,
                qty=current_qty,
                reason="v2_vwap_loss_exit: delayed adverse VWAP recross",
                session=session,
            )
        return None

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
        lookback = self._entry_lookback(profile)
        if len(self._tmf_recent_bars) < lookback + 1:
            return None

        recent = self._tmf_recent_bars[-(lookback + 1):-1]
        highest = max(b.high for b in recent)
        lowest = min(b.low for b in recent)
        
        atr = self._tmf_atr.value
        distances = self.get_effective_stop_distances(bar, session, profile)

        # V2 試探倉只下 1 口
        entry_qty = 1
        breakout_buffer = max(0.0, self._tmf_atr.value * float(
            self._v2_setting("v2_entry_breakout_atr_buffer_mult") or 0.0
        ))

        if (
            self._current_direction == SignalDirection.LONG
            and self._5m_slope > 0
            and bar.close > highest + breakout_buffer
            and self._entry_quality_allows(OrderSide.BUY, bar)
        ):
            return Signal(
                bar_time=bar.time,
                direction=SignalDirection.LONG,
                action=SignalAction.BUY,
                entry_price=bar.close,
                qty=entry_qty,
                reason=(
                    f"v2_long_entry: breakout high {highest}, "
                    f"buffer={breakout_buffer:.1f}, atr={atr:.1f}, stop={distances.initial_stop:.1f}"
                ),
                session=session,
            )

        if (
            self._current_direction == SignalDirection.SHORT
            and self._5m_slope < 0
            and bar.close < lowest - breakout_buffer
            and self._entry_quality_allows(OrderSide.SELL, bar)
        ):
            return Signal(
                bar_time=bar.time,
                direction=SignalDirection.SHORT,
                action=SignalAction.SELL,
                entry_price=bar.close,
                qty=entry_qty,
                reason=(
                    f"v2_short_entry: breakout low {lowest}, "
                    f"buffer={breakout_buffer:.1f}, atr={atr:.1f}, stop={distances.initial_stop:.1f}"
                ),
                session=session,
            )
        return None

    def _check_pyramid(self, bar: Bar, session: SessionType, profile: SessionProfile, position_side: OrderSide, current_qty: int) -> Optional[Signal]:
        # 達到上限不加碼
        if current_qty >= profile.max_qty:
            return None
            
        if self._last_add_price is None:
            return None
            
        distances = self.get_effective_stop_distances(bar, session, profile)
        pyramid_distance = distances.pyramid_distance
        
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
        early_exit = self._check_early_failure_exit(
            bar, session, position_side, entry_price, current_qty
        )
        if early_exit:
            return early_exit
        
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
        is_opposite_reversal = (
            (position_side == OrderSide.BUY and self._current_direction == SignalDirection.SHORT)
            or (position_side == OrderSide.SELL and self._current_direction == SignalDirection.LONG)
        )
        if not is_opposite_reversal:
            self._reset_reversal_confirmation()
        if (
            position_side == OrderSide.BUY
            and self._current_direction == SignalDirection.SHORT
            and self._opposite_reversal_confirmed(position_side)
        ):
            return Signal(
                bar_time=bar.time, direction=SignalDirection.LONG, action=SignalAction.CLOSE_LONG,
                qty=current_qty, reason="v2_reversal_exit: trend flipped to SHORT", session=session
            )
        if (
            position_side == OrderSide.SELL
            and self._current_direction == SignalDirection.LONG
            and self._opposite_reversal_confirmed(position_side)
        ):
            return Signal(
                bar_time=bar.time, direction=SignalDirection.SHORT, action=SignalAction.CLOSE_SHORT,
                qty=current_qty, reason="v2_reversal_exit: trend flipped to LONG", session=session
            )

        # 3. ATR 移動停損 / 初始停損
        distances = self.get_effective_stop_distances(bar, session, profile)
        trailing_dist = distances.overheat_trailing_stop if is_overheated else distances.trailing_stop
        initial_stop_dist = distances.initial_stop
        
        if position_side == OrderSide.BUY:
            # 停損價 = max(初始停損, 最高價 - 移動距離)
            initial_stop = entry_price - initial_stop_dist
            trailing_stop = initial_stop
            favorable_move = self._highest_price_since_entry - entry_price
            if favorable_move >= distances.trailing_activation:
                trailing_stop = self._highest_price_since_entry - trailing_dist
            stop_price = max(initial_stop, trailing_stop)
            if bar.low <= stop_price:
                return Signal(
                    bar_time=bar.time, direction=SignalDirection.LONG, action=SignalAction.CLOSE_LONG,
                    qty=current_qty, reason=f"v2_atr_stop: low <= {stop_price:.1f} (atr={atr:.1f}, stop={initial_stop_dist:.1f}, trail={trailing_dist:.1f}, activation={distances.trailing_activation:.1f}, heated={is_overheated})", session=session
                )
        else:
            # 停損價 = min(初始停損, 最低價 + 移動距離)
            initial_stop = entry_price + initial_stop_dist
            trailing_stop = initial_stop
            favorable_move = entry_price - self._lowest_price_since_entry
            if favorable_move >= distances.trailing_activation:
                trailing_stop = self._lowest_price_since_entry + trailing_dist
            stop_price = min(initial_stop, trailing_stop)
            if bar.high >= stop_price:
                return Signal(
                    bar_time=bar.time, direction=SignalDirection.SHORT, action=SignalAction.CLOSE_SHORT,
                    qty=current_qty, reason=f"v2_atr_stop: high >= {stop_price:.1f} (atr={atr:.1f}, stop={initial_stop_dist:.1f}, trail={trailing_dist:.1f}, activation={distances.trailing_activation:.1f}, heated={is_overheated})", session=session
                )

        return None
