from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

import requests
import urllib3

from data_fetcher import normalize_ticker
from database import db
from market_intelligence import infer_market
from tw_symbol_lookup import resolve_taiwan_ticker


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TWSE_T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEX_3ITRADE_URL = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
TWSE_T86_EARLIEST_DATE = date(2012, 5, 2)
OFFICIAL_TWSE_SOURCE = "twse_t86"
OFFICIAL_TPEX_SOURCE = "tpex_3itrade_hedge"
SUPPORTED_SYNC_SOURCES = ("twse", "tpex")
TWSE_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.twse.com.tw/zh/trading/foreign/t86.html",
}
TPEX_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.tpex.org.tw/zh-tw/mainboard/trading/info/3itrade-hedge.html",
}
TWSE_FIELD_ALIASES = {
    "證券代號": "security_code",
    "證券名稱": "security_name",
    "外資買進股數": "foreign_buy",
    "外資賣出股數": "foreign_sell",
    "外資買賣超股數": "foreign_net",
    "外資買進股數(不含外資自營商)": "foreign_ex_dealer_buy",
    "外資賣出股數(不含外資自營商)": "foreign_ex_dealer_sell",
    "外資買賣超股數(不含外資自營商)": "foreign_ex_dealer_net",
    "外資自營商買進股數": "foreign_dealer_buy",
    "外資自營商賣出股數": "foreign_dealer_sell",
    "外資自營商買賣超股數": "foreign_dealer_net",
    "投信買進股數": "investment_trust_buy",
    "投信賣出股數": "investment_trust_sell",
    "投信買賣超股數": "investment_trust_net",
    "自營商買進股數": "dealer_buy",
    "自營商賣出股數": "dealer_sell",
    "自營商買賣超股數": "dealer_net",
    "自營商買進股數(自行買賣)": "dealer_self_buy",
    "自營商賣出股數(自行買賣)": "dealer_self_sell",
    "自營商買賣超股數(自行買賣)": "dealer_self_net",
    "自營商買進股數(避險)": "dealer_hedge_buy",
    "自營商賣出股數(避險)": "dealer_hedge_sell",
    "自營商買賣超股數(避險)": "dealer_hedge_net",
    "三大法人買賣超股數": "institutional_net",
}
TPEX_JSON_FIELD_KEYS = [
    "security_code",
    "security_name",
    "foreign_ex_dealer_buy",
    "foreign_ex_dealer_sell",
    "foreign_ex_dealer_net",
    "foreign_dealer_buy",
    "foreign_dealer_sell",
    "foreign_dealer_net",
    "foreign_buy",
    "foreign_sell",
    "foreign_net",
    "investment_trust_buy",
    "investment_trust_sell",
    "investment_trust_net",
    "dealer_self_buy",
    "dealer_self_sell",
    "dealer_self_net",
    "dealer_hedge_buy",
    "dealer_hedge_sell",
    "dealer_hedge_net",
    "dealer_buy",
    "dealer_sell",
    "dealer_net",
    "institutional_net",
]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip().replace(",", "")
    if not text or text in {"--", "-", "X", "除權息"}:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _canonicalize_twse_field(label: Any) -> str:
    text = str(label or "").strip()
    text = text.replace("\u3000", "").replace(" ", "")
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("外陸資", "外資").replace("外資及陸資", "外資")
    return text


def _signed_value(value: Any) -> str:
    numeric = _safe_int(value)
    if numeric > 0:
        return f"+{numeric:,}"
    if numeric < 0:
        return f"-{abs(numeric):,}"
    return "0"


def _signal_tone(value: Any) -> str:
    numeric = _safe_int(value)
    if numeric > 0:
        return "positive"
    if numeric < 0:
        return "caution"
    return "neutral"


def _official_chip_available(snapshot: Optional[Dict[str, Any]]) -> bool:
    if not snapshot:
        return False
    source = str(snapshot.get("source") or "").strip().lower()
    if source in {OFFICIAL_TWSE_SOURCE, OFFICIAL_TPEX_SOURCE}:
        return True
    keys = (
        "foreign_net_buy_sell",
        "investment_trust_net_buy_sell",
        "dealer_net_buy_sell",
    )
    return any(snapshot.get(key) is not None for key in keys)


