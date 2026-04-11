from __future__ import annotations

import re
from typing import Optional

from data_fetcher import normalize_ticker

_FUTOPT_CONTRACT_PATTERN = re.compile(r"^[A-Z]{2,5}[A-Z]\d$")
_FUTOPT_BASE_ALIASES = {
    "TX": "TXF",
    "TXF": "TXF",
    "MTX": "MXF",
    "MXF": "MXF",
}


def is_taiwan_stock_ticker(ticker: str) -> bool:
    normalized = normalize_ticker(ticker)
    if normalized.endswith(".TW"):
        return normalized[:-3].isdigit()
    if normalized.endswith(".TWO"):
        return normalized[:-4].isdigit()
    return False


def supports_fubon_stock_realtime_ticker(ticker: str) -> bool:
    return is_taiwan_stock_ticker(ticker)


def tw_ticker_to_fubon(ticker: str) -> Optional[str]:
    normalized = normalize_ticker(ticker)
    if normalized.endswith(".TW") and normalized[:-3].isdigit():
        return normalized[:-3]
    if normalized.endswith(".TWO") and normalized[:-4].isdigit():
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
