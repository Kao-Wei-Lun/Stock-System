import copy
import requests

import pytest

import main
from fundamentals_provider import FundamentalsProvider, build_fundamental_summary
from market_intelligence import MacroSnapshotProvider, MarketEventProvider, NewsProvider
from screener_engine import normalize_screener_filters
from taiwan_chip_provider import build_taiwan_chip_summary


class StubResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Client Error", response=self)
        return None

    def json(self):
        return self._payload


class StubSession:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.headers = {}

    def get(self, *_args, **_kwargs):
        return StubResponse(self.payload, status_code=self.status_code)


@pytest.mark.anyio
async def test_market_event_provider_normalizes_yahoo_payload():
    provider = MarketEventProvider(
        session=StubSession(
            {
                "quoteSummary": {
                    "result": [
                        {
                            "calendarEvents": {
                                "earnings": {
                                    "earningsDate": [{"raw": 1775001600}],
                                }
                            },
                            "summaryDetail": {
                                "exDividendDate": {"raw": 1775606400},
                            },
                        }
                    ]
                }
            }
        )
    )

    items = provider._fetch_ticker_events_sync("AAPL")

    assert [item["event_type"] for item in items] == ["earnings", "ex_dividend"]
    assert items[0]["event_date"] == "2026-04-01"
    assert items[1]["source"] == "yahoo_finance"


def test_news_provider_normalizes_search_payload():
    provider = NewsProvider(
        session=StubSession(
            {
                "news": [
                    {
                        "title": "Apple expands AI rollout",
                        "link": "https://example.com/apple-ai",
                        "providerPublishTime": 1775001600,
                        "publisher": "Reuters",
                    }
                ]
            }
        )
    )

    items = provider._fetch_ticker_news_sync("AAPL", 5)

    assert items[0]["ticker"] == "AAPL"
    assert items[0]["published_at"].startswith("2026-04-01")
    assert items[0]["summary"] == "Reuters"


def test_market_event_provider_returns_empty_when_quote_summary_is_unauthorized():
    provider = MarketEventProvider(session=StubSession({}, status_code=401))

    items = provider._fetch_ticker_events_sync("AAPL")

    assert items == []


def test_fundamentals_provider_returns_empty_when_quote_summary_is_unauthorized():
    provider = FundamentalsProvider(session=StubSession({}, status_code=401))

    info = provider._fetch_ticker_fundamentals_sync("AAPL")

    assert info == {}


@pytest.mark.anyio
async def test_macro_snapshot_provider_persists_normalized_payload(monkeypatch):
    persisted = {}

    class StubFetcher:
        async def fetch_realtime_quote(self, ticker):
            return {
                "ticker": ticker,
                "price": 20.5,
                "change_pct": 1.2,
                "quote_timestamp": "2026-04-02T00:00:00+00:00",
                "is_delayed": True,
                "source": "yahoo_finance",
            }

    async def upsert_macro_snapshots(items):
        persisted["items"] = copy.deepcopy(items)
        return len(items)

    async def list_macro_snapshots(_snapshot_date=None):
        return copy.deepcopy(persisted["items"])

    monkeypatch.setattr(main.db, "upsert_macro_snapshots", upsert_macro_snapshots)
    monkeypatch.setattr(main.db, "list_macro_snapshots", list_macro_snapshots)

    provider = MacroSnapshotProvider(fetcher=StubFetcher())
    items = await provider.sync_macro_snapshots()

    assert len(items) >= 5
    assert any(item["metric_code"] == "VIX" for item in items)
    assert all(item["source"] == "yahoo_finance" for item in items)


