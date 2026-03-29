import copy

import pytest

import main


@pytest.fixture
def phase1_store(monkeypatch):
    store = {
        "workspace_next_id": 1,
        "alert_next_id": 1,
        "workspaces": [],
        "alerts": [],
        "notifications": [
            {
                "id": 1,
                "owner_id": 1,
                "category": "system",
                "level": "info",
                "title": "Bootstrap",
                "message": "Persistence layer ready",
                "related_entity_type": None,
                "related_entity_id": None,
                "link_url": None,
                "payload": {},
                "read_at": None,
                "created_at": "2026-03-29T00:00:00+00:00",
            }
        ],
        "quotes": {},
    }

    def clone(value):
        return copy.deepcopy(value)

    async def list_workspace_presets(owner_id=1):
        return clone(store["workspaces"])

    async def get_workspace_preset(workspace_id, owner_id=1):
        for workspace in store["workspaces"]:
            if workspace["id"] == workspace_id:
                return clone(workspace)
        return None

    async def create_workspace_preset(payload, owner_id=1):
        workspace = {
            "id": store["workspace_next_id"],
            "owner_id": owner_id,
            "name": payload["name"],
            "chart_layout": payload.get("chart_layout", "single"),
            "active_ticker": payload.get("active_ticker"),
            "current_period": payload.get("current_period", "1y"),
            "current_interval": payload.get("current_interval", "1d"),
            "workspace_tab": payload.get("workspace_tab", "chart"),
            "comparison_mode": payload.get("comparison_mode", "percent"),
            "payload": clone(payload.get("payload", {})),
            "is_default": bool(payload.get("is_default", False)),
            "created_at": "2026-03-29T01:00:00+00:00",
            "updated_at": "2026-03-29T01:00:00+00:00",
        }
        store["workspace_next_id"] += 1
        if workspace["is_default"]:
            for item in store["workspaces"]:
                item["is_default"] = False
        store["workspaces"].append(workspace)
        return clone(workspace)

    async def update_workspace_preset(workspace_id, payload, owner_id=1):
        for workspace in store["workspaces"]:
            if workspace["id"] != workspace_id:
                continue
            if "name" in payload:
                workspace["name"] = payload["name"]
            if "chart_layout" in payload:
                workspace["chart_layout"] = payload["chart_layout"]
            if "active_ticker" in payload:
                workspace["active_ticker"] = payload["active_ticker"]
            if "current_period" in payload:
                workspace["current_period"] = payload["current_period"]
            if "current_interval" in payload:
                workspace["current_interval"] = payload["current_interval"]
            if "workspace_tab" in payload:
                workspace["workspace_tab"] = payload["workspace_tab"]
            if "comparison_mode" in payload:
                workspace["comparison_mode"] = payload["comparison_mode"]
            if "payload" in payload:
                workspace["payload"] = clone(payload["payload"] or {})
            if "is_default" in payload:
                if payload["is_default"]:
                    for item in store["workspaces"]:
                        item["is_default"] = False
                workspace["is_default"] = bool(payload["is_default"])
            workspace["updated_at"] = "2026-03-29T01:30:00+00:00"
            return clone(workspace)
        return None

    async def delete_workspace_preset(workspace_id, owner_id=1):
        before = len(store["workspaces"])
        store["workspaces"] = [item for item in store["workspaces"] if item["id"] != workspace_id]
        return len(store["workspaces"]) != before

    async def list_alerts(owner_id=1):
        return clone(store["alerts"])

    async def get_alert(alert_id, owner_id=1):
        for alert in store["alerts"]:
            if alert["id"] == alert_id:
                return clone(alert)
        return None

    async def create_alert(payload, owner_id=1):
        alert = {
            "id": store["alert_next_id"],
            "owner_id": owner_id,
            "name": payload.get("name") or f"{payload['ticker']} {payload['condition']}",
            "ticker": payload["ticker"],
            "type": payload["type"],
            "condition": payload["condition"],
            "value": payload.get("value"),
            "value2": payload.get("value2"),
            "timeframe": payload.get("timeframe", "1d"),
            "condition_payload": clone(payload.get("condition_payload", {})),
            "notification_title": payload.get("notification_title") or f"{payload['ticker']} {payload['condition']}",
            "note": payload.get("note"),
            "active": bool(payload.get("active", True)),
            "triggered": bool(payload.get("triggered", False)),
            "triggered_at": payload.get("triggered_at"),
            "last_evaluated_at": payload.get("last_evaluated_at"),
            "created_at": "2026-03-29T02:00:00+00:00",
            "updated_at": "2026-03-29T02:00:00+00:00",
        }
        store["alert_next_id"] += 1
        store["alerts"].append(alert)
        return clone(alert)

    async def update_alert(alert_id, payload, owner_id=1):
        for alert in store["alerts"]:
            if alert["id"] != alert_id:
                continue
            for key, value in payload.items():
                if key == "condition_payload" and value is not None:
                    alert[key] = clone(value)
                elif value is not None:
                    alert[key] = value
            alert["updated_at"] = "2026-03-29T02:30:00+00:00"
            return clone(alert)
        return None

    async def delete_alert(alert_id, owner_id=1):
        before = len(store["alerts"])
        store["alerts"] = [item for item in store["alerts"] if item["id"] != alert_id]
        return len(store["alerts"]) != before

    async def list_notifications(owner_id=1, unread_only=False, limit=50):
        notifications = store["notifications"]
        if unread_only:
            notifications = [item for item in notifications if item["read_at"] is None]
        return clone(notifications[:limit])

    async def mark_notification_read(notification_id, owner_id=1):
        for notification in store["notifications"]:
            if notification["id"] == notification_id:
                notification["read_at"] = "2026-03-29T03:00:00+00:00"
                return clone(notification)
        return None

    async def upsert_market_quote(quote):
        stored = clone(quote)
        stored.setdefault("source", "yahoo_finance")
        stored.setdefault("quote_type", "delayed_snapshot")
        stored.setdefault("is_delayed", True)
        stored.setdefault("quote_timestamp", "2026-03-29T04:00:00+00:00")
        stored.setdefault("synced_at", "2026-03-29T04:00:05+00:00")
        store["quotes"][stored["ticker"]] = stored
        return clone(stored)

    async def get_market_quote(ticker):
        quote = store["quotes"].get(ticker)
        return clone(quote) if quote else None

    async def fetch_realtime_quote(ticker):
        if ticker == "CACHEONLY":
            return None
        normalized = ticker.upper()
        return {
            "ticker": normalized,
            "price": 210.5,
            "open": 208.0,
            "high": 212.0,
            "low": 207.8,
            "prev_close": 205.0,
            "change": 5.5,
            "change_pct": 2.68,
            "volume": 123456,
            "market_cap": 999999999,
            "name": normalized,
            "currency": "USD",
            "source": "yahoo_finance",
            "quote_type": "delayed_snapshot",
            "is_delayed": True,
            "quote_timestamp": "2026-03-29T04:00:00+00:00",
            "synced_at": "2026-03-29T04:00:05+00:00",
            "ts": 1760000000000,
        }

    monkeypatch.setattr(main.db, "list_workspace_presets", list_workspace_presets)
    monkeypatch.setattr(main.db, "get_workspace_preset", get_workspace_preset)
    monkeypatch.setattr(main.db, "create_workspace_preset", create_workspace_preset)
    monkeypatch.setattr(main.db, "update_workspace_preset", update_workspace_preset)
    monkeypatch.setattr(main.db, "delete_workspace_preset", delete_workspace_preset)
    monkeypatch.setattr(main.db, "list_alerts", list_alerts)
    monkeypatch.setattr(main.db, "get_alert", get_alert)
    monkeypatch.setattr(main.db, "create_alert", create_alert)
    monkeypatch.setattr(main.db, "update_alert", update_alert)
    monkeypatch.setattr(main.db, "delete_alert", delete_alert)
    monkeypatch.setattr(main.db, "list_notifications", list_notifications)
    monkeypatch.setattr(main.db, "mark_notification_read", mark_notification_read)
    monkeypatch.setattr(main.db, "upsert_market_quote", upsert_market_quote)
    monkeypatch.setattr(main.db, "get_market_quote", get_market_quote)
    monkeypatch.setattr(main.fetcher, "fetch_realtime_quote", fetch_realtime_quote)

    return store


