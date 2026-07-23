from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from paper_trading.margin_sync import (
    APP_TZ,
    ensure_account_margin_current,
    margin_retry_allowed,
    sync_all_paper_trading_account_margins,
    sync_paper_trading_account_margin,
)


class StubMarginProvider:
    def __init__(self, *, margin: float = 27_100, error: Exception | None = None):
        self.margin = margin
        self.error = error
        self.calls = 0

    async def estimate_margin(self, symbol, **_kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return {
            "initial_margin_per_contract": self.margin,
            "resolved_symbol": f"{symbol}E6",
            "currency": "TWD",
            "source": "fubon_query_estimate_margin",
        }


class StubPaperDb:
    def __init__(self, accounts):
        self.accounts = {int(account["id"]): dict(account) for account in accounts}
        self.updates = []

    async def update_paper_trading_account(self, account_id, update, *, owner_id=1):
        self.updates.append((account_id, dict(update), owner_id))
        self.accounts[account_id].update(update)
        return dict(self.accounts[account_id])

    async def list_paper_trading_accounts(self, *, owner_id=1):
        return [dict(account) for account in self.accounts.values()]


def account_fixture(**overrides):
    payload = {
        "id": 4,
        "product_symbol": "TMF",
        "initial_margin_per_contract": 28_900.0,
        "margin_source": "fubon_query_estimate_margin",
        "margin_reference_symbol": "TMFE6",
        "margin_currency": "TWD",
        "margin_synced_at": "2026-07-22 09:00:00",
        "margin_last_success_at": "2026-07-22 09:00:00",
        "margin_sync_error": None,
        "margin_last_error": None,
        "margin_error_category": None,
        "margin_next_retry_at": None,
    }
    payload.update(overrides)
    return payload


@pytest.mark.anyio
async def test_successful_margin_refresh_records_attempt_and_success():
    account = account_fixture()
    database = StubPaperDb([account])
    provider = StubMarginProvider(margin=27_500)

    result = await sync_paper_trading_account_margin(database, provider, account)

    assert result["ok"] is True
    assert result["margin"] == 27_500
    updated = result["account"]
    assert updated["margin_last_attempt_at"] == updated["margin_last_success_at"]
    assert updated["margin_synced_at"] == updated["margin_last_success_at"]
    assert updated["margin_last_error"] is None
    assert updated["margin_next_retry_at"] is None


@pytest.mark.anyio
async def test_configuration_failure_preserves_last_success_and_stops_automatic_retry():
    account = account_fixture()
    database = StubPaperDb([account])
    provider = StubMarginProvider(error=RuntimeError("帳號類別錯誤"))

    failed = await sync_paper_trading_account_margin(database, provider, account)
    retained = failed["account"]

    assert failed["ok"] is False
    assert retained["initial_margin_per_contract"] == 28_900.0
    assert retained["margin_source"] == "fubon_query_estimate_margin"
    assert retained["margin_last_success_at"] == "2026-07-22 09:00:00"
    assert retained["margin_synced_at"] == "2026-07-22 09:00:00"
    assert retained["margin_error_category"] == "configuration_error"
    assert retained["margin_next_retry_at"] is None

    ensured = await ensure_account_margin_current(database, provider, retained)
    assert ensured == retained
    assert provider.calls == 1


@pytest.mark.anyio
async def test_transient_failure_uses_negative_cache_until_next_retry():
    future_retry = (datetime.now(APP_TZ) + timedelta(minutes=20)).replace(microsecond=0)
    account = account_fixture(
        margin_last_success_at=None,
        margin_synced_at=None,
        margin_last_error="connection reset",
        margin_error_category="transient",
        margin_next_retry_at=future_retry.strftime("%Y-%m-%d %H:%M:%S"),
    )
    database = StubPaperDb([account])
    provider = StubMarginProvider(error=RuntimeError("connection reset"))

    result = await sync_paper_trading_account_margin(
        database,
        provider,
        account,
        manual=False,
    )

    assert result["skipped"] is True
    assert provider.calls == 0
    assert database.updates == []
    assert margin_retry_allowed(account, manual=False) is False
    assert margin_retry_allowed(account, manual=True) is True


@pytest.mark.anyio
async def test_scheduled_bulk_sync_skips_configuration_errors_but_manual_refresh_retries():
    account = account_fixture(
        margin_last_success_at=None,
        margin_synced_at=None,
        margin_error_category="configuration_error",
        margin_last_error="帳號類別錯誤",
    )
    database = StubPaperDb([account])
    provider = StubMarginProvider(error=RuntimeError("帳號類別錯誤"))

    scheduled = await sync_all_paper_trading_account_margins(
        database,
        provider,
        reason="scheduled",
    )
    manual = await sync_all_paper_trading_account_margins(
        database,
        provider,
        reason="manual-api",
    )

    assert scheduled["skipped"] == 1
    assert provider.calls == 1
    assert manual["failed"] == 1