def test_build_macro_dashboard_payload_summarizes_regime_and_posture():
    risk_off_payload = main.build_macro_dashboard_payload(
        [
            {"metric_code": "VIX", "value": 29.4, "change_pct": 1.1, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "US10Y", "value": 4.61, "change_pct": 0.3, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "DXY", "value": 104.1, "change_pct": 0.82, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "SOX", "value": 4500, "change_pct": -2.1, "date": "2026-04-02", "source": "local_db"},
        ]
    )
    trend_payload = main.build_macro_dashboard_payload(
        [
            {"metric_code": "VIX", "value": 14.8, "change_pct": -1.5, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "US10Y", "value": 4.02, "change_pct": -0.2, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "DXY", "value": 102.4, "change_pct": -0.61, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "SOX", "value": 4700, "change_pct": 1.9, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "TWII", "value": 21200, "change_pct": 0.91, "date": "2026-04-02", "source": "local_db"},
        ]
    )

    assert risk_off_payload["summary"]["overall_risk"] == "high"
    assert risk_off_payload["summary"]["regime"] == "risk_off"
    assert risk_off_payload["summary"]["trade_posture"] == "defensive"
    assert risk_off_payload["summary"]["risk_score"] >= 4

    assert trend_payload["summary"]["overall_risk"] == "low"
    assert trend_payload["summary"]["regime"] == "trend_supportive"
    assert trend_payload["summary"]["trade_posture"] == "offensive"
    assert len(trend_payload["summary"]["tailwinds"]) >= 2


def test_fundamental_and_chip_summary_builders():
    fundamental_summary = build_fundamental_summary(
        {
            "ticker": "AAPL",
            "name": "Apple",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "pe_ratio": 16.2,
            "dividend_yield": 0.005,
            "updated_at": "2026-04-02T00:00:00+00:00",
        },
        [{"event_type": "earnings", "title": "AAPL Earnings", "event_date": "2026-04-25"}],
    )
    chip_summary = build_taiwan_chip_summary(
        {
            "ticker": "2330.TW",
            "snapshot_date": "2026-04-02",
            "margin_balance": 120000,
            "short_balance": 15000,
            "securities_lending_balance": 42000,
            "institutional_net_buy_sell": 18000,
        }
    )

    assert any(signal["label"] == "近期事件" for signal in fundamental_summary["signals"])
    assert chip_summary["bias"] == "bullish"


def test_normalize_screener_filters_coerces_numeric_fields():
    filters = normalize_screener_filters(
        {
            "market": "tw",
            "min_price": "100",
            "min_volume_ratio": "1.8",
            "min_setup_quality": "4",
            "decision_verdict": "priority",
            "upcoming_event_days": "7",
            "limit": "500",
        }
    )

    assert filters["market"] == "TW"
    assert filters["min_price"] == 100
    assert filters["min_volume_ratio"] == 1.8
    assert filters["min_setup_quality"] == 4
    assert filters["decision_verdict"] == "priority"
    assert filters["upcoming_event_days"] == 7
    assert filters["limit"] == 200


