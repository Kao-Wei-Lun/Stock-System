from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import os
import re
import socket
import smtplib
import sys
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from ai_daily_report_tw import (
    _http_json,
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


def _float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


@dataclass
class DataReadiness:
    ready: bool
    timed_out: bool
    expected_date: str
    checked_at: str
    api_ok: bool
    running_count: int | None
    pending_count: int | None
    taifex_resolved_date: str | None
    kline_newest_latest_date: str | None
    chip_resolved_date: str | None
    stock_kline_ready_pct: float
    stock_kline_latest_covered_count: int
    stock_kline_universe_count: int
    reasons: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"ready={self.ready} expected={self.expected_date} api_ok={self.api_ok} "
            f"kline={self.kline_newest_latest_date} chip={self.chip_resolved_date} "
            f"taifex={self.taifex_resolved_date} running={self.running_count} "
            f"pending={self.pending_count} stock_kline={self.stock_kline_ready_pct:.2f}%"
        )


def _expected_latest_date(report_date: str) -> str:
    current = datetime.strptime(report_date, "%Y-%m-%d").date()
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current.isoformat()


def _items_count(payload: object) -> int | None:
    if not isinstance(payload, dict):
        return None
    items = payload.get("items")
    if isinstance(items, list):
        return len(items)
    total = payload.get("count")
    try:
        return int(total)
    except (TypeError, ValueError):
        return None


