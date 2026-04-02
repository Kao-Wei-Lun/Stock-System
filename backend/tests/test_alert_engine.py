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
    ],
)
def test_evaluate_alert_rule_supports_indicator_types(alert, quote, expected_match):
    result = evaluate_alert_rule(alert, quote)

    assert result["matched"] is expected_match
    assert result["reason"] == "matched"
    assert result["condition_payload"]["last_source"] == quote["source"]


def test_evaluate_alert_rule_reports_unsupported_type():
    result = evaluate_alert_rule(
        {"type": "basis", "condition": "大於", "value": 0, "condition_payload": {}},
        {"price": 100, "source": "yahoo_finance"},
    )

    assert result["matched"] is False
    assert result["reason"] == "unsupported_type"


class StubDb:
    def __init__(self, rows=None, macro_items=None):
        self.updated_alerts = []
        self.trigger_logs = []
        self.notifications = []
        self.stored_quotes = {}
        self.rows = rows or []
        self.macro_items = macro_items or []

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


@pytest.mark.anyio
async def test_alert_engine_triggers_and_persists_notifications():
    db = StubDb()
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
            "condition_payload": {},
        }
    )

    assert triggered is True
    assert db.updated_alerts[-1][1]["triggered"] is True
    assert db.updated_alerts[-1][1]["active"] is False
    assert db.trigger_logs[0]["trigger_value"] == 212
    assert db.notifications[0]["category"] == "alert"


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
