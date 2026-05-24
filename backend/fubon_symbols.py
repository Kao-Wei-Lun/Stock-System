from __future__ import annotations

import re
from typing import Optional

from data_fetcher import normalize_ticker
from tw_symbol_lookup import resolve_taiwan_ticker

_FUTOPT_FUTURE_CONTRACT_PATTERN = re.compile(r"^[A-Z]{2,5}[A-Z]\d$")
_FUTOPT_OPTION_CONTRACT_PATTERN = re.compile(r"^(?P<product>[A-Z]{2,5})\d{3,6}[A-Z]\d$")
_FUTOPT_PARTIAL_OPTION_PATTERN = re.compile(r"^(?P<product>[A-Z]{2,5})\d{1,6}$")
_FUTOPT_BASE_ALIASES = {
    "TX": "TXF",
    "TXF": "TXF",
    "MTX": "MXF",
    "MXF": "MXF",
    "TMF": "TMF",
}
_FUBON_INDEX_SYMBOLS = {
    "^TWII": "IX0001",
    "^TWOII": "IX0043",
}


def is_taiwan_market_index_ticker(ticker: str) -> bool:
    return normalize_ticker(ticker) in _FUBON_INDEX_SYMBOLS


def fubon_index_ticker_to_symbol(ticker: str) -> Optional[str]:
    return _FUBON_INDEX_SYMBOLS.get(normalize_ticker(ticker))


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
    return is_taiwan_stock_ticker(ticker) or is_taiwan_market_index_ticker(ticker)


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


def is_exact_futopt_future_contract(symbol: str) -> bool:
    return bool(_FUTOPT_FUTURE_CONTRACT_PATTERN.fullmatch(normalize_futopt_symbol_query(symbol)))


def is_exact_futopt_option_contract(symbol: str) -> bool:
    raw = str(symbol or "").strip().upper()
    return bool(_FUTOPT_OPTION_CONTRACT_PATTERN.fullmatch(raw))


def is_exact_futopt_contract(symbol: str) -> bool:
    normalized = normalize_futopt_symbol_query(symbol)
    return bool(
        _FUTOPT_FUTURE_CONTRACT_PATTERN.fullmatch(normalized)
        or _FUTOPT_OPTION_CONTRACT_PATTERN.fullmatch(normalized)
    )


def is_futopt_base_alias(symbol: str) -> bool:
    return normalize_futopt_symbol_query(symbol) in set(_FUTOPT_BASE_ALIASES.values())


def derive_futopt_product_query(symbol: str) -> Optional[str]:
    normalized = normalize_futopt_symbol_query(symbol)
    if not normalized:
        return None
    if is_exact_futopt_future_contract(normalized):
        return normalized[:-2]
    option_match = _FUTOPT_OPTION_CONTRACT_PATTERN.fullmatch(normalized)
    if option_match:
        return option_match.group("product")
    partial_option = _FUTOPT_PARTIAL_OPTION_PATTERN.fullmatch(normalized)
    if partial_option:
        return partial_option.group("product")
    letters_match = re.match(r"^[A-Z]{2,5}", normalized)
    if letters_match:
        return letters_match.group(0)
    return None


def looks_like_futopt_search_query(symbol: str) -> bool:
    normalized = normalize_futopt_symbol_query(symbol)
    if not normalized:
        return False
    if is_futopt_base_alias(normalized) or is_exact_futopt_contract(normalized):
        return True
    if re.fullmatch(r"^[A-Z]{2,5}O$", normalized):
        return True
    if _FUTOPT_PARTIAL_OPTION_PATTERN.fullmatch(normalized):
        return True
    if re.fullmatch(r"^[A-Z]{2,5}[A-Z]?\d$", normalized):
        return True
    return False
