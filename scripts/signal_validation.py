from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable


SIGNAL_FILE_RE = re.compile(r"^signals_(\d{4}-\d{2}-\d{2})\.json$")
REPORT_FILE_RE = re.compile(r"^ai_daily_tw_report_(\d{4}-\d{2}-\d{2})\.md$")


def parse_date(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()[:10]
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None
    return text


def to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _clean_price(value: object) -> float | None:
    text = str(value or "").strip()
    if not text or text == "—":
        return None
    text = text.replace(",", "")
    match = re.search(r"-?[0-9]+(?:\.[0-9]+)?", text)
    return to_float(match.group(0)) if match else None


def _split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_markdown_table_separator(line: str) -> bool:
    cells = _split_markdown_table_row(line)
    if not cells:
        return False
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) is not None for cell in cells)


def _price_after_patterns(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = _clean_price(match.group(1))
            if value is not None and value > 0:
                return value
    return None


def signal_file_path(log_dir: Path, report_date: str) -> Path:
    return log_dir / f"signals_{report_date}.json"


def _clean_signal(signal: dict) -> dict:
    numeric_keys = [
        "close",
        "breakout_price",
        "signal_low",
        "ma20",
        "price_score",
        "breakout_score",
        "volume_score",
        "institutional_score",
        "kline_score",
        "total_score",
    ]
    row = dict(signal)
    row["ticker"] = str(row.get("ticker") or "").upper().strip()
    row["name"] = str(row.get("name") or "")
    row["sector"] = str(row.get("sector") or "")
    row["signal_date"] = parse_date(row.get("signal_date")) or ""
    for key in numeric_keys:
        value = to_float(row.get(key))
        row[key] = value
    return row


def save_daily_signals(
    log_dir: Path,
    report_date: str,
    signals: list[dict],
    *,
    meta: dict | None = None,
) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    clean_signals = [_clean_signal(signal) for signal in signals if signal.get("ticker")]
    payload = {
        "schema_version": 1,
        "report_date": report_date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(clean_signals),
        "meta": meta or {},
        "signals": clean_signals,
    }
    path = signal_file_path(log_dir, report_date)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_signal_json_payloads(log_dir: Path, *, before_or_on: str | None = None, limit: int = 20) -> dict[str, dict]:
    cutoff = parse_date(before_or_on) if before_or_on else None
    payloads: list[tuple[str, dict]] = []
    if not log_dir.exists():
        return {}
    for path in log_dir.glob("signals_*.json"):
        match = SIGNAL_FILE_RE.match(path.name)
        if not match:
            continue
        file_date = match.group(1)
        if cutoff and file_date > cutoff:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            payloads.append((file_date, payload))
    payloads.sort(key=lambda item: item[0])
    return {file_date: payload for file_date, payload in payloads[-limit:]}


def parse_report_signals(path: Path) -> dict:
    match = REPORT_FILE_RE.match(path.name)
    if not match:
        return {}
    signal_date = match.group(1)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8-sig", errors="replace")

    records: list[dict] = []
    lines = text.splitlines()
    section = ""
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            section = heading.group(2)
            i += 1
            continue
        if (
            not stripped.startswith("|")
            or i + 1 >= len(lines)
            or not _is_markdown_table_separator(lines[i + 1])
        ):
            i += 1
            continue

        headers = _split_markdown_table_row(lines[i])
        header_index = {header: index for index, header in enumerate(headers)}
        if "代號" not in header_index or "訊號驗證" in section or "新聞" in section:
            i += 1
            continue

        j = i + 2
        while j < len(lines) and lines[j].strip().startswith("|"):
            cells = _split_markdown_table_row(lines[j])
            padded = cells + [""] * max(0, len(headers) - len(cells))

            def pick(*names: str) -> str:
                for name in names:
                    index = header_index.get(name)
                    if index is not None and index < len(padded):
                        return padded[index]
                return ""

            ticker = pick("代號").upper().strip()
            if not re.fullmatch(r"[0-9A-Z]{4,8}\.(?:TW|TWO)|IX[0-9A-Z]+\.(?:TW|TWO)|A[0-9A-Z]+\.(?:TW|TWO)", ticker):
                j += 1
                continue
            action_text = "；".join(padded)
            records.append(
                {
                    "ticker": ticker,
                    "name": pick("名稱"),
                    "sector": pick("族群/產業", "產業"),
                    "signal_date": signal_date,
                    "close": _clean_price(pick("收盤", "最新收盤價")),
                    "breakout_price": _clean_price(pick("突破確認價"))
                    or _price_after_patterns(action_text, [r"突破\s*([0-9][0-9,]*(?:\.[0-9]+)?)"]),
                    "signal_low": _price_after_patterns(
                        action_text,
                        [r"前低\s*([0-9][0-9,]*(?:\.[0-9]+)?)", r"跌破(?:MA5\s*)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)"],
                    ),
                    "source": "report",
                }
            )
            j += 1
        i = j

    return {
        "schema_version": 0,
        "report_date": signal_date,
        "count": len(records),
        "meta": {"source": "markdown_report"},
        "signals": records,
    }


def load_report_payloads(log_dir: Path, *, before_or_on: str | None = None, limit: int = 20) -> dict[str, dict]:
    cutoff = parse_date(before_or_on) if before_or_on else None
    payloads: list[tuple[str, dict]] = []
    if not log_dir.exists():
        return {}
    for path in log_dir.glob("ai_daily_tw_report_*.md"):
        match = REPORT_FILE_RE.match(path.name)
        if not match:
            continue
        file_date = match.group(1)
        if cutoff and file_date > cutoff:
            continue
        payload = parse_report_signals(path)
        if payload:
            payloads.append((file_date, payload))
    payloads.sort(key=lambda item: item[0])
    return {file_date: payload for file_date, payload in payloads[-limit:]}


def load_signal_payloads(log_dir: Path, *, before_or_on: str | None = None, limit: int = 20) -> list[dict]:
    json_payloads = load_signal_json_payloads(log_dir, before_or_on=before_or_on, limit=limit)
    report_payloads = load_report_payloads(log_dir, before_or_on=before_or_on, limit=limit)
    dates = sorted(set(json_payloads) | set(report_payloads))[-limit:]
    return [json_payloads.get(date) or report_payloads[date] for date in dates]


def _row_date(row: dict) -> str | None:
    return parse_date(row.get("date"))


def _price_rows_until(rows: list[dict], as_of_date: str | None) -> list[dict]:
    cutoff = parse_date(as_of_date) if as_of_date else None
    valid: list[dict] = []
    for row in rows:
        row_date = _row_date(row)
        close = to_float(row.get("close"))
        if not row_date or close is None or close <= 0:
            continue
        if cutoff and row_date > cutoff:
            continue
        valid.append(row)
    valid.sort(key=lambda row: str(row.get("date") or ""))
    return valid


def _signal_row_index(rows: list[dict], signal_date: str) -> int | None:
    for index, row in enumerate(rows):
        row_date = _row_date(row)
        if row_date and row_date >= signal_date:
            return index
    return None


def _ma20_at(rows: list[dict], end_index: int) -> float | None:
    closes = [to_float(row.get("close")) for row in rows[: end_index + 1]]
    closes = [float(value) for value in closes if value is not None and value > 0]
    if len(closes) < 20:
        return None
    return sum(closes[-20:]) / 20


def _return_at(future_rows: list[dict], entry_close: float, days: int) -> float | None:
    if len(future_rows) < days or entry_close <= 0:
        return None
    close = to_float(future_rows[days - 1].get("close"))
    if close is None:
        return None
    return ((close / entry_close) - 1) * 100


def _max_return(rows: list[dict], entry_close: float) -> float | None:
    if not rows or entry_close <= 0:
        return None
    high = max((to_float(row.get("high")) or to_float(row.get("close")) or entry_close) for row in rows)
    return ((high / entry_close) - 1) * 100


def _max_drawdown(rows: list[dict], entry_close: float) -> float | None:
    if not rows or entry_close <= 0:
        return None
    running_high = entry_close
    max_drawdown = 0.0
    for row in rows:
        high = to_float(row.get("high")) or to_float(row.get("close")) or running_high
        low = to_float(row.get("low")) or to_float(row.get("close")) or running_high
        running_high = max(running_high, high)
        if running_high > 0:
            max_drawdown = min(max_drawdown, ((low / running_high) - 1) * 100)
    return max_drawdown


def _breakout_success(future_rows: list[dict], breakout_price: float | None) -> bool | None:
    if breakout_price is None or breakout_price <= 0 or not future_rows:
        return None
    hold_days = 0
    for row in future_rows[:10]:
        close = to_float(row.get("close"))
        if close is not None and close > breakout_price:
            hold_days += 1
            if hold_days >= 2:
                return True
        else:
            hold_days = 0
    return False


def _failed_signal(
    future_rows: list[dict],
    signal_low: float | None,
    ma20: float | None,
) -> bool | None:
    if not future_rows:
        return None
    for row in future_rows[:10]:
        close = to_float(row.get("close"))
        if close is None:
            continue
        if signal_low is not None and close < signal_low:
            return True
        if ma20 is not None and close < ma20:
            return True
    return False


def compute_backtests(
    signal_payloads: list[dict],
    fetch_price_rows: Callable[[str], list[dict]],
    *,
    as_of_date: str | None = None,
) -> list[dict]:
    price_cache: dict[str, list[dict]] = {}
    results: list[dict] = []
    for payload in signal_payloads:
        signals = payload.get("signals") or []
        if not isinstance(signals, list):
            continue
        for signal in signals:
            if not isinstance(signal, dict):
                continue
            ticker = str(signal.get("ticker") or "").upper().strip()
            signal_date = parse_date(signal.get("signal_date") or payload.get("report_date"))
            if not ticker or not signal_date:
                continue
            if ticker not in price_cache:
                price_cache[ticker] = _price_rows_until(fetch_price_rows(ticker), as_of_date)
            rows = price_cache[ticker]
            signal_index = _signal_row_index(rows, signal_date)
            if signal_index is None:
                continue
            signal_row = rows[signal_index]
            entry_close = to_float(signal.get("close")) or to_float(signal_row.get("close"))
            if entry_close is None or entry_close <= 0:
                continue
            future_rows = rows[signal_index + 1 :]
            ma20 = to_float(signal.get("ma20")) or _ma20_at(rows, signal_index)
            ret_1d = _return_at(future_rows, entry_close, 1)
            ret_3d = _return_at(future_rows, entry_close, 3)
            ret_5d = _return_at(future_rows, entry_close, 5)
            ret_10d = _return_at(future_rows, entry_close, 10)
            first5 = future_rows[:5]
            result = {
                "ticker": ticker,
                "name": signal.get("name") or "",
                "sector": signal.get("sector") or "",
                "signal_date": signal_date,
                "signal_status": signal.get("signal_status") or "unknown",
                "instrument_type": signal.get("instrument_type") or "",
                "entry_close": entry_close,
                "confirmation_price": to_float(signal.get("breakout_price")),
                "signal_low": to_float(signal.get("signal_low")),
                "return_1d": ret_1d,
                "return_3d": ret_3d,
                "return_5d": ret_5d,
                "return_10d": ret_10d,
                "max_return_5d": _max_return(first5, entry_close),
                "max_drawdown_5d": _max_drawdown(first5, entry_close),
                "hit_1d": ret_1d is not None and ret_1d > 0,
                "hit_3d": ret_3d is not None and ret_3d > 0,
                "hit_5d": ret_5d is not None and ret_5d > 0,
                "breakout_success": _breakout_success(future_rows, to_float(signal.get("breakout_price"))),
                "failed_signal": _failed_signal(future_rows, to_float(signal.get("signal_low")), ma20),
            }
            results.append(result)
    results.sort(key=lambda row: (str(row.get("signal_date") or ""), str(row.get("ticker") or "")))
    return results


def _known_rate(rows: list[dict], key: str) -> float | None:
    known = [row for row in rows if row.get(key) is not None]
    if not known:
        return None
    return sum(1 for row in known if row.get(key)) / len(known) * 100


def _avg(values: list[float | None]) -> float | None:
    known = [float(value) for value in values if value is not None]
    if not known:
        return None
    return sum(known) / len(known)


def summarize_backtests(backtests: list[dict], *, today_count: int, lookback_days: int = 20) -> dict:
    dates = sorted({str(row.get("signal_date")) for row in backtests if row.get("signal_date")})
    allowed_dates = set(dates[-lookback_days:])
    recent = [row for row in backtests if row.get("signal_date") in allowed_dates]
    confirmed = [row for row in recent if row.get("signal_status") == "confirmed_uptrend"]
    failed_rows = [
        row
        for row in recent
        if row.get("signal_status") == "failed_breakout" or row.get("failed_signal") is True
    ]
    known_failed_base = [row for row in recent if row.get("failed_signal") is not None or row.get("signal_status")]
    return {
        "today_signal_count": today_count,
        "lookback_signal_days": min(len(allowed_dates), lookback_days),
        "evaluated_signal_count": len(recent),
        "avg_hit_1d": _known_rate(recent, "hit_1d"),
        "avg_hit_3d": _known_rate(recent, "hit_3d"),
        "avg_hit_5d": _known_rate(recent, "hit_5d"),
        "confirmed_uptrend_avg_return": _avg([row.get("return_5d") for row in confirmed]),
        "failed_breakout_ratio": (len(failed_rows) / len(known_failed_base) * 100) if known_failed_base else None,
    }


def latest_backtest_by_ticker(backtests: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in sorted(backtests, key=lambda item: str(item.get("signal_date") or "")):
        ticker = str(row.get("ticker") or "")
        if ticker:
            latest[ticker] = row
    return latest


def hit_rate_by_status(backtests: list[dict], *, hit_key: str = "hit_5d") -> dict[str, dict]:
    buckets: dict[str, list[dict]] = {}
    for row in backtests:
        status = str(row.get("signal_status") or "unknown")
        if row.get(hit_key) is None:
            continue
        buckets.setdefault(status, []).append(row)
    return {
        status: {
            "hit_rate": _known_rate(rows, hit_key),
            "sample_size": len(rows),
        }
        for status, rows in buckets.items()
    }
