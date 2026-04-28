from __future__ import annotations

from datetime import datetime, timezone

from paper_trading.bot_runner import PaperTradingBot
from paper_trading.cost_model import OrderSide, SessionType
from paper_trading.risk_engine import determine_session, trading_session_key
from paper_trading.strategy_engine import StrategyConfig


def _trade_message(symbol: str, price: float, ts: datetime, *, volume: int = 1) -> dict:
    return {
        "event": "data",
        "channel": "trades",
        "data": {
            "symbol": symbol,
            "price": price,
            "volume": volume,
            "time": int(ts.timestamp() * 1_000_000),
        },
    }


def test_parse_candle_converts_utc_payload_to_taipei_night_session() -> None:
    bar = PaperTradingBot._parse_candle(
        {
            "date": "2026-04-24T13:01:00+00:00",
            "open": 20500,
            "high": 20520,
            "low": 20490,
            "close": 20510,
            "volume": 88,
        },
        "TMF",
    )

    assert bar is not None
    assert bar.time.hour == 21
    assert bar.time.utcoffset().total_seconds() == 8 * 60 * 60
    assert determine_session(bar.time) == SessionType.NIGHT


def test_trading_session_key_keeps_night_session_across_midnight() -> None:
    assert trading_session_key(datetime(2026, 4, 24, 23, 59), SessionType.NIGHT) == "2026-04-24:night"
    assert trading_session_key(datetime(2026, 4, 25, 0, 1), SessionType.NIGHT) == "2026-04-24:night"
    assert trading_session_key(datetime(2026, 4, 25, 8, 45), SessionType.DAY) == "2026-04-25:day"


def test_realtime_strategy_resets_at_day_session_boundary_after_night() -> None:
    bot = PaperTradingBot(bot_id=1)
    bot.start(None)

    bot.process_candle(
        "TXF",
        {
            "date": "2026-04-25T04:59:00+08:00",
            "open": 19_900,
            "high": 19_910,
            "low": 19_890,
            "close": 19_905,
            "volume": 100,
        },
    )

    night_session_key = bot._current_session_key
    assert night_session_key == "2026-04-24:night"
    assert len(bot.strategy._tx_vwap._bars) == 1

    bot.process_candle(
        "TXF",
        {
            "date": "2026-04-25T08:45:00+08:00",
            "open": 20_000,
            "high": 20_010,
            "low": 19_990,
            "close": 20_005,
            "volume": 100,
        },
    )

    assert bot._current_session_key == "2026-04-25:day"
    assert len(bot.strategy._tx_vwap._bars) == 1
    assert bot.strategy._tx_vwap._bars[-1].time.hour == 8


def test_speed_mode_trade_messages_build_realtime_one_minute_bars() -> None:
    bot = PaperTradingBot(bot_id=1)
    bot.start(None)

    bot._on_ws_message(_trade_message("TMFE6", 20500, datetime(2026, 4, 24, 13, 1, 10, tzinfo=timezone.utc), volume=2))
    bot._on_ws_message(_trade_message("TMFE6", 20520, datetime(2026, 4, 24, 13, 1, 40, tzinfo=timezone.utc), volume=3))

    current = bot._tick_aggregator["TMFE6"]
    assert bot.get_state()["bar_count"] == 0
    assert len(bot.strategy._tmf_recent_bars) == 0
    assert current["open"] == 20500
    assert current["high"] == 20520
    assert current["low"] == 20500
    assert current["close"] == 20520
    assert current["volume"] == 5
    assert bot.get_state()["latest_realtime_bar"]["close"] == 20520
    assert bot.get_state()["latest_realtime_bar_is_partial"] is True

    bot._on_ws_message(_trade_message("TMFE6", 20530, datetime(2026, 4, 24, 13, 2, 1, tzinfo=timezone.utc), volume=1))

    assert bot.get_state()["bar_count"] == 1
    assert len(bot.strategy._tmf_recent_bars) == 1
    assert bot.strategy._tmf_recent_bars[-1].close == 20520
    assert bot._tick_aggregator["TMFE6"]["minute"] == "2026-04-24 13:02"
    assert bot._tick_aggregator["TMFE6"]["open"] == 20530


def test_speed_mode_same_minute_tx_ticks_do_not_advance_multi_minute_aggregators() -> None:
    bot = PaperTradingBot(bot_id=1)
    bot.start(None)

    for second, price in enumerate([20500, 20510, 20520, 20530, 20540], start=10):
        bot._on_ws_message(
            _trade_message(
                "TXFE6",
                price,
                datetime(2026, 4, 24, 13, 1, second, tzinfo=timezone.utc),
            )
        )

    assert bot.get_state()["bar_count"] == 0
    assert len(bot.strategy._tx_vwap._bars) == 0
    assert len(bot.strategy._tx_5m._buffer) == 0
    assert len(bot.strategy._tx_5m._completed) == 0
    assert len(bot.strategy._tmf_recent_bars) == 0

    bot._on_ws_message(
        _trade_message(
            "TXFE6",
            20550,
            datetime(2026, 4, 24, 13, 2, 1, tzinfo=timezone.utc),
        )
    )

    assert bot.get_state()["bar_count"] == 1
    assert len(bot.strategy._tx_vwap._bars) == 1
    assert len(bot.strategy._tx_5m._buffer) == 1
    assert len(bot.strategy._tmf_recent_bars) == 1


