import providers


def test_subscribe_fubon_streams_uses_speed_mode_channels_for_taiwan_stock(monkeypatch):
    channels = []

    monkeypatch.setattr(providers.fubon_manager, "connected", True)
    monkeypatch.setattr(providers.fubon_manager, "_ws_mode", "Speed")
    monkeypatch.setattr(providers.fubon_manager, "subscribe_stock", lambda symbol, channel: channels.append((symbol, channel)))

    providers._subscribe_fubon_streams("2330.TW")

    assert channels == [("2330", "trades"), ("2330", "books")]


def test_subscribe_fubon_streams_uses_normal_mode_channels_for_taiwan_stock(monkeypatch):
    channels = []

    monkeypatch.setattr(providers.fubon_manager, "connected", True)
    monkeypatch.setattr(providers.fubon_manager, "_ws_mode", "Normal")
    monkeypatch.setattr(providers.fubon_manager, "subscribe_stock", lambda symbol, channel: channels.append((symbol, channel)))

    providers._subscribe_fubon_streams("2330.TW")

    assert channels == [("2330", "aggregates"), ("2330", "books"), ("2330", "candles")]
