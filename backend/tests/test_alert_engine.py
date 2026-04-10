import pytest

import main
from alert_engine import AlertEngine, evaluate_alert_rule


@pytest.mark.parametrize(
    ("alert", "quote", "expected_match"),
    [
        (
            {"type": "price", "condition": "大於", "value": 210, "condition_payload": {}},
            {"price": 211, "source": "yahoo_finance"},
            True,
        ),
        (
            {"type": "price", "condition": "下穿", "value": 200, "condition_payload": {"last_observed_value": 205}},
            {"price": 198, "source": "yahoo_finance"},
            True,
        ),
        (
            {"type": "pct", "condition": "小於", "value": -1, "condition_payload": {}},
            {"change_pct": -2.5, "source": "yahoo_finance"},
            True,
        ),
        (
            {"type": "rsi", "condition": "上穿", "value": 30, "condition_payload": {}},
            {"rsi": 35, "rsi_prev": 28, "source": "yahoo_finance"},
            True,
        ),
        (
            {"type": "macd", "condition": "上穿", "value": None, "condition_payload": {}},
            {"macd": 0.8, "macd_prev": -0.2, "macd_signal": 0.3, "macd_signal_prev": 0.1, "source": "yahoo_finance"},
            True,
        ),
        (
            {"type": "volume", "condition": "大於", "value": 1.8, "condition_payload": {}},
            {"volume_ratio": 2.4, "source": "yahoo_finance"},
            True,
        ),
        (
            {"type": "market_risk", "condition": "high", "value": None, "condition_payload": {}},
            {
                "macro_overall_risk": "high",
                "macro_regime": "risk_off",
                "macro_trade_posture": "defensive",
                "source": "local_db",
            },
            True,
        ),
        (
            {"type": "basis", "condition": "大於", "value": 1.2, "condition_payload": {"metric": "basis_pct"}},
            {"basis_pct": 1.56, "basis": 34, "source": "local_db"},
            True,
        ),
        (
            {"type": "institutional", "condition": "high", "value": None, "condition_payload": {}},
            {"institutional_anomaly_level": "high", "institutional_anomaly_score": 3.1, "source": "local_db"},
            True,
        ),
        (
            {"type": "event", "condition": "within_days", "value": 7, "condition_payload": {}},
            {"days_until_event": 3, "event_title": "Earnings", "source": "local_db"},
            True,
        ),
    ],
)
def test_evaluate_alert_rule_supports_indicator_types(alert, quote, expected_match):
    result = evaluate_alert_rule(alert, quote)

    assert result["matched"] is expected_match
    assert result["reason"] == "matched"
    assert result["condition_payload"]["last_source"] == quote["source"]


def test_evaluate_alert_rule_reports_unsupported_type():
    result = evaluate_alert_rule(
        {"type": "mystery", "condition": "大於", "value": 0, "condition_payload": {}},
        {"price": 100, "source": "yahoo_finance"},
    )

    assert result["matched"] is False
    assert result["reason"] == "unsupported_type"


