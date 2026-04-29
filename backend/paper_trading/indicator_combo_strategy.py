from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from paper_trading.cost_model import OrderSide, SessionType
from paper_trading.simulation_broker import Bar
from paper_trading.strategy_engine import (
    Signal,
    SignalAction,
    SignalDirection,
    StrategyConfig,
)


@dataclass
class IndicatorStopDistances:
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


class ClockBarAggregator:
    """Aggregate 1m bars into clock-aligned bars and emit on completed buckets."""

    def __init__(self, minutes: int):
        self.minutes = max(1, int(minutes or 1))
        self._bucket_key: Optional[tuple[int, int, int, int, int]] = None
        self._buffer: list[Bar] = []

    def update(self, bar: Bar) -> Optional[Bar]:
        if self.minutes <= 1:
            return bar

        key = self._bucket_for(bar.time)
        if self._bucket_key is not None and key != self._bucket_key:
            self._bucket_key = key
            self._buffer = [bar]
            return None

        if self._bucket_key is None:
            self._bucket_key = key

        minute_key = bar.time.strftime("%Y-%m-%d %H:%M")
        if self._buffer and self._buffer[-1].time.strftime("%Y-%m-%d %H:%M") == minute_key:
            self._buffer[-1] = bar
        else:
            self._buffer.append(bar)

        if len(self._buffer) >= self.minutes:
            completed = self._aggregate(self._buffer[-self.minutes:])
            self._buffer.clear()
            self._bucket_key = None
            return completed
        return None

    def reset(self) -> None:
        self._bucket_key = None
        self._buffer.clear()

    def _bucket_for(self, ts: datetime) -> tuple[int, int, int, int, int]:
        bucket_minute = (ts.minute // self.minutes) * self.minutes
        return (ts.year, ts.month, ts.day, ts.hour, bucket_minute)

    @staticmethod
    def _aggregate(bars: list[Bar]) -> Bar:
        return Bar(
            time=bars[-1].time,
            open=bars[0].open,
            high=max(item.high for item in bars),
            low=min(item.low for item in bars),
            close=bars[-1].close,
            volume=sum(item.volume for item in bars),
            symbol=bars[-1].symbol,
        )


class IndicatorComboStrategyEngine:
    """TMF strategies built from TXF EMA/MACD trend and TMF KD/PSAR/ATR timing."""

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig.from_dict({"strategy_type": "tmf_pullback_breakout"})
        self._tx_aggregator = ClockBarAggregator(self._setting("indicator_trend_timeframe_minutes"))
        self._tmf_aggregator = ClockBarAggregator(self._setting("indicator_entry_timeframe_minutes"))
        self._trend_bars: list[Bar] = []
        self._entry_bars: list[Bar] = []
        self._max_bars = 240

        self._trend_snapshot: Optional[dict] = None
        self._entry_snapshot: Optional[dict] = None
        self._current_direction = SignalDirection.NEUTRAL

        self._entry_price: Optional[float] = None
        self._entry_side: Optional[OrderSide] = None
        self._stop_price: Optional[float] = None
        self._target_price: Optional[float] = None
        self._pending_entry_atr: Optional[float] = None
        self._bars_since_entry = 0
        self._cooldown_remaining = 0

        self.signals: list[Signal] = []

    @property
    def current_direction(self) -> SignalDirection:
        return self._current_direction

    @property
    def current_atr(self) -> float:
        if self._entry_snapshot is None:
            return 0.0
        return float(self._entry_snapshot.get("atr14") or 0.0)

    def update_tx_bar(self, bar: Bar) -> None:
        completed = self._tx_aggregator.update(bar)
        if completed is None:
            return
        self._trend_bars.append(completed)
        self._trend_bars = self._trend_bars[-self._max_bars:]
        self._trend_snapshot = _build_indicator_snapshot(self._trend_bars)
        self._current_direction = self._resolve_trend_direction(self._trend_snapshot)

    def warmup_tmf_bar(self, bar: Bar, session: SessionType) -> None:
        completed = self._tmf_aggregator.update(bar)
        if completed is not None:
            self._append_entry_bar(completed)

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
        completed = self._tmf_aggregator.update(bar)
        if completed is None:
            return None

        self._append_entry_bar(completed)
        snapshot = self._entry_snapshot
        if snapshot is None:
            return None

        if has_position and position_side is not None:
            if self._entry_price is None and position_entry_price is not None:
                self.set_position_info(position_entry_price, position_side)
            self._bars_since_entry += 1
            signal = self._check_exit(completed, session, position_side, int(position_qty or 1))
            if signal:
                self.signals.append(signal)
                return signal
            return None

        if self._entry_price is not None:
            self.clear_position_info()

        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            return None

        signal = self._check_entry(completed, session)
        if signal:
            self.signals.append(signal)
            return signal
        return None

    def set_position_info(self, entry_price: float, side: OrderSide) -> None:
        atr = max(1.0, float(self._pending_entry_atr or self.current_atr or 1.0))
        stop_distance = atr * float(self._setting("indicator_atr_stop_mult"))
        target_distance = atr * float(self._setting("indicator_atr_target_mult"))
        self._entry_price = float(entry_price)
        self._entry_side = side
        self._bars_since_entry = 0
        if side == OrderSide.BUY:
            self._stop_price = self._entry_price - stop_distance
            self._target_price = self._entry_price + target_distance
        else:
            self._stop_price = self._entry_price + stop_distance
            self._target_price = self._entry_price - target_distance
        self._pending_entry_atr = None

    def clear_position_info(self) -> None:
        had_position = self._entry_price is not None
        self._entry_price = None
        self._entry_side = None
        self._stop_price = None
        self._target_price = None
        self._pending_entry_atr = None
        self._bars_since_entry = 0
        if had_position:
            self._cooldown_remaining = max(
                self._cooldown_remaining,
                int(self._setting("indicator_cooldown_bars")),
            )

    def on_position_reduced(self) -> None:
        self._bars_since_entry = 0

    def get_effective_stop_distances(
        self,
        bar: Bar,
        session: SessionType,
        profile=None,
    ) -> IndicatorStopDistances:
        atr = max(1.0, float(self.current_atr or 1.0))
        initial = atr * float(self._setting("indicator_atr_stop_mult"))
        trailing = initial
        target = atr * float(self._setting("indicator_atr_target_mult"))
        return IndicatorStopDistances(
            initial_stop=initial,
            trailing_stop=trailing,
            overheat_trailing_stop=trailing,
            trailing_activation=target,
            pyramid_distance=target,
            atr=atr,
            noise_initial=0.0,
            noise_trailing=0.0,
            price_reference=float(bar.close or 0.0),
        )

    def reset_session(self) -> None:
        self._tx_aggregator.reset()
        self._tmf_aggregator.reset()
        self._current_direction = self._resolve_trend_direction(self._trend_snapshot)

    def reset(self) -> None:
        self.reset_session()
        self.clear_position_info()
        self.signals.clear()
        self._cooldown_remaining = 0

    def _setting(self, name: str):
        getter = getattr(self.config, "indicator_setting", None)
        if callable(getter):
            return getter(name)
        return getattr(self.config, name)

    def _append_entry_bar(self, bar: Bar) -> None:
        self._entry_bars.append(bar)
        self._entry_bars = self._entry_bars[-self._max_bars:]
        self._entry_snapshot = _build_indicator_snapshot(self._entry_bars)

    def _resolve_trend_direction(self, snapshot: Optional[dict]) -> SignalDirection:
        if not snapshot or not _finite(
            snapshot.get("close"),
            snapshot.get("ema20"),
            snapshot.get("ema60"),
            snapshot.get("ema20_slope3"),
            snapshot.get("hist"),
        ):
            return SignalDirection.NEUTRAL

        hist_min = float(self._setting("indicator_trend_hist_min"))
        if (
            snapshot["close"] > snapshot["ema60"]
            and snapshot["ema20"] > snapshot["ema60"]
            and snapshot["ema20_slope3"] > 0
            and snapshot["hist"] >= hist_min
        ):
            return SignalDirection.LONG
        if (
            snapshot["close"] < snapshot["ema60"]
            and snapshot["ema20"] < snapshot["ema60"]
            and snapshot["ema20_slope3"] < 0
            and snapshot["hist"] <= -hist_min
        ):
            return SignalDirection.SHORT
        return SignalDirection.NEUTRAL

    def _check_entry(self, bar: Bar, session: SessionType) -> Optional[Signal]:
        snapshot = self._entry_snapshot
        trend = self._trend_snapshot
        if snapshot is None or trend is None or len(self._entry_bars) < 3:
            return None
        previous = _build_indicator_snapshot(self._entry_bars[:-1])
        before_previous = _build_indicator_snapshot(self._entry_bars[:-2])
        if previous is None or before_previous is None:
            return None

        required = [
            trend.get("close"),
            trend.get("ema20"),
            trend.get("ema60"),
            trend.get("ema20_slope3"),
            trend.get("hist"),
            snapshot.get("ema20"),
            snapshot.get("hist"),
            snapshot.get("k"),
            snapshot.get("d"),
            snapshot.get("atr14"),
            snapshot.get("psar"),
        ]
        if not _finite(*required):
            return None

        entry_hist_min = float(self._setting("indicator_entry_hist_min"))
        kd_long = (
            snapshot["k"] > snapshot["d"]
            and snapshot["k"] > previous["k"]
            and snapshot["k"] <= float(self._setting("indicator_kd_long_max"))
        )
        kd_short = (
            snapshot["k"] < snapshot["d"]
            and snapshot["k"] < previous["k"]
            and snapshot["k"] >= float(self._setting("indicator_kd_short_min"))
        )
        macd_long = (
            snapshot["hist"] >= entry_hist_min
            or snapshot["hist"] > previous["hist"] > before_previous["hist"]
        )
        macd_short = (
            snapshot["hist"] <= -entry_hist_min
            or snapshot["hist"] < previous["hist"] < before_previous["hist"]
        )

        touch_atr = float(self._setting("indicator_touch_atr_mult"))
        prev_bar = self._entry_bars[-2]
        prev2_bar = self._entry_bars[-3]
        entry_type = str(self._setting("indicator_entry_type") or "pullback_breakout")
        if entry_type == "pullback_reclaim":
            long_trigger = bar.low <= snapshot["ema20"] + touch_atr * snapshot["atr14"] and bar.close >= snapshot["ema20"]
            short_trigger = bar.high >= snapshot["ema20"] - touch_atr * snapshot["atr14"] and bar.close <= snapshot["ema20"]
        elif entry_type == "psar_flip":
            long_trigger = bool(snapshot["psar_flip_long"])
            short_trigger = bool(snapshot["psar_flip_short"])
        elif entry_type == "kd_momentum":
            long_trigger = kd_long
            short_trigger = kd_short
        else:
            long_trigger = (
                bar.close > max(prev_bar.high, prev2_bar.high)
                and prev_bar.low <= previous["ema20"] + touch_atr * previous["atr14"]
            )
            short_trigger = (
                bar.close < min(prev_bar.low, prev2_bar.low)
                and prev_bar.high >= previous["ema20"] - touch_atr * previous["atr14"]
            )

        if bool(self._setting("indicator_require_psar_entry")):
            long_trigger = long_trigger and snapshot["ptrend"] == 1 and snapshot["psar"] < bar.close
            short_trigger = short_trigger and snapshot["ptrend"] == -1 and snapshot["psar"] > bar.close

        if (
            bool(self._setting("indicator_longs_enabled"))
            and self._current_direction == SignalDirection.LONG
            and kd_long
            and macd_long
            and long_trigger
        ):
            self._pending_entry_atr = float(snapshot["atr14"])
            return Signal(
                bar_time=bar.time,
                direction=SignalDirection.LONG,
                action=SignalAction.BUY,
                entry_price=bar.close,
                qty=1,
                reason=f"{self.config.strategy_type}_long_entry: {entry_type}, atr={snapshot['atr14']:.1f}",
                session=session,
            )

        if (
            bool(self._setting("indicator_shorts_enabled"))
            and self._current_direction == SignalDirection.SHORT
            and kd_short
            and macd_short
            and short_trigger
        ):
            self._pending_entry_atr = float(snapshot["atr14"])
            return Signal(
                bar_time=bar.time,
                direction=SignalDirection.SHORT,
                action=SignalAction.SELL,
                entry_price=bar.close,
                qty=1,
                reason=f"{self.config.strategy_type}_short_entry: {entry_type}, atr={snapshot['atr14']:.1f}",
                session=session,
            )
        return None

    def _check_exit(
        self,
        bar: Bar,
        session: SessionType,
        position_side: OrderSide,
        current_qty: int,
    ) -> Optional[Signal]:
        snapshot = self._entry_snapshot
        if snapshot is None or self._entry_price is None:
            return None
        qty = max(1, int(current_qty or 1))
        min_hold = int(self._setting("indicator_min_hold_bars"))

        if position_side == OrderSide.BUY:
            if self._stop_price is not None and bar.low <= self._stop_price:
                return self._close_signal(bar, SignalDirection.LONG, SignalAction.CLOSE_LONG, qty, session, "atr_stop")
            if self._target_price is not None and bar.high >= self._target_price:
                return self._close_signal(bar, SignalDirection.LONG, SignalAction.CLOSE_LONG, qty, session, "atr_target")
            if bool(self._setting("indicator_trail_psar")) and self._bars_since_entry >= int(self._setting("indicator_trail_after_bars")):
                if _finite(snapshot.get("psar")) and snapshot["psar"] < bar.close:
                    self._stop_price = max(self._stop_price or -math.inf, float(snapshot["psar"]))
            if self._bars_since_entry >= min_hold and self._long_exit_signal(snapshot):
                return self._close_signal(bar, SignalDirection.LONG, SignalAction.CLOSE_LONG, qty, session, "signal_exit")

        if position_side == OrderSide.SELL:
            if self._stop_price is not None and bar.high >= self._stop_price:
                return self._close_signal(bar, SignalDirection.SHORT, SignalAction.CLOSE_SHORT, qty, session, "atr_stop")
            if self._target_price is not None and bar.low <= self._target_price:
                return self._close_signal(bar, SignalDirection.SHORT, SignalAction.CLOSE_SHORT, qty, session, "atr_target")
            if bool(self._setting("indicator_trail_psar")) and self._bars_since_entry >= int(self._setting("indicator_trail_after_bars")):
                if _finite(snapshot.get("psar")) and snapshot["psar"] > bar.close:
                    self._stop_price = min(self._stop_price or math.inf, float(snapshot["psar"]))
            if self._bars_since_entry >= min_hold and self._short_exit_signal(snapshot):
                return self._close_signal(bar, SignalDirection.SHORT, SignalAction.CLOSE_SHORT, qty, session, "signal_exit")
        return None

    def _close_signal(
        self,
        bar: Bar,
        direction: SignalDirection,
        action: SignalAction,
        qty: int,
        session: SessionType,
        reason: str,
    ) -> Signal:
        stop_text = f"{self._stop_price:.1f}" if self._stop_price is not None else "na"
        target_text = f"{self._target_price:.1f}" if self._target_price is not None else "na"
        return Signal(
            bar_time=bar.time,
            direction=direction,
            action=action,
            qty=qty,
            reason=f"{self.config.strategy_type}_{reason}: stop={stop_text}, target={target_text}",
            session=session,
        )

    def _long_exit_signal(self, snapshot: dict) -> bool:
        previous = _build_indicator_snapshot(self._entry_bars[:-1])
        if previous is None or not _finite(snapshot.get("k"), snapshot.get("d"), previous.get("k"), previous.get("d"), snapshot.get("hist")):
            return False
        kd_exit = snapshot["k"] < snapshot["d"] and previous["k"] >= previous["d"]
        return kd_exit or snapshot["hist"] < 0 or snapshot["ptrend"] == -1

    def _short_exit_signal(self, snapshot: dict) -> bool:
        previous = _build_indicator_snapshot(self._entry_bars[:-1])
        if previous is None or not _finite(snapshot.get("k"), snapshot.get("d"), previous.get("k"), previous.get("d"), snapshot.get("hist")):
            return False
        kd_exit = snapshot["k"] > snapshot["d"] and previous["k"] <= previous["d"]
        return kd_exit or snapshot["hist"] > 0 or snapshot["ptrend"] == 1


def _build_indicator_snapshot(bars: list[Bar]) -> Optional[dict]:
    if not bars:
        return None
    closes = [bar.close for bar in bars]
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]

    ema20 = _ema(closes, 20)
    ema60 = _ema(closes, 60)
    macd, signal = _macd(closes)
    hist = [
        (m - s) if m is not None and s is not None else math.nan
        for m, s in zip(macd, signal)
    ]
    k_values, d_values = _kd(highs, lows, closes)
    atr = _atr(highs, lows, closes, 14)
    psar, ptrend = _psar(highs, lows, closes)
    index = len(bars) - 1
    prev_index = index - 1
    return {
        "time": bars[index].time,
        "open": bars[index].open,
        "high": bars[index].high,
        "low": bars[index].low,
        "close": bars[index].close,
        "ema20": _value_at(ema20, index),
        "ema60": _value_at(ema60, index),
        "ema20_slope3": (
            _value_at(ema20, index) - _value_at(ema20, index - 3)
            if index >= 3 and _finite(_value_at(ema20, index), _value_at(ema20, index - 3))
            else math.nan
        ),
        "macd": _value_at(macd, index),
        "macd_signal": _value_at(signal, index),
        "hist": _value_at(hist, index),
        "k": _value_at(k_values, index),
        "d": _value_at(d_values, index),
        "atr14": _value_at(atr, index),
        "psar": _value_at(psar, index),
        "ptrend": _value_at(ptrend, index, 0),
        "psar_flip_long": (
            prev_index >= 0
            and _value_at(ptrend, index, 0) == 1
            and _value_at(ptrend, prev_index, 0) == -1
        ),
        "psar_flip_short": (
            prev_index >= 0
            and _value_at(ptrend, index, 0) == -1
            and _value_at(ptrend, prev_index, 0) == 1
        ),
    }


