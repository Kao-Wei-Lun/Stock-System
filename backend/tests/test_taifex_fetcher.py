"""Unit tests for taifex_fetcher module."""

from datetime import date
from pathlib import Path
import sys

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import taifex_fetcher
from taifex_fetcher import TaifexFetcher, _safe_int


class _MockResponse:
    def __init__(self, status_code=200, headers=None, payload=None):
        self.status_code = status_code
        self.headers = headers or {"content-type": "application/json"}
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_fetch_dashboard_uses_exact_snapshot_from_db(monkeypatch):
    fetcher = TaifexFetcher()
    snapshot = {
        "query_date": "2026-04-03",
        "resolved_date": "2026-04-03",
        "overview": [],
        "futures": [],
        "options": [],
        "call_puts": [],
        "cash_summary": [],
        "leaderboards": {},
        "cost_estimates": {},
    }

    async def get_exact(target_date):
        assert target_date == date(2026, 4, 3)
        return snapshot

    async def unexpected(*_args, **_kwargs):
        pytest.fail("network/db fallback should not be needed when exact snapshot exists")

    monkeypatch.setattr(taifex_fetcher.db, "get_institutional_snapshot_exact", get_exact)
    monkeypatch.setattr(taifex_fetcher.db, "get_institutional_snapshot", unexpected)
    monkeypatch.setattr(fetcher, "_fetch_and_store_dashboard", unexpected)

    result = await fetcher.fetch_dashboard(date(2026, 4, 3))

    assert result == snapshot
    assert "2026-04-03" in fetcher._dashboard_cache


def test_fetch_twse_cash_summary_uses_finmind_when_primary_unavailable(monkeypatch):
    fetcher = TaifexFetcher()
    fallback_rows = [
        {"institution": "外資", "buy_amount": 100, "sell_amount": 60, "net_amount": 40},
    ]
    fallback_meta = {"source": "finmind", "warning": "fallback"}

    monkeypatch.setattr(
        taifex_fetcher.requests,
        "get",
        lambda *args, **kwargs: _MockResponse(status_code=503, headers={"content-type": "text/html"}),
    )
    monkeypatch.setattr(fetcher, "_fetch_finmind_cash_summary", lambda _target_date: (fallback_rows, fallback_meta))

    rows, meta = fetcher._fetch_twse_cash_summary(date(2026, 4, 3))

    assert rows == fallback_rows
    assert meta == fallback_meta


def test_fallback_cash_summary_prefers_last_known_snapshot():
    fetcher = TaifexFetcher()
    fetcher._latest_cash_summary_snapshot = (
        "2026-04-02",
        [{"institution": "外資", "buy_amount": 100, "sell_amount": 50, "net_amount": 50}],
    )

    rows, meta = fetcher._fallback_cash_summary("2026-04-03", "TWSE 主來源不可用")

    assert rows[0]["institution"] == "外資"
    assert meta["source"] == "twse-last-known"
    assert "2026-04-02" in meta["warning"]


def test_build_cost_estimates_summarizes_institution_and_retail_bias():
    fetcher = TaifexFetcher()
    futures_rows = [
        {
            "commodity": "臺股期貨",
            "institution": "外資",
            "oi_long_amount": 1000,
            "oi_long_volume": 5,
            "oi_short_amount": 0,
            "oi_short_volume": 0,
            "oi_net_volume": 5,
        },
        {
            "commodity": "臺股期貨",
            "institution": "投信",
            "oi_long_amount": 0,
            "oi_long_volume": 0,
            "oi_short_amount": 760,
            "oi_short_volume": 4,
            "oi_net_volume": -4,
        },
        {
            "commodity": "臺股期貨",
            "institution": "自營商",
            "oi_long_amount": 450,
            "oi_long_volume": 3,
            "oi_short_amount": 0,
            "oi_short_volume": 0,
            "oi_net_volume": 3,
        },
    ]
    call_put_rows = [
        {
            "commodity": "臺指選擇權",
            "institution": "外資",
            "option_side": "買權",
            "oi_net_volume": 120,
            "oi_buy_amount": 600,
            "oi_buy_volume": 120,
        },
        {
            "commodity": "臺指選擇權",
            "institution": "外資",
            "option_side": "賣權",
            "oi_net_volume": 30,
            "oi_buy_amount": 150,
            "oi_buy_volume": 30,
        },
    ]

    result = fetcher._build_cost_estimates("臺股期貨", "臺指選擇權", futures_rows, call_put_rows)

    assert result["futures"]["band_low"] == 750.0
    assert result["futures"]["band_high"] == 1000.0
    assert result["futures"]["institution_estimate"]["side"] == "多"
    assert result["futures"]["retail_estimate"]["side"] == "空"
    assert result["options"]["institutions"][0]["balance"] == 90


def test_build_history_from_snapshots_aggregates_series():
    fetcher = TaifexFetcher()
    snapshots = [
        {
            "resolved_date": "2026-04-03",
            "futures": [
                {"commodity": "臺股期貨", "institution": "外資", "oi_net_volume": 5, "trade_net_volume": 3},
                {"commodity": "臺股期貨", "institution": "投信", "oi_net_volume": -2, "trade_net_volume": -1},
                {"commodity": "臺股期貨", "institution": "自營商", "oi_net_volume": 1, "trade_net_volume": 2},
            ],
            "call_puts": [
                {"commodity": "臺指選擇權", "institution": "外資", "option_side": "買權", "oi_net_volume": 70},
                {"commodity": "臺指選擇權", "institution": "外資", "option_side": "賣權", "oi_net_volume": 10},
                {"commodity": "臺指選擇權", "institution": "投信", "option_side": "買權", "oi_net_volume": 5},
                {"commodity": "臺指選擇權", "institution": "投信", "option_side": "賣權", "oi_net_volume": 15},
            ],
            "cash_summary": [
                {"institution": "外資及陸資(不含外資自營商)", "net_amount": 100},
                {"institution": "投信", "net_amount": 20},
                {"institution": "自營商", "net_amount": -10},
            ],
        }
    ]
    monkeypatch_payload = {
        "futures": {
            "institution_estimate": {"price": 1010.0},
            "retail_estimate": {"price": 995.0},
            "band_low": 980.0,
            "band_high": 1020.0,
        }
    }

    fetcher._build_cost_estimates = lambda *args, **kwargs: monkeypatch_payload

    result = fetcher._build_history_from_snapshots(snapshots, "臺股期貨", "臺指選擇權")

    assert result["futures_oi"][0]["外資"] == 5
    assert result["futures_oi"][0]["合計"] == 4
    assert result["call_put_balance"][0]["外資"] == 60
    assert result["cash_net"][0]["自營商"] == -10
    assert result["cost_band"][0]["法人合成"] == 1010.0


def test_safe_int_handles_empty_numeric_values():
    assert _safe_int("1,234") == 1234
    assert _safe_int("nan") == 0
    assert _safe_int(None) == 0
