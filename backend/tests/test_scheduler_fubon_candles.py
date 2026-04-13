from scheduler import _build_fubon_candle_payload


def test_build_fubon_candle_payload_ignores_zero_low():
    payload = _build_fubon_candle_payload(
        "2330.TW",
        {
            "date": "2026-04-13T09:01:00+08:00",
            "timeframe": "1",
            "open": 815,
            "high": 818,
            "low": 0,
            "close": 817,
            "volume": 125,
        },
    )

    assert payload["open"] == 815
    assert payload["high"] == 818
    assert payload["low"] == 815
    assert payload["close"] == 817
