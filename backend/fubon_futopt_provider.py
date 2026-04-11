from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional

from data_fetcher import normalize_ticker
from fubon_quote_provider import build_fubon_quote_payload
from fubon_symbols import (
    is_exact_futopt_contract,
    is_futopt_base_alias,
    normalize_futopt_symbol_query,
)

log = logging.getLogger(__name__)

FUBON_FUTOPT_INTERVALS = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "60m": "60",
    "1h": "60",
}
FUTOPT_CACHE_TTL_SECONDS = 60
FUTOPT_PERIOD_OFFSETS = {
    "1d": timedelta(days=1),
    "5d": timedelta(days=5),
    "1mo": timedelta(days=31),
    "3mo": timedelta(days=93),
    "6mo": timedelta(days=186),
}


def _coerce_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_contract_date(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _rows_from_futopt_candles(payload: Optional[dict]) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    rows = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        close_price = _coerce_float(item.get("close"))
        if close_price is None:
            continue
        open_price = _coerce_float(item.get("open"))
        high_price = _coerce_float(item.get("high"))
        low_price = _coerce_float(item.get("low"))
        rows.append(
            {
                "date": str(item.get("date")),
                "open": round(open_price if open_price is not None else close_price, 4),
                "high": round(high_price if high_price is not None else close_price, 4),
                "low": round(low_price if low_price is not None else close_price, 4),
                "close": round(close_price, 4),
                "volume": _coerce_int(item.get("volume")),
                "adj_close": round(close_price, 4),
                "source": "fubon_neo",
            }
        )
    return rows


def _filter_rows_by_period(rows: list[dict], period: str | None) -> list[dict]:
    normalized_period = str(period or "1d").strip().lower()
    offset = FUTOPT_PERIOD_OFFSETS.get(normalized_period)
    if not offset or not rows:
        return rows

    boundary = datetime.now().astimezone() - offset
    filtered = []
    for row in rows:
        raw_date = str(row.get("date") or "").replace(" ", "T").replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw_date)
        except ValueError:
            filtered.append(row)
            continue
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        if parsed >= boundary:
            filtered.append(row)
    return filtered or rows


class FubonFutoptProvider:
    def __init__(self, manager):
        self._manager = manager
        self._contract_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}

    async def resolve_contract(self, symbol: str, *, session: str = "REGULAR") -> Optional[dict]:
        normalized_symbol = normalize_ticker(symbol)
        query = normalize_futopt_symbol_query(normalized_symbol)
        if is_exact_futopt_contract(query):
            return {
                "requested_symbol": normalized_symbol,
                "resolved_symbol": query,
                "name": query,
                "contract_type": None,
                "end_date": None,
            }
        if not is_futopt_base_alias(query):
            return None

        contracts = await self._load_contracts(query, session=session)
        if not contracts:
            return None

        today = date.today()

        def _sort_key(item: dict) -> tuple[int, date, str]:
            end_date = _parse_contract_date(item.get("endDate") or item.get("settlementDate")) or date.max
            return (0 if end_date >= today else 1, end_date, str(item.get("symbol") or ""))

        resolved = sorted(contracts, key=_sort_key)[0]
        return {
            "requested_symbol": normalized_symbol,
            "resolved_symbol": str(resolved.get("symbol") or query).upper(),
            "name": resolved.get("name") or query,
            "contract_type": resolved.get("contractType"),
            "end_date": resolved.get("endDate") or resolved.get("settlementDate"),
        }

    async def fetch_quote(self, symbol: str, *, session: str = "REGULAR") -> Optional[dict]:
        resolved = await self.resolve_contract(symbol, session=session)
        if not resolved:
            return None

        response = await self._manager.fetch_futopt_quote(resolved["resolved_symbol"], session=session)
        payload = build_fubon_quote_payload(
            resolved["resolved_symbol"],
            response or {},
            source="fubon_neo",
        )
        if not payload:
            return None

        payload["ticker"] = resolved["resolved_symbol"]
        payload["resolved_symbol"] = str(response.get("symbol") or resolved["resolved_symbol"])
        payload["market"] = "FUTURE"
        payload["exchange"] = response.get("exchange") or "TAIFEX"
        payload["name"] = response.get("name") or resolved.get("name") or resolved["resolved_symbol"]
        payload["currency"] = response.get("currency") or "TWD"
        return payload

    async def fetch_intraday_ohlc(
        self,
        symbol: str,
        *,
        period: str = "1d",
        interval: str = "1m",
        session: str = "REGULAR",
    ) -> Optional[dict]:
        normalized_interval = str(interval or "1m").strip().lower()
        timeframe = FUBON_FUTOPT_INTERVALS.get(normalized_interval)
        if not timeframe:
            raise ValueError(f"Unsupported futopt interval '{normalized_interval}'")

        resolved = await self.resolve_contract(symbol, session=session)
        if not resolved:
            return None

        response = await self._manager.fetch_futopt_intraday_candles(
            resolved["resolved_symbol"],
            timeframe=timeframe,
            session=session,
        )
        rows = _filter_rows_by_period(_rows_from_futopt_candles(response), period)
        return {
            "ticker": resolved["resolved_symbol"],
            "requested_symbol": resolved["requested_symbol"],
            "resolved_symbol": resolved["resolved_symbol"],
            "period": period,
            "interval": normalized_interval,
            "data": rows,
        }

    async def _load_contracts(self, base_symbol: str, *, session: str) -> list[dict]:
        cache_key = (base_symbol, session)
        cached = self._contract_cache.get(cache_key)
        now = time.time()
        if cached and now - cached[0] < FUTOPT_CACHE_TTL_SECONDS:
            return list(cached[1])

        contracts: list[dict] = []
        for contract_type in ("I", "E"):
            try:
                payload = await self._manager.fetch_futopt_tickers(
                    type="FUTURE",
                    exchange="TAIFEX",
                    session=session,
                    contractType=contract_type,
                )
            except Exception as exc:
                log.warning("Fubon futopt tickers fetch failed for %s/%s: %s", base_symbol, contract_type, exc)
                continue

            for item in payload.get("data") or [] if isinstance(payload, dict) else []:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol") or "").upper()
                if symbol.startswith(base_symbol):
                    contracts.append(item)

        deduped = {str(item.get("symbol") or "").upper(): item for item in contracts}
        items = list(deduped.values())
        self._contract_cache[cache_key] = (now, items)
        return items