@pytest.fixture
def intelligence_store(monkeypatch):
    store = {
        "events": [
            {
                "id": 1,
                "ticker": "AAPL",
                "event_type": "earnings",
                "title": "AAPL Earnings",
                "event_date": "2026-04-10",
                "importance": "high",
            }
        ],
        "news": [
            {
                "id": 2,
                "ticker": "AAPL",
                "title": "Apple expands AI rollout",
                "published_at": "2026-04-02T00:00:00+00:00",
                "source": "Reuters",
                "url": "https://example.com/apple-ai",
            }
        ],
        "macro": [
            {
                "metric_code": "VIX",
                "metric_name": "CBOE Volatility Index",
                "value": 29.4,
                "change_pct": 1.1,
                "date": "2026-04-02",
                "source": "yahoo_finance",
            }
        ],
        "fundamentals": {
            "ticker": "AAPL",
            "name": "Apple",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "pe_ratio": 19.4,
            "dividend_yield": 0.006,
            "updated_at": "2026-04-02T00:00:00+00:00",
        },
        "chips": {
            "ticker": "2330.TW",
            "snapshot_date": "2026-04-02",
            "margin_balance": 120000,
            "short_balance": 15000,
            "securities_lending_balance": 42000,
            "institutional_net_buy_sell": 18000,
            "summary": {
                "bias": "bullish",
                "signals": [{"label": "法人方向", "value": "+18,000"}],
            },
        },
        "presets": [],
    }

    async def list_market_events(ticker=None, date_from=None, date_to=None, limit=100):
        items = [item for item in store["events"] if not ticker or item["ticker"] == ticker]
        return items[:limit]

    async def list_news_articles(ticker=None, limit=50):
        items = [item for item in store["news"] if not ticker or item["ticker"] == ticker]
        return items[:limit]

    async def list_macro_snapshots(snapshot_date=None):
        return store["macro"]

    async def get_stock_info(ticker):
        return store["fundamentals"] if ticker == "AAPL" else None

    async def get_taiwan_chip_snapshot(ticker, snapshot_date=None):
        return store["chips"] if ticker == "2330.TW" else None

    async def list_screener_presets(owner_id=1):
        return copy.deepcopy(store["presets"])

    async def create_screener_preset(payload, owner_id=1):
        record = {"id": 9, "owner_id": owner_id, **payload}
        store["presets"].append(record)
        return record

    async def update_screener_preset(preset_id, payload, owner_id=1):
        return {"id": preset_id, "owner_id": owner_id, **payload}

    async def delete_screener_preset(preset_id, owner_id=1):
        return True

    async def sync_ticker_events(ticker):
        return await list_market_events(ticker=ticker)

    async def sync_ticker_news(ticker, limit=10):
        return await list_news_articles(ticker=ticker, limit=limit)

    async def sync_macro_snapshots():
        return await list_macro_snapshots()

    async def sync_ticker_fundamentals(ticker):
        return await get_stock_info(ticker)

    async def sync_ticker_snapshot(ticker, target_date=None, force_refresh=False):
        return await get_taiwan_chip_snapshot(
            ticker,
            snapshot_date=target_date.isoformat() if target_date else None,
        )

    async def run_screener(filters=None):
        return {
            "filters": filters or {},
            "items": [
                {
                    "ticker": "AAPL",
                    "market": "US",
                    "name": "Apple",
                    "score": 88,
                    "base_score": 82,
                    "macro_adjustment": 6,
                    "setup_quality": 4,
                    "change_pct": 2.3,
                }
            ],
            "market_context": {
                "overall_risk": "medium",
                "trade_posture": "selective",
                "decision_hint": "環境偏震盪，只做最強標的，並縮小部位與嚴守停損。",
            },
            "total": 1,
            "generated_at": "2026-04-02T00:00:00Z",
        }

    monkeypatch.setattr(main.db, "list_market_events", list_market_events)
    monkeypatch.setattr(main.db, "list_news_articles", list_news_articles)
    monkeypatch.setattr(main.db, "list_macro_snapshots", list_macro_snapshots)
    monkeypatch.setattr(main.db, "get_stock_info", get_stock_info)
    monkeypatch.setattr(main.db, "get_taiwan_chip_snapshot", get_taiwan_chip_snapshot)
    monkeypatch.setattr(main.db, "list_screener_presets", list_screener_presets)
    monkeypatch.setattr(main.db, "create_screener_preset", create_screener_preset)
    monkeypatch.setattr(main.db, "update_screener_preset", update_screener_preset)
    monkeypatch.setattr(main.db, "delete_screener_preset", delete_screener_preset)
    monkeypatch.setattr(main.market_event_provider, "sync_ticker_events", sync_ticker_events)
    monkeypatch.setattr(main.news_provider, "sync_ticker_news", sync_ticker_news)
    monkeypatch.setattr(main.macro_snapshot_provider, "sync_macro_snapshots", sync_macro_snapshots)
    monkeypatch.setattr(main.fundamentals_provider, "sync_ticker_fundamentals", sync_ticker_fundamentals)
    monkeypatch.setattr(main.taiwan_chip_provider, "sync_ticker_snapshot", sync_ticker_snapshot)
    monkeypatch.setattr(main.screener_engine, "run", run_screener)

    return store


def test_market_intelligence_routes(client, intelligence_store):
    events_response = client.get("/api/events/calendar?days=14")
    assert events_response.status_code == 200
    assert events_response.json()["items"][0]["title"] == "AAPL Earnings"

    news_response = client.get("/api/news/AAPL")
    assert news_response.status_code == 200
    assert news_response.json()["items"][0]["source"] == "Reuters"

    macro_response = client.get("/api/market/macro")
    assert macro_response.status_code == 200
    assert macro_response.json()["summary"]["overall_risk"] in {"medium", "high"}
    assert macro_response.json()["summary"]["trade_posture"] in {"selective", "defensive"}
    assert macro_response.json()["summary"]["decision_hint"]

    fundamentals_response = client.get("/api/fundamentals/AAPL")
    assert fundamentals_response.status_code == 200
    assert fundamentals_response.json()["detail"]["sector"] == "Technology"

    chips_response = client.get("/api/tw/chips/2330")
    assert chips_response.status_code == 200
    assert chips_response.json()["summary"]["bias"] == "bullish"

    screener_response = client.post("/api/screener/run", json={"filters": {"market": "US"}})
    assert screener_response.status_code == 200
    assert screener_response.json()["items"][0]["ticker"] == "AAPL"
    assert screener_response.json()["market_context"]["trade_posture"] == "selective"


