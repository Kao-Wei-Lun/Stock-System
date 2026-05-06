from __future__ import annotations

from datetime import timezone

import pytest

from taiwan_history_backfill_service import TaiwanHistoryBackfillService


class FakeSnapshotProvider:
    async def fetch_snapshot(self, market, refresh=False):
        data = {
            "TSE": [
                {
                    "ticker": "2330.TW",
                    "symbol": "2330",
                    "market": "TSE",
                    "name": "TSMC",
                    "sector": "Semiconductor",
                    "type": "EQUITY",
                }
            ],
            "OTC": [
                {
                    "ticker": "3374.TWO",
                    "symbol": "3374",
                    "market": "OTC",
                    "name": "Xintec",
                    "sector": "Semiconductor",
                    "type": "EQUITY",
                }
            ],
        }
        return {"date": "2026-05-06", "data": data.get(market, [])}


class FakeDb:
    def __init__(self):
        self.universe = {}
        self.statuses = {}
        self.stock_info = {}
        self.latest_rows = {}

    async def upsert_tw_equity_universe(self, rows):
        for row in rows:
            self.universe[row["ticker"]] = dict(row)
        return len(rows)

    async def deactivate_stale_tw_equities(self, snapshot_date):
        count = 0
        for row in self.universe.values():
            if row.get("latest_snapshot_date") != snapshot_date and row.get("is_active", True):
                row["is_active"] = False
                count += 1
        return count

    async def list_tw_equity_universe(self, active_only=True, include_etf=True, markets=None, limit=None):
        rows = list(self.universe.values())
        if active_only:
            rows = [row for row in rows if row.get("is_active", True)]
        if not include_etf:
            rows = [row for row in rows if not row.get("is_etf")]
        if limit:
            rows = rows[:limit]
        return rows

    async def upsert_stock_info(self, ticker, info):
        self.stock_info[ticker] = dict(info)

    async def get_tw_history_sync_status(self, ticker, interval="1d"):
        return self.statuses.get((ticker, interval))

    async def list_tw_history_sync_status(self, interval=None, status=None, limit=500):
        rows = list(self.statuses.values())
        if interval:
            rows = [row for row in rows if row.get("interval") == interval]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows[:limit]

    async def record_tw_history_sync_status(
        self,
        *,
        ticker,
        interval,
        status,
        requested_start_date=None,
        requested_end_date=None,
        last_success_date=None,
        rows_synced=0,
        error=None,
        source="fubon_neo",
    ):
        key = (ticker, interval)
        previous = self.statuses.get(key, {"attempts": 0, "rows_synced_total": 0})
        next_status = {
            **previous,
            "ticker": ticker,
            "interval": interval,
            "status": status,
            "requested_start_date": requested_start_date,
            "requested_end_date": requested_end_date,
            "last_success_date": last_success_date or previous.get("last_success_date"),
            "last_rows_synced": rows_synced,
            "rows_synced_total": previous.get("rows_synced_total", 0) + rows_synced,
            "attempts": previous.get("attempts", 0) + 1,
            "last_error": error,
            "source": source,
        }
        self.statuses[key] = next_status
        return next_status

    async def get_latest_ohlcv(self, ticker, interval="1d"):
        return self.latest_rows.get((ticker, interval))

    async def get_tw_universe_coverage(self, interval="1d"):
        universe_count = len([row for row in self.universe.values() if row.get("is_active", True)])
        covered_count = len(
            [
                ticker
                for ticker in self.universe
                if (ticker, interval) in self.latest_rows
            ]
        )
        return {
            "interval": interval,
            "universe_count": universe_count,
            "covered_count": covered_count,
            "coverage_pct": round(covered_count / universe_count * 100, 2) if universe_count else 0,
        }


class FakeFetcher:
    def __init__(self, db):
        self.db = db
        self.calls = []

    async def fetch_and_store(self, ticker, period="1y", interval="1d", include_info=False):
        self.calls.append(
            {
                "ticker": ticker,
                "period": period,
                "interval": interval,
                "include_info": include_info,
            }
        )
        self.db.latest_rows[(ticker, interval)] = {"date": "2026-05-06"}
        return 123


@pytest.mark.anyio
async def test_taiwan_history_backfill_syncs_universe_and_history():
    db = FakeDb()
    fetcher = FakeFetcher(db)
    service = TaiwanHistoryBackfillService(
        db=db,
        fetcher=fetcher,
        market_snapshot_provider=FakeSnapshotProvider(),
        app_tz=timezone.utc,
        intervals=("1d", "1wk"),
        request_delay_seconds=0,
    )

    payload = await service.sync_history(reason="test")

    assert payload["source"] == "fubon_neo"
    assert payload["universe"]["count"] == 2
    assert payload["result_count"] == 4
    assert payload["success_count"] == 4
    assert payload["coverage"]["coverage_pct"] == 100
    assert {row["ticker"] for row in db.universe.values()} == {"2330.TW", "3374.TWO"}
    assert db.stock_info["2330.TW"]["longName"] == "TSMC"
    assert all(call["period"] == "max" for call in fetcher.calls)
    assert all(call["include_info"] is False for call in fetcher.calls)

    fetcher.calls.clear()
    payload = await service.sync_history(reason="incremental")

    assert payload["success_count"] == 4
    assert all(call["period"] == "5d" for call in fetcher.calls)
