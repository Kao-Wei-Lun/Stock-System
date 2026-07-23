import asyncio
from datetime import datetime, timedelta

import pytest

import main
from cache import AsyncTTLCache


@pytest.mark.anyio
async def test_async_ttl_cache_collapses_concurrent_loads_and_does_not_cache_errors():
    cache = AsyncTTLCache(ttl_seconds=30, max_entries=2)
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return {"ok": True}

    first, second = await asyncio.gather(
        cache.get_or_load("same", loader),
        cache.get_or_load("same", loader),
    )
    assert first == second == {"ok": True}
    assert calls == 1

    async def failing_loader():
        raise RuntimeError("temporary")

    with pytest.raises(RuntimeError):
        await cache.get_or_load("failure", failing_loader)
    assert await cache.get_or_load("failure", loader) == {"ok": True}


def test_ohlc_limit_and_since_are_forwarded_to_indexed_query(client, monkeypatch):
    calls = []

    async def fake_get_ohlcv(ticker, period="1y", interval="1d", **options):
        calls.append((ticker, period, interval, options))
        return [{"date": "2026-07-23T09:31:00+08:00", "close": 101}]

    monkeypatch.setattr(main.db, "get_ohlcv", fake_get_ohlcv)
    monkeypatch.setattr(main.market_data, "_needs_history_backfill", lambda *_: False)
    monkeypatch.setattr(main.market_data, "_has_suspicious_daily_rows", lambda *_: False)

    response = client.get(
        "/api/ohlc/2330.TW?period=1d&interval=1m&limit=120&warmup=250&since=2026-07-23T09:30:00%2B08:00"
    )

    assert response.status_code == 200
    assert response.json()["incremental"] is True
    assert calls == [("2330.TW", "1d", "1m", {"limit": 250, "since": "2026-07-23T09:30:00+08:00"})]


def test_futopt_ohlc_response_is_bounded_without_breaking_legacy_loader(client, monkeypatch):
    start = datetime(2026, 7, 23, 9, 0)

    async def fake_load(*_args, **_kwargs):
        rows = [{"date": (start + timedelta(minutes=index)).isoformat(), "close": index} for index in range(600)]
        return {"ticker": "*TMFF", "data": rows, "refresh_status": "not_needed"}

    monkeypatch.setattr(main.market_data, "load_futopt_ohlc_db_first", fake_load)
    response = client.get("/api/futopt/ohlc/*TMFF?refresh_mode=none&limit=400&warmup=250")

    assert response.status_code == 200
    assert response.json()["row_count"] == 400
    assert response.json()["data"][0]["close"] == 200


def test_snapshot_summary_omits_full_market_rows_and_is_cached(client, monkeypatch):
    asyncio.run(main.market_data._snapshot_summary_cache.clear())
    calls = 0

    async def fake_fetch_snapshot(market, *, refresh=False):
        nonlocal calls
        calls += 1
        return {
            "market": market,
            "date": "2026-07-23",
            "time": "120000",
            "source": "test",
            "summary": {"count": 1000, "advancers": 600, "decliners": 350, "unchanged": 50},
            "data": [{"ticker": "2330.TW"}] * 1000,
        }

    monkeypatch.setattr(main.market_data.fubon_market_snapshot_provider, "fetch_snapshot", fake_fetch_snapshot)
    first = client.get("/api/fubon/snapshot/TSE/summary")
    second = client.get("/api/fubon/snapshot/TSE/summary")

    assert first.status_code == second.status_code == 200
    assert "data" not in first.json()
    assert first.json()["summary"]["count"] == 1000
    assert calls == 1


def test_watchlist_metadata_avoids_quote_and_ohlcv_hydration(client, monkeypatch):
    asyncio.run(main.watchlist._watchlist_metadata_cache.clear())
    calls = []

    async def groups():
        calls.append("groups")
        return [{"id": 1, "name": "Core", "color": "#fff", "items": [
            {"id": 2, "ticker": "2330.TW", "tags": ["AI"], "sort_order": 0},
        ]}]

    async def info(tickers):
        calls.append("info")
        return {"2330.TW": {"name": "台積電"}}

    monkeypatch.setattr(main.db, "get_watchlist_groups", groups)
    monkeypatch.setattr(main.db, "get_stock_info_many", info)
    response = client.get("/api/watchlist/metadata")

    assert response.status_code == 200
    assert response.json()["quotes_included"] is False
    assert response.json()["items"][0]["name"] == "台積電"
    assert calls == ["groups", "info"]


def test_large_json_responses_support_gzip(client):
    response = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"
