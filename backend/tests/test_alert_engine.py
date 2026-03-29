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
            {"type": "macd", "condition": "大於", "value": 0, "condition_payload": {}},
            {"price": 100, "source": "yahoo_finance"},
            False,
        ),
    ],
)
def test_evaluate_alert_rule_supports_price_and_pct(alert, quote, expected_match):
    result = evaluate_alert_rule(alert, quote)

    assert result["matched"] is expected_match
    assert "last_source" in result["condition_payload"] or result["reason"] == "unsupported_type"


class StubDb:
    def __init__(self):
        self.updated_alerts = []
        self.trigger_logs = []
        self.notifications = []
        self.stored_quotes = {}

    async def upsert_market_quote(self, quote):
        self.stored_quotes[quote["ticker"]] = dict(quote)
        return dict(quote)

    async def get_market_quote(self, ticker):
        quote = self.stored_quotes.get(ticker)
        return dict(quote) if quote else None

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
