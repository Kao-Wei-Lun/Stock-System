from __future__ import annotations

from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
for path in (str(PROJECT_ROOT), str(BACKEND_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import email_delivery  # noqa: E402
from routers import reports  # noqa: E402


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(reports.router)
    return TestClient(app)


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


def test_daily_tw_report_email_endpoint_sends_existing_report(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_EMAIL_API_TOKEN", "secret")
    monkeypatch.setenv("REPORT_EMAIL_ALLOWED_TO", "alpha@example.com,beta@example.com")
    monkeypatch.setattr(reports, "PROJECT_ROOT", tmp_path)

    log_dir = tmp_path / "log"
    log_dir.mkdir()
    (log_dir / "ai_daily_tw_report_2026-05-18.md").write_text(_complete_report(), encoding="utf-8")
    (log_dir / "ai_daily_tw_report_2026-05-18.html").write_text(
        '<html><body><table style="border:1px solid #999"><tr><td>Report</td></tr></table></body></html>',
        encoding="utf-8",
    )

    captured: dict[str, str] = {}

    def fake_send_email(*, to: str, subject: str, plain_text: str, html_text: str):
        captured.update({"to": to, "subject": subject, "plain_text": plain_text, "html_text": html_text})
        message = email_delivery.build_message(
            sender="sender@example.com",
            to=to,
            subject=subject,
            plain_text=plain_text,
            html_text=html_text,
        )
        return message, email_delivery.SmtpSendResult(host="smtp.example.com", port=587, ssl=False, starttls=True)

    monkeypatch.setattr(reports.email_delivery, "send_email", fake_send_email)

    response = _client().post(
        "/api/reports/daily-tw/email",
        headers={"X-Report-Email-Token": "secret"},
        json={
            "report_date": "2026-05-18",
            "to": ["alpha@example.com", "beta@example.com"],
            "subject": "台股每日盤後 AI 交易策略報告｜2026-05-18",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "sent"
    assert payload["smtp"] == {"host": "smtp.example.com", "port": 587, "ssl": False, "starttls": True}
    assert captured["to"] == "alpha@example.com,beta@example.com"
    assert "觀察清單，不是買賣建議" in captured["plain_text"]
    assert "border:1px solid" in captured["html_text"]
    assert (log_dir / "ai_daily_tw_report_2026-05-18.eml").exists()


def test_daily_tw_report_email_endpoint_rejects_unallowed_recipient(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_EMAIL_API_TOKEN", "secret")
    monkeypatch.setenv("REPORT_EMAIL_ALLOWED_TO", "alpha@example.com")
    monkeypatch.setattr(reports, "PROJECT_ROOT", tmp_path)

    response = _client().post(
        "/api/reports/daily-tw/email",
        headers={"X-Report-Email-Token": "secret"},
        json={"report_date": "2026-05-18", "to": ["other@example.com"]},
    )

    assert response.status_code == 403
    assert "not allowed" in response.json()["detail"]


def test_daily_tw_report_email_endpoint_reports_missing_files(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_EMAIL_API_TOKEN", "secret")
    monkeypatch.setenv("REPORT_EMAIL_ALLOWED_TO", "alpha@example.com")
    monkeypatch.setattr(reports, "PROJECT_ROOT", tmp_path)

    response = _client().post(
        "/api/reports/daily-tw/email",
        headers={"X-Report-Email-Token": "secret"},
        json={"report_date": "2026-05-18", "to": ["alpha@example.com"]},
    )

    assert response.status_code == 404
    assert "Markdown report not found" in response.json()["detail"]


def test_daily_tw_report_email_endpoint_rejects_incomplete_report(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_EMAIL_API_TOKEN", "secret")
    monkeypatch.setenv("REPORT_EMAIL_ALLOWED_TO", "alpha@example.com")
    monkeypatch.setattr(reports, "PROJECT_ROOT", tmp_path)

    log_dir = tmp_path / "log"
    log_dir.mkdir()
    (log_dir / "ai_daily_tw_report_2026-05-18.md").write_text("# Report\n\n## 今日結論\n缺章節\n", encoding="utf-8")
    (log_dir / "ai_daily_tw_report_2026-05-18.html").write_text("<html><body>Report</body></html>", encoding="utf-8")

    def fail_send_email(**_kwargs):
        raise AssertionError("SMTP should not be called for incomplete reports")

    monkeypatch.setattr(reports.email_delivery, "send_email", fail_send_email)

    response = _client().post(
        "/api/reports/daily-tw/email",
        headers={"X-Report-Email-Token": "secret"},
        json={"report_date": "2026-05-18", "to": ["alpha@example.com"]},
    )

    assert response.status_code == 422
    assert "missing required sections" in response.json()["detail"]
