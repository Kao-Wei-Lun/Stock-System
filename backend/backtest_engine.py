from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class StrategyDefinition:
    key: str
    name: str
    min_bars: int


STRATEGY_DEFINITIONS = (
    StrategyDefinition("ma_cross", "MA 黃金/死亡交叉", 55),
    StrategyDefinition("rsi_reversion", "RSI 超買超賣", 20),
    StrategyDefinition("macd_cross", "MACD 交叉", 40),
    StrategyDefinition("bollinger_breakout", "布林通道突破", 25),
    StrategyDefinition("kd_cross", "KD 交叉", 20),
)
STRATEGY_REGISTRY = {item.key: item for item in STRATEGY_DEFINITIONS}
STRATEGY_ALIASES = {
    alias: item.key
    for item in STRATEGY_DEFINITIONS
    for alias in {
        item.key,
        item.name,
        item.name.lower(),
    }
}


def list_backtest_strategies() -> List[Dict[str, Any]]:
    return [
        {
            "key": item.key,
            "name": item.name,
            "min_bars": item.min_bars,
        }
        for item in STRATEGY_DEFINITIONS
    ]


def resolve_strategy(strategy: str) -> StrategyDefinition:
    key = STRATEGY_ALIASES.get(str(strategy or "").strip(), "")
    if not key:
        raise ValueError(f"Unsupported backtest strategy: {strategy}")
    return STRATEGY_REGISTRY[key]


def run_backtest(rows: List[Dict[str, Any]], options: Dict[str, Any]) -> Dict[str, Any]:
    strategy = resolve_strategy(options.get("strategy"))
    ticker = str(options.get("ticker") or "").strip().upper() or None
    filtered_rows = _filter_rows(rows, options.get("start"), options.get("end"))
    if len(filtered_rows) < strategy.min_bars:
        raise ValueError("請確認日期範圍內有足夠資料再執行回測。")

    capital = max(float(options.get("capital") or 0), 0.0)
    if capital <= 0:
        raise ValueError("初始資金必須大於 0。")

    fee_rate = max(float(options.get("fee_rate") or 0), 0.0)
    slippage_rate = max(float(options.get("slippage_rate") or 0), 0.0)
    stop_loss_pct = _normalize_optional_pct(options.get("stop_loss_pct"))
    take_profit_pct = _normalize_optional_pct(options.get("take_profit_pct"))
    position_sizing = str(options.get("position_sizing") or "full_equity")

    indicator_context = _build_indicator_context(filtered_rows)
    cash = capital
    position = None
    trades: List[Dict[str, Any]] = []
    equity_curve: List[Dict[str, Any]] = []

    for index in range(1, len(filtered_rows)):
        signal = _strategy_signal(strategy.key, filtered_rows, indicator_context, index - 1)
        bar = filtered_rows[index]

        if position and index > position["entry_index"]:
            exit_decision = _evaluate_risk_exit(position, bar, stop_loss_pct, take_profit_pct, slippage_rate)
            if exit_decision:
                cash, trade = _close_position(position, cash, exit_decision["price"], fee_rate, bar["date"], exit_decision["reason"], index)
                trades.append(trade)
                position = None

        if position and signal == "sell":
            exit_price = _apply_sell_slippage(_safe_float(bar.get("open"), bar.get("close")), slippage_rate)
            cash, trade = _close_position(position, cash, exit_price, fee_rate, bar["date"], "strategy_exit", index)
            trades.append(trade)
            position = None
        elif not position and signal == "buy":
            entry_price = _apply_buy_slippage(_safe_float(bar.get("open"), bar.get("close")), slippage_rate)
            position = _open_position(cash, entry_price, fee_rate, bar["date"], index, position_sizing, ticker)
            if position:
                cash = position["cash_after_entry"]

        close_price = _safe_float(bar.get("close"), bar.get("open"))
        equity_curve.append(
            {
                "date": bar["date"],
                "equity": cash + (position["quantity"] * close_price if position else 0.0),
                "cash": cash,
                "position_qty": position["quantity"] if position else 0.0,
                "close_price": close_price,
                "payload": {
                    "signal": signal,
                    "position_open": bool(position),
                },
            }
        )

    if position:
        last_bar = filtered_rows[-1]
        exit_price = _apply_sell_slippage(_safe_float(last_bar.get("close"), last_bar.get("open")), slippage_rate)
        cash, trade = _close_position(
            position,
            cash,
            exit_price,
            fee_rate,
            last_bar["date"],
            "end_of_test",
            len(filtered_rows) - 1,
        )
        trades.append(trade)
        position = None
        if equity_curve:
            equity_curve[-1]["equity"] = cash
            equity_curve[-1]["cash"] = cash
            equity_curve[-1]["position_qty"] = 0.0
            equity_curve[-1]["payload"] = {
                **(equity_curve[-1].get("payload") or {}),
                "position_closed": True,
            }

    summary = _build_summary(
        filtered_rows=filtered_rows,
        ticker=ticker,
        strategy=strategy,
        capital=capital,
        cash=cash,
        trades=trades,
        equity_curve=equity_curve,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        position_sizing=position_sizing,
        interval=str(options.get("interval") or "1d"),
    )
    return summary


