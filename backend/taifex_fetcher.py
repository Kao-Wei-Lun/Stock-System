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


class TaifexFetcher:
    def __init__(self):
        self._cache: Dict[str, Tuple[float, Dict]] = {}

    async def fetch_dashboard(self, query_date: Optional[date] = None) -> Dict:
        target_date = query_date or datetime.now().date()
        cache_key = _format_iso_date(target_date)
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

        loop = asyncio.get_event_loop()
        payload = await loop.run_in_executor(None, self._fetch_dashboard_sync, target_date)
        self._cache[cache_key] = (time.time(), payload)
        return payload

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

        return {
            "query_date": _format_iso_date(target_date),
            "resolved_date": _format_iso_date(resolved_date),
            "previous_date": _format_iso_date(previous_date) if previous_date else None,
            "overview": overview,
            "futures": futures,
            "options": options,
            "call_puts": call_puts,
            "cash_summary": cash_summary,
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
        return _table_rows(response.text)

    def _fetch_contract_rows(self, page: str, target_date: Optional[date]) -> List[Dict]:
        if not target_date:
            return []
        table = self._post_page(page, target_date)
        if table is None:
            return []

        rows: List[Dict] = []
        for row in table.itertuples(index=False, name=None):
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


taifex_fetcher = TaifexFetcher()
