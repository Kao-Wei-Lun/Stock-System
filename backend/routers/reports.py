"""Report delivery routes."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

import email_delivery


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LOCAL_CLIENTS = {"127.0.0.1", "::1", "localhost"}

router = APIRouter(prefix="/api/reports", tags=["reports"])


class DailyTwReportEmailPayload(BaseModel):
    report_date: str = Field(..., min_length=10, max_length=10)
    to: list[str] = Field(..., min_length=1)
    subject: str | None = Field(None, max_length=200)


def _split_recipients(value: str) -> list[str]:
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


def _normalize_recipient(value: str) -> str:
    text = value.strip()
    if not text or "@" not in text or "\r" in text or "\n" in text:
        raise HTTPException(status_code=400, detail=f"Invalid recipient: {value!r}")
    return text


def _allowed_recipients() -> set[str]:
    raw = os.environ.get("REPORT_EMAIL_ALLOWED_TO", "").strip()
    if not raw:
        raw = os.environ.get("DAILY_REPORT_EMAIL_TO", "").strip()
    return {recipient.lower() for recipient in _split_recipients(raw)}


def _validate_recipients(recipients: list[str]) -> list[str]:
    normalized = [_normalize_recipient(value) for value in recipients]
    allowed = _allowed_recipients()
    if allowed:
        blocked = [recipient for recipient in normalized if recipient.lower() not in allowed]
        if blocked:
            raise HTTPException(status_code=403, detail=f"Recipients are not allowed: {', '.join(blocked)}")
    return normalized


def _client_is_local(request: Request) -> bool:
    host = (request.client.host if request.client else "").strip().lower()
    return host in LOCAL_CLIENTS or host.startswith("127.")


def _authorize_report_email(request: Request, token_header: str | None) -> None:
    expected_token = os.environ.get("REPORT_EMAIL_API_TOKEN", "").strip()
    if expected_token:
        if token_header != expected_token:
            raise HTTPException(status_code=403, detail="Invalid report email token")
        return
    if not _client_is_local(request):
        raise HTTPException(status_code=403, detail="Report email endpoint only accepts localhost requests")


def _report_paths(report_date: str) -> tuple[Path, Path, Path]:
    if not REPORT_DATE_RE.match(report_date):
        raise HTTPException(status_code=400, detail="report_date must be YYYY-MM-DD")
    log_dir = PROJECT_ROOT / "log"
    return (
        log_dir / f"ai_daily_tw_report_{report_date}.md",
        log_dir / f"ai_daily_tw_report_{report_date}.html",
        log_dir / f"ai_daily_tw_report_{report_date}.eml",
    )


@router.post("/daily-tw/email")
async def send_daily_tw_report_email(
    payload: DailyTwReportEmailPayload,
    request: Request,
    x_report_email_token: str | None = Header(default=None, alias="X-Report-Email-Token"),
):
    _authorize_report_email(request, x_report_email_token)
    recipients = _validate_recipients(payload.to)
    md_path, html_path, eml_path = _report_paths(payload.report_date)
    if not md_path.exists():
        raise HTTPException(status_code=404, detail=f"Markdown report not found: {md_path}")
    if not html_path.exists():
        raise HTTPException(status_code=404, detail=f"HTML report not found: {html_path}")

    markdown_text = md_path.read_text(encoding="utf-8")
    html_text = html_path.read_text(encoding="utf-8")
    subject = payload.subject or f"台股每日盤後 AI 交易策略報告｜{payload.report_date}"
    try:
        message, smtp_result = email_delivery.send_email(
            to=",".join(recipients),
            subject=subject,
            plain_text=markdown_text,
            html_text=html_text,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    eml_path.parent.mkdir(parents=True, exist_ok=True)
    eml_path.write_bytes(bytes(message))
    return {
        "status": "sent",
        "report_date": payload.report_date,
        "to": recipients,
        "subject": subject,
        "markdown_path": str(md_path),
        "html_path": str(html_path),
        "eml_path": str(eml_path),
        "smtp": {
            "host": smtp_result.host,
            "port": smtp_result.port,
            "ssl": smtp_result.ssl,
            "starttls": smtp_result.starttls,
        },
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