def _build_indicator_context(rows: List[Dict[str, Any]]) -> Dict[str, List[Optional[float]]]:
    closes = [_safe_float(row.get("close")) for row in rows]
    highs = [_safe_float(row.get("high"), row.get("close")) for row in rows]
    lows = [_safe_float(row.get("low"), row.get("close")) for row in rows]

    macd_line, signal_line = _calc_macd(closes)
    bb_mid, bb_upper, bb_lower = _calc_bollinger(closes, period=20, multiplier=2.0)
    stoch_k, stoch_d = _calc_stoch_kd(highs, lows, closes, period=9, k_smoothing=3, d_smoothing=3)

    return {
        "close": closes,
        "ma20": _calc_sma(closes, 20),
        "ma50": _calc_sma(closes, 50),
        "rsi14": _calc_rsi(closes, 14),
        "macd": macd_line,
        "macd_signal": signal_line,
        "bb_mid": bb_mid,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "stoch_k": stoch_k,
        "stoch_d": stoch_d,
    }


def _strategy_signal(
    strategy_key: str,
    rows: List[Dict[str, Any]],
    ctx: Dict[str, List[Optional[float]]],
    index: int,
) -> Optional[str]:
    if index <= 0:
        return None

    if strategy_key == "ma_cross":
        return _cross_signal(ctx["ma20"], ctx["ma50"], index)

    if strategy_key == "rsi_reversion":
        current = ctx["rsi14"][index]
        previous = ctx["rsi14"][index - 1]
        if current is None or previous is None:
            return None
        if current > 30 and previous <= 30:
            return "buy"
        if current < 70 and previous >= 70:
            return "sell"
        return None

    if strategy_key == "macd_cross":
        return _cross_signal(ctx["macd"], ctx["macd_signal"], index)

    if strategy_key == "bollinger_breakout":
        close_now = ctx["close"][index]
        close_prev = ctx["close"][index - 1]
        upper_now = ctx["bb_upper"][index]
        upper_prev = ctx["bb_upper"][index - 1]
        mid_now = ctx["bb_mid"][index]
        mid_prev = ctx["bb_mid"][index - 1]
        if None in {close_now, close_prev, upper_now, upper_prev, mid_now, mid_prev}:
            return None
        if close_now > upper_now and close_prev <= upper_prev:
            return "buy"
        if close_now < mid_now and close_prev >= mid_prev:
            return "sell"
        return None

    if strategy_key == "kd_cross":
        k_now = ctx["stoch_k"][index]
        k_prev = ctx["stoch_k"][index - 1]
        d_now = ctx["stoch_d"][index]
        d_prev = ctx["stoch_d"][index - 1]
        if None in {k_now, k_prev, d_now, d_prev}:
            return None
        if k_now > d_now and k_prev <= d_prev and min(k_now, d_now) < 35:
            return "buy"
        if k_now < d_now and k_prev >= d_prev and max(k_now, d_now) > 65:
            return "sell"
        return None

    return None


def _cross_signal(primary: List[Optional[float]], baseline: List[Optional[float]], index: int) -> Optional[str]:
    current_primary = primary[index]
    previous_primary = primary[index - 1]
    current_baseline = baseline[index]
    previous_baseline = baseline[index - 1]
    if None in {current_primary, previous_primary, current_baseline, previous_baseline}:
        return None
    if current_primary > current_baseline and previous_primary <= previous_baseline:
        return "buy"
    if current_primary < current_baseline and previous_primary >= previous_baseline:
        return "sell"
    return None


def _evaluate_risk_exit(
    position: Dict[str, Any],
    bar: Dict[str, Any],
    stop_loss_pct: Optional[float],
    take_profit_pct: Optional[float],
    slippage_rate: float,
) -> Optional[Dict[str, Any]]:
    low = _safe_float(bar.get("low"), bar.get("close"))
    high = _safe_float(bar.get("high"), bar.get("close"))
    entry_price = position["entry_price"]

    if stop_loss_pct:
        stop_price = entry_price * (1 - stop_loss_pct)
        if low <= stop_price:
            return {
                "price": _apply_sell_slippage(stop_price, slippage_rate),
                "reason": "stop_loss",
            }

    if take_profit_pct:
        take_profit_price = entry_price * (1 + take_profit_pct)
        if high >= take_profit_price:
            return {
                "price": _apply_sell_slippage(take_profit_price, slippage_rate),
                "reason": "take_profit",
            }

    return None


