from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import time
from typing import Optional

from paper_trading.cost_model import OrderSide, SessionType
from paper_trading.simulation_broker import Bar
from paper_trading.strategy_engine import (
    Signal,
    SignalAction,
    SignalDirection,
    StrategyConfig,
)


NO_NEW_DAY_ENTRY_AFTER = time(13, 30)
DEFAULT_STOP_POINTS = 80.0


@dataclass
class TmfStopDistances:
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

    def _bucket_for(self, ts) -> tuple[int, int, int, int, int]:
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


class TmfKdMacdMaStrategyEngine:
    """TMF 1m KD/MACD/MA v1.4 with optional completed 5m/15m long filters."""

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig.from_dict({"strategy_type": "tmf_kd_macd_ma_v14"})
        self._bars_1m: list[Bar] = []
        self._bars_5m: list[Bar] = []
        self._bars_15m: list[Bar] = []
        self._agg_5m = ClockBarAggregator(5)
        self._agg_15m = ClockBarAggregator(15)
        self._max_1m_bars = 1200
        self._max_htf_bars = 360
        self._current_direction = SignalDirection.NEUTRAL
        self._entry_price: Optional[float] = None
        self._entry_side: Optional[OrderSide] = None
        self._stop_price: Optional[float] = None
        self._pending_stop_distance: Optional[float] = None
        self.signals: list[Signal] = []

    @property
    def current_direction(self) -> SignalDirection:
        return self._current_direction

    @property
    def current_atr(self) -> float:
        return 0.0

    def update_tx_bar(self, bar: Bar) -> None:
        return None

    def warmup_tmf_bar(self, bar: Bar, session: SessionType) -> None:
        self._ingest_bar(bar)

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
        self._ingest_bar(bar)
        snapshot = _build_tmf_snapshot(self._bars_1m)
        if snapshot is None:
            return None

        if has_position and position_side is not None:
            if self._entry_price is None and position_entry_price is not None:
                self.set_position_info(position_entry_price, position_side)
            signal = self._check_exit(bar, session, snapshot, position_side, int(position_qty or 1))
            if signal:
                self.signals.append(signal)
                return signal
            return None

        if self._entry_price is not None:
            self.clear_position_info()

        signal = self._check_entry(bar, session, snapshot)
        if signal:
            self.signals.append(signal)
            return signal
        return None

    def get_effective_stop_distances(self, bar: Bar, session: SessionType, profile=None) -> TmfStopDistances:
        stop = _positive_float(getattr(profile, "stop_loss_points", None), DEFAULT_STOP_POINTS)
        return TmfStopDistances(
            initial_stop=stop,
            trailing_stop=stop,
            overheat_trailing_stop=stop,
            trailing_activation=stop,
            pyramid_distance=stop,
            atr=0.0,
            noise_initial=0.0,
            noise_trailing=0.0,
            price_reference=float(bar.close or 0.0),
        )

    def set_position_info(self, entry_price: float, side: OrderSide) -> None:
        stop_distance = _positive_float(self._pending_stop_distance, DEFAULT_STOP_POINTS)
        self._entry_price = float(entry_price)
        self._entry_side = side
        self._stop_price = (
            self._entry_price - stop_distance
            if side == OrderSide.BUY
            else self._entry_price + stop_distance
        )
        self._pending_stop_distance = None

    def clear_position_info(self) -> None:
        self._entry_price = None
        self._entry_side = None
        self._stop_price = None
        self._pending_stop_distance = None

    def on_position_reduced(self) -> None:
        return None

    def reset_session(self) -> None:
        self._agg_5m.reset()
        self._agg_15m.reset()
        self._bars_1m.clear()
        self._bars_5m.clear()
        self._bars_15m.clear()
        self._current_direction = SignalDirection.NEUTRAL

    def reset(self) -> None:
        self.reset_session()
        self.clear_position_info()
        self.signals.clear()

    def _ingest_bar(self, bar: Bar) -> None:
        completed_5m = self._agg_5m.update(bar)
        completed_15m = self._agg_15m.update(bar)
        if completed_5m is not None:
            self._bars_5m.append(completed_5m)
            self._bars_5m = self._bars_5m[-self._max_htf_bars:]
        if completed_15m is not None:
            self._bars_15m.append(completed_15m)
            self._bars_15m = self._bars_15m[-self._max_htf_bars:]
        self._bars_1m.append(bar)
        self._bars_1m = self._bars_1m[-self._max_1m_bars:]

    def _check_entry(self, bar: Bar, session: SessionType, snapshot: dict) -> Optional[Signal]:
        if session != SessionType.DAY or bar.time.time() >= NO_NEW_DAY_ENTRY_AFTER:
            return None

        long_entry = self._long_entry(snapshot)
        short_entry = self._base_short_entry(snapshot)
        if long_entry and short_entry:
            return None

        if long_entry:
            self._current_direction = SignalDirection.LONG
            self._pending_stop_distance = self._configured_stop_distance(bar, session)
            return Signal(
                bar_time=bar.time,
                direction=SignalDirection.LONG,
                action=SignalAction.BUY,
                entry_price=bar.close,
                qty=1,
                reason=f"{self.config.strategy_type}_long_entry",
                session=session,
            )

        if short_entry:
            self._current_direction = SignalDirection.SHORT
            self._pending_stop_distance = self._configured_stop_distance(bar, session)
            return Signal(
                bar_time=bar.time,
                direction=SignalDirection.SHORT,
                action=SignalAction.SELL,
                entry_price=bar.close,
                qty=1,
                reason=f"{self.config.strategy_type}_short_entry",
                session=session,
            )
        return None

    def _check_exit(
        self,
        bar: Bar,
        session: SessionType,
        snapshot: dict,
        position_side: OrderSide,
        current_qty: int,
    ) -> Optional[Signal]:
        qty = max(1, int(current_qty or 1))
        if position_side == OrderSide.BUY:
            if self._stop_price is not None and bar.low <= self._stop_price:
                return self._close_signal(bar, SignalDirection.LONG, SignalAction.CLOSE_LONG, qty, session, "stop_loss")
            if snapshot["k"] > 90:
                return self._close_signal(bar, SignalDirection.LONG, SignalAction.CLOSE_LONG, qty, session, "kd_k_gt_90")
            if (
                snapshot["close"] < snapshot["ma5"]
                and snapshot["ma5_slope3"] < 0
                and snapshot["hist"] < snapshot["prev_hist"]
            ):
                return self._close_signal(bar, SignalDirection.LONG, SignalAction.CLOSE_LONG, qty, session, "weakness_exit")
            if (
                snapshot["ma5"] < snapshot["ma20"]
                and snapshot["hist"] > 0
                and snapshot["prev_close"] < snapshot["prev_ma5"]
            ):
                return self._close_signal(bar, SignalDirection.LONG, SignalAction.CLOSE_LONG, qty, session, "ma_exit")
            if self._base_short_entry(snapshot):
                return self._close_signal(bar, SignalDirection.LONG, SignalAction.CLOSE_LONG, qty, session, "short_entry")

        if position_side == OrderSide.SELL:
            if self._stop_price is not None and bar.high >= self._stop_price:
                return self._close_signal(bar, SignalDirection.SHORT, SignalAction.CLOSE_SHORT, qty, session, "stop_loss")
            if snapshot["k"] < 10:
                return self._close_signal(bar, SignalDirection.SHORT, SignalAction.CLOSE_SHORT, qty, session, "kd_k_lt_10")
            if snapshot["hist"] < -35:
                return self._close_signal(bar, SignalDirection.SHORT, SignalAction.CLOSE_SHORT, qty, session, "macd_lt_-35")
            if (
                snapshot["ma5"] > snapshot["ma10"]
                and snapshot["hist"] < 0
                and snapshot["prev_close"] > snapshot["prev_ma5"]
            ):
                return self._close_signal(bar, SignalDirection.SHORT, SignalAction.CLOSE_SHORT, qty, session, "ma_exit")
            if self._long_entry(snapshot):
                return self._close_signal(bar, SignalDirection.SHORT, SignalAction.CLOSE_SHORT, qty, session, "long_entry")
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
        self._current_direction = SignalDirection.NEUTRAL
        return Signal(
            bar_time=bar.time,
            direction=direction,
            action=action,
            qty=qty,
            reason=f"{self.config.strategy_type}_{reason}",
            session=session,
        )

    def _long_entry(self, snapshot: dict) -> bool:
        base = (
            (snapshot["dif"] < -20 or snapshot["signal"] < -20)
            and (snapshot["green_shrinking"] or snapshot["turns_red"])
            and snapshot["prev_k"] < 20
            and snapshot["k"] >= 20
            and snapshot["close"] < snapshot["ma20"]
        )
        if not base:
            return False

        strategy_type = self.config.strategy_type
        if strategy_type == "tmf_kd_macd_ma_v14_5m_kd":
            return _htf_delta_positive(self._bars_5m, "k")
        if strategy_type == "tmf_kd_macd_ma_v14_15m_kd":
            return _htf_delta_positive(self._bars_15m, "k")
        if strategy_type == "tmf_kd_macd_ma_v14_15m_macd":
            return _htf_delta_positive(self._bars_15m, "hist")
        return True

    def _base_short_entry(self, snapshot: dict) -> bool:
        return (
            (snapshot["dif"] > 29 or snapshot["signal"] > 29)
            and (snapshot["red_shrinking"] or snapshot["turns_green"])
            and snapshot["prev_k"] > 80
            and snapshot["k"] < snapshot["prev_k"]
            and snapshot["close"] > snapshot["ma5"]
            and snapshot["close"] < snapshot["prev_close"]
        )

    def _configured_stop_distance(self, bar: Bar, session: SessionType) -> float:
        try:
            profile = self.config.get_profile(bar.time, session)
        except Exception:
            profile = None
        return _positive_float(getattr(profile, "stop_loss_points", None), DEFAULT_STOP_POINTS)


