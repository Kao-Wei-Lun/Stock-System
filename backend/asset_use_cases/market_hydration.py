"""Reusable market quote and FX hydration policies."""

from __future__ import annotations

import time
from typing import Any, Dict, List


def is_public_auto_fx_source(source: str | None) -> bool:
    return str(source or "").strip().lower() in {"taifex_daily_reference", "public_auto"}


def provider_wait_budget(*, has_persisted_value: bool, timeout_seconds: float) -> float:
    """Bound foreground waiting when a persisted fallback is already available."""
    return min(float(timeout_seconds), 1.5) if has_persisted_value else float(timeout_seconds)


def read_fresh_quote_cache(
    cache: Dict[str, tuple[float, int, Dict[str, Any]]],
    symbol: str,
    *,
    provider_identity: int,
    now: float | None = None,
) -> Dict[str, Any] | None:
    cached = cache.get(symbol)
    if not cached:
        return None
    if cached[0] > (time.monotonic() if now is None else now) and cached[1] == provider_identity:
        return cached[2]
    cache.pop(symbol, None)
    return None


async def load_all_asset_rows(
    fetcher,
    *,
    owner_id: int,
    page_size: int,
    **kwargs,
) -> List[Dict[str, Any]]:
    """Read a complete ledger in stable pages so long histories are never truncated."""
    rows: List[Dict[str, Any]] = []
    offset = 0
    while True:
        page = await fetcher(owner_id=owner_id, limit=page_size, offset=offset, **kwargs)
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += len(page)
