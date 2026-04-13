from __future__ import annotations

import re
from typing import Optional

from data_fetcher import normalize_ticker
from tw_symbol_lookup import resolve_taiwan_ticker

_FUTOPT_CONTRACT_PATTERN = re.compile(r"^[A-Z]{2,5}[A-Z]\d$")
_FUTOPT_BASE_ALIASES = {
    "TX": "TXF",
    "TXF": "TXF",
    "MTX": "MXF",
    "MXF": "MXF",
}


def _resolve_taiwan_stock_ticker(ticker: str) -> Optional[str]:
    normalized = normalize_ticker(ticker)
    resolved = resolve_taiwan_ticker(normalized) or resolve_taiwan_ticker(str(ticker or "").strip().upper())
    if not resolved:
        return None
    if resolved.endswith(".TW") or resolved.endswith(".TWO"):
        return resolved
    return None


def is_taiwan_stock_ticker(ticker: str) -> bool:
    return _resolve_taiwan_stock_ticker(ticker) is not None


def supports_fubon_stock_realtime_ticker(ticker: str) -> bool:
    return is_taiwan_stock_ticker(ticker)


def tw_ticker_to_fubon(ticker: str) -> Optional[str]:
    normalized = _resolve_taiwan_stock_ticker(ticker)
    if normalized and normalized.endswith(".TW"):
        return normalized[:-3]
    if normalized and normalized.endswith(".TWO"):
        return normalized[:-4]
    return None


def fubon_market_to_ticker(symbol: str, market: str | None) -> str:
    normalized_symbol = str(symbol or "").strip().upper()
    normalized_market = str(market or "").strip().upper()
    if normalized_market == "OTC":
        return f"{normalized_symbol}.TWO"
    return f"{normalized_symbol}.TW"


def normalize_futopt_symbol_query(symbol: str) -> str:
    raw = str(symbol or "").strip().upper()
    return _FUTOPT_BASE_ALIASES.get(raw, raw)


def is_exact_futopt_contract(symbol: str) -> bool:
    return bool(_FUTOPT_CONTRACT_PATTERN.fullmatch(normalize_futopt_symbol_query(symbol)))


def is_futopt_base_alias(symbol: str) -> bool:
    return normalize_futopt_symbol_query(symbol) in set(_FUTOPT_BASE_ALIASES.values())