def _open_position(
    cash: float,
    entry_price: float,
    fee_rate: float,
    entry_date: str,
    entry_index: int,
    position_sizing: str,
    ticker: Optional[str],
) -> Optional[Dict[str, Any]]:
    if entry_price <= 0 or cash <= 0 or position_sizing != "full_equity":
        return None
    quantity = int(cash / (entry_price * (1 + fee_rate)))
    if quantity <= 0:
        return None
    entry_fee = quantity * entry_price * fee_rate
    entry_cost = quantity * entry_price + entry_fee
    return {
        "entry_date": entry_date,
        "entry_price": entry_price,
        "entry_index": entry_index,
        "quantity": quantity,
        "entry_fee": entry_fee,
        "entry_cost": entry_cost,
        "cash_after_entry": cash - entry_cost,
        "side": "long",
        "ticker": ticker,
    }


def _close_position(
    position: Dict[str, Any],
    cash: float,
    exit_price: float,
    fee_rate: float,
    exit_date: str,
    exit_reason: str,
    exit_index: int,
) -> tuple[float, Dict[str, Any]]:
    quantity = position["quantity"]
    exit_fee = quantity * exit_price * fee_rate
    proceeds = quantity * exit_price - exit_fee
    gross_pnl = quantity * (exit_price - position["entry_price"])
    net_pnl = proceeds - position["entry_cost"]
    updated_cash = cash + proceeds
    trade = {
        "ticker": position.get("ticker"),
        "side": position["side"],
        "entry_date": position["entry_date"],
        "entry_price": position["entry_price"],
        "exit_date": exit_date,
        "exit_price": exit_price,
        "quantity": quantity,
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "return_pct": (net_pnl / position["entry_cost"]) * 100 if position["entry_cost"] else 0.0,
        "fee_amount": position["entry_fee"] + exit_fee,
        "holding_bars": max(exit_index - position["entry_index"], 0),
        "exit_reason": exit_reason,
        "payload": {
            "entry_cost": position["entry_cost"],
            "entry_fee": position["entry_fee"],
            "exit_fee": exit_fee,
        },
    }
    return updated_cash, trade


def _build_summary(
    *,
    filtered_rows: List[Dict[str, Any]],
    ticker: Optional[str],
    strategy: StrategyDefinition,
    capital: float,
    cash: float,
    trades: List[Dict[str, Any]],
    equity_curve: List[Dict[str, Any]],
    fee_rate: float,
    slippage_rate: float,
    stop_loss_pct: Optional[float],
    take_profit_pct: Optional[float],
    position_sizing: str,
    interval: str,
) -> Dict[str, Any]:
    wins = [trade for trade in trades if trade["net_pnl"] > 0]
    losses = [trade for trade in trades if trade["net_pnl"] < 0]
    equity_values = [point["equity"] for point in equity_curve] or [capital, cash]
    total_return = ((cash / capital) - 1) * 100 if capital else 0.0
    profit_factor = (
        sum(item["net_pnl"] for item in wins) / abs(sum(item["net_pnl"] for item in losses))
        if losses
        else (None if wins else 0.0)
    )

    return {
        "ticker": ticker,
        "strategy_key": strategy.key,
        "strategy": strategy.name,
        "start": filtered_rows[0]["date"],
        "end": filtered_rows[-1]["date"],
        "interval": interval,
        "capital": capital,
        "finalEquity": cash,
        "totalReturn": total_return,
        "sellTrades": len(trades),
        "winRate": (len(wins) / len(trades) * 100) if trades else 0.0,
        "maxDrawdown": _calc_max_drawdown(equity_values),
        "sharpe": _calc_sharpe(equity_values),
        "bars": len(filtered_rows),
        "feeRate": fee_rate,
        "slippageRate": slippage_rate,
        "stopLoss": stop_loss_pct,
        "takeProfit": take_profit_pct,
        "positionSizing": position_sizing,
        "netProfit": cash - capital,
        "profitFactor": profit_factor,
        "avgTradeReturn": (
            sum(trade["return_pct"] for trade in trades) / len(trades)
            if trades
            else 0.0
        ),
        "trades": trades,
        "equity_curve": equity_curve,
    }


def _filter_rows(rows: List[Dict[str, Any]], start: Any, end: Any) -> List[Dict[str, Any]]:
    start_text = str(start or "").strip()
    end_text = str(end or "").strip()
    filtered = []
    for row in rows:
        row_date = str(row.get("date") or "").split("T", 1)[0]
        if not row_date:
            continue
        if start_text and row_date < start_text:
            continue
        if end_text and row_date > end_text:
            continue
        normalized = dict(row)
        normalized["date"] = row_date
        filtered.append(normalized)
    return filtered


