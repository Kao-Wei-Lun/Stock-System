from __future__ import annotations

from datetime import datetime, timezone

from paper_trading.bot_runner import PaperTradingBot
from paper_trading.cost_model import SessionType
from paper_trading.risk_engine import determine_session
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


def test_speed_mode_trade_messages_build_realtime_one_minute_bars() -> None:
    bot = PaperTradingBot(bot_id=1)
    bot.start(None)

    bot._on_ws_message(_trade_message("TMFE6", 20500, datetime(2026, 4, 24, 13, 1, 10, tzinfo=timezone.utc), volume=2))
    bot._on_ws_message(_trade_message("TMFE6", 20520, datetime(2026, 4, 24, 13, 1, 40, tzinfo=timezone.utc), volume=3))

    current = bot._tick_aggregator["TMFE6"]
    assert bot.get_state()["bar_count"] == 1
    assert len(bot.strategy._tmf_recent_bars) == 1
    assert current["open"] == 20500
    assert current["high"] == 20520
    assert current["low"] == 20500
    assert current["close"] == 20520
    assert current["volume"] == 5

    bot._on_ws_message(_trade_message("TMFE6", 20530, datetime(2026, 4, 24, 13, 2, 1, tzinfo=timezone.utc), volume=1))

    assert bot.get_state()["bar_count"] == 2
    assert len(bot.strategy._tmf_recent_bars) == 2
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

    assert bot.get_state()["bar_count"] == 1
    assert len(bot.strategy._tx_vwap._bars) == 1
    assert len(bot.strategy._tx_5m._buffer) == 1
    assert len(bot.strategy._tx_5m._completed) == 0
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

    assert bot.get_state()["bar_count"] == 1
    assert len(bot.strategy._tmf_recent_bars) == 1
    assert len(bot.strategy._tmf_atr._trs) == 1


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