def _value_at(values: list, index: int, fallback=math.nan):
    if index < 0 or index >= len(values):
        return fallback
    value = values[index]
    return fallback if value is None else value


def _finite(*values) -> bool:
    for value in values:
        if value is None:
            return False
        try:
            if not math.isfinite(float(value)):
                return False
        except (TypeError, ValueError):
            return False
    return True


def _ema(values: list[float], period: int) -> list[Optional[float]]:
    result: list[Optional[float]] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return result
    multiplier = 2 / (period + 1)
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    for index in range(period, len(values)):
        seed = (values[index] - seed) * multiplier + seed
        result[index] = seed
    return result


def _macd(values: list[float]) -> tuple[list[Optional[float]], list[Optional[float]]]:
    ema_fast = _ema(values, 12)
    ema_slow = _ema(values, 26)
    macd_line: list[Optional[float]] = [None] * len(values)
    compact: list[float] = []
    for index, (fast, slow) in enumerate(zip(ema_fast, ema_slow)):
        if fast is None or slow is None:
            continue
        value = fast - slow
        macd_line[index] = value
        compact.append(value)
    signal_compact = _ema(compact, 9)
    signal: list[Optional[float]] = [None] * len(values)
    compact_index = 0
    for index, value in enumerate(macd_line):
        if value is None:
            continue
        signal[index] = signal_compact[compact_index]
        compact_index += 1
    return macd_line, signal


