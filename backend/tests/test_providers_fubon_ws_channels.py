import providers
import pytest


def test_subscribe_fubon_streams_tracks_supported_taiwan_stock(monkeypatch):
    tracked = []

    monkeypatch.setattr(
        providers.fubon_realtime_pool,
        "track_ticker",
        lambda ticker, source="ws": tracked.append((ticker, source)),
    )

    providers._subscribe_fubon_streams("2330.TW")

    assert tracked == [("2330.TW", "ws")]


@pytest.mark.parametrize("ticker", ["*TMFF", "*TXFF"])
def test_subscribe_fubon_streams_tracks_dynamic_futopt_aliases(monkeypatch, ticker):
    tracked = []

    monkeypatch.setattr(
        providers.fubon_realtime_pool,
        "track_ticker",
        lambda tracked_ticker, source="ws": tracked.append((tracked_ticker, source)),
    )

    providers._subscribe_fubon_streams(ticker)

    assert tracked == [(ticker, "ws")]


def test_subscribe_fubon_streams_ignores_unsupported_ticker(monkeypatch):
    tracked = []

    monkeypatch.setattr(
        providers.fubon_realtime_pool,
        "track_ticker",
        lambda ticker, source="ws": tracked.append((ticker, source)),
    )

    providers._subscribe_fubon_streams("AAPL")

    assert tracked == []


def test_unsubscribe_fubon_streams_untracks_ticker(monkeypatch):
    tracked = []

    monkeypatch.setattr(
        providers.fubon_realtime_pool,
        "untrack_ticker",
        lambda ticker, source="ws": tracked.append((ticker, source)),
    )

    providers._unsubscribe_fubon_streams("TXFE6")

    assert tracked == [("TXFE6", "ws")]