def test_taiwan_chip_route_returns_404_when_official_data_is_unavailable(client, intelligence_store, monkeypatch):
    async def get_taiwan_chip_snapshot(_ticker, snapshot_date=None):
        return None

    async def sync_ticker_snapshot(_ticker, target_date=None, force_refresh=False):
        return None

    monkeypatch.setattr(main.db, "get_taiwan_chip_snapshot", get_taiwan_chip_snapshot)
    monkeypatch.setattr(main.taiwan_chip_provider, "sync_ticker_snapshot", sync_ticker_snapshot)

    response = client.get("/api/tw/chips/2330?refresh=true")

    assert response.status_code == 404
    assert "No official Taiwan chip data available" in response.json()["detail"]


def test_tradingview_screener_wrapper_route_injects_environment(client, monkeypatch):
    class FakeResponse:
        status_code = 200
        text = "<html><head><title>TV</title></head><body>ok</body></html>"

        def raise_for_status(self):
            return None

    captured = {}

    def fake_get(url, timeout=0, headers=None):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr(main.intelligence.requests, "get", fake_get)

    response = client.get("/api/tradingview/widgets/screener?locale=zh_TW")

    assert response.status_code == 200
    assert "window.environment='battle';" in response.text
    assert "self.environment='battle';" in response.text
    assert captured["url"].endswith("/embed-widget/screener/?locale=zh_TW")
    assert captured["timeout"] == 10


def test_screener_preset_routes(client, intelligence_store):
    create_response = client.post(
        "/api/screener/presets",
        json={"name": "Momentum", "description": "Saved", "filters": {"market": "US"}},
    )
    assert create_response.status_code == 200
    assert create_response.json()["name"] == "Momentum"

    list_response = client.get("/api/screener/presets")
    assert list_response.status_code == 200
    assert any(item["name"] == "Momentum" for item in list_response.json()["items"])


def test_taifex_structured_route_supports_filtered_queries(client, monkeypatch):
    captured = {}

    async def list_taifex_structured_rows(
        section,
        *,
        resolved_date=None,
        start_date=None,
        end_date=None,
        commodity=None,
        institution=None,
        option_side=None,
        limit=200,
    ):
        captured.update(
            {
                "section": section,
                "resolved_date": resolved_date,
                "start_date": start_date,
                "end_date": end_date,
                "commodity": commodity,
                "institution": institution,
                "option_side": option_side,
                "limit": limit,
            }
        )
        return [
            {
                "resolved_date": "2026-04-15",
                "commodity": "臺股期貨",
                "institution": "外資",
                "oi_net_volume": 1234,
            }
        ]

    monkeypatch.setattr(main.db, "list_taifex_structured_rows", list_taifex_structured_rows)

    response = client.get(
        "/api/taifex/structured/futures"
        "?start_date=2026-04-01&end_date=2026-04-15&commodity=%E8%87%BA%E8%82%A1%E6%9C%9F%E8%B2%A8"
        "&institution=%E5%A4%96%E8%B3%87&limit=50"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["oi_net_volume"] == 1234
    assert captured == {
        "section": "futures",
        "resolved_date": None,
        "start_date": "2026-04-01",
        "end_date": "2026-04-15",
        "commodity": "臺股期貨",
        "institution": "外資",
        "option_side": None,
        "limit": 50,
    }


def test_taifex_structured_route_rejects_invalid_filter_combinations(client):
    response = client.get("/api/taifex/structured/futures?date=2026-04-15&start_date=2026-04-01")

    assert response.status_code == 400
    assert "date cannot be combined" in response.json()["detail"]
