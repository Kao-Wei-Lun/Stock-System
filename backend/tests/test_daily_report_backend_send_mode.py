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


def _complete_report(report_date: str = "2026-05-18") -> str:
    sections = [
        "API/資料池檢查",
        "今日結論",
        "Codex/AI 綜合分析",
        "法人偏多個股與 ETF 分類",
        "強勢股",
        "多頭股",
        "持續沿5日均線上漲的個股",
        "近5日訊號驗證",
        "訊號後績效驗證",
        "可能轉強族群",
        "個股潛伏起漲候選",
        "ETF/基金/REIT 候選",
        "新聞與事件雷達",
        "隔日三情境交易策略",
    ]
    lines = [f"# 台股每日盤後 AI 交易策略報告｜{report_date}", ""]
    for section in sections:
        lines.extend([f"## {section}", "| 欄位 | 值 |", "|---|---|", "| 風險 | 觀察清單，不是買賣建議 |", ""])
    return "\n".join(lines)


def test_report_from_context_preview_preserves_priority_table_after_ai_section(tmp_path, monkeypatch):
    monkeypatch.setattr(report_email, "PROJECT_ROOT", tmp_path)
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    (log_dir / "ai_daily_tw_report_2026-05-18.context-preview.md").write_text(
        "\n".join(
            [
                "# report",
                "",
                "## 1) 今日結論",
                "結論",
                "",
                "## 1A) Codex/AI 綜合分析",
                "舊 AI 內容",
                "",
                "## 1B) 今日優先觀察清單（A/B/C 分級）",
                "| 代號 | 名稱 |",
                "|---|---|",
                "| 2330.TW | 台積電 |",
                "",
                "## 2) 法人偏多候選（依標的類型分類）",
                "法人內容",
            ]
        ),
        encoding="utf-8",
    )
    (log_dir / "codex_ai_analysis_2026-05-18.md").write_text("### 一句話結論\n新 AI 內容", encoding="utf-8")

    report, note = report_email._report_from_context_preview("2026-05-18")

    assert note
    assert "新 AI 內容" in report
    assert "舊 AI 內容" not in report
    assert "## 1B) 今日優先觀察清單" in report
    assert "| 2330.TW | 台積電 |" in report
    assert report.index("## 1A)") < report.index("## 1B)") < report.index("## 2)")


def test_main_backend_send_mode_writes_report_before_calling_api(tmp_path, monkeypatch):
    monkeypatch.setattr(report_email, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(report_email, "check_api", lambda _base: SimpleNamespace(ok=True, error=None))
    monkeypatch.setattr(
        report_email,
        "build_report",
        lambda *, base_url, report_date: _complete_report(report_date),
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


def test_main_backend_send_mode_rejects_incomplete_report_before_api_call(tmp_path, monkeypatch):
    monkeypatch.setattr(report_email, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(report_email, "check_api", lambda _base: SimpleNamespace(ok=True, error=None))
    monkeypatch.setattr(report_email, "build_report", lambda *, base_url, report_date: "# Report\n\n## 今日結論\n缺章節\n")

    def fail_send(**_kwargs):
        raise AssertionError("backend email API should not be called for incomplete reports")

    monkeypatch.setattr(report_email, "_send_via_backend_email_api", fail_send)
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
            "alpha@example.com",
            "--skip-data-ready-wait",
            "--send-mode",
            "backend",
        ],
    )

    try:
        report_email.main()
    except ValueError as exc:
        assert "missing required sections" in str(exc)
    else:
        raise AssertionError("Expected incomplete report validation to fail")