def test_v2_speed_mode_same_minute_tmf_ticks_update_one_strategy_bar_and_one_atr_slot() -> None:
    bot = PaperTradingBot(bot_id=1, strategy_config=StrategyConfig(strategy_type="v2"))
    bot.start(None)

    for second, price in enumerate([20500, 20510, 20520], start=10):
        bot._on_ws_message(
            _trade_message(
                "TMFE6",
                price,
                datetime(2026, 4, 24, 13, 1, second, tzinfo=timezone.utc),
            )
        )

    assert bot.get_state()["bar_count"] == 0
    assert len(bot.strategy._tmf_recent_bars) == 0
    assert len(bot.strategy._tmf_atr._trs) == 0

    bot._on_ws_message(
        _trade_message(
            "TMFE6",
            20530,
            datetime(2026, 4, 24, 13, 2, 1, tzinfo=timezone.utc),
        )
    )

    assert bot.get_state()["bar_count"] == 1
    assert len(bot.strategy._tmf_recent_bars) == 1
    assert len(bot.strategy._tmf_atr._trs) == 1


def test_duplicate_same_minute_candles_do_not_refill_orders_or_advance_cooldown() -> None:
    bot = PaperTradingBot(bot_id=1)
    bot.start(None)
    bot.account.cooldown_remaining_bars = 3
    bot.broker.create_market_order("TMF", OrderSide.BUY, 1, session=SessionType.DAY, reason="test_entry")

    payload = {
        "date": "2026-04-24T08:46:00+08:00",
        "open": 20500,
        "high": 20520,
        "low": 20490,
        "close": 20510,
        "volume": 88,
    }
    bot.process_candle("TMF", payload)

    assert bot.get_state()["bar_count"] == 1
    assert bot.get_state()["total_fills"] == 1
    assert bot.account.cooldown_remaining_bars == 2

    duplicate_payload = {**payload, "high": 20530, "close": 20525}
    bot.process_candle("TMF", duplicate_payload)

    assert bot.get_state()["bar_count"] == 1
    assert bot.get_state()["total_fills"] == 1
    assert bot.account.cooldown_remaining_bars == 2
    assert bot.account.position.last_price == 20525


def test_trade_records_keep_strategy_entry_and_exit_reasons() -> None:
    bot = PaperTradingBot(bot_id=1)
    bot.start(None)
    bot.broker.create_market_order("TMF", OrderSide.BUY, 1, session=SessionType.DAY, reason="v2_long_entry: test")

    bot.process_candle(
        "TMF",
        {
            "date": "2026-04-24T08:46:00+08:00",
            "open": 20500,
            "high": 20520,
            "low": 20490,
            "close": 20510,
            "volume": 88,
        },
    )
    bot.broker.create_market_order("TMF", OrderSide.SELL, 1, session=SessionType.DAY, reason="v2_atr_stop: test")

    bot.process_candle(
        "TMF",
        {
            "date": "2026-04-24T08:47:00+08:00",
            "open": 20495,
            "high": 20500,
            "low": 20480,
            "close": 20490,
            "volume": 88,
        },
    )

    assert bot.account.trades[0].entry_reason == "v2_long_entry: test"
    assert bot.account.trades[0].exit_reason == "v2_atr_stop: test"


def test_txf_candle_can_drive_tmf_paper_bar_when_tmf_has_no_separate_ws_candle() -> None:
    bot = PaperTradingBot(bot_id=1)
    bot.start(None)

    bot.process_candle(
        "TXFE6",
        {
            "date": "2026-04-24T21:01:00+08:00",
            "open": 20500,
            "high": 20520,
            "low": 20490,
            "close": 20510,
            "volume": 88,
        },
    )

    assert bot.get_state()["bar_count"] == 1
    assert bot._last_processed_minute["TMF"] == "2026-04-24 21:01"


def test_resolved_contract_bot_uses_fubon_tmf_contract_without_txf_fallback() -> None:
    bot = PaperTradingBot(
        bot_id=1,
        tx_symbol="TXFE6",
        tmf_symbol="TMFE6",
        tx_requested_symbol="TXF",
        tmf_requested_symbol="TMF",
    )
    bot.start(None)

    bot.process_candle(
        "TXFE6",
        {
            "date": "2026-04-24T21:01:00+08:00",
            "open": 20500,
            "high": 20520,
            "low": 20490,
            "close": 20510,
            "volume": 88,
        },
    )

    assert bot.get_state()["bar_count"] == 0
    assert len(bot.strategy._tx_vwap._bars) == 1
    assert len(bot.strategy._tmf_recent_bars) == 0

    bot.process_candle(
        "TMFE6",
        {
            "date": "2026-04-24T21:01:00+08:00",
            "open": 20500,
            "high": 20520,
            "low": 20490,
            "close": 20510,
            "volume": 88,
        },
    )

    state = bot.get_state()
    assert state["bar_count"] == 1
    assert state["data_source"] == "fubon_neo"
    assert state["direction_symbol"] == "TXF"
    assert state["product_symbol"] == "TMF"
    assert state["resolved_direction_symbol"] == "TXFE6"
    assert state["resolved_product_symbol"] == "TMFE6"


def test_resolved_contract_bot_ignores_other_contract_months() -> None:
    bot = PaperTradingBot(bot_id=1, tx_symbol="TXFE6", tmf_symbol="TMFE6")
    bot.start(None)

    bot.process_candle(
        "TMFG6",
        {
            "date": "2026-04-24T21:01:00+08:00",
            "open": 20500,
            "high": 20520,
            "low": 20490,
            "close": 20510,
            "volume": 88,
        },
    )

    assert bot.get_state()["bar_count"] == 0
    assert len(bot.strategy._tmf_recent_bars) == 0
