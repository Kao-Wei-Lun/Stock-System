from datetime import datetime, timezone

import pytest

from futopt_history_service import (
    FutoptCandleRecorder,
    latest_row_to_futopt_period,
    load_futopt_ohlc_db_first,
    merge_futopt_ohlcv_rows,
)


def _row(date_value: str, close: float, source: str = "fubon_neo_ws") -> dict:
    return {
        "date": date_value,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 1,
        "adj_close": close,
        "source": source,
    }


class FakeDb:
    def __init__(self):
        self.rows = {
            ("TMF", "1m"): [_row("2026-07-22T08:45:00+08:00", 100)],
        }
        self.resolutions = []

    async def get_ohlcv(self, ticker, period="1d", interval="1m"):
        return list(self.rows.get((ticker, interval), []))

    async def upsert_ohlcv_batch(self, ticker, rows, interval="1m"):
        current = {str(item["date"]): dict(item) for item in self.rows.get((ticker, interval), [])}
        current.update({str(item["date"]): dict(item) for item in rows})
        self.rows[(ticker, interval)] = [current[key] for key in sorted(current)]
        return len(rows)

    async def save_paper_trading_contract_resolution(self, payload):
        self.resolutions.append(payload)
        return len(self.resolutions)

    async def get_latest_ohlcv(self, ticker, interval="1m"):
        rows = self.rows.get((ticker, interval), [])
        return rows[-1] if rows else None


class FakeProvider:
    def __init__(self):
        self.calls = []

    async def fetch_intraday_ohlc(self, symbol, *, period="1d", interval="1m"):
        self.calls.append({"symbol": symbol, "period": period, "interval": interval})
        return {
            "ticker": "TMFH6",
            "requested_symbol": symbol,
            "resolved_symbol": "TMFH6",
            "contract_type": "I",
            "end_date": "2026-08-19",
            "instrument_type": "future",
            "data": [
                _row("2026-07-22T08:45:00+08:00", 101, "fubon_neo"),
                _row("2026-07-22T08:46:00+08:00", 102, "fubon_neo"),
            ],
        }


class FakeRealtimePool:
    def register_message_handler(self, _handler):
        return None

    def unregister_message_handler(self, _handler):
        return None

    def track_ticker(self, _ticker, source="ws"):
        return None

    def untrack_ticker(self, _ticker, source="ws"):
        return None


def test_merge_futopt_rows_deduplicates_alias_and_contract_series():
    rows = merge_futopt_ohlcv_rows(
        [_row("2026-07-22T08:45:00+08:00", 100)],
        [
            _row("2026-07-22T08:45:00+08:00", 101),
            _row("2026-07-22T08:46:00+08:00", 102),
        ],
    )

    assert [item["close"] for item in rows] == [101, 102]


@pytest.mark.anyio
async def test_db_first_loader_persists_refresh_then_returns_merged_database_rows():
    db = FakeDb()
    provider = FakeProvider()

    payload = await load_futopt_ohlc_db_first(
        provider,
        db,
        "TMF",
        period="1d",
        interval="1m",
    )

    assert payload["ticker"] == "TMF"
    assert payload["resolved_symbol"] == "TMFH6"
    assert payload["data_source"] == "database"
    assert payload["sync_status"] == "refreshed"
    assert payload["storage_tickers"] == ["TMF", "TMFH6"]
    assert [item["close"] for item in payload["data"]] == [101, 102]
    assert ("TMFH6", "1m") in db.rows


@pytest.mark.parametrize(
    ("last_date", "expected"),
    [
        ("2026-07-22T08:00:00+08:00", "1d"),
        ("2026-07-19T08:00:00+08:00", "5d"),
        ("2026-07-10T08:00:00+08:00", "1mo"),
        ("2026-05-20T08:00:00+08:00", "3mo"),
        ("2026-01-01T08:00:00+08:00", "6mo"),
    ],
)
def test_restart_gap_selects_smallest_supported_backfill_period(last_date, expected):
    now = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc).astimezone()
    assert latest_row_to_futopt_period({"date": last_date}, now=now) == expected


@pytest.mark.anyio
async def test_recorder_auto_backfill_uses_database_watermark():
    db = FakeDb()
    db.rows[("TMF", "1m")] = [_row("2026-07-19T08:00:00+08:00", 100)]
    provider = FakeProvider()
    recorder = FutoptCandleRecorder(
        provider=provider,
        db=db,
        realtime_pool=FakeRealtimePool(),
        symbols=("TMF",),
    )

    await recorder.backfill(period=None)

    assert provider.calls[0]["period"] in {"5d", "1mo"}
    assert recorder.get_status()["last_backfill"]["period"] == "auto"
