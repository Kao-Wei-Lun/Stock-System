"""Network data assembly for the Taiwan daily report."""

from __future__ import annotations

import urllib.parse
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class DailyReportSourceData:
    coverage: dict
    history_status: dict
    status_counts: Counter
    screener: dict
    momentum_candidates_raw: list
    market_context: dict
    taifex: dict | None
    structured: dict


def assemble_source_data(
    *,
    base_url: str,
    report_date: str,
    http_json: Callable[..., object],
) -> DailyReportSourceData:
    """Fetch required sources fail-fast and optional sources independently."""
    coverage_value = http_json(f"{base_url}/api/tw/universe/coverage?interval=1d", timeout=30)
    history_value = http_json(
        f"{base_url}/api/tw/history/status?interval=1d&limit=5000",
        timeout=60,
    )
    coverage = coverage_value if isinstance(coverage_value, dict) else {}
    history_status = history_value if isinstance(history_value, dict) else {}
    status_counts = Counter(
        item.get("status")
        for item in history_status.get("items") or []
        if isinstance(item, dict) and item.get("status") is not None
    )

    screener_value = http_json(
        f"{base_url}/api/screener/run",
        method="POST",
        json_body={
            "filters": {
                "market": "TW",
                "setup_type": "accumulation",
                "sort_by": "accumulation_score",
                "limit": 200,
            }
        },
        timeout=180,
    )
    screener = screener_value if isinstance(screener_value, dict) else {}
    market_context = screener.get("market_context")
    if not isinstance(market_context, dict):
        market_context = {}

    momentum_candidates_raw: list = []
    try:
        momentum_value = http_json(
            f"{base_url}/api/screener/run",
            method="POST",
            json_body={
                "filters": {
                    "market": "TW",
                    "setup_type": "any",
                    "sort_by": "score",
                    "limit": 350,
                }
            },
            timeout=180,
        )
        if isinstance(momentum_value, dict):
            momentum_candidates_raw = list(momentum_value.get("items") or [])
    except Exception:  # noqa: BLE001 - optional momentum pool
        momentum_candidates_raw = []

    taifex: dict | None = None
    try:
        taifex_value = http_json(
            f"{base_url}/api/taifex/institutional?date={report_date}",
            timeout=60,
        )
        taifex = taifex_value if isinstance(taifex_value, dict) else None
    except Exception:  # noqa: BLE001 - report can render without TAIFEX
        taifex = None

    structured: dict[str, Any] = {
        "futures": {"items": []},
        "options": {"items": []},
    }
    try:
        futures_url = (
            f"{base_url}/api/taifex/structured/futures?date={report_date}&commodity="
            + urllib.parse.quote("臺股期貨")
            + "&limit=50"
        )
        options_url = (
            f"{base_url}/api/taifex/structured/options?date={report_date}&commodity="
            + urllib.parse.quote("臺指選擇權")
            + "&limit=50"
        )
        structured["futures"] = http_json(futures_url, timeout=60)
        structured["options"] = http_json(options_url, timeout=60)
    except Exception:  # noqa: BLE001 - preserve available partial structured data
        pass

    return DailyReportSourceData(
        coverage=coverage,
        history_status=history_status,
        status_counts=status_counts,
        screener=screener,
        momentum_candidates_raw=momentum_candidates_raw,
        market_context=market_context,
        taifex=taifex,
        structured=structured,
    )
