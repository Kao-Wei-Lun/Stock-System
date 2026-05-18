from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for path in (str(PROJECT_ROOT), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from scripts import send_daily_tw_report_email as report_email  # noqa: E402


def test_main_backend_send_mode_writes_report_before_calling_api(tmp_path, monkeypatch):
    monkeypatch.setattr(report_email, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(report_email, "check_api", lambda _base: SimpleNamespace(ok=True, error=None))
    monkeypatch.setattr(
        report_email,
        "build_report",
        lambda *, base_url, report_date: f"# 每日盤後 AI 交易策略報告（台股）｜{report_date}\n\n| 欄位 | 值 |\n|---|---|\n| 風險 | 觀察清單，不是買賣建議 |\n",
    )
    monkeypatch.setattr(
        report_email,
        "_smtp_config",
        lambda: (_ for _ in ()).throw(AssertionError("direct SMTP should not run in backend mode")),
    )

    calls: list[dict[str, str]] = []

    def fake_send_via_backend_email_api(*, base_url: str, report_date: str, to: str, subject: str):
        md_path = tmp_path / "log" / f"ai_daily_tw_report_{report_date}.md"
        html_path = tmp_path / "log" / f"ai_daily_tw_report_{report_date}.html"
        assert md_path.exists()
        assert html_path.exists()
        calls.append({"base_url": base_url, "report_date": report_date, "to": to, "subject": subject})
        return {
            "status": "sent",
            "eml_path": str(tmp_path / "log" / f"ai_daily_tw_report_{report_date}.eml"),
            "smtp": {"host": "smtp.example.com", "port": 587, "ssl": False, "starttls": True},
        }

    monkeypatch.setattr(report_email, "_send_via_backend_email_api", fake_send_via_backend_email_api)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "send_daily_tw_report_email.py",
            "--date",
            "2026-05-18",
            "--base",
            "http://localhost:8001",
            "--to",
            "alpha@example.com,beta@example.com",
            "--out",
            "log/ai_daily_tw_report_2026-05-18.md",
            "--html-out",
            "log/ai_daily_tw_report_2026-05-18.html",
            "--eml-out",
            "log/ai_daily_tw_report_2026-05-18.eml",
            "--skip-data-ready-wait",
            "--send-mode",
            "backend",
        ],
    )

    assert report_email.main() == 0
    assert calls == [
        {
            "base_url": "http://localhost:8001",
            "report_date": "2026-05-18",
            "to": "alpha@example.com,beta@example.com",
            "subject": "台股每日盤後 AI 交易策略報告｜2026-05-18",
        }
    ]
