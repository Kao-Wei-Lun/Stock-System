from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for path in (str(PROJECT_ROOT), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from scripts import send_daily_tw_report_email as report_email  # noqa: E402


def test_check_data_readiness_accepts_complete_latest_data(monkeypatch):
    def fake_http_json(url, **_kwargs):
        path = url.replace("http://qv", "")
        if path == "/api/health":
            return {"status": "ok"}
        if path == "/api/tw/universe/coverage?interval=1d":
            return {"newest_latest_date": "2026-05-13"}
        if path == "/api/tw/universe/analysis-coverage?interval=1d":
            return {
                "latest_coverage_pct": 83.5,
                "latest_covered_count": 1670,
                "universe_count": 2000,
            }
        if "status=running" in path or "status=pending" in path:
            return {"items": []}
        if path == "/api/taifex/institutional?date=2026-05-13":
            return {"resolved_date": "2026-05-13"}
        if path == "/api/tw/chips/coverage?date=2026-05-13":
            return {"resolved_date": "2026-05-13"}
        raise AssertionError(path)

    monkeypatch.setattr(report_email, "_http_json", fake_http_json)

    readiness = report_email.check_data_readiness(
        base_url="http://qv",
        report_date="2026-05-13",
        min_stock_kline_ready_pct=80.0,
    )

    assert readiness.ready is True
    assert readiness.expected_date == "2026-05-13"
    assert readiness.stock_kline_ready_pct == 83.5
    assert readiness.reasons == []
    assert readiness.errors == []


def test_check_data_readiness_rejects_stale_or_incomplete_data(monkeypatch):
    def fake_http_json(url, **_kwargs):
        path = url.replace("http://qv", "")
        if path == "/api/health":
            return {"status": "ok"}
        if path == "/api/tw/universe/coverage?interval=1d":
            return {"newest_latest_date": "2026-05-13"}
        if path == "/api/tw/universe/analysis-coverage?interval=1d":
            return {"latest_coverage_pct": 79.9, "latest_covered_count": 1598, "universe_count": 2000}
        if "status=running" in path:
            return {"items": []}
        if "status=pending" in path:
            return {"items": [{"ticker": "2330.TW"}]}
        if path == "/api/taifex/institutional?date=2026-05-13":
            return {"resolved_date": "2026-05-13"}
        if path == "/api/tw/chips/coverage?date=2026-05-13":
            return {"resolved_date": "2026-05-12"}
        raise AssertionError(path)

    monkeypatch.setattr(report_email, "_http_json", fake_http_json)

    readiness = report_email.check_data_readiness(
        base_url="http://qv",
        report_date="2026-05-13",
        min_stock_kline_ready_pct=80.0,
    )

    assert readiness.ready is False
    assert any("pending count is 1" in reason for reason in readiness.reasons)
    assert any("Chip date is 2026-05-12" in reason for reason in readiness.reasons)
    assert any("Analysis stock Kline coverage is 79.90%" in reason for reason in readiness.reasons)


def test_check_data_readiness_uses_direct_analysis_coverage_fallback(monkeypatch):
    def fake_http_json(url, **_kwargs):
        path = url.replace("http://qv", "")
        if path == "/api/health":
            return {"status": "ok"}
        if path == "/api/tw/universe/coverage?interval=1d":
            return {"newest_latest_date": "2026-05-13"}
        if path == "/api/tw/universe/analysis-coverage?interval=1d":
            raise RuntimeError("route still running old SQL")
        if "status=running" in path or "status=pending" in path:
            return {"items": []}
        if path == "/api/taifex/institutional?date=2026-05-13":
            return {"resolved_date": "2026-05-13"}
        if path == "/api/tw/chips/coverage?date=2026-05-13":
            return {"resolved_date": "2026-05-13"}
        raise AssertionError(path)

    monkeypatch.setattr(report_email, "_http_json", fake_http_json)
    monkeypatch.setattr(
        report_email,
        "_fetch_analysis_coverage_direct",
        lambda interval, errors: {
            "latest_coverage_pct": 94.6,
            "latest_covered_count": 1836,
            "universe_count": 1939,
        },
    )

    readiness = report_email.check_data_readiness(
        base_url="http://qv",
        report_date="2026-05-13",
        min_stock_kline_ready_pct=80.0,
    )

    assert readiness.ready is True
    assert readiness.stock_kline_ready_pct == 94.6
    assert readiness.errors == []


def test_wait_for_data_ready_times_out_without_sleeping(monkeypatch):
    readiness = report_email.DataReadiness(
        ready=False,
        timed_out=False,
        expected_date="2026-05-13",
        checked_at="2026-05-13T19:30:00+08:00",
        api_ok=True,
        running_count=0,
        pending_count=0,
        taifex_resolved_date="2026-05-13",
        kline_newest_latest_date="2026-05-12",
        chip_resolved_date="2026-05-13",
        stock_kline_ready_pct=82.0,
        stock_kline_latest_covered_count=1640,
        stock_kline_universe_count=2000,
        reasons=["Kline newest date is 2026-05-12, expected 2026-05-13"],
    )

    monkeypatch.setattr(report_email, "check_data_readiness", lambda **_kwargs: readiness)
    monkeypatch.setattr(report_email.time, "sleep", lambda _seconds: (_ for _ in ()).throw(AssertionError("slept")))

    result = report_email.wait_for_data_ready(
        base_url="http://qv",
        report_date="2026-05-13",
        timeout_minutes=0,
        check_interval_seconds=300,
        min_stock_kline_ready_pct=80.0,
    )

    assert result.timed_out is True
    assert result.ready is False