def _kd(highs: list[float], lows: list[float], closes: list[float]) -> tuple[list[Optional[float]], list[Optional[float]]]:
    k_values: list[Optional[float]] = [None] * len(closes)
    d_values: list[Optional[float]] = [None] * len(closes)
    previous_k = 50.0
    previous_d = 50.0
    for index in range(len(closes)):
        if index < 8:
            continue
        high = max(highs[index - 8:index + 1])
        low = min(lows[index - 8:index + 1])
        rsv = 50.0 if high == low else ((closes[index] - low) / (high - low)) * 100
        previous_k = (2 * previous_k + rsv) / 3
        previous_d = (2 * previous_d + previous_k) / 3
        k_values[index] = previous_k
        d_values[index] = previous_d
    return k_values, d_values


def _atr(highs: list[float], lows: list[float], closes: list[float], period: int) -> list[Optional[float]]:
    true_ranges: list[float] = []
    for index in range(len(closes)):
        if index == 0:
            true_ranges.append(highs[index] - lows[index])
        else:
            prev_close = closes[index - 1]
            true_ranges.append(max(
                highs[index] - lows[index],
                abs(highs[index] - prev_close),
                abs(lows[index] - prev_close),
            ))
    result: list[Optional[float]] = [None] * len(closes)
    for index in range(period - 1, len(closes)):
        result[index] = sum(true_ranges[index - period + 1:index + 1]) / period
    return result


