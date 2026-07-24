from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for path in (str(PROJECT_ROOT), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from scripts import ai_daily_report_tw as report_tw  # noqa: E402
from scripts import signal_validation  # noqa: E402
from scripts.daily_report import classification, data_assembly, rendering, scoring, validation  # noqa: E402
from scripts.daily_report.delivery import build_delivery_bodies  # noqa: E402


def test_daily_report_modules_do_not_import_facade():
    modules = (classification, data_assembly, rendering, scoring, validation)
    for module in modules:
        source = inspect.getsource(module)
        assert "import ai_daily_report_tw" not in source
        assert "from ai_daily_report_tw" not in source
        assert "from scripts.ai_daily_report_tw" not in source


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        ({"invalidated": True, "ever_broke": True, "latest_close": 90, "breakout_price": 100, "signal_days_5": 3, "breakout_hold_days": 0}, "invalidated"),
        ({"invalidated": False, "ever_broke": True, "latest_close": 99, "breakout_price": 100, "signal_days_5": 2, "breakout_hold_days": 0}, "failed_breakout"),
        ({"invalidated": False, "ever_broke": True, "latest_close": 105, "breakout_price": 100, "signal_days_5": 2, "breakout_hold_days": 2}, "confirmed_uptrend"),
        ({"invalidated": False, "ever_broke": True, "latest_close": 105, "breakout_price": 100, "signal_days_5": 1, "breakout_hold_days": 1}, "new_breakout"),
        ({"invalidated": False, "ever_broke": False, "latest_close": 99, "breakout_price": 100, "signal_days_5": 2, "breakout_hold_days": 0}, "watch_only"),
    ],
)
def test_signal_classification_contract(inputs, expected):
    assert classification.classify_signal(**inputs) == expected
    assert classification.signal_status_label(expected)
    assert classification.signal_observation(expected)


def test_candidate_scoring_preserves_five_components_and_total():
    result = scoring.candidate_score_breakdown(
        close=101,
        breakout_price=100,
        signal_low=95,
        candle={"high": 102, "is_red": True, "is_black": False, "long_upper": False},
        volume_expanded=True,
        volume_ratio=1.8,
        chip={"institutional_5d_sum": 100, "foreign_5d_sum": 50},
        kline_summary="強勢紅K收高",
        validation={"breakout_confirmed": True, "breakout_hold_days": 2},
    )

    assert set(scoring.SCORE_FIELDS).issubset(result)
    assert result["total_score"] == sum(result[field] for field in scoring.SCORE_FIELDS)
    assert result["total_score"] == 100
    unconfirmed = scoring.candidate_score_breakdown(
        close=99,
        breakout_price=100,
        signal_low=95,
        candle={"high": 99.5, "is_red": True, "is_black": False, "long_upper": False},
        volume_expanded=True,
        volume_ratio=1.8,
        chip={"institutional_5d_sum": 100, "foreign_5d_sum": 50},
        kline_summary="強勢紅K收高",
    )
    assert unconfirmed["total_score"] < 100


def test_data_assembly_keeps_required_and_optional_sources_separate():
    requests: list[str] = []

    def fake_http(url: str, **kwargs):
        requests.append(url)
        if "universe/coverage" in url:
            return {"coverage_pct": 100}
        if "history/status" in url:
            return {"items": [{"status": "success"}, {"status": "running"}]}
        if "screener/run" in url:
            setup = kwargs["json_body"]["filters"]["setup_type"]
            if setup == "any":
                raise TimeoutError("optional momentum timed out")
            return {"items": [{"ticker": "2330.TW"}], "market_context": {"regime": "risk_on"}}
        raise ConnectionError("optional provider unavailable")

    assembled = data_assembly.assemble_source_data(
        base_url="http://example.test",
        report_date="2026-07-24",
        http_json=fake_http,
    )

    assert assembled.coverage["coverage_pct"] == 100
    assert assembled.status_counts["running"] == 1
    assert assembled.screener["items"][0]["ticker"] == "2330.TW"
    assert assembled.momentum_candidates_raw == []
    assert assembled.taifex is None
    assert assembled.structured["futures"] == {"items": []}
    assert any("taifex/institutional" in url for url in requests)