def test_workspace_api_crud(client, phase1_store):
    create_response = client.post(
        "/api/workspaces",
        json={
            "name": "Morning Desk",
            "chart_layout": "single",
            "active_ticker": "AAPL",
            "current_period": "1y",
            "current_interval": "1d",
            "workspace_tab": "chart",
            "comparison_mode": "percent",
            "payload": {"drawings": [], "activeTool": "cursor"},
            "is_default": True,
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "Morning Desk"
    assert created["payload"]["activeTool"] == "cursor"
    workspace_id = created["id"]

    list_response = client.get("/api/workspaces")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == workspace_id

    get_response = client.get(f"/api/workspaces/{workspace_id}")
    assert get_response.status_code == 200
    assert get_response.json()["active_ticker"] == "AAPL"

    update_response = client.put(
        f"/api/workspaces/{workspace_id}",
        json={
            "comparison_mode": "price",
            "payload": {"drawings": ["trendline"], "activeTool": "measure"},
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["comparison_mode"] == "price"
    assert updated["payload"]["drawings"] == ["trendline"]

    delete_response = client.delete(f"/api/workspaces/{workspace_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["ok"] is True
    assert client.get(f"/api/workspaces/{workspace_id}").status_code == 404


def test_alerts_api_crud(client, phase1_store):
    create_response = client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "type": "price",
            "condition": "gt",
            "value": 210,
            "timeframe": "1d",
            "condition_payload": {"operator": "gt", "value": 210},
            "active": True,
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["ticker"] == "AAPL"
    assert created["condition_payload"]["operator"] == "gt"
    alert_id = created["id"]

    list_response = client.get("/api/alerts")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == alert_id

    update_response = client.patch(
        f"/api/alerts/{alert_id}",
        json={"active": False, "note": "Pause after earnings"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["active"] is False
    assert updated["note"] == "Pause after earnings"

    delete_response = client.delete(f"/api/alerts/{alert_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["ok"] is True
    assert client.patch(f"/api/alerts/{alert_id}", json={"active": True}).status_code == 404


def test_notifications_list_and_read(client, phase1_store):
    list_response = client.get("/api/notifications?unread_only=true")
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1
    assert list_response.json()["items"][0]["read_at"] is None

    read_response = client.post("/api/notifications/1/read")
    assert read_response.status_code == 200
    assert read_response.json()["read_at"] == "2026-03-29T03:00:00+00:00"

    unread_after = client.get("/api/notifications?unread_only=true")
    assert unread_after.status_code == 200
    assert unread_after.json()["items"] == []


def test_quote_endpoint_persists_market_snapshot(client, phase1_store):
    response = client.get("/api/quote/AAPL")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["source"] == "yahoo_finance"
    assert payload["quote_type"] == "delayed_snapshot"
    assert payload["is_delayed"] is True
    assert payload["quote_timestamp"] == "2026-03-29T04:00:00+00:00"
    assert phase1_store["quotes"]["AAPL"]["price"] == 210.5


def test_quote_endpoint_falls_back_to_local_snapshot(client, phase1_store):
    phase1_store["quotes"]["CACHEONLY"] = {
        "ticker": "CACHEONLY",
        "price": 88.8,
        "open": 87.0,
        "high": 89.0,
        "low": 86.5,
        "prev_close": 85.0,
        "change": 3.8,
        "change_pct": 4.47,
        "volume": 4567,
        "market_cap": 123456789,
        "name": "CACHEONLY",
        "currency": "USD",
        "source": "local_cache",
        "quote_type": "cached_snapshot",
        "is_delayed": True,
        "quote_timestamp": "2026-03-28T23:59:00+00:00",
        "synced_at": "2026-03-29T00:00:10+00:00",
        "ts": 1759999999000,
    }

    response = client.get("/api/quote/CACHEONLY")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local_cache"
    assert payload["quote_type"] == "cached_snapshot"
    assert payload["price"] == 88.8