def _psar(highs: list[float], lows: list[float], closes: list[float], step: float = 0.02, max_step: float = 0.2) -> tuple[list[Optional[float]], list[int]]:
    count = len(closes)
    psar: list[Optional[float]] = [None] * count
    trend = [0] * count
    if count < 3:
        return psar, trend
    bull = closes[1] >= closes[0]
    af = step
    ep = highs[0] if bull else lows[0]
    sar = lows[0] if bull else highs[0]
    psar[1] = sar
    trend[0] = trend[1] = 1 if bull else -1
    for index in range(2, count):
        if bull:
            sar = sar + af * (ep - sar)
            sar = min(sar, lows[index - 1], lows[index - 2])
            if lows[index] < sar:
                bull = False
                sar = ep
                ep = lows[index]
                af = step
            elif highs[index] > ep:
                ep = highs[index]
                af = min(af + step, max_step)
        else:
            sar = sar + af * (ep - sar)
            sar = max(sar, highs[index - 1], highs[index - 2])
            if highs[index] > sar:
                bull = True
                sar = ep
                ep = highs[index]
                af = step
            elif lows[index] < ep:
                ep = lows[index]
                af = min(af + step, max_step)
        psar[index] = sar
        trend[index] = 1 if bull else -1
    return psar, trend
