"""Unit tests for data_fetcher module."""

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import data_fetcher
from data_fetcher import DataFetcher, _date_text_to_iso, normalize_ticker, ticker_candidates


def _row(date_text, close, open_price=None, high=None, low=None, volume=0):
    return {
        "date": date_text,
        "open": close if open_price is None else open_price,
        "high": close if high is None else high,
        "low": close if low is None else low,
        "close": close,
        "volume": volume,
        "adj_close": close,
    }


def test_normalize_ticker_prefers_taiwan_lookup(monkeypatch):
    monkeypatch.setattr(
        data_fetcher,
        "resolve_taiwan_ticker",
        lambda ticker: "2330.TW" if ticker == "2330" else None,
    )

    assert normalize_ticker("2330") == "2330.TW"
    assert normalize_ticker(" aapl ") == "AAPL"


def test_normalize_ticker_preserves_supported_futopt_aliases_and_contracts(monkeypatch):
    monkeypatch.setattr(data_fetcher, "resolve_taiwan_ticker", lambda _ticker: None)

    assert normalize_ticker("txf") == "TXF"
    assert normalize_ticker("mtx") == "MTX"
    assert normalize_ticker("TXFE6") == "TXFE6"
    assert normalize_ticker("MXFJ6") == "MXFJ6"


def test_ticker_candidates_adds_alternate_taiwan_suffix(monkeypatch):
    monkeypatch.setattr(data_fetcher, "resolve_taiwan_ticker", lambda _ticker: None)

    assert ticker_candidates("2330.TW") == ["2330.TW", "2330.TWO"]
    assert ticker_candidates("6510.TWO") == ["6510.TWO", "6510.TW"]


def test_download_sync_daily_gap_uses_finmind_fallback(monkeypatch):
    fetcher = DataFetcher()
    chart = {
        "meta": {
            "longName": "TSMC",
            "shortName": "TSMC",
            "marketCap": 999999,
            "currency": "TWD",
            "exchangeName": "TWSE",
            "exchangeTimezoneName": "Asia/Taipei",
        }
    }
    gap_checks = iter([True, False, False])

    monkeypatch.setattr(fetcher, "_resolve_period_bounds", lambda _period: (1, 2))
    monkeypatch.setattr(fetcher, "_fetch_chart_result", lambda *args, **kwargs: chart)
    monkeypatch.setattr(
        fetcher,
        "_rows_from_chart",
        lambda _chart, _interval: [
            _row("2026-01-01", 100.0, 99.0, 101.0, 98.0, 1000),
            _row("2026-02-20", 120.0, 118.0, 121.0, 117.0, 1500),
        ],
    )
    monkeypatch.setattr(fetcher, "_has_large_daily_gap", lambda *_args, **_kwargs: next(gap_checks))
    monkeypatch.setattr(
        fetcher,
        "_fetch_finmind_daily_rows",
        lambda *_args, **_kwargs: [_row("2026-01-20", 110.0, 109.0, 111.0, 108.0, 900)],
    )
    monkeypatch.setattr(
        fetcher,
        "_fetch_twse_daily_rows",
        lambda *_args, **_kwargs: pytest.fail("TWSE fallback should not be needed once FinMind fills the gap"),
    )
    monkeypatch.setattr(
        fetcher,
        "_fetch_chunked_daily_rows",
        lambda *_args, **_kwargs: pytest.fail("Chunked fallback should not be needed once FinMind fills the gap"),
    )

    rows, info = fetcher._download_sync("2330.TW", period="1y", interval="1d", include_info=True)

    assert [row["date"] for row in rows] == ["2026-01-01", "2026-01-20", "2026-02-20"]
    assert info["longName"] == "TSMC"
    assert info["currency"] == "TWD"


def test_quote_sync_builds_delayed_snapshot(monkeypatch):
    fetcher = DataFetcher()
    quote_time = int(datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc).timestamp())
    chart = {
        "meta": {
            "regularMarketPrice": 210.5,
            "regularMarketOpen": 208.0,
            "regularMarketDayHigh": 212.0,
            "regularMarketDayLow": 207.5,
            "regularMarketVolume": 123456,
            "previousClose": 205.0,
            "regularMarketTime": quote_time,
            "marketCap": 999999999,
            "longName": "Apple Inc.",
            "currency": "USD",
        }
    }
    monkeypatch.setattr(fetcher, "_fetch_chart_result", lambda *args, **kwargs: chart)
    monkeypatch.setattr(
        fetcher,
        "_rows_from_chart",
        lambda _chart, _interval: [
            _row("2026-04-02", 205.0, 203.0, 206.0, 202.0, 100000),
            _row("2026-04-03", 210.0, 208.0, 211.0, 207.0, 123456),
        ],
    )

    quote = fetcher._quote_sync("AAPL")

    assert quote["ticker"] == "AAPL"
    assert quote["price"] == 210.5
    assert quote["change"] == 5.5
    assert quote["change_pct"] == 2.68
    assert quote["quote_type"] == "delayed_snapshot"
    assert quote["is_delayed"] is True
    assert quote["quote_timestamp"] == "2026-04-03T09:00:00+00:00"
    assert quote["name"] == "Apple Inc."


def test_row_from_twse_parses_roc_date_and_numeric_fields():
    fetcher = DataFetcher()

    row = fetcher._row_from_twse(["115/04/03", "1,234", "", "101.5", "103", "100", "102.5"])

    assert row == {
        "date": "2026-04-03",
        "open": 101.5,
        "high": 103.0,
        "low": 100.0,
        "close": 102.5,
        "volume": 1234,
        "adj_close": 102.5,
    }


def test_date_text_to_iso_handles_date_only_and_invalid_values():
    assert _date_text_to_iso("2026-04-03") == "2026-04-03T00:00:00+00:00"
    assert _date_text_to_iso("2026-04-03T09:30:00Z") == "2026-04-03T09:30:00+00:00"
    assert _date_text_to_iso("not-a-date") is None
