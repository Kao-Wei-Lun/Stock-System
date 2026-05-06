from __future__ import annotations

from datetime import date, timedelta

import pytest

import screener_engine
from screener_engine import ScreenerEngine


def _build_rows(count: int = 60):
    start = date(2026, 1, 1)
    rows = []
    for index in range(count):
        close = 100 + index * 1.5
        rows.append(
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": 1000000 + index * 1000,
            }
        )
    return rows


def _build_flat_rows(count: int = 60, close: float = 100.0):
    start = date(2026, 1, 1)
    return [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 500000,
        }
        for index in range(count)
    ]


def _build_accumulation_rows(count: int = 80):
    start = date(2026, 1, 1)
    rows = []
    for index in range(count):
        if index < count - 20:
            close = 92 + index * 0.12
        else:
            close = 101 + ((index - (count - 20)) % 5) * 0.8
        rows.append(
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "open": close - 0.4,
                "high": close + 1.2,
                "low": close - 1.2,
                "close": close,
                "volume": 700000 + index * 1000,
            }
        )
    return rows


def _build_accumulation_rows_with_bullish_engulfing(count: int = 80):
    rows = _build_accumulation_rows(count)
    rows[-2].update(
        {
            "open": 104.0,
            "high": 104.5,
            "low": 101.5,
            "close": 102.0,
            "volume": 720000,
        }
    )
    rows[-1].update(
        {
            "open": 101.6,
            "high": 106.4,
            "low": 101.0,
            "close": 105.8,
            "volume": 1200000,
        }
    )
    return rows


def _build_chip_snapshots(ticker: str, *, positive: bool = True):
    start = date(2026, 3, 1)
    direction = 1 if positive else -1
    return [
        {
            "id": index + 1,
            "ticker": ticker,
            "snapshot_date": (start + timedelta(days=index)).isoformat(),
            "foreign_net_buy_sell": direction * (10000 + index * 100),
            "investment_trust_net_buy_sell": direction * 2000,
            "dealer_net_buy_sell": -direction * 500,
            "institutional_net_buy_sell": direction * (11500 + index * 100),
            "summary": {"bias": "bullish" if positive else "bearish"},
        }
        for index in range(12)
    ]


@pytest.mark.anyio
async def test_screener_uses_local_macro_context_in_score_adjustment(monkeypatch):
    screener_engine._screen_cache.clear()
    store = {
        "macro": [
            {"metric_code": "VIX", "value": 28.6, "change_pct": 1.1, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "US10Y", "value": 4.58, "change_pct": 0.1, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "DXY", "value": 104.0, "change_pct": 0.81, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "SOX", "value": 4500, "change_pct": -1.8, "date": "2026-04-02", "source": "local_db"},
        ]
    }

    async def list_macro_snapshots(snapshot_date=None):
        return list(store["macro"])

    async def list_screenable_tickers(limit=500):
        return [
            {
                "ticker": "AAPL",
                "name": "Apple",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "close": 210,
                "volume": 2000000,
                "avg_volume": 1000000,
                "quote_change_pct": 2.3,
                "pe_ratio": 18.2,
                "dividend_yield": 0.006,
                "week_52_high": 220,
                "date": "2026-04-02",
                "quote_timestamp": "2026-04-02T09:00:00+00:00",
            }
        ]

    async def get_recent_ohlcv_rows(ticker, limit=260):
        return _build_rows()

    async def list_market_events(ticker=None, date_from=None, date_to=None, limit=5):
        return []

    async def get_taiwan_chip_snapshot(ticker):
        return None

    async def get_institutional_snapshot():
        return None

    monkeypatch.setattr(screener_engine.db, "list_macro_snapshots", list_macro_snapshots)
    monkeypatch.setattr(screener_engine.db, "list_screenable_tickers", list_screenable_tickers)
    monkeypatch.setattr(screener_engine.db, "get_recent_ohlcv_rows", get_recent_ohlcv_rows)
    monkeypatch.setattr(screener_engine.db, "list_market_events", list_market_events)
    monkeypatch.setattr(screener_engine.db, "get_taiwan_chip_snapshot", get_taiwan_chip_snapshot)
    monkeypatch.setattr(screener_engine.db, "get_institutional_snapshot", get_institutional_snapshot)

    engine = ScreenerEngine()
    risk_off_payload = await engine.run({"market": "US", "limit": 10})

    store["macro"] = [
        {"metric_code": "VIX", "value": 14.8, "change_pct": -1.5, "date": "2026-04-03", "source": "local_db"},
        {"metric_code": "US10Y", "value": 4.02, "change_pct": -0.2, "date": "2026-04-03", "source": "local_db"},
        {"metric_code": "DXY", "value": 102.4, "change_pct": -0.61, "date": "2026-04-03", "source": "local_db"},
        {"metric_code": "SOX", "value": 4700, "change_pct": 1.9, "date": "2026-04-03", "source": "local_db"},
        {"metric_code": "TWII", "value": 21200, "change_pct": 0.91, "date": "2026-04-03", "source": "local_db"},
    ]
    trend_payload = await engine.run({"market": "US", "limit": 10})

    assert risk_off_payload["market_context"]["trade_posture"] == "defensive"
    assert risk_off_payload["items"][0]["macro_adjustment"] < 0
    assert risk_off_payload["items"][0]["macro_adjustment_reason"]
    assert risk_off_payload["items"][0]["decision_card"]["verdict"]
    assert risk_off_payload["items"][0]["decision_card"]["summary"]
    assert risk_off_payload["items"][0]["decision_card"]["total_score"] == risk_off_payload["items"][0]["score"]
    assert {section["key"] for section in risk_off_payload["items"][0]["decision_card"]["sections"]} >= {
        "trend",
        "relative_strength",
        "volume",
        "confirmation",
        "event",
        "fundamentals",
        "macro",
    }

    assert trend_payload["market_context"]["trade_posture"] == "offensive"
    assert trend_payload["items"][0]["macro_adjustment"] > 0
    assert trend_payload["items"][0]["score"] > risk_off_payload["items"][0]["score"]
    assert trend_payload["items"][0]["decision_card"]["sections"][-1]["label"] == "市場風險"


