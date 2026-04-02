from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def compute_trade_result(entry: Dict[str, Any]) -> Dict[str, Any]:
    direction = str(entry.get("direction") or "long").strip().lower() or "long"
    entry_price = _safe_float(entry.get("entry_price"))
    exit_price = _safe_float(entry.get("exit_price"))
    size = _safe_float(entry.get("size"), 0.0)
    entry_time = _parse_datetime(entry.get("entry_time"))
    exit_time = _parse_datetime(entry.get("exit_time"))
    multiplier = 1 if direction != "short" else -1

    result = {
        "closed": bool(exit_time and exit_price is not None),
        "pnl": None,
        "pnl_pct": None,
        "holding_days": None,
        "is_win": None,
    }

    if entry_time and exit_time:
        result["holding_days"] = max((exit_time - entry_time).days, 0)

    if entry_price is None or exit_price is None or size <= 0:
        return result

    pnl = (exit_price - entry_price) * size * multiplier
    capital = entry_price * size
    pnl_pct = (pnl / capital * 100) if capital else None
    result.update(
        {
            "closed": True,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "is_win": pnl > 0,
        }
    )
    return result


def build_journal_stats(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    closed_entries = []
    open_entries = []
    for entry in entries:
        result = entry.get("result") or {}
        if result.get("closed"):
            closed_entries.append(entry)
        else:
            open_entries.append(entry)

    wins = [entry for entry in closed_entries if (entry.get("result") or {}).get("pnl", 0) > 0]
    losses = [entry for entry in closed_entries if (entry.get("result") or {}).get("pnl", 0) < 0]
    win_pnl = sum((entry.get("result") or {}).get("pnl", 0) for entry in wins)
    loss_pnl = sum((entry.get("result") or {}).get("pnl", 0) for entry in losses)
    net_pnl = sum((entry.get("result") or {}).get("pnl", 0) or 0 for entry in closed_entries)
    avg_return = (
        sum((entry.get("result") or {}).get("pnl_pct", 0) or 0 for entry in closed_entries) / len(closed_entries)
        if closed_entries
        else 0.0
    )

    return {
        "total_entries": len(entries),
        "closed_entries": len(closed_entries),
        "open_entries": len(open_entries),
        "win_rate": (len(wins) / len(closed_entries) * 100) if closed_entries else 0.0,
        "net_pnl": net_pnl,
        "avg_pnl": (net_pnl / len(closed_entries)) if closed_entries else 0.0,
        "avg_return_pct": avg_return,
        "profit_factor": (win_pnl / abs(loss_pnl)) if loss_pnl < 0 else (None if win_pnl > 0 else 0.0),
        "best_trade": max(((entry.get("result") or {}).get("pnl", 0) or 0 for entry in closed_entries), default=0.0),
        "worst_trade": min(((entry.get("result") or {}).get("pnl", 0) or 0 for entry in closed_entries), default=0.0),
        "markets": _aggregate_by_key(entries, "market"),
        "strategies": _aggregate_by_key(entries, "strategy_code"),
        "strategy_breakdown": _aggregate_field_breakdown(entries, "strategy_code"),
        "emotions": _aggregate_by_key(entries, "emotion_tag"),
        "tag_breakdown": _aggregate_tag_breakdown(entries),
        "source_breakdown": _aggregate_prefixed_tags(entries, "來源:"),
        "market_posture_breakdown": _aggregate_prefixed_tags(entries, "市場:"),
    }


def _aggregate_by_key(entries: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    buckets: Dict[str, int] = {}
    for entry in entries:
        value = str(entry.get(key) or "").strip()
        if not value:
            continue
        buckets[value] = buckets.get(value, 0) + 1
    return [
        {"key": bucket_key, "count": count}
        for bucket_key, count in sorted(buckets.items(), key=lambda item: (-item[1], item[0]))
    ]


def _aggregate_tag_breakdown(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries:
        for tag in _extract_tags(entry):
            if tag.startswith("來源:") or tag.startswith("市場:"):
                continue
            buckets.setdefault(tag, []).append(entry)
    return _summarize_entry_buckets(buckets)


def _aggregate_field_breakdown(entries: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries:
        value = str(entry.get(key) or "").strip()
        if not value:
            continue
        buckets.setdefault(value, []).append(entry)
    return _summarize_entry_buckets(buckets)


def _aggregate_prefixed_tags(entries: List[Dict[str, Any]], prefix: str) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries:
        for tag in _extract_tags(entry):
            if not tag.startswith(prefix):
                continue
            label = tag[len(prefix):].strip() or tag
            buckets.setdefault(label, []).append(entry)
    return _summarize_entry_buckets(buckets)


def _extract_tags(entry: Dict[str, Any]) -> List[str]:
    return [
        str(tag).strip()
        for tag in (entry.get("tags") or [])
        if str(tag or "").strip()
    ]


def _summarize_entry_buckets(buckets: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    summaries = []
    for bucket_key, bucket_entries in buckets.items():
        closed_entries = [entry for entry in bucket_entries if (entry.get("result") or {}).get("closed")]
        win_entries = [entry for entry in closed_entries if ((entry.get("result") or {}).get("pnl") or 0) > 0]
        net_pnl = sum(((entry.get("result") or {}).get("pnl") or 0) for entry in closed_entries)
        avg_return_pct = (
            sum(((entry.get("result") or {}).get("pnl_pct") or 0) for entry in closed_entries) / len(closed_entries)
            if closed_entries
            else 0.0
        )
        summaries.append(
            {
                "key": bucket_key,
                "count": len(bucket_entries),
                "closed_count": len(closed_entries),
                "win_rate": (len(win_entries) / len(closed_entries) * 100) if closed_entries else 0.0,
                "net_pnl": net_pnl,
                "avg_return_pct": avg_return_pct,
            }
        )

    return sorted(
        summaries,
        key=lambda item: (
            -item["count"],
            -item["net_pnl"],
            item["key"],
        ),
    )


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value in (None, ""):
        return default
    return float(value)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    normalized = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
