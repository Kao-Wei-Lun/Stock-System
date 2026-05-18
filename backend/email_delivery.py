"""SMTP delivery helpers shared by backend routes and automation scripts."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import os
import smtplib
import socket
import sys


@dataclass(frozen=True)
class SmtpSendResult:
    host: str
    port: int
    ssl: bool
    starttls: bool


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_smtp_config() -> dict[str, object]:
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


def smtp_attempts(config: dict[str, object]) -> list[dict[str, object]]:
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


def socket_probe(host: str, port: int) -> str:
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            return f"socket ok peer={sock.getpeername()}"
    except Exception as exc:  # noqa: BLE001
        return f"socket failed: {type(exc).__name__}: {exc}"


def smtp_failure_message(errors: list[tuple[dict[str, object], BaseException]]) -> str:
    details: list[str] = []
    for config, exc in errors:
        host = str(config["host"])
        port = int(config["port"])
        starttls = bool(config.get("starttls")) and not bool(config.get("ssl"))
        use_ssl = bool(config.get("ssl"))
        details.append(
            f"- host={host}, port={port}, starttls={starttls}, ssl={use_ssl}, "
            f"{socket_probe(host, port)}, error={type(exc).__name__}: {exc}"
        )
    return (
        "SMTP send failed after all attempts.\n"
        f"Python executable: {sys.executable}\n"
        + "\n".join(details)
        + "\nNext steps: if socket failed with WinError 10013, allow this python.exe outbound TCP "
        "in Windows Firewall / endpoint policy, or run the backend report email API from the service process."
    )


def _reject_header_injection(value: str, *, field: str) -> None:
    if "\r" in value or "\n" in value:
        raise ValueError(f"{field} must not contain newline characters")


def build_message(*, sender: str, to: str, subject: str, plain_text: str, html_text: str) -> EmailMessage:
    _reject_header_injection(sender, field="sender")
    _reject_header_injection(to, field="to")
    _reject_header_injection(subject, field="subject")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="quantvision.local")
    msg.set_content(plain_text, subtype="plain", charset="utf-8")
    msg.add_alternative(html_text, subtype="html", charset="utf-8")
    return msg


def send_with_smtp(message: EmailMessage, config: dict[str, object]) -> None:
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


def send_prebuilt_message(message: EmailMessage, config: dict[str, object] | None = None) -> SmtpSendResult:
    smtp_config = config or load_smtp_config()
    errors: list[tuple[dict[str, object], BaseException]] = []
    for attempt in smtp_attempts(smtp_config):
        try:
            send_with_smtp(message, attempt)
            return SmtpSendResult(
                host=str(attempt["host"]),
                port=int(attempt["port"]),
                ssl=bool(attempt.get("ssl")),
                starttls=bool(attempt.get("starttls")) and not bool(attempt.get("ssl")),
            )
        except (OSError, smtplib.SMTPException) as exc:
            errors.append((attempt, exc))
    raise RuntimeError(smtp_failure_message(errors))


def send_email(*, to: str, subject: str, plain_text: str, html_text: str) -> tuple[EmailMessage, SmtpSendResult]:
    config = load_smtp_config()
    message = build_message(
        sender=str(config["sender"]),
        to=to,
        subject=subject,
        plain_text=plain_text,
        html_text=html_text,
    )
    return message, send_prebuilt_message(message, config)