class StubDb:
    def __init__(self, rows=None, macro_items=None, snapshots=None, market_events=None):
        self.updated_alerts = []
        self.trigger_logs = []
        self.notifications = []
        self.stored_quotes = {}
        self.rows = rows or []
        self.macro_items = macro_items or []
        self.snapshots = snapshots or []
        self.market_events = market_events or []

    async def upsert_market_quote(self, quote):
        self.stored_quotes[quote["ticker"]] = dict(quote)
        return dict(quote)

    async def get_market_quote(self, ticker):
        quote = self.stored_quotes.get(ticker)
        return dict(quote) if quote else None

    async def get_recent_ohlcv_rows(self, ticker, limit=80):
        return [dict(item) for item in self.rows[-limit:]]

    async def list_macro_snapshots(self, snapshot_date=None):
        return [dict(item) for item in self.macro_items]

    async def get_institutional_snapshot(self, target_date=None):
        if target_date:
            candidates = [item for item in self.snapshots if item.get("resolved_date") <= target_date.isoformat()]
            return dict(candidates[-1]) if candidates else None
        return dict(self.snapshots[-1]) if self.snapshots else None

    async def get_institutional_snapshots(self, target_date, limit):
        items = [item for item in self.snapshots if item.get("resolved_date") <= target_date.isoformat()]
        return [dict(item) for item in items[-limit:]]

    async def list_market_events(self, ticker=None, date_from=None, date_to=None, limit=100):
        items = []
        for item in self.market_events:
            event_ticker = item.get("ticker")
            if ticker and event_ticker != ticker:
                continue
            event_date = item.get("event_date")
            if date_from and event_date < date_from:
                continue
            if date_to and event_date > date_to:
                continue
            items.append(dict(item))
        return items[:limit]

    async def update_alert(self, alert_id, payload, owner_id=1):
        self.updated_alerts.append((alert_id, payload, owner_id))
        return {"id": alert_id, **payload}

    async def create_alert_trigger_log(self, alert_id, ticker, payload=None, owner_id=1, trigger_value=None, threshold_value=None):
        record = {
            "alert_id": alert_id,
            "ticker": ticker,
            "payload": payload or {},
            "owner_id": owner_id,
            "trigger_value": trigger_value,
            "threshold_value": threshold_value,
        }
        self.trigger_logs.append(record)
        return record

    async def create_notification(self, payload, owner_id=1):
        record = dict(payload)
        record["owner_id"] = owner_id
        self.notifications.append(record)
        return record


class StubQuoteProvider:
    def __init__(self, quote):
        self.quote = quote

    async def fetch_quote(self, ticker):
        return dict(self.quote) if self.quote else None


class StubExternalNotifier:
    def __init__(self):
        self.notifications = []

    async def send_alert(self, notification):
        self.notifications.append(dict(notification))
        return ["stub"]


def _build_rows():
    closes = list(range(160, 120, -1))
    rows = []
    for index, close in enumerate(closes):
        rows.append(
            {
                "date": f"2026-02-{index + 1:02d}",
                "open": close - 1,
                "high": close + 1,
                "low": close - 2,
                "close": close,
                "volume": 1_000_000 + (index * 5_000),
            }
        )
    return rows


