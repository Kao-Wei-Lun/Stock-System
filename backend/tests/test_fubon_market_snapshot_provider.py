import asyncio

from fubon_market_snapshot_provider import FubonMarketSnapshotProvider


class StubSnapshotManager:
    def __init__(self):
        self.calls = []

    async def fetch_stock_snapshot_quotes(self, *, market="TSE"):
        self.calls.append(("quotes", market))
        return {
            "date": "2026-04-11",
            "time": "133000",
            "market": market,
            "data": [
                {
                    "symbol": "2330",
                    "name": "TSMC",
                    "closePrice": 950,
                    "change": 12,
                    "changePercent": 1.28,
                    "tradeVolume": 25000,
                    "tradeValue": 23750000,
                    "lastUpdated": 1760000000000000,
                },
                {
                    "symbol": "2317",
                    "name": "Hon Hai",
                    "closePrice": 210,
                    "change": -3,
                    "changePercent": -1.41,
                    "tradeVolume": 18000,
                    "tradeValue": 3780000,
                    "lastUpdated": 1760000000000000,
                },
                {
                    "symbol": "2454",
                    "name": "MediaTek",
                    "closePrice": 1245,
                    "change": 0,
                    "changePercent": 0,
                    "tradeVolume": 9000,
                    "tradeValue": 11205000,
                    "lastUpdated": 1760000000000000,
                },
            ],
        }

    async def fetch_stock_snapshot_movers(self, *, market="TSE", direction="up", change="percent"):
        self.calls.append(("movers", market, direction, change))
        return {
            "date": "2026-04-11",
            "time": "133000",
            "market": market,
            "change": change,
            "data": [
                {
                    "symbol": "3008",
                    "name": "Largan",
                    "closePrice": 2500,
                    "change": 120,
                    "changePercent": 5.04,
                    "tradeVolume": 1200,
                    "tradeValue": 3000000,
                    "lastUpdated": 1760000000000000,
                },
                {
                    "symbol": "3661",
                    "name": "Alchip",
                    "closePrice": 4200,
                    "change": 180,
                    "changePercent": 4.48,
                    "tradeVolume": 800,
                    "tradeValue": 3360000,
                    "lastUpdated": 1760000000000000,
                },
            ],
        }

    async def fetch_stock_snapshot_actives(self, *, market="TSE", trade="value"):
        self.calls.append(("actives", market, trade))
        return {
            "date": "2026-04-11",
            "time": "133000",
            "market": market,
            "trade": trade,
            "data": [
                {
                    "symbol": "2330",
                    "name": "TSMC",
                    "closePrice": 950,
                    "change": 12,
                    "changePercent": 1.28,
                    "tradeVolume": 25000,
                    "tradeValue": 23750000,
                    "lastUpdated": 1760000000000000,
                },
            ],
        }


def test_snapshot_provider_normalizes_market_snapshot_rows():
    provider = FubonMarketSnapshotProvider(StubSnapshotManager(), ttl_seconds=60)

    payload = asyncio.run(provider.fetch_snapshot("TSE"))

    assert payload["market"] == "TSE"
    assert payload["summary"] == {
        "count": 3,
        "advancers": 1,
        "decliners": 1,
        "unchanged": 1,
        "total_trade_value": 38735000,
    }
    assert payload["data"][0]["ticker"] == "2330.TW"
    assert payload["data"][1]["ticker"] == "2317.TW"
    assert payload["data"][0]["quote_timestamp"].startswith("2025-")


def test_snapshot_provider_limits_movers_and_caches_results():
    manager = StubSnapshotManager()
    provider = FubonMarketSnapshotProvider(manager, ttl_seconds=60)

    payload = asyncio.run(provider.fetch_movers("TSE", direction="up", change="percent", limit=1))
    cached = asyncio.run(provider.fetch_movers("TSE", direction="up", change="percent", limit=2))

    assert len(payload["data"]) == 1
    assert len(cached["data"]) == 2
    assert manager.calls == [("movers", "TSE", "up", "percent")]


def test_snapshot_provider_fetches_actives():
    manager = StubSnapshotManager()
    provider = FubonMarketSnapshotProvider(manager, ttl_seconds=60)

    payload = asyncio.run(provider.fetch_actives("TSE", trade="value", limit=5))

    assert payload["data"][0]["ticker"] == "2330.TW"
    assert payload["trade"] == "value"
    assert manager.calls == [("actives", "TSE", "value")]