def _as_date_text(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.match(r"^\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else text


def _as_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _fetch_json(base_url: str, path: str, errors: list[str]) -> object | None:
    try:
        return _http_json(f"{base_url}{path}", timeout=30)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{path}: {type(exc).__name__}: {exc}")
        return None


def _fetch_analysis_coverage_direct(interval: str, errors: list[str]) -> object | None:
    """Fallback used when a stale running API still has a broken readiness route."""
    backend_dir = PROJECT_ROOT / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    async def _load() -> object:
        from database import db  # Imported lazily so regular report rendering stays light.

        await db.connect()
        try:
            return await db.get_tw_analysis_kline_coverage(interval)
        finally:
            await db.close()

    try:
        return asyncio.run(_load())
    except Exception as exc:  # noqa: BLE001
        errors.append(f"direct analysis coverage fallback: {type(exc).__name__}: {exc}")
        return None


def check_data_readiness(
    *,
    base_url: str,
    report_date: str,
    min_stock_kline_ready_pct: float,
) -> DataReadiness:
    base = base_url.rstrip("/")
    expected_date = _expected_latest_date(report_date)
    checked_at = _now_tw().isoformat()
    errors: list[str] = []
    reasons: list[str] = []

    health = _fetch_json(base, "/api/health", errors)
    coverage = _fetch_json(base, "/api/tw/universe/coverage?interval=1d", errors)
    analysis_errors: list[str] = []
    analysis_coverage = _fetch_json(base, "/api/tw/universe/analysis-coverage?interval=1d", analysis_errors)
    if not isinstance(analysis_coverage, dict):
        analysis_coverage = _fetch_analysis_coverage_direct("1d", analysis_errors)
    if not isinstance(analysis_coverage, dict):
        errors.extend(analysis_errors)
    running = _fetch_json(base, "/api/tw/history/status?interval=1d&status=running&limit=5000", errors)
    pending = _fetch_json(base, "/api/tw/history/status?interval=1d&status=pending&limit=5000", errors)
    taifex = _fetch_json(base, f"/api/taifex/institutional?date={expected_date}", errors)
    chips = _fetch_json(base, f"/api/tw/chips/coverage?date={expected_date}", errors)

    api_ok = isinstance(health, dict) and str(health.get("status") or "").lower() == "ok"
    running_count = _items_count(running)
    pending_count = _items_count(pending)
    kline_newest = _as_date_text((coverage or {}).get("newest_latest_date") if isinstance(coverage, dict) else None)
    taifex_date = _as_date_text((taifex or {}).get("resolved_date") if isinstance(taifex, dict) else None)
    chip_raw_date = None
    if isinstance(chips, dict):
        chip_raw_date = chips.get("resolved_date") or chips.get("latest_date")
    chip_date = _as_date_text(chip_raw_date)
    stock_pct = 0.0
    stock_latest_count = 0
    stock_universe_count = 0
    if isinstance(analysis_coverage, dict):
        stock_pct = _as_float(analysis_coverage.get("latest_coverage_pct") or analysis_coverage.get("coverage_pct"))
        stock_latest_count = _as_int(
            analysis_coverage.get("latest_covered_count") or analysis_coverage.get("covered_count")
        )
        stock_universe_count = _as_int(analysis_coverage.get("universe_count"))

    if not api_ok:
        reasons.append("API health is not ok")
    if running_count != 0:
        reasons.append(f"running count is {running_count}")
    if pending_count != 0:
        reasons.append(f"pending count is {pending_count}")
    if taifex_date != expected_date:
        reasons.append(f"TAIFEX date is {taifex_date}, expected {expected_date}")
    if kline_newest != expected_date:
        reasons.append(f"Kline newest date is {kline_newest}, expected {expected_date}")
    if chip_date != expected_date:
        reasons.append(f"Chip date is {chip_date}, expected {expected_date}")
    if stock_pct < min_stock_kline_ready_pct:
        reasons.append(f"Analysis stock Kline coverage is {stock_pct:.2f}%, expected >= {min_stock_kline_ready_pct:.2f}%")

    return DataReadiness(
        ready=not reasons and not errors,
        timed_out=False,
        expected_date=expected_date,
        checked_at=checked_at,
        api_ok=api_ok,
        running_count=running_count,
        pending_count=pending_count,
        taifex_resolved_date=taifex_date,
        kline_newest_latest_date=kline_newest,
        chip_resolved_date=chip_date,
        stock_kline_ready_pct=stock_pct,
        stock_kline_latest_covered_count=stock_latest_count,
        stock_kline_universe_count=stock_universe_count,
        reasons=reasons,
        errors=errors,
    )


def wait_for_data_ready(
    *,
    base_url: str,
    report_date: str,
    timeout_minutes: float,
    check_interval_seconds: float,
    min_stock_kline_ready_pct: float,
) -> DataReadiness:
    deadline = time.monotonic() + max(0.0, timeout_minutes) * 60.0
    interval = max(1.0, check_interval_seconds)

    while True:
        readiness = check_data_readiness(
            base_url=base_url,
            report_date=report_date,
            min_stock_kline_ready_pct=min_stock_kline_ready_pct,
        )
        print(f"Data readiness check: {readiness.summary()}")
        if readiness.ready:
            print("Data readiness satisfied; generating report.")
            return readiness

        if readiness.reasons:
            print("Not ready: " + "; ".join(readiness.reasons))
        if readiness.errors:
            print("Readiness check errors: " + "; ".join(readiness.errors))

        remaining = deadline - time.monotonic()
        if timeout_minutes <= 0 or remaining <= 0:
            print("Data readiness wait timed out; generating report with available data.")
            return replace(readiness, timed_out=True)

        sleep_seconds = min(interval, max(1.0, remaining))
        print(f"Waiting {sleep_seconds:.0f}s before next readiness check.")
        time.sleep(sleep_seconds)


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
    parser.add_argument(
        "--context-only",
        action="store_true",
        help="Build the report context JSON/preview files and exit without requiring recipients or SMTP",
    )
    parser.add_argument(
        "--wait-for-data-ready",
        dest="wait_for_data_ready",
        action="store_true",
        default=_bool_env("DAILY_REPORT_WAIT_FOR_DATA_READY", True),
        help="Poll market-data readiness before generating the report",
    )
    parser.add_argument(
        "--skip-data-ready-wait",
        dest="wait_for_data_ready",
        action="store_false",
        help="Generate immediately without readiness polling",
    )
    parser.add_argument(
        "--data-ready-timeout-minutes",
        type=float,
        default=_float_env("DAILY_REPORT_DATA_READY_TIMEOUT_MINUTES", 180.0),
    )
    parser.add_argument(
        "--data-ready-check-interval-seconds",
        type=float,
        default=_float_env("DAILY_REPORT_DATA_READY_CHECK_INTERVAL_SECONDS", 300.0),
    )
    parser.add_argument(
        "--min-stock-kline-ready-pct",
        type=float,
        default=_float_env("DAILY_REPORT_MIN_STOCK_KLINE_READY_PCT", 80.0),
    )
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

    if args.wait_for_data_ready:
        wait_for_data_ready(
            base_url=args.base,
            report_date=report_date,
            timeout_minutes=args.data_ready_timeout_minutes,
            check_interval_seconds=args.data_ready_check_interval_seconds,
            min_stock_kline_ready_pct=args.min_stock_kline_ready_pct,
        )

    if args.context_only:
        os.environ["DAILY_REPORT_AI_ANALYSIS_ENABLED"] = "false"

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

    if args.context_only:
        print(f"Context-only preview written to: {md_path}")
        print(f"HTML preview written to: {html_path}")
        print(f"Codex context should be available at: {PROJECT_ROOT / 'log' / f'codex_report_context_{report_date}.json'}")
        print(f"Codex analysis target path: {PROJECT_ROOT / 'log' / f'codex_ai_analysis_{report_date}.md'}")
        return 0

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