def _build_institutional_snapshots():
    return [
        {
            "resolved_date": "2026-03-30",
            "default_futures_commodity": "臺股期貨",
            "default_options_commodity": "臺指選擇權",
            "futures_commodities": ["臺股期貨"],
            "options_commodities": ["臺指選擇權"],
            "spot_reference": [{"ticker": "^TWII", "label": "加權指數", "price": 19980}],
            "cost_estimates": {"futures": {"institution_estimate": {"price": 20010}}},
            "futures": [
                {"commodity": "臺股期貨", "institution": "外資", "oi_net_volume": 10, "trade_net_volume": 8},
                {"commodity": "臺股期貨", "institution": "投信", "oi_net_volume": 2, "trade_net_volume": 1},
                {"commodity": "臺股期貨", "institution": "自營商", "oi_net_volume": 1, "trade_net_volume": 1},
            ],
            "call_puts": [
                {"commodity": "臺指選擇權", "institution": "外資", "option_side": "買權", "oi_net_volume": 30},
                {"commodity": "臺指選擇權", "institution": "外資", "option_side": "賣權", "oi_net_volume": 12},
            ],
            "cash_summary_aggregated": [{"institution": "合計", "net_amount": 120}],
        },
        {
            "resolved_date": "2026-03-31",
            "default_futures_commodity": "臺股期貨",
            "default_options_commodity": "臺指選擇權",
            "futures_commodities": ["臺股期貨"],
            "options_commodities": ["臺指選擇權"],
            "spot_reference": [{"ticker": "^TWII", "label": "加權指數", "price": 20020}],
            "cost_estimates": {"futures": {"institution_estimate": {"price": 20045}}},
            "futures": [
                {"commodity": "臺股期貨", "institution": "外資", "oi_net_volume": 12, "trade_net_volume": 9},
                {"commodity": "臺股期貨", "institution": "投信", "oi_net_volume": 1, "trade_net_volume": 1},
                {"commodity": "臺股期貨", "institution": "自營商", "oi_net_volume": 1, "trade_net_volume": 2},
            ],
            "call_puts": [
                {"commodity": "臺指選擇權", "institution": "外資", "option_side": "買權", "oi_net_volume": 32},
                {"commodity": "臺指選擇權", "institution": "外資", "option_side": "賣權", "oi_net_volume": 14},
            ],
            "cash_summary_aggregated": [{"institution": "合計", "net_amount": 150}],
        },
        {
            "resolved_date": "2026-04-01",
            "default_futures_commodity": "臺股期貨",
            "default_options_commodity": "臺指選擇權",
            "futures_commodities": ["臺股期貨"],
            "options_commodities": ["臺指選擇權"],
            "spot_reference": [{"ticker": "^TWII", "label": "加權指數", "price": 20060}],
            "cost_estimates": {"futures": {"institution_estimate": {"price": 20100}}},
            "futures": [
                {"commodity": "臺股期貨", "institution": "外資", "oi_net_volume": 11, "trade_net_volume": 10},
                {"commodity": "臺股期貨", "institution": "投信", "oi_net_volume": 2, "trade_net_volume": 1},
                {"commodity": "臺股期貨", "institution": "自營商", "oi_net_volume": 1, "trade_net_volume": 1},
            ],
            "call_puts": [
                {"commodity": "臺指選擇權", "institution": "外資", "option_side": "買權", "oi_net_volume": 35},
                {"commodity": "臺指選擇權", "institution": "外資", "option_side": "賣權", "oi_net_volume": 13},
            ],
            "cash_summary_aggregated": [{"institution": "合計", "net_amount": 130}],
        },
        {
            "resolved_date": "2026-04-02",
            "default_futures_commodity": "臺股期貨",
            "default_options_commodity": "臺指選擇權",
            "futures_commodities": ["臺股期貨"],
            "options_commodities": ["臺指選擇權"],
            "spot_reference": [{"ticker": "^TWII", "label": "加權指數", "price": 20120}],
            "cost_estimates": {"futures": {"institution_estimate": {"price": 20570}}},
            "futures": [
                {"commodity": "臺股期貨", "institution": "外資", "oi_net_volume": 42, "trade_net_volume": 28},
                {"commodity": "臺股期貨", "institution": "投信", "oi_net_volume": 9, "trade_net_volume": 7},
                {"commodity": "臺股期貨", "institution": "自營商", "oi_net_volume": 5, "trade_net_volume": 3},
            ],
            "call_puts": [
                {"commodity": "臺指選擇權", "institution": "外資", "option_side": "買權", "oi_net_volume": 90},
                {"commodity": "臺指選擇權", "institution": "外資", "option_side": "賣權", "oi_net_volume": 12},
            ],
            "cash_summary_aggregated": [{"institution": "合計", "net_amount": 640}],
        },
    ]


@pytest.mark.anyio
async def test_alert_engine_triggers_and_persists_notifications():
    db = StubDb(
        macro_items=[
            {"metric_code": "VIX", "value": 21.4, "change_pct": 0.3, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "US10Y", "value": 4.36, "change_pct": 0.05, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "DXY", "value": 103.2, "change_pct": 0.2, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "SOX", "value": 4625, "change_pct": 0.9, "date": "2026-04-02", "source": "local_db"},
        ]
    )
    provider = StubQuoteProvider(
        {
            "ticker": "AAPL",
            "price": 212,
            "change_pct": 1.5,
            "source": "yahoo_finance",
            "quote_type": "delayed_snapshot",
            "is_delayed": True,
            "quote_timestamp": "2026-03-29T04:00:00+00:00",
        }
    )
    engine = AlertEngine(db, provider)

    triggered = await engine.evaluate_alert(
        {
            "id": 7,
            "ticker": "AAPL",
            "name": "AAPL breakout",
            "notification_title": "AAPL breakout",
            "type": "price",
            "condition": "大於",
            "value": 210,
            "condition_payload": {
                "context_source": "watchlist_group",
                "context_group_name": "Journal Flow",
                "context_tags": ["優先候選", "Q4"],
                "snapshot_price": 210.5,
            },
        }
    )

    assert triggered is True
    assert db.updated_alerts[-1][1]["triggered"] is True
    assert db.updated_alerts[-1][1]["active"] is False
    assert db.trigger_logs[0]["trigger_value"] == 212
    assert db.trigger_logs[0]["payload"]["macro_summary"]["trade_posture"] == "balanced"
    assert db.trigger_logs[0]["payload"]["context_group_name"] == "Journal Flow"
    assert db.notifications[0]["category"] == "alert"
    assert db.notifications[0]["payload"]["context_source"] == "watchlist_group"
    assert db.notifications[0]["payload"]["context_group_name"] == "Journal Flow"
    assert db.notifications[0]["payload"]["context_tags"] == ["優先候選", "Q4"]
    assert db.notifications[0]["payload"]["snapshot_price"] == 210.5
    assert db.notifications[0]["payload"]["macro_summary"]["trade_posture"] == "balanced"


