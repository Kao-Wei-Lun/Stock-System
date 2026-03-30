import logging
import time
from typing import Dict, List

import requests

log = logging.getLogger(__name__)

FINMIND_DATA_URL = "https://api.finmindtrade.com/api/v4/data"
LOOKUP_CACHE_TTL_SECONDS = 60 * 60 * 12

_lookup_cache = {
    "expires_at": 0.0,
    "names": {},
    "canonical": {},
    "rows": [],
}


def _build_ticker_aliases(stock_id: str, market_type: str) -> tuple[str, List[str]]:
    primary_ticker = f"{stock_id}.TW"
    aliases = [stock_id, primary_ticker]

    if market_type in {"tpex", "emerging"}:
        primary_ticker = f"{stock_id}.TWO"
        aliases.insert(1, primary_ticker)

    return primary_ticker, aliases


def _load_lookup(force: bool = False) -> tuple[Dict[str, str], Dict[str, str], List[Dict[str, str]]]:
    now = time.time()
    cached_names = _lookup_cache["names"]
    cached_canonical = _lookup_cache["canonical"]
    cached_rows = _lookup_cache["rows"]
    if not force and cached_names and now < _lookup_cache["expires_at"]:
        return cached_names, cached_canonical, cached_rows

    try:
        response = requests.get(
            FINMIND_DATA_URL,
            params={"dataset": "TaiwanStockInfo"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != 200:
            raise RuntimeError(payload.get("msg") or "FinMind lookup failed")

        names: Dict[str, str] = {}
        canonical: Dict[str, str] = {}
        rows: List[Dict[str, str]] = []
        primary_seen = set()
        for item in payload.get("data", []):
            stock_id = str(item.get("stock_id") or "").strip().upper()
            stock_name = str(item.get("stock_name") or "").strip()
            market_type = str(item.get("type") or "").strip().lower()
            if not stock_id or not stock_name:
                continue

            primary_ticker, aliases = _build_ticker_aliases(stock_id, market_type)
            for alias in aliases:
                names.setdefault(alias, stock_name)
                canonical.setdefault(alias, primary_ticker)
            if primary_ticker in primary_seen:
                continue
            primary_seen.add(primary_ticker)
            rows.append(
                {
                    "ticker": primary_ticker,
                    "name": stock_name,
                    "stock_id": stock_id,
                    "market_type": market_type,
                }
            )

        _lookup_cache["expires_at"] = now + LOOKUP_CACHE_TTL_SECONDS
        _lookup_cache["names"] = names
        _lookup_cache["canonical"] = canonical
        _lookup_cache["rows"] = rows
        return names, canonical, rows
    except Exception as exc:
        if cached_names:
            log.warning("taiwan symbol lookup refresh failed, using cached data: %s", exc)
            return cached_names, cached_canonical, cached_rows
        log.warning("taiwan symbol lookup failed: %s", exc)
        return {}, {}, []


def get_taiwan_ticker_name(ticker: str) -> str | None:
    raw = (ticker or "").strip().upper()
    if not raw:
        return None
    names, _, _ = _load_lookup()
    return names.get(raw)


def resolve_taiwan_ticker(ticker: str) -> str | None:
    raw = (ticker or "").strip().upper()
    if not raw:
        return None
    _, canonical, _ = _load_lookup()
    return canonical.get(raw)


def search_taiwan_tickers(query: str, limit: int = 20) -> List[Dict[str, str]]:
    keyword = (query or "").strip()
    if not keyword:
        return []

    _, _, rows = _load_lookup()
    upper_keyword = keyword.upper()

    def score(row: Dict[str, str]) -> tuple[int, str]:
        stock_id = row["stock_id"]
        ticker = row["ticker"]
        name = row["name"]
        if stock_id == upper_keyword or ticker == upper_keyword:
            return (0, ticker)
        if stock_id.startswith(upper_keyword) or ticker.startswith(upper_keyword):
            return (1, ticker)
        if keyword in name:
            return (2, ticker)
        return (3, ticker)

    matched_rows = [
        row
        for row in rows
        if upper_keyword in row["stock_id"]
        or upper_keyword in row["ticker"]
        or keyword in row["name"]
    ]
    matched_rows.sort(key=score)
    return [
        {"ticker": row["ticker"], "name": row["name"]}
        for row in matched_rows[: max(1, min(limit, 50))]
    ]
