"""
TAIFEX institutional positions fetcher.
"""

from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests
import urllib3

TAIFEX_BASE_URL = "https://www.taifex.com.tw/cht/3"
TWSE_CASH_SUMMARY_URL = "https://www.twse.com.tw/rwd/zh/fund/BFI82U"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
CACHE_TTL_SECONDS = 300
MAX_LOOKBACK_DAYS = 180
INSTITUTION_ORDER = ["外資", "投信", "自營商"]
TAIFEX_SKIP_COMMODITIES = {"期貨 小計", "期貨合計", "選擇權 小計", "選擇權合計"}
HISTORY_DAY_OPTIONS = {10, 20, 30, 60, 90}

# TAIFEX contract values from official product specification pages.
# Futures / options amounts on the daily institutional pages are in
# thousand NTD, so we convert back to point-based entry prices with:
# price ~= amount * 1000 / (contracts * point_value).
FUTURES_POINT_VALUE = {
    "臺股期貨": 200,
    "小型臺指期貨": 50,
    "微型臺指期貨": 10,
    "電子期貨": 4000,
    "小型電子期貨": 500,
    "金融期貨": 1000,
    "小型金融期貨": 250,
    "非金電期貨": 1000,
    "櫃買指數期貨": 1000,
    "臺灣中型100期貨": 50,
    "臺灣永續期貨": 50,
    "臺灣生技期貨": 50,
    "航運期貨": 50,
    "半導體30期貨": 50,
}

OPTIONS_POINT_VALUE = {
    "臺指選擇權": 50,
    "電子選擇權": 250,
    "金融選擇權": 250,
}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _format_taifex_date(value: date) -> str:
    return value.strftime("%Y/%m/%d")


