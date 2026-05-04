from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional

from data_fetcher import normalize_ticker
from futopt_session import resolve_futopt_session
from fubon_quote_provider import build_fubon_quote_payload
from fubon_symbols import (
    derive_futopt_product_query,
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
FUTOPT_SEARCH_CONTRACT_TYPES = ("I", "S", "E", "C", "R", "B")


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


def _object_field(value: Any, *names: str) -> Any:
    if isinstance(value, dict):
        for name in names:
            if name in value:
                return value.get(name)
        return None
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return None


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


def _instrument_type_label(item: dict, default_type: str) -> str:
    raw_type = str(item.get("type") or default_type or "").upper()
    return "option" if raw_type.startswith("OPTION") else "future"


def _contract_sort_key(item: dict, query: str) -> tuple[int, int, date, str]:
    symbol = str(item.get("symbol") or "").upper()
    name = str(item.get("name") or "").upper()
    today = date.today()
    end_date = _parse_contract_date(item.get("endDate") or item.get("settlementDate")) or date.max
    if symbol == query:
        match_rank = 0
    elif symbol.startswith(query):
        match_rank = 1
    elif query in symbol:
        match_rank = 2
    elif query in name:
        match_rank = 3
    else:
        match_rank = 4
    active_rank = 0 if end_date >= today else 1
    return (match_rank, active_rank, end_date, symbol)


def _instrument_type_from_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip().upper()
    return "option" if any(char.isdigit() for char in raw[:-2]) else "future"


class FubonFutoptProvider:
    def __init__(self, manager):
        self._manager = manager
        self._contract_cache: dict[tuple[str, str, str, str | None], tuple[float, list[dict]]] = {}

    async def resolve_contract(self, symbol: str, *, session: str = "REGULAR") -> Optional[dict]:
        normalized_symbol = normalize_ticker(symbol)
        query = normalize_futopt_symbol_query(normalized_symbol)
        resolved_session = resolve_futopt_session(session)
        if is_exact_futopt_contract(query):
            return {
                "requested_symbol": normalized_symbol,
                "resolved_symbol": query,
                "name": query,
                "contract_type": None,
                "end_date": None,
                "instrument_type": _instrument_type_from_symbol(query),
            }
        if not is_futopt_base_alias(query):
            return None

        contracts = await self._load_contracts(query, session=resolved_session)
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
            "instrument_type": _instrument_type_label(resolved, "FUTURE"),
        }

    async def fetch_quote(self, symbol: str, *, session: str = "AUTO") -> Optional[dict]:
        resolved_session = resolve_futopt_session(session)
        resolved = await self.resolve_contract(symbol, session=resolved_session)
        if not resolved:
            return None

        response = await self._manager.fetch_futopt_quote(resolved["resolved_symbol"], session=resolved_session)
        payload = build_fubon_quote_payload(
            resolved["resolved_symbol"],
            response or {},
            source="fubon_neo",
        )
        if not payload:
            return None

        payload["ticker"] = resolved["resolved_symbol"]
        payload["resolved_symbol"] = str(response.get("symbol") or resolved["resolved_symbol"])
        payload["market"] = "OPTION" if resolved.get("instrument_type") == "option" else "FUTURE"
        payload["exchange"] = response.get("exchange") or "TAIFEX"
        payload["name"] = response.get("name") or resolved.get("name") or resolved["resolved_symbol"]
        payload["currency"] = response.get("currency") or "TWD"
        return payload

    async def estimate_margin(
        self,
        symbol: str,
        *,
        lot: int = 1,
        session: str = "REGULAR",
    ) -> Optional[dict]:
        resolved_session = resolve_futopt_session(session)
        resolved = await self.resolve_contract(symbol, session=resolved_session)
        if not resolved:
            return None
        if str(resolved.get("instrument_type") or "future").lower() != "future":
            raise ValueError(f"Margin estimate only supports futures contracts: {symbol}")

        quote = await self._manager.fetch_futopt_quote(
            resolved["resolved_symbol"],
            session=resolved_session,
        ) or {}
        price = _coerce_float(
            quote.get("closePrice")
            or quote.get("lastPrice")
            or quote.get("price")
            or quote.get("referencePrice")
            or quote.get("previousClose")
        )
        if price is None:
            payload = build_fubon_quote_payload(
                resolved["resolved_symbol"],
                quote,
                source="fubon_neo",
            ) or {}
            price = _coerce_float(payload.get("price") or payload.get("close") or payload.get("previous_close"))
        if price is None:
            raise RuntimeError(f"Unable to determine quote price for margin estimate: {resolved['resolved_symbol']}")

        response = await self._manager.query_futopt_estimate_margin(
            resolved["resolved_symbol"],
            price=price,
            lot=max(1, int(lot or 1)),
            session=resolved_session,
        )
        if _object_field(response, "is_success", "isSuccess") is False:
            raise RuntimeError(str(_object_field(response, "message") or "Fubon margin estimate failed"))

        data = _object_field(response, "data") or response
        if isinstance(data, list):
            data = data[0] if data else {}
        estimate_margin = _coerce_float(
            _object_field(data, "estimate_margin", "estimateMargin", "initial_margin", "margin")
        )
        if estimate_margin is None:
            raise RuntimeError("Fubon margin estimate response did not include estimate_margin")

        return {
            "product_symbol": normalize_ticker(symbol),
            "requested_symbol": resolved["requested_symbol"],
            "resolved_symbol": resolved["resolved_symbol"],
            "initial_margin_per_contract": estimate_margin,
            "estimate_margin": estimate_margin,
            "currency": _object_field(data, "currency") or quote.get("currency") or "TWD",
            "date": _object_field(data, "date"),
            "price": price,
            "lot": max(1, int(lot or 1)),
            "source": "fubon_query_estimate_margin",
        }

    async def fetch_intraday_ohlc(
        self,
        symbol: str,
        *,
        period: str = "1d",
        interval: str = "1m",
        session: str = "ALL",
    ) -> Optional[dict]:
        normalized_interval = str(interval or "1m").strip().lower()
        timeframe = FUBON_FUTOPT_INTERVALS.get(normalized_interval)
        if not timeframe:
            raise ValueError(f"Unsupported futopt interval '{normalized_interval}'")

        resolve_session = "REGULAR" if session.upper() == "ALL" else session
        resolved = await self.resolve_contract(symbol, session=resolve_session)
        if not resolved:
            return None

        if session.upper() == "ALL":
            import asyncio
            res_regular, res_afterhours = await asyncio.gather(
                self._manager.fetch_futopt_intraday_candles(
                    resolved["resolved_symbol"],
                    timeframe=timeframe,
                    session="REGULAR",
                ),
                self._manager.fetch_futopt_intraday_candles(
                    resolved["resolved_symbol"],
                    timeframe=timeframe,
                    session="AFTERHOURS",
                ),
                return_exceptions=True
            )

            rows_regular = _rows_from_futopt_candles(res_regular if isinstance(res_regular, dict) else None)
            rows_afterhours = _rows_from_futopt_candles(res_afterhours if isinstance(res_afterhours, dict) else None)

            all_rows = sorted(rows_regular + rows_afterhours, key=lambda x: x["date"])
            rows = _filter_rows_by_period(all_rows, period)
        else:
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
            "contract_type": resolved.get("contract_type"),
            "end_date": resolved.get("end_date"),
            "instrument_type": resolved.get("instrument_type") or "future",
            "period": period,
            "interval": normalized_interval,
            "data": rows,
        }

    async def search_contracts(
        self,
        query: str,
        *,
        session: str = "REGULAR",
        limit: int = 20,
    ) -> list[dict]:
        normalized_query = normalize_futopt_symbol_query(str(query or "").strip().upper())
        if not normalized_query:
            return []

        product_query = derive_futopt_product_query(normalized_query)
        if not product_query:
            return []

        search_types = ["OPTION"] if product_query.endswith("O") else ["FUTURE"]
        if is_exact_futopt_contract(normalized_query):
            if any(char.isdigit() for char in normalized_query[:-2]):
                search_types = ["OPTION"]
            elif product_query not in {"TXF", "MXF"}:
                search_types = ["FUTURE", "OPTION"]

        matches: dict[str, dict] = {}
        for search_type in search_types:
            for contract_type in FUTOPT_SEARCH_CONTRACT_TYPES:
                try:
                    contracts = await self._fetch_cached_tickers(
                        type=search_type,
                        exchange="TAIFEX",
                        session=session,
                        contractType=contract_type,
                        product=product_query,
                    )
                except Exception as exc:
                    log.warning(
                        "Fubon futopt search failed for %s/%s/%s: %s",
                        product_query,
                        search_type,
                        contract_type,
                        exc,
                    )
                    continue

                for item in contracts:
                    symbol = str(item.get("symbol") or "").upper()
                    name = str(item.get("name") or "")
                    haystack_name = name.upper()
                    if not symbol:
                        continue
                    if normalized_query not in symbol and normalized_query not in haystack_name and not symbol.startswith(product_query):
                        continue
                    matches[symbol] = {
                        "ticker": symbol,
                        "name": name or symbol,
                        "exchange": "TAIFEX",
                        "market": "FUTOPT",
                        "asset_class": "futopt",
                        "instrument_type": _instrument_type_label(item, search_type),
                        "source": "fubon_neo",
                        "contract_type": item.get("contractType"),
                        "end_date": item.get("endDate") or item.get("settlementDate"),
                    }

        sorted_items = sorted(
            matches.values(),
            key=lambda item: _contract_sort_key(
                {
                    "symbol": item.get("ticker"),
                    "name": item.get("name"),
                    "endDate": item.get("end_date"),
                },
                normalized_query,
            ),
        )
        return sorted_items[: max(1, min(int(limit or 20), 50))]

    async def _load_contracts(self, base_symbol: str, *, session: str) -> list[dict]:
        contracts: list[dict] = []
        for contract_type in ("I", "E"):
            try:
                contracts_for_type = await self._fetch_cached_tickers(
                    type="FUTURE",
                    exchange="TAIFEX",
                    session=session,
                    contractType=contract_type,
                )
            except Exception as exc:
                log.warning("Fubon futopt tickers fetch failed for %s/%s: %s", base_symbol, contract_type, exc)
                continue

            for item in contracts_for_type:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol") or "").upper()
                if symbol.startswith(base_symbol):
                    contracts.append(item)

        return list({str(item.get("symbol") or "").upper(): item for item in contracts}.values())

    async def _fetch_cached_tickers(
        self,
        *,
        type: str,
        exchange: str,
        session: str,
        contractType: str,
        product: str | None = None,
    ) -> list[dict]:
        cache_key = (type, contractType, session, str(product or "").upper() or None)
        cached = self._contract_cache.get(cache_key)
        now = time.time()
        if cached and now - cached[0] < FUTOPT_CACHE_TTL_SECONDS:
            return list(cached[1])

        payload = await self._manager.fetch_futopt_tickers(
            type=type,
            exchange=exchange,
            session=session,
            contractType=contractType,
            product=product,
        )
        items = [
            item
            for item in (payload.get("data") or [] if isinstance(payload, dict) else [])
            if isinstance(item, dict)
        ]
        self._contract_cache[cache_key] = (now, items)
        return list(items)