def build_taiwan_chip_summary(snapshot: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not snapshot:
        return {
            "bias": "neutral",
            "headline": "尚未同步台股籌碼資料",
            "signals": [],
        }

    if _official_chip_available(snapshot):
        total_net = _safe_int(snapshot.get("institutional_net_buy_sell"))
        foreign_net = _safe_int(snapshot.get("foreign_net_buy_sell"))
        trust_net = _safe_int(snapshot.get("investment_trust_net_buy_sell"))
        dealer_net = _safe_int(snapshot.get("dealer_net_buy_sell"))
        source_label = "官方三大法人"
        if str(snapshot.get("source") or "").strip().lower() == OFFICIAL_TWSE_SOURCE:
            source_label = "TWSE 官方三大法人"
        elif str(snapshot.get("source") or "").strip().lower() == OFFICIAL_TPEX_SOURCE:
            source_label = "TPEX 官方三大法人"

        bias = "neutral"
        if total_net > 0:
            bias = "bullish"
        elif total_net < 0:
            bias = "bearish"

        signals = [
            {
                "tone": _signal_tone(total_net),
                "label": "三大法人合計",
                "value": _signed_value(total_net),
            },
            {
                "tone": _signal_tone(foreign_net),
                "label": "外資",
                "value": _signed_value(foreign_net),
            },
            {
                "tone": _signal_tone(trust_net),
                "label": "投信",
                "value": _signed_value(trust_net),
            },
            {
                "tone": _signal_tone(dealer_net),
                "label": "自營商",
                "value": _signed_value(dealer_net),
            },
        ]

        return {
            "bias": bias,
            "headline": f"{snapshot.get('ticker') or 'TW'} {source_label} / {snapshot.get('snapshot_date') or 'N/A'}",
            "signals": signals,
            "metrics": {
                "foreign_net_buy_sell": foreign_net,
                "investment_trust_net_buy_sell": trust_net,
                "dealer_net_buy_sell": dealer_net,
                "institutional_net_buy_sell": total_net,
            },
        }

    margin_balance = _safe_int(snapshot.get("margin_balance"))
    short_balance = _safe_int(snapshot.get("short_balance"))
    lending_balance = _safe_int(snapshot.get("securities_lending_balance"))
    institutional_net = _safe_int(snapshot.get("institutional_net_buy_sell"))
    bias = "neutral"
    if institutional_net > 0 and short_balance < margin_balance:
        bias = "bullish"
    elif institutional_net < 0 and short_balance >= margin_balance * 0.3:
        bias = "bearish"

    signals = [
        {
            "tone": "positive" if institutional_net > 0 else "caution" if institutional_net < 0 else "neutral",
            "label": "法人方向",
            "value": _signed_value(institutional_net),
        },
        {
            "tone": "neutral",
            "label": "融資餘額",
            "value": f"{margin_balance:,}",
        },
        {
            "tone": "neutral",
            "label": "融券餘額",
            "value": f"{short_balance:,}",
        },
        {
            "tone": "neutral",
            "label": "借券餘額",
            "value": f"{lending_balance:,}",
        },
    ]

    return {
        "bias": bias,
        "headline": f"{snapshot.get('ticker') or 'TW'} 籌碼摘要 / {snapshot.get('snapshot_date') or 'N/A'}",
        "signals": signals,
        "metrics": {
            "margin_balance": margin_balance,
            "short_balance": short_balance,
            "securities_lending_balance": lending_balance,
            "institutional_net_buy_sell": institutional_net,
        },
    }


class TaiwanChipProvider:
    def __init__(
        self,
        fetcher: Optional[Any] = None,
        session: Optional[requests.Session] = None,
        *,
        verify_ssl: bool = False,
    ):
        self._fetcher = fetcher
        self._session = session or requests.Session()
        self._session.headers.update(TWSE_REQUEST_HEADERS)
        self._verify_ssl = verify_ssl
        self._sync_lock = asyncio.Lock()

    async def sync_ticker_snapshot(
        self,
        ticker: str,
        target_date: date | str | None = None,
        *,
        force_refresh: bool = False,
    ) -> Optional[Dict[str, Any]]:
        normalized = normalize_ticker(ticker)
        market = infer_market(normalized)
        if market != "TW":
            return await db.get_taiwan_chip_snapshot(normalized)

        query_date = self._coerce_target_date(target_date)
        existing = await db.get_taiwan_chip_snapshot(normalized, query_date.isoformat())
        if existing and not force_refresh:
            return existing

        sync_result = await self.ensure_daily_snapshot(
            query_date,
            force_refresh=force_refresh,
            allow_fallback=True,
            sources=self._sources_for_ticker(normalized),
        )
        resolved_date = sync_result.get("resolved_date") or query_date.isoformat()
        snapshot = await db.get_taiwan_chip_snapshot(normalized, resolved_date)
        if snapshot:
            return snapshot

        if query_date < TWSE_T86_EARLIEST_DATE:
            return existing

        return await db.get_taiwan_chip_snapshot(normalized)

    async def ensure_daily_snapshot(
        self,
        target_date: date | str | None = None,
        *,
        force_refresh: bool = False,
        allow_fallback: bool = True,
        sources: tuple[str, ...] | None = None,
    ) -> Dict[str, Any]:
        requested_date = self._coerce_target_date(target_date)
        normalized_sources = self._normalize_sources(sources)
        if "twse" in normalized_sources and requested_date < TWSE_T86_EARLIEST_DATE:
            raise ValueError(f"TWSE T86 earliest date is {TWSE_T86_EARLIEST_DATE.isoformat()}")

        requested_iso = requested_date.isoformat()
        if not force_refresh:
            source_counts = await db.get_taiwan_chip_snapshot_source_counts(requested_iso)
            if self._has_required_sources(source_counts, normalized_sources):
                return {
                    "requested_date": requested_iso,
                    "resolved_date": requested_iso,
                    "row_count": sum(source_counts.values()),
                    "source": "local_db",
                }

        async with self._sync_lock:
            if not force_refresh:
                source_counts = await db.get_taiwan_chip_snapshot_source_counts(requested_iso)
                if self._has_required_sources(source_counts, normalized_sources):
                    return {
                        "requested_date": requested_iso,
                        "resolved_date": requested_iso,
                        "row_count": sum(source_counts.values()),
                        "source": "local_db",
                    }

            fetched_results = await asyncio.to_thread(self._fetch_sources_sync, requested_date, normalized_sources)
            merged_snapshots = [
                snapshot
                for result in fetched_results.values()
                for snapshot in result.get("snapshots", [])
            ]
            if merged_snapshots:
                await db.upsert_taiwan_chip_snapshots(merged_snapshots)
                return {
                    "requested_date": requested_iso,
                    "resolved_date": requested_iso,
                    "row_count": len(merged_snapshots),
                    "source": "+".join(
                        result.get("source_name")
                        for result in fetched_results.values()
                        if result.get("snapshots")
                    ),
                    "formats": {
                        source_name: result.get("format_version")
                        for source_name, result in fetched_results.items()
                        if result.get("snapshots")
                    },
                }

            failure_messages = [
                result.get("message")
                for result in fetched_results.values()
                if result.get("message")
            ]
            failure_message = "；".join(dict.fromkeys(failure_messages))
            if allow_fallback:
                fallback = await self._resolve_fallback_snapshot(
                    requested_date,
                    force_refresh=force_refresh,
                    sources=normalized_sources,
                )
                if fallback:
                    fallback["requested_date"] = requested_iso
                    fallback["warning"] = failure_message
                    return fallback

            raise RuntimeError(failure_message or f"No Taiwan chip data available for {requested_iso}")

    async def _resolve_fallback_snapshot(
        self,
        requested_date: date,
        *,
        force_refresh: bool = False,
        sources: tuple[str, ...] | None = None,
    ) -> Optional[Dict[str, Any]]:
        requested_iso = requested_date.isoformat()
        normalized_sources = self._normalize_sources(sources)
        latest_local = await db.get_latest_taiwan_chip_snapshot_date(on_or_before=requested_iso)
        if latest_local:
            return {
                "resolved_date": latest_local,
                "row_count": await db.get_taiwan_chip_snapshot_count(latest_local),
                "source": "local_db",
            }

        for offset in range(1, 15):
            candidate = requested_date - timedelta(days=offset)
            if "twse" in normalized_sources and candidate < TWSE_T86_EARLIEST_DATE:
                break
            candidate_iso = candidate.isoformat()
            if not force_refresh:
                source_counts = await db.get_taiwan_chip_snapshot_source_counts(candidate_iso)
                if self._has_required_sources(source_counts, normalized_sources):
                    return {
                        "resolved_date": candidate_iso,
                        "row_count": sum(source_counts.values()),
                        "source": "local_db",
                    }
            fetched_results = await asyncio.to_thread(self._fetch_sources_sync, candidate, normalized_sources)
            merged_snapshots = [
                snapshot
                for result in fetched_results.values()
                for snapshot in result.get("snapshots", [])
            ]
            if not merged_snapshots:
                continue
            await db.upsert_taiwan_chip_snapshots(merged_snapshots)
            return {
                "resolved_date": candidate_iso,
                "row_count": len(merged_snapshots),
                "source": "+".join(
                    result.get("source_name")
                    for result in fetched_results.values()
                    if result.get("snapshots")
                ),
                "formats": {
                    source_name: result.get("format_version")
                    for source_name, result in fetched_results.items()
                    if result.get("snapshots")
                },
            }
        return None

    def _fetch_sources_sync(self, target_date: date, sources: tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        if "twse" in sources:
            results["twse"] = self._fetch_daily_snapshot_sync(target_date)
        if "tpex" in sources:
            results["tpex"] = self._fetch_tpex_daily_snapshot_sync(target_date)
        return results

    def _fetch_daily_snapshot_sync(self, target_date: date) -> Dict[str, Any]:
        response = self._session.get(
            TWSE_T86_URL,
            params={
                "date": target_date.strftime("%Y%m%d"),
                "selectType": "ALL",
                "response": "json",
            },
            timeout=30,
            verify=self._verify_ssl,
        )
        response.raise_for_status()
        payload = response.json()

        stat = str(payload.get("stat") or "").strip()
        fields = payload.get("fields") or []
        rows = payload.get("data") or []
        if stat != "OK" or not fields or not rows:
            message = stat if stat and stat != "OK" else f"TWSE T86 returned no rows for {target_date.isoformat()}"
            return {
                "snapshots": [],
                "message": message,
                "format_version": None,
                "source_name": OFFICIAL_TWSE_SOURCE,
            }

        normalized_fields = [TWSE_FIELD_ALIASES.get(_canonicalize_twse_field(field), "") for field in fields]
        format_version = "current" if "foreign_ex_dealer_net" in normalized_fields else "legacy"
        snapshots = []
        snapshot_date = target_date.isoformat()
        for row in rows:
            snapshot = self._build_snapshot_from_row(row, normalized_fields, snapshot_date, format_version)
            if snapshot:
                snapshots.append(snapshot)

        return {
            "snapshots": snapshots,
            "message": "",
            "format_version": format_version,
            "source_name": OFFICIAL_TWSE_SOURCE,
        }

    def _fetch_tpex_daily_snapshot_sync(self, target_date: date) -> Dict[str, Any]:
        response = self._session.get(
            TPEX_3ITRADE_URL,
            params={
                "l": "zh-tw",
                "o": "json",
                "d": self._to_roc_date_string(target_date),
                "s": "0,asc",
            },
            timeout=30,
            verify=self._verify_ssl,
            headers=TPEX_REQUEST_HEADERS,
        )
        response.raise_for_status()
        payload = response.json()

        stat = str(payload.get("stat") or "").strip().lower()
        tables = payload.get("tables") or []
        table = tables[0] if tables else {}
        rows = table.get("data") or []
        if stat != "ok" or not rows:
            return {
                "snapshots": [],
                "message": f"TPEX 3itrade returned no rows for {target_date.isoformat()}",
                "format_version": None,
                "source_name": OFFICIAL_TPEX_SOURCE,
            }

        snapshot_date = target_date.isoformat()
        snapshots = []
        for row in rows:
            snapshot = self._build_snapshot_from_row(
                row,
                TPEX_JSON_FIELD_KEYS,
                snapshot_date,
                "current",
                source=OFFICIAL_TPEX_SOURCE,
                default_suffix="TWO",
            )
            if snapshot:
                snapshots.append(snapshot)

        return {
            "snapshots": snapshots,
            "message": "",
            "format_version": "current",
            "source_name": OFFICIAL_TPEX_SOURCE,
        }

    def _build_snapshot_from_row(
        self,
        row: Any,
        normalized_fields: list[str],
        snapshot_date: str,
        format_version: str,
        *,
        source: str = OFFICIAL_TWSE_SOURCE,
        default_suffix: str = "TW",
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(row, list) or not row:
            return None

        row_map: Dict[str, Any] = {}
        for index, key in enumerate(normalized_fields):
            if not key or index >= len(row):
                continue
            row_map[key] = row[index]

        security_code = str(row_map.get("security_code") or "").strip().upper()
        security_name = str(row_map.get("security_name") or "").strip()
        if not security_code:
            return None
        ticker = resolve_taiwan_ticker(security_code) or f"{security_code}.{default_suffix}"

        foreign_ex_buy = _parse_optional_int(row_map.get("foreign_ex_dealer_buy"))
        foreign_ex_sell = _parse_optional_int(row_map.get("foreign_ex_dealer_sell"))
        foreign_ex_net = _parse_optional_int(row_map.get("foreign_ex_dealer_net"))
        foreign_dealer_buy = _parse_optional_int(row_map.get("foreign_dealer_buy"))
        foreign_dealer_sell = _parse_optional_int(row_map.get("foreign_dealer_sell"))
        foreign_dealer_net = _parse_optional_int(row_map.get("foreign_dealer_net"))
        foreign_buy = _parse_optional_int(row_map.get("foreign_buy"))
        foreign_sell = _parse_optional_int(row_map.get("foreign_sell"))
        foreign_net = _parse_optional_int(row_map.get("foreign_net"))

        if foreign_net is None and any(value is not None for value in (foreign_ex_net, foreign_dealer_net)):
            foreign_net = _safe_int(foreign_ex_net) + _safe_int(foreign_dealer_net)
        if foreign_buy is None and any(value is not None for value in (foreign_ex_buy, foreign_dealer_buy)):
            foreign_buy = _safe_int(foreign_ex_buy) + _safe_int(foreign_dealer_buy)
        if foreign_sell is None and any(value is not None for value in (foreign_ex_sell, foreign_dealer_sell)):
            foreign_sell = _safe_int(foreign_ex_sell) + _safe_int(foreign_dealer_sell)

        trust_buy = _parse_optional_int(row_map.get("investment_trust_buy"))
        trust_sell = _parse_optional_int(row_map.get("investment_trust_sell"))
        trust_net = _parse_optional_int(row_map.get("investment_trust_net"))

        dealer_buy = _parse_optional_int(row_map.get("dealer_buy"))
        dealer_sell = _parse_optional_int(row_map.get("dealer_sell"))
        dealer_net = _parse_optional_int(row_map.get("dealer_net"))
        dealer_self_buy = _parse_optional_int(row_map.get("dealer_self_buy"))
        dealer_self_sell = _parse_optional_int(row_map.get("dealer_self_sell"))
        dealer_self_net = _parse_optional_int(row_map.get("dealer_self_net"))
        dealer_hedge_buy = _parse_optional_int(row_map.get("dealer_hedge_buy"))
        dealer_hedge_sell = _parse_optional_int(row_map.get("dealer_hedge_sell"))
        dealer_hedge_net = _parse_optional_int(row_map.get("dealer_hedge_net"))

        if dealer_buy is None and any(value is not None for value in (dealer_self_buy, dealer_hedge_buy)):
            dealer_buy = _safe_int(dealer_self_buy) + _safe_int(dealer_hedge_buy)
        if dealer_sell is None and any(value is not None for value in (dealer_self_sell, dealer_hedge_sell)):
            dealer_sell = _safe_int(dealer_self_sell) + _safe_int(dealer_hedge_sell)
        if dealer_net is None and any(value is not None for value in (dealer_self_net, dealer_hedge_net)):
            dealer_net = _safe_int(dealer_self_net) + _safe_int(dealer_hedge_net)

        institutional_net = _parse_optional_int(row_map.get("institutional_net"))
        if institutional_net is None:
            institutional_net = _safe_int(foreign_net) + _safe_int(trust_net) + _safe_int(dealer_net)

        snapshot = {
            "ticker": ticker,
            "market": "TW",
            "snapshot_date": snapshot_date,
            "margin_balance": None,
            "short_balance": None,
            "securities_lending_balance": None,
            "foreign_net_buy_sell": foreign_net,
            "investment_trust_net_buy_sell": trust_net,
            "dealer_net_buy_sell": dealer_net,
            "institutional_net_buy_sell": institutional_net,
            "source": source,
            "branch_payload": {
                "security_code": security_code,
                "security_name": security_name,
                "format_version": format_version,
                "exchange": "TPEX" if source == OFFICIAL_TPEX_SOURCE else "TWSE",
                "foreign_buy": foreign_buy,
                "foreign_sell": foreign_sell,
                "foreign_net": foreign_net,
                "foreign_ex_dealer_buy": foreign_ex_buy,
                "foreign_ex_dealer_sell": foreign_ex_sell,
                "foreign_ex_dealer_net": foreign_ex_net,
                "foreign_dealer_buy": foreign_dealer_buy,
                "foreign_dealer_sell": foreign_dealer_sell,
                "foreign_dealer_net": foreign_dealer_net,
                "investment_trust_buy": trust_buy,
                "investment_trust_sell": trust_sell,
                "investment_trust_net": trust_net,
                "dealer_buy": dealer_buy,
                "dealer_sell": dealer_sell,
                "dealer_net": dealer_net,
                "dealer_self_buy": dealer_self_buy,
                "dealer_self_sell": dealer_self_sell,
                "dealer_self_net": dealer_self_net,
                "dealer_hedge_buy": dealer_hedge_buy,
                "dealer_hedge_sell": dealer_hedge_sell,
                "dealer_hedge_net": dealer_hedge_net,
                "institutional_net": institutional_net,
            },
        }
        snapshot["summary"] = build_taiwan_chip_summary(snapshot)
        return snapshot

    @staticmethod
    def _coerce_target_date(value: date | str | None) -> date:
        if isinstance(value, date):
            return value
        if isinstance(value, str) and value.strip():
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        return date.today()

    @staticmethod
    def _to_roc_date_string(value: date) -> str:
        return f"{value.year - 1911:03d}/{value.month:02d}/{value.day:02d}"

    @staticmethod
    def _sources_for_ticker(ticker: str) -> tuple[str, ...]:
        if str(ticker or "").strip().upper().endswith(".TWO"):
            return ("tpex",)
        return ("twse",)

    @staticmethod
    def _normalize_sources(sources: tuple[str, ...] | None) -> tuple[str, ...]:
        if not sources:
            return SUPPORTED_SYNC_SOURCES
        normalized = tuple(
            str(source).strip().lower()
            for source in sources
            if str(source).strip().lower() in SUPPORTED_SYNC_SOURCES
        )
        return normalized or SUPPORTED_SYNC_SOURCES

    @staticmethod
    def _has_required_sources(source_counts: Dict[str, int], sources: tuple[str, ...]) -> bool:
        source_aliases = {
            "twse": OFFICIAL_TWSE_SOURCE,
            "tpex": OFFICIAL_TPEX_SOURCE,
        }
        return all(int(source_counts.get(source_aliases[source], 0)) > 0 for source in sources)