def _format_iso_date(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def _safe_int(value) -> int:
    if value is None:
        return 0
    text = str(value).strip().replace(",", "")
    if not text or text.lower() == "nan":
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _table_rows(html: str) -> Optional[pd.DataFrame]:
    tables = pd.read_html(StringIO(html))
    if not tables:
        return None
    table = tables[0]
    if table.empty:
        return None
    return table.fillna("")


def _signed_average_price(amount: int, volume: int, point_value: Optional[int]) -> Optional[float]:
    if not point_value or not volume:
        return None
    return round((abs(amount) * 1000) / (abs(volume) * point_value), 2)


def _weighted_average_price(items: Iterable[Tuple[int, Optional[float]]]) -> Optional[float]:
    weighted = 0.0
    weight_sum = 0
    for weight, price in items:
        if not weight or price is None:
            continue
        weighted += abs(weight) * price
        weight_sum += abs(weight)
    if not weight_sum:
        return None
    return round(weighted / weight_sum, 2)


def _round_or_none(value: Optional[float], digits: int = 2) -> Optional[float]:
    return None if value is None else round(value, digits)


def _normalize_cash_institution(name: str) -> Optional[str]:
    if "外資" in name:
        return "外資"
    if "投信" in name:
        return "投信"
    if "自營商" in name:
        return "自營商"
    return None


def _empty_institution_row() -> Dict[str, int]:
    return {name: 0 for name in INSTITUTION_ORDER}


class TaifexFetcher:
    def __init__(self):
        self._dashboard_cache: Dict[str, Tuple[float, Dict]] = {}
        self._page_cache: Dict[str, Tuple[float, Optional[pd.DataFrame]]] = {}
        self._history_cache: Dict[str, Tuple[float, Dict]] = {}

    async def fetch_dashboard(self, query_date: Optional[date] = None) -> Dict:
        target_date = query_date or datetime.now().date()
        cache_key = _format_iso_date(target_date)
        cached = self._dashboard_cache.get(cache_key)
        if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

        loop = asyncio.get_event_loop()
        payload = await loop.run_in_executor(None, self._fetch_dashboard_sync, target_date)
        self._dashboard_cache[cache_key] = (time.time(), payload)
        return payload

    async def fetch_insights(
        self,
        query_date: Optional[date] = None,
        futures_commodity: Optional[str] = None,
        options_commodity: Optional[str] = None,
        days: int = 30,
    ) -> Dict:
        target_date = query_date or datetime.now().date()
        normalized_days = self._normalize_history_days(days)
        cache_key = ":".join(
            [
                _format_iso_date(target_date),
                futures_commodity or "",
                options_commodity or "",
                str(normalized_days),
            ]
        )
        cached = self._history_cache.get(cache_key)
        if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

        loop = asyncio.get_event_loop()
        payload = await loop.run_in_executor(
            None,
            self._fetch_insights_sync,
            target_date,
            futures_commodity,
            options_commodity,
            normalized_days,
        )
        self._history_cache[cache_key] = (time.time(), payload)
        return payload

    def _normalize_history_days(self, days: int) -> int:
        try:
            numeric = int(days)
        except (TypeError, ValueError):
            numeric = 30
        if numeric in HISTORY_DAY_OPTIONS:
            return numeric
        return 30

    def _fetch_dashboard_sync(self, target_date: date) -> Dict:
        resolved_date, overview = self._fetch_first_available("futAndOptDate", target_date)
        futures = self._fetch_contract_rows("futContractsDate", resolved_date)
        options = self._fetch_contract_rows("optContractsDate", resolved_date)
        call_puts = self._fetch_call_put_rows(resolved_date)
        cash_summary = self._fetch_twse_cash_summary(resolved_date)
        previous_date = self._find_previous_available_date(resolved_date)

        previous_overview = self._fetch_overview(previous_date) if previous_date else []
        previous_futures = self._fetch_contract_rows("futContractsDate", previous_date) if previous_date else []
        previous_options = self._fetch_contract_rows("optContractsDate", previous_date) if previous_date else []
        previous_call_puts = self._fetch_call_put_rows(previous_date) if previous_date else []
        previous_cash_summary = self._fetch_twse_cash_summary(previous_date) if previous_date else []

        self._apply_changes(overview, previous_overview, ("institution",))
        self._apply_changes(futures, previous_futures, ("commodity", "institution"))
        self._apply_changes(options, previous_options, ("commodity", "institution"))
        self._apply_changes(call_puts, previous_call_puts, ("commodity", "option_side", "institution"))
        self._apply_cash_changes(cash_summary, previous_cash_summary)

        futures_options = self._collect_commodities(futures)
        options_options = self._collect_commodities(options)
        default_futures = self._default_commodity(futures_options, "臺股期貨")
        default_options = self._default_commodity(options_options, "臺指選擇權")

        return {
            "query_date": _format_iso_date(target_date),
            "resolved_date": _format_iso_date(resolved_date),
            "previous_date": _format_iso_date(previous_date) if previous_date else None,
            "overview": overview,
            "futures": futures,
            "options": options,
            "call_puts": call_puts,
            "cash_summary": cash_summary,
            "cash_summary_aggregated": self._aggregate_cash_summary(cash_summary),
            "futures_commodities": futures_options,
            "options_commodities": options_options,
            "default_futures_commodity": default_futures,
            "default_options_commodity": default_options,
            "leaderboards": self._build_leaderboards(futures, options, call_puts),
            "cost_estimates": self._build_cost_estimates(
                default_futures,
                default_options,
                futures,
                call_puts,
            ),
        }

    def _fetch_insights_sync(
        self,
        target_date: date,
        futures_commodity: Optional[str],
        options_commodity: Optional[str],
        days: int,
    ) -> Dict:
        dashboard = self._fetch_dashboard_sync(target_date)
        resolved_date = datetime.strptime(dashboard["resolved_date"], "%Y-%m-%d").date()

        futures_choice = self._default_commodity(
            dashboard.get("futures_commodities", []),
            futures_commodity or dashboard.get("default_futures_commodity"),
        )
        options_choice = self._default_commodity(
            dashboard.get("options_commodities", []),
            options_commodity or dashboard.get("default_options_commodity"),
        )

        return {
            "query_date": dashboard["query_date"],
            "resolved_date": dashboard["resolved_date"],
            "previous_date": dashboard["previous_date"],
            "days": days,
            "futures_commodity": futures_choice,
            "options_commodity": options_choice,
            "leaderboards": dashboard["leaderboards"],
            "cost_estimates": self._build_cost_estimates(
                futures_choice,
                options_choice,
                dashboard["futures"],
                dashboard["call_puts"],
            ),
            "history": self._build_history(
                self._collect_available_dates(resolved_date, days),
                futures_choice,
                options_choice,
            ),
        }

    def _collect_available_dates(self, target_date: date, days: int) -> List[date]:
        dates: List[date] = []
        cursor = target_date
        attempts = 0
        while len(dates) < days and attempts < MAX_LOOKBACK_DAYS:
            if self._fetch_overview(cursor):
                dates.append(cursor)
            cursor -= timedelta(days=1)
            attempts += 1
        dates.reverse()
        return dates

    def _build_history(self, dates: List[date], futures_commodity: str, options_commodity: str) -> Dict:
        futures_oi_series = []
        futures_trade_series = []
        options_oi_series = []
        call_put_balance_series = []
        cash_net_series = []
        cost_band_series = []

        for current_date in dates:
            futures_rows = [
                row for row in self._fetch_contract_rows("futContractsDate", current_date)
                if row["commodity"] == futures_commodity
            ]
            call_put_rows = [
                row for row in self._fetch_call_put_rows(current_date)
                if row["commodity"] == options_commodity
            ]
            cash_rows = self._aggregate_cash_summary(self._fetch_twse_cash_summary(current_date))
            costs = self._build_cost_estimates(futures_commodity, options_commodity, futures_rows, call_put_rows)

            futures_oi_row = {"date": _format_iso_date(current_date)}
            futures_trade_row = {"date": _format_iso_date(current_date)}
            options_oi_row = {"date": _format_iso_date(current_date)}
            call_put_row = {"date": _format_iso_date(current_date)}
            cash_row = {"date": _format_iso_date(current_date)}

            futures_by_institution = {row["institution"]: row for row in futures_rows}
            options_totals = self._aggregate_option_call_put_rows(call_put_rows)
            call_put_balance = self._call_put_balance_by_institution(call_put_rows)
            cash_by_institution = {row["institution"]: row for row in cash_rows}

            for institution in INSTITUTION_ORDER:
                futures_oi_row[institution] = _safe_int(futures_by_institution.get(institution, {}).get("oi_net_volume"))
                futures_trade_row[institution] = _safe_int(futures_by_institution.get(institution, {}).get("trade_net_volume"))
                options_oi_row[institution] = _safe_int(options_totals.get(institution, 0))
                call_put_row[institution] = _safe_int(call_put_balance.get(institution, 0))
                cash_row[institution] = _safe_int(cash_by_institution.get(institution, {}).get("net_amount"))

            futures_oi_row["合計"] = sum(futures_oi_row[name] for name in INSTITUTION_ORDER)
            futures_trade_row["合計"] = sum(futures_trade_row[name] for name in INSTITUTION_ORDER)
            options_oi_row["合計"] = sum(options_oi_row[name] for name in INSTITUTION_ORDER)
            call_put_row["合計"] = sum(call_put_row[name] for name in INSTITUTION_ORDER)
            cash_row["合計"] = sum(cash_row[name] for name in INSTITUTION_ORDER)

            futures_oi_series.append(futures_oi_row)
            futures_trade_series.append(futures_trade_row)
            options_oi_series.append(options_oi_row)
            call_put_balance_series.append(call_put_row)
            cash_net_series.append(cash_row)
            cost_band_series.append(
                {
                    "date": _format_iso_date(current_date),
                    "法人合成": costs["futures"]["institution_estimate"]["price"],
                    "散戶推估": costs["futures"]["retail_estimate"]["price"],
                    "成本帶低": costs["futures"]["band_low"],
                    "成本帶高": costs["futures"]["band_high"],
                }
            )

        return {
            "futures_oi": futures_oi_series,
            "futures_trade": futures_trade_series,
            "options_oi": options_oi_series,
            "call_put_balance": call_put_balance_series,
            "cash_net": cash_net_series,
            "cost_band": cost_band_series,
        }

    def _fetch_first_available(self, page: str, target_date: date) -> Tuple[date, List[Dict]]:
        for offset in range(0, 15):
            candidate = target_date - timedelta(days=offset)
            rows = self._fetch_page_rows(page, candidate)
            if rows:
                return candidate, rows
        return target_date, []

    def _find_previous_available_date(self, target_date: date) -> Optional[date]:
        for offset in range(1, 15):
            candidate = target_date - timedelta(days=offset)
            rows = self._fetch_page_rows("futAndOptDate", candidate)
            if rows:
                return candidate
        return None

    def _fetch_page_rows(self, page: str, target_date: date) -> List[Dict]:
        if page == "futAndOptDate":
            return self._fetch_overview(target_date)
        if page == "futContractsDate":
            return self._fetch_contract_rows(page, target_date)
        if page == "optContractsDate":
            return self._fetch_contract_rows(page, target_date)
        if page == "callsAndPutsDate":
            return self._fetch_call_put_rows(target_date)
        return []

    def _post_page(self, page: str, target_date: date, commodity_id: str = "") -> Optional[pd.DataFrame]:
        cache_key = f"{page}:{_format_iso_date(target_date)}:{commodity_id}"
        cached = self._page_cache.get(cache_key)
        if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

        payload = {
            "queryType": "1",
            "goDay": "",
            "doQuery": "1",
            "dateaddcnt": "",
            "queryDate": _format_taifex_date(target_date),
        }
        if page in {"futContractsDate", "optContractsDate", "callsAndPutsDate"}:
            payload["commodityId"] = commodity_id

        response = requests.post(
            f"{TAIFEX_BASE_URL}/{page}",
            data=payload,
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        if response.status_code >= 400:
            response.raise_for_status()
        table = _table_rows(response.text)
        self._page_cache[cache_key] = (time.time(), table)
        return table

    def _fetch_contract_rows(self, page: str, target_date: Optional[date]) -> List[Dict]:
        if not target_date:
            return []
        table = self._post_page(page, target_date)
        if table is None:
            return []

        rows: List[Dict] = []
        for row in table.itertuples(index=False, name=None):
            if len(row) < 15:
                continue
            rows.append(
                {
                    "rank": _safe_int(row[0]),
                    "commodity": str(row[1]).strip(),
                    "institution": str(row[2]).strip(),
                    "trade_long_volume": _safe_int(row[3]),
                    "trade_long_amount": _safe_int(row[4]),
                    "trade_short_volume": _safe_int(row[5]),
                    "trade_short_amount": _safe_int(row[6]),
                    "trade_net_volume": _safe_int(row[7]),
                    "trade_net_amount": _safe_int(row[8]),
                    "oi_long_volume": _safe_int(row[9]),
                    "oi_long_amount": _safe_int(row[10]),
                    "oi_short_volume": _safe_int(row[11]),
                    "oi_short_amount": _safe_int(row[12]),
                    "oi_net_volume": _safe_int(row[13]),
                    "oi_net_amount": _safe_int(row[14]),
                }
            )
        return rows

    def _fetch_overview(self, target_date: Optional[date]) -> List[Dict]:
        if not target_date:
            return []
        table = self._post_page("futAndOptDate", target_date)
        if table is None:
            return []

        rows: List[Dict] = []
        for row in table.itertuples(index=False, name=None):
            if len(row) < 13:
                continue
            rows.append(
                {
                    "institution": str(row[0]).strip(),
                    "trade_long_futures_volume": _safe_int(row[1]),
                    "trade_long_options_volume": _safe_int(row[2]),
                    "trade_long_futures_amount": _safe_int(row[3]),
                    "trade_long_options_amount": _safe_int(row[4]),
                    "trade_short_futures_volume": _safe_int(row[5]),
                    "trade_short_options_volume": _safe_int(row[6]),
                    "trade_short_futures_amount": _safe_int(row[7]),
                    "trade_short_options_amount": _safe_int(row[8]),
                    "trade_net_futures_volume": _safe_int(row[9]),
                    "trade_net_options_volume": _safe_int(row[10]),
                    "trade_net_futures_amount": _safe_int(row[11]),
                    "trade_net_options_amount": _safe_int(row[12]),
                }
            )
        return rows

    def _fetch_call_put_rows(self, target_date: Optional[date]) -> List[Dict]:
        if not target_date:
            return []
        table = self._post_page("callsAndPutsDate", target_date)
        if table is None:
            return []

        rows: List[Dict] = []
        for row in table.itertuples(index=False, name=None):
            if len(row) < 16:
                continue
            rows.append(
                {
                    "rank": _safe_int(row[0]),
                    "commodity": str(row[1]).strip(),
                    "option_side": str(row[2]).strip(),
                    "institution": str(row[3]).strip(),
                    "trade_buy_volume": _safe_int(row[4]),
                    "trade_buy_amount": _safe_int(row[5]),
                    "trade_sell_volume": _safe_int(row[6]),
                    "trade_sell_amount": _safe_int(row[7]),
                    "trade_net_volume": _safe_int(row[8]),
                    "trade_net_amount": _safe_int(row[9]),
                    "oi_buy_volume": _safe_int(row[10]),
                    "oi_buy_amount": _safe_int(row[11]),
                    "oi_sell_volume": _safe_int(row[12]),
                    "oi_sell_amount": _safe_int(row[13]),
                    "oi_net_volume": _safe_int(row[14]),
                    "oi_net_amount": _safe_int(row[15]),
                }
            )
        return rows

    def _fetch_twse_cash_summary(self, target_date: Optional[date]) -> List[Dict]:
        if not target_date:
            return []
        response = requests.get(
            TWSE_CASH_SUMMARY_URL,
            params={
                "dayDate": target_date.strftime("%Y%m%d"),
                "response": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=20,
            verify=False,
        )
        payload = response.json()
        rows = []
        for raw_row in payload.get("data") or []:
            if len(raw_row) < 4:
                continue
            rows.append(
                {
                    "institution": str(raw_row[0]).strip(),
                    "buy_amount": _safe_int(raw_row[1]),
                    "sell_amount": _safe_int(raw_row[2]),
                    "net_amount": _safe_int(raw_row[3]),
                }
            )
        return rows

    def _apply_changes(
        self,
        current_rows: List[Dict],
        previous_rows: List[Dict],
        key_fields: Iterable[str],
    ) -> None:
        previous_map = {
            tuple(row.get(field) for field in key_fields): row
            for row in previous_rows
        }
        tracked_fields = [
            "trade_net_volume",
            "trade_net_amount",
            "oi_net_volume",
            "oi_net_amount",
            "trade_net_futures_volume",
            "trade_net_options_volume",
            "trade_net_futures_amount",
            "trade_net_options_amount",
        ]

        for row in current_rows:
            key = tuple(row.get(field) for field in key_fields)
            previous = previous_map.get(key, {})
            for field in tracked_fields:
                if field in row:
                    row[f"{field}_change"] = _safe_int(row.get(field)) - _safe_int(previous.get(field))

    def _apply_cash_changes(self, current_rows: List[Dict], previous_rows: List[Dict]) -> None:
        previous_map = {row["institution"]: row for row in previous_rows}
        for row in current_rows:
            previous = previous_map.get(row["institution"], {})
            row["net_amount_change"] = _safe_int(row["net_amount"]) - _safe_int(previous.get("net_amount"))

    def _collect_commodities(self, rows: List[Dict]) -> List[str]:
        return [
            commodity
            for commodity in dict.fromkeys(row["commodity"] for row in rows)
            if commodity and commodity not in TAIFEX_SKIP_COMMODITIES
        ]

    def _default_commodity(self, choices: List[str], preferred: Optional[str]) -> str:
        if preferred and preferred in choices:
            return preferred
        if not choices:
            return preferred or ""
        if "臺股期貨" in choices:
            return "臺股期貨"
        if "臺指選擇權" in choices:
            return "臺指選擇權"
        return choices[0]

    def _aggregate_cash_summary(self, rows: List[Dict]) -> List[Dict]:
        grouped = {name: 0 for name in INSTITUTION_ORDER}
        for row in rows:
            normalized = _normalize_cash_institution(str(row.get("institution", "")))
            if not normalized:
                continue
            grouped[normalized] += _safe_int(row.get("net_amount"))
        return [
            {
                "institution": name,
                "net_amount": grouped[name],
            }
            for name in INSTITUTION_ORDER
        ]

    def _build_leaderboards(self, futures: List[Dict], options: List[Dict], call_puts: List[Dict]) -> Dict:
        filtered_futures = [row for row in futures if row["commodity"] not in TAIFEX_SKIP_COMMODITIES]
        filtered_options = [row for row in options if row["commodity"] not in TAIFEX_SKIP_COMMODITIES]
        filtered_call_puts = [row for row in call_puts if row["commodity"] not in TAIFEX_SKIP_COMMODITIES]

        long_rank = sorted(
            [row for row in filtered_futures if row["oi_net_volume"] > 0],
            key=lambda row: row["oi_net_volume"],
            reverse=True,
        )[:10]
        short_rank = sorted(
            [row for row in filtered_futures if row["oi_net_volume"] < 0],
            key=lambda row: row["oi_net_volume"],
        )[:10]
        trade_long_rank = sorted(
            [row for row in filtered_futures if row["trade_net_volume"] > 0],
            key=lambda row: row["trade_net_volume"],
            reverse=True,
        )[:10]
        trade_short_rank = sorted(
            [row for row in filtered_futures if row["trade_net_volume"] < 0],
            key=lambda row: row["trade_net_volume"],
        )[:10]
        option_abs_rank = sorted(
            filtered_options,
            key=lambda row: abs(row["oi_net_volume"]),
            reverse=True,
        )[:10]
        call_put_abs_rank = sorted(
            filtered_call_puts,
            key=lambda row: abs(row["oi_net_volume"]),
            reverse=True,
        )[:10]

        return {
            "futures_long": long_rank,
            "futures_short": short_rank,
            "futures_trade_long": trade_long_rank,
            "futures_trade_short": trade_short_rank,
            "options_abs": option_abs_rank,
            "call_put_abs": call_put_abs_rank,
        }

    def _aggregate_option_call_put_rows(self, rows: List[Dict]) -> Dict[str, int]:
        totals = _empty_institution_row()
        for row in rows:
            institution = row.get("institution")
            if institution not in totals:
                continue
            totals[institution] += _safe_int(row.get("oi_net_volume"))
        return totals

    def _call_put_balance_by_institution(self, rows: List[Dict]) -> Dict[str, int]:
        balance = _empty_institution_row()
        for institution in INSTITUTION_ORDER:
            call_value = sum(
                _safe_int(row.get("oi_net_volume"))
                for row in rows
                if row.get("institution") == institution and row.get("option_side") == "買權"
            )
            put_value = sum(
                _safe_int(row.get("oi_net_volume"))
                for row in rows
                if row.get("institution") == institution and row.get("option_side") == "賣權"
            )
            balance[institution] = call_value - put_value
        return balance

    def _build_cost_estimates(
        self,
        futures_commodity: str,
        options_commodity: str,
        futures_rows: List[Dict],
        call_put_rows: List[Dict],
    ) -> Dict:
        selected_futures = [
            row for row in futures_rows
            if row.get("commodity") == futures_commodity
        ]
        selected_call_puts = [
            row for row in call_put_rows
            if row.get("commodity") == options_commodity
        ]

        future_point_value = FUTURES_POINT_VALUE.get(futures_commodity)
        option_point_value = OPTIONS_POINT_VALUE.get(options_commodity)

        band_candidates: List[float] = []
        long_weights: List[Tuple[int, Optional[float]]] = []
        short_weights: List[Tuple[int, Optional[float]]] = []
        dominant_weights: List[Tuple[int, Optional[float]]] = []
        total_net = 0
        institution_rows = []

        for institution in INSTITUTION_ORDER:
            row = next((item for item in selected_futures if item.get("institution") == institution), None)
            if not row:
                institution_rows.append(
                    {
                        "institution": institution,
                        "net_volume": 0,
                        "dominant_side": "中性",
                        "avg_long_price": None,
                        "avg_short_price": None,
                        "dominant_price": None,
                    }
                )
                continue

            avg_long = _signed_average_price(
                row.get("oi_long_amount", 0),
                row.get("oi_long_volume", 0),
                future_point_value,
            )
            avg_short = _signed_average_price(
                row.get("oi_short_amount", 0),
                row.get("oi_short_volume", 0),
                future_point_value,
            )
            if avg_long is not None:
                band_candidates.append(avg_long)
                long_weights.append((_safe_int(row.get("oi_long_volume")), avg_long))
            if avg_short is not None:
                band_candidates.append(avg_short)
                short_weights.append((_safe_int(row.get("oi_short_volume")), avg_short))

            net_volume = _safe_int(row.get("oi_net_volume"))
            total_net += net_volume
            if net_volume > 0:
                dominant_side = "多"
                dominant_price = avg_long
            elif net_volume < 0:
                dominant_side = "空"
                dominant_price = avg_short
            else:
                dominant_side = "中性"
                dominant_price = avg_long or avg_short

            if dominant_price is not None:
                dominant_weights.append((abs(net_volume), dominant_price))

            institution_rows.append(
                {
                    "institution": institution,
                    "net_volume": net_volume,
                    "dominant_side": dominant_side,
                    "avg_long_price": avg_long,
                    "avg_short_price": avg_short,
                    "dominant_price": dominant_price,
                }
            )

        institution_side = "多" if total_net > 0 else "空" if total_net < 0 else "中性"
        institution_price = _weighted_average_price(dominant_weights)
        retail_side = "空" if institution_side == "多" else "多" if institution_side == "空" else "中性"
        retail_price = _weighted_average_price(
            short_weights if institution_side == "多" else long_weights if institution_side == "空" else []
        )
        if retail_price is None:
            retail_price = institution_price

        option_rows = []
        for institution in INSTITUTION_ORDER:
            inst_rows = [row for row in selected_call_puts if row.get("institution") == institution]
            call_row = next((row for row in inst_rows if row.get("option_side") == "買權"), None)
            put_row = next((row for row in inst_rows if row.get("option_side") == "賣權"), None)
            option_rows.append(
                {
                    "institution": institution,
                    "call_oi_net": _safe_int(call_row.get("oi_net_volume", 0) if call_row else 0),
                    "put_oi_net": _safe_int(put_row.get("oi_net_volume", 0) if put_row else 0),
                    "call_avg_buy": _signed_average_price(
                        call_row.get("oi_buy_amount", 0) if call_row else 0,
                        call_row.get("oi_buy_volume", 0) if call_row else 0,
                        option_point_value,
                    ),
                    "put_avg_buy": _signed_average_price(
                        put_row.get("oi_buy_amount", 0) if put_row else 0,
                        put_row.get("oi_buy_volume", 0) if put_row else 0,
                        option_point_value,
                    ),
                    "balance": _safe_int(call_row.get("oi_net_volume", 0) if call_row else 0)
                    - _safe_int(put_row.get("oi_net_volume", 0) if put_row else 0),
                }
            )

        return {
            "futures": {
                "commodity": futures_commodity,
                "point_value": future_point_value,
                "band_low": _round_or_none(min(band_candidates) if band_candidates else None),
                "band_high": _round_or_none(max(band_candidates) if band_candidates else None),
                "institution_estimate": {
                    "side": institution_side,
                    "price": institution_price,
                    "net_volume": total_net,
                },
                "retail_estimate": {
                    "side": retail_side,
                    "price": retail_price,
                    "net_volume": abs(total_net),
                },
                "institutions": institution_rows,
            },
            "options": {
                "commodity": options_commodity,
                "point_value": option_point_value,
                "institutions": option_rows,
            },
        }


taifex_fetcher = TaifexFetcher()