def test_rendering_facade_and_delivery_bodies_are_equivalent():
    markdown = "# 測試\n\n- 風險提醒\n\n| 代號 | 狀態 |\n|---|---|\n| 2330.TW | 觀察中 |\n"
    expected_html = rendering.markdown_to_email_html(markdown, title="測試")
    expected_plain = rendering.markdown_to_plain_text(markdown)

    assert report_tw.markdown_to_email_html(markdown, title="測試") == expected_html
    assert report_tw.markdown_to_plain_text(markdown) == expected_plain
    bodies = build_delivery_bodies(markdown, title="測試")
    assert bodies.html_text == expected_html
    assert bodies.plain_text == expected_plain
    assert "風險提醒" in bodies.html_text


def test_structured_signal_json_wins_and_markdown_remains_fallback(tmp_path: Path):
    signal_validation.save_daily_signals(
        tmp_path,
        "2026-07-23",
        [{"ticker": "2330.TW", "signal_date": "2026-07-23", "close": 100}],
        meta={"source": "structured"},
    )
    (tmp_path / "ai_daily_tw_report_2026-07-23.md").write_text(
        "# 報告\n\n## 候選\n| 代號 | 名稱 | 收盤 |\n|---|---|---:|\n| 2317.TW | 鴻海 | 200 |\n",
        encoding="utf-8",
    )
    (tmp_path / "ai_daily_tw_report_2026-07-22.md").write_text(
        "# 報告\n\n## 候選\n| 代號 | 名稱 | 收盤 |\n|---|---|---:|\n| 2454.TW | 聯發科 | 1200 |\n",
        encoding="utf-8",
    )

    payloads = signal_validation.load_signal_payloads(
        tmp_path,
        before_or_on="2026-07-23",
        limit=20,
    )
    by_date = {payload["report_date"]: payload for payload in payloads}
    assert by_date["2026-07-23"]["meta"]["source"] == "structured"
    assert by_date["2026-07-23"]["signals"][0]["ticker"] == "2330.TW"
    assert by_date["2026-07-22"]["meta"]["source"] == "markdown_report"
    assert by_date["2026-07-22"]["signals"][0]["ticker"] == "2454.TW"


def test_signal_backtest_exposes_1_3_5_10_day_validation():
    rows = [
        {"date": f"2026-07-{day:02d}", "open": 100 + day, "high": 101 + day, "low": 99 + day, "close": 100 + day}
        for day in range(1, 13)
    ]
    payloads = [
        {
            "report_date": "2026-07-01",
            "signals": [
                {
                    "ticker": "2330.TW",
                    "signal_date": "2026-07-01",
                    "close": 101,
                    "signal_status": "new_breakout",
                }
            ],
        }
    ]

    backtests = signal_validation.compute_backtests(payloads, lambda _ticker: rows)
    assert backtests[0]["hit_1d"] is True
    assert backtests[0]["hit_3d"] is True
    assert backtests[0]["hit_5d"] is True
    assert backtests[0]["hit_10d"] is True
    summary = signal_validation.summarize_backtests(backtests, today_count=1)
    assert summary["avg_hit_10d"] == 100.0


def test_saved_signal_schema_contains_status_and_score_breakdown(tmp_path: Path):
    signal = {
        "ticker": "2330.TW",
        "signal_date": "2026-07-24",
        "signal_status": "confirmed_uptrend",
        "price_score": 30,
        "breakout_score": 25,
        "volume_score": 20,
        "institutional_score": 15,
        "kline_score": 10,
        "total_score": 100,
    }
    path = signal_validation.save_daily_signals(tmp_path, "2026-07-24", [signal])
    payload = json.loads(path.read_text(encoding="utf-8"))
    saved = payload["signals"][0]

    assert path.name == "signals_2026-07-24.json"
    assert saved["signal_status"] in classification.SIGNAL_STATUS_ORDER
    assert all(field in saved for field in scoring.SCORE_FIELDS)