@pytest.mark.anyio
async def test_screener_filters_and_sorts_by_setup_quality(monkeypatch):
    screener_engine._screen_cache.clear()

    async def list_macro_snapshots(snapshot_date=None):
        return [
            {"metric_code": "VIX", "value": 14.8, "change_pct": -1.5, "date": "2026-04-03", "source": "local_db"},
            {"metric_code": "US10Y", "value": 4.02, "change_pct": -0.2, "date": "2026-04-03", "source": "local_db"},
            {"metric_code": "DXY", "value": 102.4, "change_pct": -0.61, "date": "2026-04-03", "source": "local_db"},
            {"metric_code": "SOX", "value": 4700, "change_pct": 1.9, "date": "2026-04-03", "source": "local_db"},
        ]

    async def list_screenable_tickers(limit=500):
        return [
            {
                "ticker": "AAPL",
                "name": "Apple",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "close": 210,
                "volume": 2000000,
                "avg_volume": 1000000,
                "quote_change_pct": 2.3,
                "pe_ratio": 18.2,
                "dividend_yield": 0.006,
                "week_52_high": 220,
                "date": "2026-04-03",
                "quote_timestamp": "2026-04-03T09:00:00+00:00",
            },
            {
                "ticker": "MSFT",
                "name": "Microsoft",
                "sector": "Technology",
                "industry": "Software",
                "close": 95,
                "volume": 800000,
                "avg_volume": 1000000,
                "quote_change_pct": -1.1,
                "pe_ratio": 30.1,
                "dividend_yield": 0.009,
                "week_52_high": 130,
                "date": "2026-04-03",
                "quote_timestamp": "2026-04-03T09:00:00+00:00",
            },
        ]

    async def get_recent_ohlcv_rows(ticker, limit=260):
        if ticker == "AAPL":
            return _build_rows()
        return _build_flat_rows(close=95.0)

    async def list_market_events(ticker=None, date_from=None, date_to=None, limit=5):
        return []

    async def get_taiwan_chip_snapshot(ticker):
        return None

    async def get_institutional_snapshot():
        return None

    monkeypatch.setattr(screener_engine.db, "list_macro_snapshots", list_macro_snapshots)
    monkeypatch.setattr(screener_engine.db, "list_screenable_tickers", list_screenable_tickers)
    monkeypatch.setattr(screener_engine.db, "get_recent_ohlcv_rows", get_recent_ohlcv_rows)
    monkeypatch.setattr(screener_engine.db, "list_market_events", list_market_events)
    monkeypatch.setattr(screener_engine.db, "get_taiwan_chip_snapshot", get_taiwan_chip_snapshot)
    monkeypatch.setattr(screener_engine.db, "get_institutional_snapshot", get_institutional_snapshot)

    engine = ScreenerEngine()
    payload = await engine.run({"market": "US", "min_setup_quality": 4, "sort_by": "setup_quality", "limit": 10})

    assert payload["total"] == 1
    assert payload["items"][0]["ticker"] == "AAPL"
    assert payload["items"][0]["setup_quality"] >= 4
    assert payload["items"][0]["decision_card"]["verdict_key"] == "priority"

    wait_payload = await engine.run({"market": "US", "decision_verdict": "wait", "limit": 10})
    assert wait_payload["total"] == 1
    assert wait_payload["items"][0]["ticker"] == "MSFT"
    assert wait_payload["items"][0]["decision_card"]["verdict_key"] == "wait"