def _calc_sma(values: List[float], period: int) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(values)
    if period <= 0:
        return result
    rolling_sum = 0.0
    for index, value in enumerate(values):
        rolling_sum += value
        if index >= period:
            rolling_sum -= values[index - period]
        if index >= period - 1:
            result[index] = rolling_sum / period
    return result


def _calc_ema(values: List[float], period: int) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(values)
    if period <= 0 or not values:
        return result
    multiplier = 2 / (period + 1)
    seed = None
    for index, value in enumerate(values):
        if index < period - 1:
            continue
        if seed is None:
            seed = sum(values[index - period + 1:index + 1]) / period
            result[index] = seed
            continue
        seed = (value - seed) * multiplier + seed
        result[index] = seed
    return result


def _calc_rsi(values: List[float], period: int) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(values)
    if len(values) <= period:
        return result

    gains = []
    losses = []
    for index in range(1, len(values)):
        delta = values[index] - values[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100 - (100 / (1 + rs))

    for index in range(period + 1, len(values)):
        gain = gains[index - 1]
        loss = losses[index - 1]
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        if avg_loss == 0:
            result[index] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[index] = 100 - (100 / (1 + rs))

    return result


def _calc_macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[List[Optional[float]], List[Optional[float]]]:
    ema_fast = _calc_ema(values, fast)
    ema_slow = _calc_ema(values, slow)
    macd_line: List[Optional[float]] = [None] * len(values)
    for index in range(len(values)):
        if ema_fast[index] is None or ema_slow[index] is None:
            continue
        macd_line[index] = ema_fast[index] - ema_slow[index]

    compact = [value for value in macd_line if value is not None]
    signal_compact = _calc_ema(compact, signal)
    signal_line: List[Optional[float]] = [None] * len(values)
    compact_index = 0
    for index, value in enumerate(macd_line):
        if value is None:
            continue
        signal_line[index] = signal_compact[compact_index]
        compact_index += 1
    return macd_line, signal_line


def _calc_bollinger(values: List[float], period: int, multiplier: float) -> tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    middle = _calc_sma(values, period)
    upper: List[Optional[float]] = [None] * len(values)
    lower: List[Optional[float]] = [None] * len(values)
    for index in range(period - 1, len(values)):
        window = values[index - period + 1:index + 1]
        mean = middle[index]
        if mean is None:
            continue
        variance = sum((value - mean) ** 2 for value in window) / period
        std = variance ** 0.5
        upper[index] = mean + (std * multiplier)
        lower[index] = mean - (std * multiplier)
    return middle, upper, lower


def _calc_stoch_kd(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    *,
    period: int,
    k_smoothing: int,
    d_smoothing: int,
) -> tuple[List[Optional[float]], List[Optional[float]]]:
    rsv: List[Optional[float]] = [None] * len(closes)
    for index in range(period - 1, len(closes)):
        window_high = max(highs[index - period + 1:index + 1])
        window_low = min(lows[index - period + 1:index + 1])
        if window_high == window_low:
            rsv[index] = 50.0
        else:
            rsv[index] = ((closes[index] - window_low) / (window_high - window_low)) * 100

    k_values: List[Optional[float]] = [None] * len(closes)
    d_values: List[Optional[float]] = [None] * len(closes)
    previous_k = 50.0
    previous_d = 50.0
    for index, value in enumerate(rsv):
        if value is None:
            continue
        previous_k = ((k_smoothing - 1) * previous_k + value) / k_smoothing
        previous_d = ((d_smoothing - 1) * previous_d + previous_k) / d_smoothing
        k_values[index] = previous_k
        d_values[index] = previous_d
    return k_values, d_values


def _calc_max_drawdown(equity_values: List[float]) -> float:
    peak = equity_values[0]
    max_drawdown = 0.0
    for value in equity_values:
        if value > peak:
            peak = value
        if peak <= 0:
            continue
        drawdown = ((peak - value) / peak) * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return max_drawdown


def _calc_sharpe(equity_values: List[float]) -> float:
    if len(equity_values) < 2:
        return 0.0
    returns = []
    for index in range(1, len(equity_values)):
        previous = equity_values[index - 1]
        current = equity_values[index]
        if previous <= 0:
            continue
        returns.append((current - previous) / previous)
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / len(returns)
    std = variance ** 0.5
    return (mean / std * sqrt(252)) if std else 0.0


def _safe_float(value: Any, fallback: Any = 0.0) -> float:
    candidate = fallback if value is None else value
    return float(candidate)


def _normalize_optional_pct(value: Any) -> Optional[float]:
    if value in (None, "", 0, 0.0):
        return None
    return max(float(value), 0.0)


def _apply_buy_slippage(price: float, slippage_rate: float) -> float:
    return price * (1 + slippage_rate)


def _apply_sell_slippage(price: float, slippage_rate: float) -> float:
    return price * (1 - slippage_rate)