@pytest.mark.anyio
async def test_alert_engine_dispatches_external_notifications_after_local_persist():
    db = StubDb()
    notifier = StubExternalNotifier()
    provider = StubQuoteProvider(
        {
            "ticker": "AAPL",
            "price": 212,
            "change_pct": 1.5,
            "source": "yahoo_finance",
            "quote_timestamp": "2026-03-29T04:00:00+00:00",
        }
    )
    engine = AlertEngine(db, provider, external_notifier=notifier)

    triggered = await engine.evaluate_alert(
        {
            "id": 8,
            "ticker": "AAPL",
            "name": "AAPL breakout",
            "notification_title": "AAPL breakout",
            "type": "price",
            "condition": "大於",
            "value": 210,
            "condition_payload": {},
        }
    )

    assert triggered is True
    assert notifier.notifications[0]["title"] == "AAPL breakout"
    assert notifier.notifications[0]["payload"]["trigger_value"] == 212


@pytest.mark.anyio
async def test_alert_engine_supports_macd_cross_alerts():
    rows = _build_rows()
    db = StubDb(rows=rows)
    provider = StubQuoteProvider(
        {
            "ticker": "AAPL",
            "price": 125,
            "change_pct": 2.1,
            "volume": 2_600_000,
            "source": "yahoo_finance",
            "quote_type": "delayed_snapshot",
            "is_delayed": True,
            "quote_timestamp": "2026-03-29T04:00:00+00:00",
        }
    )
    engine = AlertEngine(db, provider)

    triggered = await engine.evaluate_alert(
        {
            "id": 9,
            "ticker": "AAPL",
            "name": "AAPL MACD golden cross",
            "notification_title": "AAPL MACD golden cross",
            "type": "macd",
            "condition": "上穿",
            "value": None,
            "condition_payload": {},
        }
    )

    assert triggered is True
    assert db.trigger_logs[0]["threshold_value"] is not None
    assert "macd" in db.trigger_logs[0]["payload"]["alert"]["type"]


@pytest.mark.anyio
async def test_alert_engine_supports_market_risk_alerts():
    db = StubDb(
        macro_items=[
            {"metric_code": "VIX", "value": 28.6, "change_pct": 1.1, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "US10Y", "value": 4.58, "change_pct": 0.1, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "DXY", "value": 104.0, "change_pct": 0.81, "date": "2026-04-02", "source": "local_db"},
            {"metric_code": "SOX", "value": 4500, "change_pct": -1.8, "date": "2026-04-02", "source": "local_db"},
        ]
    )
    provider = StubQuoteProvider(None)
    engine = AlertEngine(db, provider)

    triggered = await engine.evaluate_alert(
        {
            "id": 11,
            "ticker": "MARKET",
            "name": "Market risk-off alert",
            "notification_title": "Market risk-off alert",
            "type": "market_risk",
            "condition": "high",
            "value": None,
            "condition_payload": {},
        }
    )

    assert triggered is True
    assert db.updated_alerts[-1][1]["triggered"] is True
    assert db.trigger_logs[0]["ticker"] == "MARKET"
    assert db.notifications[0]["payload"]["source"] == "local_db"
    assert "ticker" not in db.notifications[0]["payload"]