def _build_tmf_snapshot(bars: list[Bar]) -> Optional[dict]:
    if len(bars) < 40:
        return None
    closes = [float(bar.close) for bar in bars]
    highs = [float(bar.high) for bar in bars]
    lows = [float(bar.low) for bar in bars]
    ma5 = _sma(closes, 5)
    ma10 = _sma(closes, 10)
    ma20 = _sma(closes, 20)
    k_values, _d_values = _kd_rolling(highs, lows, closes)
    dif_values, signal_values, hist_values = _macd_hist(closes)
    index = len(bars) - 1
    prev = index - 1
    required = [
        ma5[index],
        ma10[index],
        ma20[index],
        ma5[prev],
        k_values[index],
        k_values[prev],
        dif_values[index],
        signal_values[index],
        hist_values[index],
        hist_values[prev],
    ]
    if not _finite(*required):
        return None
    return {
        "close": closes[index],
        "prev_close": closes[prev],
        "ma5": ma5[index],
        "ma10": ma10[index],
        "ma20": ma20[index],
        "prev_ma5": ma5[prev],
        "ma5_slope3": ma5[index] - ma5[index - 3] if index >= 3 and _finite(ma5[index - 3]) else math.nan,
        "k": k_values[index],
        "prev_k": k_values[prev],
        "dif": dif_values[index],
        "signal": signal_values[index],
        "hist": hist_values[index],
        "prev_hist": hist_values[prev],
        "green_shrinking": hist_values[index] < 0 and hist_values[index] > hist_values[prev],
        "turns_red": hist_values[prev] <= 0 and hist_values[index] > 0,
        "red_shrinking": hist_values[index] > 0 and hist_values[index] < hist_values[prev],
        "turns_green": hist_values[prev] >= 0 and hist_values[index] < 0,
    }


