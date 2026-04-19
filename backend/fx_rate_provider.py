from __future__ import annotations

import csv
import io
import time
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Sequence

import requests

TAIFEX_DAILY_FX_RATES_URL = "https://www.taifex.com.tw/data_gov/taifex_open_data.asp?data_name=DailyForeignExchangeRates"
_DEFAULT_TIMEOUT_SECONDS = 10
_DEFAULT_CACHE_TTL_SECONDS = 300

_DATE_INDEX = 0
_USD_TWD_INDEX = 1
_CNY_TWD_INDEX = 2
_EUR_USD_INDEX = 3
_USD_JPY_INDEX = 4
_GBP_USD_INDEX = 5
_AUD_USD_INDEX = 6
_USD_HKD_INDEX = 7
_USD_CNY_INDEX = 8
_USD_ZAR_INDEX = 9
_NZD_USD_INDEX = 10
_MIN_COLUMN_COUNT = 11


class TaifexDailyFxRateProvider:
    source_name = "taifex_daily_reference"

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        url: str = TAIFEX_DAILY_FX_RATES_URL,
        timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
        cache_ttl_seconds: int = _DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self._session = session or requests.Session()
        self._url = url
        self._timeout_seconds = timeout_seconds
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cached_payload: Dict[str, Any] | None = None
        self._cached_at = 0.0

    def fetch_latest_rates(self, *, force_refresh: bool = False) -> Dict[str, Any]:
        now = time.monotonic()
        if (
            not force_refresh
            and self._cached_payload is not None
            and (now - self._cached_at) < self._cache_ttl_seconds
        ):
            return deepcopy(self._cached_payload)

        response = self._session.get(self._url, timeout=self._timeout_seconds)
        response.raise_for_status()
        payload = self._parse_csv_bytes(response.content)
        self._cached_payload = payload
        self._cached_at = now
        return deepcopy(payload)

    def _parse_csv_bytes(self, content: bytes) -> Dict[str, Any]:
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header or len(header) < _MIN_COLUMN_COUNT:
            raise ValueError("TAIFEX FX dataset header was missing or incomplete")

        rows = [row for row in reader if any(str(value or "").strip() for value in row)]
        if not rows:
            raise ValueError("TAIFEX FX dataset did not contain any rows")

        latest_row = max(rows, key=lambda row: self._parse_snapshot_date(self._get_cell(row, _DATE_INDEX)))
        snapshot_date = self._parse_snapshot_date(self._get_cell(latest_row, _DATE_INDEX)).isoformat()
        rates_to_twd = self._build_rates_to_twd(latest_row)
        if not rates_to_twd:
            raise ValueError("TAIFEX FX dataset did not produce any usable FX rates")

        return {
            "snapshot_date": snapshot_date,
            "source": self.source_name,
            "rates": rates_to_twd,
            "raw": self._build_raw_mapping(header, latest_row),
        }

    @staticmethod
    def _get_cell(row: Sequence[Any], index: int) -> str:
        if index >= len(row):
            return ""
        return str(row[index] or "").strip()

    @staticmethod
    def _build_raw_mapping(header: Sequence[Any], row: Sequence[Any]) -> Dict[str, Any]:
        return {
            str(column_name or "").strip() or f"column_{index}": row[index] if index < len(row) else None
            for index, column_name in enumerate(header)
        }

    @staticmethod
    def _parse_snapshot_date(value: Any):
        text = str(value or "").strip()
        if len(text) != 8 or not text.isdigit():
            raise ValueError(f"Invalid TAIFEX FX date {value!r}")
        return datetime.strptime(text, "%Y%m%d").date()

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _build_rates_to_twd(self, row: Sequence[Any]) -> List[Dict[str, Any]]:
        usd_to_twd = self._safe_float(self._get_cell(row, _USD_TWD_INDEX))
        cny_to_twd = self._safe_float(self._get_cell(row, _CNY_TWD_INDEX))
        eur_to_usd = self._safe_float(self._get_cell(row, _EUR_USD_INDEX))
        usd_to_jpy = self._safe_float(self._get_cell(row, _USD_JPY_INDEX))
        gbp_to_usd = self._safe_float(self._get_cell(row, _GBP_USD_INDEX))
        aud_to_usd = self._safe_float(self._get_cell(row, _AUD_USD_INDEX))
        usd_to_hkd = self._safe_float(self._get_cell(row, _USD_HKD_INDEX))
        usd_to_cny = self._safe_float(self._get_cell(row, _USD_CNY_INDEX))
        usd_to_zar = self._safe_float(self._get_cell(row, _USD_ZAR_INDEX))
        nzd_to_usd = self._safe_float(self._get_cell(row, _NZD_USD_INDEX))

        if not usd_to_twd or usd_to_twd <= 0:
            raise ValueError("TAIFEX FX dataset is missing USD/TWD")

        usd_value_map: Dict[str, float] = {
            "USD": 1.0,
            "TWD": 1.0 / usd_to_twd,
        }

        candidates = {
            "CNY": (1.0 / usd_to_cny)
            if usd_to_cny and usd_to_cny > 0
            else (cny_to_twd / usd_to_twd if cny_to_twd and cny_to_twd > 0 else None),
            "EUR": eur_to_usd,
            "JPY": (1.0 / usd_to_jpy) if usd_to_jpy and usd_to_jpy > 0 else None,
            "GBP": gbp_to_usd,
            "AUD": aud_to_usd,
            "HKD": (1.0 / usd_to_hkd) if usd_to_hkd and usd_to_hkd > 0 else None,
            "ZAR": (1.0 / usd_to_zar) if usd_to_zar and usd_to_zar > 0 else None,
            "NZD": nzd_to_usd,
        }
        for currency, usd_value in candidates.items():
            if usd_value and usd_value > 0:
                usd_value_map[currency] = usd_value

        twd_value_in_usd = usd_value_map["TWD"]
        rates = []
        for from_currency, usd_value in sorted(usd_value_map.items()):
            if from_currency == "TWD":
                continue
            rate_to_twd = usd_value / twd_value_in_usd
            rates.append(
                {
                    "from_currency": from_currency,
                    "to_currency": "TWD",
                    "rate": round(rate_to_twd, 6),
                    "source": self.source_name,
                }
            )
        return rates
