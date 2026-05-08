from __future__ import annotations

import argparse
import os
import socket
import smtplib
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from ai_daily_report_tw import (
    _now_tw,
    build_report,
    check_api,
    markdown_to_email_html,
    markdown_to_plain_text,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _smtp_config() -> dict[str, object]:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.environ.get("SMTP_PORT", "587").strip())
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = "".join(os.environ.get("SMTP_PASSWORD", "").split())
    sender = os.environ.get("SMTP_FROM", username).strip()
    starttls = _bool_env("SMTP_STARTTLS", True)
    ssl = _bool_env("SMTP_SSL", False)
    if not username:
        raise RuntimeError("Missing SMTP_USERNAME in .env")
    if not password:
        raise RuntimeError("Missing SMTP_PASSWORD in .env")
    if not sender:
        raise RuntimeError("Missing SMTP_FROM in .env")
    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "sender": sender,
        "starttls": starttls,
        "ssl": ssl,
    }


def _smtp_attempts(config: dict[str, object]) -> list[dict[str, object]]:
    host = str(config["host"])
    primary = dict(config)
    attempts = [primary]
    fallback_ports = os.environ.get("SMTP_FALLBACK_PORTS", "").strip()
    if fallback_ports:
        for raw_port in fallback_ports.split(","):
            raw_port = raw_port.strip()
            if not raw_port:
                continue
            port = int(raw_port)
            attempts.append({**config, "port": port, "starttls": port == 587, "ssl": port == 465})
    elif host.lower() == "smtp.gmail.com":
        attempts.append({**config, "port": 465, "starttls": False, "ssl": True})
        attempts.append({**config, "port": 587, "starttls": True, "ssl": False})

    deduped: list[dict[str, object]] = []
    seen: set[tuple[str, int, bool, bool]] = set()
    for attempt in attempts:
        key = (
            str(attempt["host"]),
            int(attempt["port"]),
            bool(attempt.get("starttls")),
            bool(attempt.get("ssl")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(attempt)
    return deduped


def _socket_probe(host: str, port: int) -> str:
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            return f"socket ok peer={sock.getpeername()}"
    except Exception as exc:  # noqa: BLE001
        return f"socket failed: {type(exc).__name__}: {exc}"


def _send_with_smtp(message: EmailMessage, config: dict[str, object]) -> None:
    host = str(config["host"])
    port = int(config["port"])
    username = str(config["username"])
    password = str(config["password"])
    use_ssl = bool(config.get("ssl"))
    use_starttls = bool(config.get("starttls")) and not use_ssl

    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_cls(host, port, timeout=60) as smtp:
        smtp.ehlo()
        if use_starttls:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(username, password)
        smtp.send_message(message)


def _smtp_failure_message(errors: list[tuple[dict[str, object], BaseException]]) -> str:
    details: list[str] = []
    for config, exc in errors:
        host = str(config["host"])
        port = int(config["port"])
        starttls = bool(config.get("starttls")) and not bool(config.get("ssl"))
        use_ssl = bool(config.get("ssl"))
        details.append(
            f"- host={host}, port={port}, starttls={starttls}, ssl={use_ssl}, "
            f"{_socket_probe(host, port)}, error={type(exc).__name__}: {exc}"
        )
    return (
        "SMTP send failed after all attempts.\n"
        f"Python executable: {sys.executable}\n"
        + "\n".join(details)
        + "\nNext steps: if socket failed with WinError 10013, allow this python.exe outbound TCP "
        "in Windows Firewall / endpoint policy, or run the Windows Scheduled Task created for this project."
    )


def _build_message(*, sender: str, to: str, subject: str, plain_text: str, html_text: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="quantvision.local")
    msg.set_content(plain_text, subtype="plain", charset="utf-8")
    msg.add_alternative(html_text, subtype="html", charset="utf-8")
    return msg


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    _load_dotenv(PROJECT_ROOT / ".env")

    parser = argparse.ArgumentParser(description="Generate and email the TW daily AI strategy report")
    parser.add_argument("--base", default=os.environ.get("QV_API_BASE", "http://localhost:8001").rstrip("/"))
    parser.add_argument("--date", default=_now_tw().strftime("%Y-%m-%d"))
    parser.add_argument("--out", default="")
    parser.add_argument("--html-out", default="")
    parser.add_argument("--eml-out", default="")
    parser.add_argument("--to", default=os.environ.get("DAILY_REPORT_EMAIL_TO", "").strip())
    parser.add_argument("--subject", default="")
    parser.add_argument("--dry-run", action="store_true", help="Write .eml if requested but do not send")
    args = parser.parse_args()

    report_date = args.date
    md_path = Path(args.out) if args.out else PROJECT_ROOT / "log" / f"ai_daily_tw_report_{report_date}.md"
    html_path = Path(args.html_out) if args.html_out else PROJECT_ROOT / "log" / f"ai_daily_tw_report_{report_date}.html"
    eml_path = Path(args.eml_out) if args.eml_out else PROJECT_ROOT / "log" / f"ai_daily_tw_report_{report_date}.eml"
    if not md_path.is_absolute():
        md_path = PROJECT_ROOT / md_path
    if not html_path.is_absolute():
        html_path = PROJECT_ROOT / html_path
    if not eml_path.is_absolute():
        eml_path = PROJECT_ROOT / eml_path

    api = check_api(args.base)
    if not api.ok:
        report = (
            f"# 每日盤後 AI 交易策略報告（台股）｜{report_date}\n\n"
            "## API 連線失敗\n"
            f"- API Base: {args.base}\n"
            f"- 錯誤：{api.error}\n"
        )
    else:
        report = build_report(base_url=args.base, report_date=report_date)

    html_text = markdown_to_email_html(report, title=f"每日盤後 AI 交易策略報告｜{report_date}")
    plain_text = markdown_to_plain_text(report)
    _write_text(md_path, report)
    _write_text(html_path, html_text)

    subject = args.subject or f"台股每日盤後 AI 交易策略報告｜{report_date}"
    to = args.to
    if not to:
        raise RuntimeError("Missing recipient. Set DAILY_REPORT_EMAIL_TO or pass --to.")

    if args.dry_run:
        sender = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USERNAME") or "dry-run@quantvision.local"
        message = _build_message(sender=sender, to=to, subject=subject, plain_text=plain_text, html_text=html_text)
        eml_path.parent.mkdir(parents=True, exist_ok=True)
        eml_path.write_bytes(bytes(message))
        print(f"Dry-run EML written to: {eml_path}")
        print(f"Markdown written to: {md_path}")
        print(f"HTML written to: {html_path}")
        return 0

    config = _smtp_config()
    message = _build_message(
        sender=str(config["sender"]),
        to=to,
        subject=subject,
        plain_text=plain_text,
        html_text=html_text,
    )
    if args.eml_out:
        eml_path.parent.mkdir(parents=True, exist_ok=True)
        eml_path.write_bytes(bytes(message))

    errors: list[tuple[dict[str, object], BaseException]] = []
    sent_config: dict[str, object] | None = None
    for attempt in _smtp_attempts(config):
        try:
            _send_with_smtp(message, attempt)
            sent_config = attempt
            break
        except (OSError, smtplib.SMTPException) as exc:
            errors.append((attempt, exc))
    if sent_config is None:
        raise RuntimeError(_smtp_failure_message(errors))

    print(f"Email sent to: {to}")
    print(
        "SMTP used: "
        f"{sent_config['host']}:{sent_config['port']} "
        f"ssl={bool(sent_config.get('ssl'))} starttls={bool(sent_config.get('starttls')) and not bool(sent_config.get('ssl'))}"
    )
    print(f"Markdown written to: {md_path}")
    print(f"HTML written to: {html_path}")
    if args.eml_out:
        print(f"EML written to: {eml_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
