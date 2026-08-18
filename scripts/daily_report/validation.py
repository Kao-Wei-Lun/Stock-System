"""Structured signal persistence and 1/3/5/10-day validation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class SignalValidationArtifacts:
    signal_file: Path | None
    signal_store_error: str | None
    backtest_error: str | None
    summary: dict
    latest_by_ticker: dict[str, dict]
    hit_rates_by_status: dict[str, dict]


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int = 60) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def persist_and_validate_signals(
    *,
    signal_module: Any,
    log_dir: Path,
    report_date: str,
    daily_signals: list[dict],
    base_url: str,
    fetch_price_rows: Callable[[str], list[dict]],
) -> SignalValidationArtifacts:
    signal_file: Path | None = None
    signal_store_error: str | None = None
    try:
        signal_file = signal_module.save_daily_signals(
            log_dir,
            report_date,
            daily_signals,
            meta={"source": "ai_daily_report_tw", "base_url": base_url},
        )
    except Exception as exc:  # noqa: BLE001 - report still renders with an explicit warning
        signal_store_error = str(exc)

    summary = {
        "today_signal_count": len(daily_signals),
        "lookback_signal_days": 0,
        "evaluated_signal_count": 0,
        "avg_hit_1d": None,
        "avg_hit_3d": None,
        "avg_hit_5d": None,
        "avg_hit_10d": None,
        "confirmed_uptrend_avg_return": None,
        "failed_breakout_ratio": None,
    }
    backtest_error: str | None = None
    latest_by_ticker: dict[str, dict] = {}
    hit_rates_by_status: dict[str, dict] = {}
    try:
        lookback_days = _env_int("DAILY_REPORT_SIGNAL_VALIDATION_LOOKBACK_DAYS", 20, minimum=1, maximum=60)
        # load_signal_payloads prefers structured daily JSON and only falls back
        # to legacy Markdown for dates without a JSON artifact.
        payloads = signal_module.load_signal_payloads(
            log_dir,
            before_or_on=report_date,
            limit=lookback_days,
        )
        backtests = signal_module.compute_backtests(
            payloads,
            fetch_price_rows,
            as_of_date=report_date,
        )
        summary = signal_module.summarize_backtests(
            backtests,
            today_count=len(daily_signals),
            lookback_days=lookback_days,
        )
        latest_by_ticker = signal_module.latest_backtest_by_ticker(backtests)
        hit_rates_by_status = signal_module.hit_rate_by_status(backtests, hit_key="hit_5d")
    except Exception as exc:  # noqa: BLE001 - keep daily report generation available
        backtest_error = str(exc)

    return SignalValidationArtifacts(
        signal_file=signal_file,
        signal_store_error=signal_store_error,
        backtest_error=backtest_error,
        summary=summary,
        latest_by_ticker=latest_by_ticker,
        hit_rates_by_status=hit_rates_by_status,
    )
