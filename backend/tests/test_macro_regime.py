"""Unit tests for macro_regime module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from macro_regime import build_macro_summary, build_macro_dashboard_payload


def _item(metric_code, value=None, change_pct=None, **kwargs):
    row = {"metric_code": metric_code, "value": value, "change_pct": change_pct}
    row.update(kwargs)
    return row


class TestBuildMacroSummary:
    def test_empty_items_returns_unknown(self):
        result = build_macro_summary([])
        assert result["overall_risk"] == "unknown"
        assert result["regime"] == "unknown"
        assert result["trade_posture"] == "standby"

    def test_high_vix_triggers_risk(self):
        items = [_item("VIX", value=30)]
        result = build_macro_summary(items)
        assert result["risk_score"] >= 2
        assert any("VIX" in d["label"] for d in result["risk_drivers"])

    def test_low_vix_triggers_tailwind(self):
        items = [_item("VIX", value=14)]
        result = build_macro_summary(items)
        assert result["tailwind_score"] >= 1
        assert any("VIX" in d["label"] for d in result["tailwinds"])

    def test_medium_vix_cautious(self):
        items = [_item("VIX", value=20)]
        result = build_macro_summary(items)
        assert result["risk_score"] >= 1

    def test_high_us10y_cautious(self):
        items = [_item("US10Y", value=5.0)]
        result = build_macro_summary(items)
        assert result["risk_score"] >= 1

    def test_low_us10y_positive(self):
        items = [_item("US10Y", value=3.8)]
        result = build_macro_summary(items)
        assert result["tailwind_score"] >= 1

    def test_dxy_strong_caution(self):
        items = [_item("DXY", change_pct=1.0)]
        result = build_macro_summary(items)
        assert result["risk_score"] >= 1

    def test_dxy_weak_positive(self):
        items = [_item("DXY", change_pct=-0.8)]
        result = build_macro_summary(items)
        assert result["tailwind_score"] >= 1

    def test_sox_weak_risk(self):
        items = [_item("SOX", change_pct=-2.0)]
        result = build_macro_summary(items)
        assert any("費半" in d["label"] for d in result["risk_drivers"])

    def test_sox_strong_positive(self):
        items = [_item("SOX", change_pct=2.0)]
        result = build_macro_summary(items)
        assert any("費半" in d["label"] for d in result["tailwinds"])

    def test_twii_weak_risk(self):
        items = [_item("TWII", change_pct=-1.5)]
        result = build_macro_summary(items)
        assert any("台股" in d["label"] for d in result["risk_drivers"])

    def test_high_risk_scenario(self):
        """Multiple risk signals => defensive posture."""
        items = [
            _item("VIX", value=30),
            _item("US10Y", value=5.0),
            _item("DXY", change_pct=1.0),
            _item("SOX", change_pct=-2.0),
        ]
        result = build_macro_summary(items)
        assert result["overall_risk"] == "high"
        assert result["regime"] == "risk_off"
        assert result["trade_posture"] == "defensive"

    def test_full_tailwind_scenario(self):
        """Multiple positive signals => offensive posture."""
        items = [
            _item("VIX", value=13),
            _item("US10Y", value=3.8),
            _item("DXY", change_pct=-0.8),
            _item("SOX", change_pct=2.0),
            _item("TWII", change_pct=1.0),
        ]
        result = build_macro_summary(items)
        assert result["overall_risk"] == "low"
        assert result["trade_posture"] == "offensive"

    def test_summary_has_required_keys(self):
        items = [_item("VIX", value=18)]
        result = build_macro_summary(items)
        for key in ("overall_risk", "regime", "trade_posture", "decision_hint",
                     "drivers", "risk_drivers", "tailwinds"):
            assert key in result, f"Missing key: {key}"

    def test_drivers_capped_at_6(self):
        items = [
            _item("VIX", value=30),
            _item("US10Y", value=5.0),
            _item("DXY", change_pct=1.0),
            _item("SOX", change_pct=-2.0),
            _item("TWII", change_pct=-1.5),
        ]
        result = build_macro_summary(items)
        assert len(result["drivers"]) <= 6


class TestBuildMacroDashboardPayload:
    def test_empty(self):
        result = build_macro_dashboard_payload([])
        assert result["snapshot_date"] is None
        assert result["summary"]["overall_risk"] == "unknown"

    def test_with_items(self):
        items = [_item("VIX", value=20, date="2026-04-03")]
        result = build_macro_dashboard_payload(items)
        assert result["snapshot_date"] == "2026-04-03"
        assert result["items"] == items
