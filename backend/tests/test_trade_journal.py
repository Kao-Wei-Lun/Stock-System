import copy

import pytest

import main
from journal_service import build_journal_stats, compute_trade_result


@pytest.fixture
def trade_journal_store(monkeypatch):
    store = {
        "next_id": 1,
        "entries": {},
        "notifications": {
            1: {
                "id": 1,
                "owner_id": 1,
                "category": "system",
                "level": "info",
                "title": "Journal",
                "message": "Ready",
                "payload": {},
                "read_at": None,
                "created_at": "2026-04-01T08:00:00+00:00",
            }
        },
    }

    def clone(value):
        return copy.deepcopy(value)

    def normalize(payload, existing=None):
        source = clone(existing or {})
        source.update(clone(payload or {}))
        source.setdefault("market", "US")
        source.setdefault("direction", "long")
        source.setdefault("strategy_code", "")
        source.setdefault("exit_time", None)
        source.setdefault("exit_price", None)
        source.setdefault("stop_loss", None)
        source.setdefault("take_profit", None)
        source.setdefault("entry_reason", "")
        source.setdefault("exit_reason", "")
        source.setdefault("emotion_tag", "")
        source.setdefault("review_notes", "")
        source["ticker"] = source["ticker"].upper()
        source["tags"] = list(dict.fromkeys(source.get("tags") or []))
        source["attachments"] = clone(source.get("attachments") or [])
        source["result"] = compute_trade_result(source)
        return source

    async def list_trade_journal_entries(owner_id=1, ticker=None, market=None, strategy_code=None, tag=None, search=None, limit=50):
        items = list(store["entries"].values())
        if ticker:
            items = [item for item in items if item["ticker"] == ticker]
        if market:
            items = [item for item in items if item["market"] == market]
        if strategy_code:
            items = [item for item in items if item["strategy_code"] == strategy_code]
        if tag:
            items = [item for item in items if tag in item["tags"]]
        if search:
            lowered = search.lower()
            items = [
                item for item in items
                if lowered in item["ticker"].lower()
                or lowered in item["entry_reason"].lower()
                or lowered in item["review_notes"].lower()
            ]
        items.sort(key=lambda item: item["entry_time"], reverse=True)
        return clone(items[:limit])

    async def get_trade_journal_entry(entry_id, owner_id=1):
        entry = store["entries"].get(entry_id)
        return clone(entry) if entry else None

    async def create_trade_journal_entry(payload, owner_id=1):
        entry_id = store["next_id"]
        store["next_id"] += 1
        normalized = normalize(payload)
        normalized.update(
            {
                "id": entry_id,
                "owner_id": owner_id,
                "created_at": "2026-04-01T08:05:00+00:00",
                "updated_at": "2026-04-01T08:05:00+00:00",
            }
        )
        store["entries"][entry_id] = normalized
        return clone(normalized)

    async def update_trade_journal_entry(entry_id, payload, owner_id=1):
        if entry_id not in store["entries"]:
            return None
        normalized = normalize(payload, existing=store["entries"][entry_id])
        normalized.update(
            {
                "id": entry_id,
                "owner_id": owner_id,
                "created_at": store["entries"][entry_id]["created_at"],
                "updated_at": "2026-04-01T08:10:00+00:00",
            }
        )
        store["entries"][entry_id] = normalized
        return clone(normalized)

    async def delete_trade_journal_entry(entry_id, owner_id=1):
        return store["entries"].pop(entry_id, None) is not None

    async def get_trade_journal_stats(owner_id=1, ticker=None, market=None, strategy_code=None, tag=None, search=None):
        entries = await list_trade_journal_entries(
            owner_id=owner_id,
            ticker=ticker,
            market=market,
            strategy_code=strategy_code,
            tag=tag,
            search=search,
            limit=500,
        )
        return build_journal_stats(entries)

    async def set_notification_read_state(notification_id, read, owner_id=1):
        notification = store["notifications"].get(notification_id)
        if not notification:
            return None
        notification["read_at"] = "2026-04-01T09:00:00+00:00" if read else None
        return clone(notification)

    monkeypatch.setattr(main.db, "list_trade_journal_entries", list_trade_journal_entries)
    monkeypatch.setattr(main.db, "get_trade_journal_entry", get_trade_journal_entry)
    monkeypatch.setattr(main.db, "create_trade_journal_entry", create_trade_journal_entry)
    monkeypatch.setattr(main.db, "update_trade_journal_entry", update_trade_journal_entry)
    monkeypatch.setattr(main.db, "delete_trade_journal_entry", delete_trade_journal_entry)
    monkeypatch.setattr(main.db, "get_trade_journal_stats", get_trade_journal_stats)
    monkeypatch.setattr(main.db, "set_notification_read_state", set_notification_read_state)
    monkeypatch.setattr(main.db, "mark_notification_read", lambda notification_id, owner_id=1: set_notification_read_state(notification_id, True, owner_id))

    return store


