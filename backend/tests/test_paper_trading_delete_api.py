from __future__ import annotations

import main


class FakePaperTradingDeleteDb:
    def __init__(self):
        self.accounts = {1: {"id": 1, "name": "TMF Account"}}
        self.bots = {
            10: {"id": 10, "account_id": 1, "name": "TMF Bot", "status": "idle"},
            11: {"id": 11, "account_id": 1, "name": "Running Bot", "status": "running"},
        }

    async def list_paper_trading_bots(self, owner_id=1, account_id=None):
        items = list(self.bots.values())
        if account_id is not None:
            items = [item for item in items if int(item["account_id"]) == int(account_id)]
        return items

    async def delete_paper_trading_bot(self, bot_id, owner_id=1):
        return self.bots.pop(int(bot_id), None) is not None

    async def delete_paper_trading_account(self, account_id, owner_id=1):
        account_id = int(account_id)
        if self.accounts.pop(account_id, None) is None:
            return False
        self.bots = {
            bot_id: bot
            for bot_id, bot in self.bots.items()
            if int(bot["account_id"]) != account_id
        }
        return True


def test_delete_paper_trading_bot_removes_idle_bot(client, monkeypatch):
    fake_db = FakePaperTradingDeleteDb()
    main.paper_trading._active_bots.clear()
    monkeypatch.setattr(main.paper_trading, "db", fake_db)

    response = client.delete("/api/paper-trading/bots/10")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "bot_id": 10}
    assert 10 not in fake_db.bots


def test_delete_paper_trading_bot_blocks_running_instance(client, monkeypatch):
    fake_db = FakePaperTradingDeleteDb()
    main.paper_trading._active_bots.clear()
    main.paper_trading._active_bots[11] = object()
    monkeypatch.setattr(main.paper_trading, "db", fake_db)

    try:
        response = client.delete("/api/paper-trading/bots/11")
        assert response.status_code == 409
        assert 11 in fake_db.bots
    finally:
        main.paper_trading._active_bots.clear()


def test_delete_paper_trading_account_removes_account_and_related_bots(client, monkeypatch):
    fake_db = FakePaperTradingDeleteDb()
    main.paper_trading._active_bots.clear()
    monkeypatch.setattr(main.paper_trading, "db", fake_db)

    response = client.delete("/api/paper-trading/accounts/1")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "account_id": 1}
    assert fake_db.accounts == {}
    assert fake_db.bots == {}


def test_delete_paper_trading_account_blocks_running_related_bot(client, monkeypatch):
    fake_db = FakePaperTradingDeleteDb()
    main.paper_trading._active_bots.clear()
    main.paper_trading._active_bots[11] = object()
    monkeypatch.setattr(main.paper_trading, "db", fake_db)

    try:
        response = client.delete("/api/paper-trading/accounts/1")
        assert response.status_code == 409
        assert 1 in fake_db.accounts
    finally:
        main.paper_trading._active_bots.clear()