def _htf_delta_positive(bars: list[Bar], field: str) -> bool:
    snapshot = _build_tmf_snapshot(bars)
    previous = _build_tmf_snapshot(bars[:-1]) if len(bars) > 1 else None
    if snapshot is None or previous is None:
        return False
    return _finite(snapshot.get(field), previous.get(field)) and snapshot[field] > previous[field]


def _sma(values: list[float], period: int) -> list[Optional[float]]:
    result: list[Optional[float]] = [None] * len(values)
    if period <= 0:
        return result
    rolling = 0.0
    for index, value in enumerate(values):
        rolling += value
        if index >= period:
            rolling -= values[index - period]
        if index >= period - 1:
            result[index] = rolling / period
    return result


def _rolling_optional(values: list[Optional[float]], period: int) -> list[Optional[float]]:
    result: list[Optional[float]] = [None] * len(values)
    for index in range(period - 1, len(values)):
        window = values[index - period + 1:index + 1]
        if all(_finite(item) for item in window):
            result[index] = sum(float(item) for item in window) / period
    return result


def _ema_optional(values: list[Optional[float]], span: int) -> list[Optional[float]]:
    result: list[Optional[float]] = [None] * len(values)
    if span <= 0:
        return result
    alpha = 2 / (span + 1)
    ema: Optional[float] = None
    valid_count = 0
    for index, value in enumerate(values):
        if not _finite(value):
            continue
        numeric = float(value)
        ema = numeric if ema is None else (numeric - ema) * alpha + ema
        valid_count += 1
        if valid_count >= span:
            result[index] = ema
    return result


def _macd_hist(closes: list[float]) -> tuple[list[Optional[float]], list[Optional[float]], list[Optional[float]]]:
    close_values = [float(item) for item in closes]
    fast = _ema_optional(close_values, 12)
    slow = _ema_optional(close_values, 26)
    dif: list[Optional[float]] = [None] * len(closes)
    for index, (fast_value, slow_value) in enumerate(zip(fast, slow)):
        if _finite(fast_value, slow_value):
            dif[index] = float(fast_value) - float(slow_value)
    signal = _ema_optional(dif, 9)
    hist: list[Optional[float]] = [None] * len(closes)
    for index, (dif_value, signal_value) in enumerate(zip(dif, signal)):
        if _finite(dif_value, signal_value):
            hist[index] = float(dif_value) - float(signal_value)
    return dif, signal, hist


def _kd_rolling(
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> tuple[list[Optional[float]], list[Optional[float]]]:
    rsv: list[Optional[float]] = [None] * len(closes)
    for index in range(8, len(closes)):
        high = max(highs[index - 8:index + 1])
        low = min(lows[index - 8:index + 1])
        rsv[index] = 50.0 if high == low else ((closes[index] - low) / (high - low)) * 100
    k_values = _rolling_optional(rsv, 3)
    d_values = _rolling_optional(k_values, 3)
    return k_values, d_values


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


def _positive_float(value, fallback: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback
    return numeric if numeric > 0 else fallback