def test_trade_journal_crud_and_attachment_metadata(client, trade_journal_store):
    create_response = client.post(
        "/api/journal/trades",
        json={
            "ticker": "AAPL",
            "market": "US",
            "direction": "long",
            "strategy_code": "breakout",
            "entry_time": "2026-03-31T09:30:00",
            "entry_price": 200,
            "exit_time": "2026-03-31T13:30:00",
            "exit_price": 210,
            "size": 100,
            "entry_reason": "Opening range breakout",
            "review_notes": "Held with discipline",
            "emotion_tag": "calm",
            "tags": ["breakout", "earnings"],
            "attachments": [
                {"file_path": "C:/journal/aapl-breakout.png", "file_type": "image/png"},
            ],
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["ticker"] == "AAPL"
    assert created["attachments"][0]["file_type"] == "image/png"
    assert created["result"]["pnl"] == 1000

    list_response = client.get("/api/journal/trades?ticker=AAPL&tag=breakout")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == created["id"]

    update_response = client.patch(
        f"/api/journal/trades/{created['id']}",
        json={
            "review_notes": "Updated review",
            "tags": ["breakout", "trend"],
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["review_notes"] == "Updated review"
    assert "trend" in update_response.json()["tags"]

    stats_response = client.get("/api/journal/trades/stats?ticker=AAPL")
    assert stats_response.status_code == 200
    assert stats_response.json()["closed_entries"] == 1

    delete_response = client.delete(f"/api/journal/trades/{created['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["ok"] is True


def test_trade_journal_statistics_aggregation():
    entries = [
        {
            "market": "US",
            "strategy_code": "breakout",
            "emotion_tag": "calm",
            "result": {"closed": True, "pnl": 1500, "pnl_pct": 5.0},
        },
        {
            "market": "TW",
            "strategy_code": "pullback",
            "emotion_tag": "hesitant",
            "result": {"closed": True, "pnl": -500, "pnl_pct": -1.5},
        },
        {
            "market": "US",
            "strategy_code": "breakout",
            "emotion_tag": "calm",
            "result": {"closed": False, "pnl": None, "pnl_pct": None},
        },
    ]

    stats = build_journal_stats(entries)

    assert stats["total_entries"] == 3
    assert stats["closed_entries"] == 2
    assert stats["win_rate"] == 50.0
    assert stats["net_pnl"] == 1000
    assert stats["markets"][0]["key"] == "US"


def test_notification_read_unread_patch(client, trade_journal_store):
    response = client.patch("/api/notifications/1/read", json={"read": True})
    assert response.status_code == 200
    assert response.json()["read_at"] == "2026-04-01T09:00:00+00:00"

    unread_response = client.patch("/api/notifications/1/read", json={"read": False})
    assert unread_response.status_code == 200
    assert unread_response.json()["read_at"] is None
