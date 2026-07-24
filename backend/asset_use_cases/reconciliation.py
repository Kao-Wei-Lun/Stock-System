"""Reconciliation projection helpers."""

from __future__ import annotations

from typing import Any, Dict, List


def build_reconciliation_positions_payload(
    snapshot: Dict[str, Any],
    account_id: int,
) -> List[Dict[str, Any]]:
    return [
        {
            "ticker": item.get("ticker"),
            "display_name": item.get("display_name"),
            "quantity": item.get("quantity"),
            "last_price": item.get("last_price"),
            "market_value_base": item.get("market_value_base"),
            "quote_timestamp": item.get("quote_timestamp"),
            "quote_source": item.get("quote_source"),
            "manual_price_override_id": item.get("manual_price_override_id"),
        }
        for item in snapshot.get("holdings") or []
        if int(item.get("account_id") or 0) == int(account_id)
    ]