@pytest.mark.anyio
async def test_screener_detects_accumulation_setup(monkeypatch):
    screener_engine._screen_cache.clear()

    async def list_macro_snapshots(snapshot_date=None):
        return [
            {"metric_code": "VIX", "value": 15.0, "change_pct": -1.2, "date": "2026-04-03", "source": "local_db"},
            {"metric_code": "SOX", "value": 4700, "change_pct": 1.4, "date": "2026-04-03", "source": "local_db"},
        ]

    async def list_screenable_tickers(limit=500):
        return [
            {
                "ticker": "1234.TW",
                "name": "Accumulation",
                "sector": "Technology",
                "industry": "Hardware",
                "close": 105.8,
                "volume": 720000,
                "avg_volume": 700000,
                "quote_change_pct": 0.4,
                "pe_ratio": 18.2,
                "dividend_yield": 0.01,
                "week_52_high": 130,
                "date": "2026-04-03",
            },
            {
                "ticker": "5678.TW",
                "name": "Overheated",
                "sector": "Technology",
                "industry": "Hardware",
                "close": 210,
                "volume": 2500000,
                "avg_volume": 1000000,
                "quote_change_pct": 5.0,
                "pe_ratio": 18.2,
                "dividend_yield": 0.01,
                "week_52_high": 215,
                "date": "2026-04-03",
            },
        ]

    async def get_recent_ohlcv_rows(ticker, limit=260):
        if ticker == "1234.TW":
            return _build_accumulation_rows_with_bullish_engulfing()
        return _build_rows(80)

    async def list_market_events(ticker=None, date_from=None, date_to=None, limit=5):
        return []

    async def get_taiwan_chip_snapshot(ticker):
        positive = ticker == "1234.TW"
        snapshots = _build_chip_snapshots(ticker, positive=positive)
        latest = snapshots[-1]
        return {**latest, "summary": {"bias": "bullish" if positive else "bearish"}}

    async def list_taiwan_chip_snapshots(ticker, limit=20):
        return _build_chip_snapshots(ticker, positive=ticker == "1234.TW")

    monkeypatch.setattr(screener_engine.db, "list_macro_snapshots", list_macro_snapshots)
    monkeypatch.setattr(screener_engine.db, "list_screenable_tickers", list_screenable_tickers)
    monkeypatch.setattr(screener_engine.db, "get_recent_ohlcv_rows", get_recent_ohlcv_rows)
    monkeypatch.setattr(screener_engine.db, "list_market_events", list_market_events)
    monkeypatch.setattr(screener_engine.db, "get_taiwan_chip_snapshot", get_taiwan_chip_snapshot)
    monkeypatch.setattr(screener_engine.db, "list_taiwan_chip_snapshots", list_taiwan_chip_snapshots)

    engine = ScreenerEngine()
    payload = await engine.run({"market": "TW", "setup_type": "accumulation", "sort_by": "accumulation_score"})

    assert payload["total"] == 1
    assert payload["items"][0]["ticker"] == "1234.TW"
    assert payload["items"][0]["accumulation_score"] >= 58
    assert payload["items"][0]["accumulation_profile"]["qualified"] is True
    assert payload["items"][0]["candlestick_score"] > 0
    assert any(
        pattern["key"] == "bullish_engulfing"
        for pattern in payload["items"][0]["candlestick_profile"]["patterns"]
    )
    assert "accumulation" in {
        section["key"]
        for section in payload["items"][0]["decision_card"]["sections"]
    }
    assert "candlestick" in {
        section["key"]
        for section in payload["items"][0]["decision_card"]["sections"]
    }