@pytest.mark.anyio
async def test_alert_engine_supports_basis_alerts():
    snapshots = _build_institutional_snapshots()
    db = StubDb(snapshots=snapshots)
    provider = StubQuoteProvider(
        {
            "ticker": "^TWII",
            "price": 20100,
            "source": "yahoo_finance",
            "quote_timestamp": "2026-04-02T05:00:00+00:00",
        }
    )
    engine = AlertEngine(db, provider)

    triggered = await engine.evaluate_alert(
        {
            "id": 12,
            "ticker": "^TWII",
            "name": "Basis divergence",
            "notification_title": "Basis divergence",
            "type": "basis",
            "condition": "大於",
            "value": 2.0,
            "condition_payload": {
                "metric": "basis_pct",
                "futures_commodity": "臺股期貨",
                "spot_ticker": "^TWII",
            },
        }
    )

    assert triggered is True
    assert db.trigger_logs[0]["trigger_value"] > 2.0
    assert db.trigger_logs[0]["payload"]["quote"]["basis_futures_commodity"] == "臺股期貨"
    assert "Basis" in db.notifications[0]["message"]


@pytest.mark.anyio
async def test_alert_engine_supports_institutional_anomaly_alerts():
    db = StubDb(snapshots=_build_institutional_snapshots())
    provider = StubQuoteProvider(None)
    engine = AlertEngine(db, provider)

    triggered = await engine.evaluate_alert(
        {
            "id": 13,
            "ticker": "^TWII",
            "name": "Institutional anomaly",
            "notification_title": "Institutional anomaly",
            "type": "institutional",
            "condition": "high",
            "value": None,
            "condition_payload": {
                "futures_commodity": "臺股期貨",
                "options_commodity": "臺指選擇權",
                "history_days": 20,
            },
        }
    )

    assert triggered is True
    assert db.trigger_logs[0]["payload"]["quote"]["institutional_anomaly_level"] == "high"
    assert "法人異常警報觸發" in db.notifications[0]["message"]


@pytest.mark.anyio
async def test_alert_engine_supports_event_alerts():
    db = StubDb(
        market_events=[
            {
                "ticker": "AAPL",
                "event_type": "earnings",
                "title": "AAPL Earnings Call",
                "description": "Quarterly results",
                "event_date": "2026-04-05",
                "event_time": None,
                "importance": "high",
                "url": "https://example.com/aapl",
            },
        ]
    )
    provider = StubQuoteProvider(None)
    engine = AlertEngine(db, provider)

    triggered = await engine.evaluate_alert(
        {
            "id": 14,
            "ticker": "AAPL",
            "name": "AAPL event reminder",
            "notification_title": "AAPL event reminder",
            "type": "event",
            "condition": "within_days",
            "value": 3,
            "condition_payload": {
                "event_type": "earnings",
                "reference_date": "2026-04-03",
                "event_scope": "ticker",
            },
        }
    )

    assert triggered is True
    assert db.trigger_logs[0]["payload"]["quote"]["event_title"] == "AAPL Earnings Call"
    assert db.notifications[0]["payload"]["trigger_value"] == 2


def test_alert_trigger_log_api_smoke(client, monkeypatch):
    async def get_alert(alert_id, owner_id=1):
        return {"id": alert_id, "ticker": "AAPL"}

    async def list_alert_trigger_logs(alert_id, owner_id=1, limit=20):
        return [
            {
                "id": 1,
                "alert_id": alert_id,
                "ticker": "AAPL",
                "trigger_value": 212,
                "threshold_value": 210,
                "payload": {"quote": {"price": 212}},
                "created_at": "2026-03-29T04:00:05+00:00",
            }
        ]

    monkeypatch.setattr(main.db, "get_alert", get_alert)
    monkeypatch.setattr(main.db, "list_alert_trigger_logs", list_alert_trigger_logs)

    response = client.get("/api/alerts/7/triggers?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["trigger_value"] == 212
