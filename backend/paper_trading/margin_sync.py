from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, tzinfo
from typing import Any
from zoneinfo import ZoneInfo

from paper_trading.cost_model import get_product_spec
from fubon_provider import classify_fubon_error

log = logging.getLogger(__name__)

APP_TZ = ZoneInfo("Asia/Taipei")
DEFAULT_FALLBACK_MARGIN = 28_900.0
TRANSIENT_RETRY_MINUTES = 30
UNKNOWN_RETRY_MINUTES = 60


def _coerce_positive_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric > 0 else None


def _parse_datetime(value: Any, app_tz: tzinfo = APP_TZ) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=app_tz)
    return parsed.astimezone(app_tz)


def margin_synced_today(account: dict | None, app_tz: tzinfo = APP_TZ) -> bool:
    if not account:
        return False
    synced_at = _parse_datetime(
        account.get("margin_last_success_at") or account.get("margin_synced_at"),
        app_tz,
    )
    if synced_at is None:
        return False
    return synced_at.date() == datetime.now(app_tz).date()


def classify_margin_error(error: Any) -> str:
    text = str(error or "").lower()
    if "futures-compatible" in text or "futures/options account" in text:
        return "configuration_error"
    return classify_fubon_error(error)


def margin_retry_allowed(
    account: dict | None,
    *,
    app_tz: tzinfo = APP_TZ,
    manual: bool = False,
) -> bool:
    if manual or not account:
        return True
    if account.get("margin_error_category") == "configuration_error":
        return False
    next_retry = _parse_datetime(account.get("margin_next_retry_at"), app_tz)
    return next_retry is None or next_retry <= datetime.now(app_tz)


def _fallback_margin(product_symbol: str, current_margin: Any = None) -> tuple[float, str]:
    current = _coerce_positive_float(current_margin)
    if current is not None:
        return current, "fallback_existing"
    product_margin = _coerce_positive_float(get_product_spec(product_symbol).initial_margin)
    if product_margin is not None:
        return product_margin, "fallback_product_spec"
    return DEFAULT_FALLBACK_MARGIN, "fallback_default"


async def build_margin_update(
    provider,
    product_symbol: str,
    *,
    current_margin: Any = None,
    app_tz: tzinfo = APP_TZ,
) -> tuple[dict, bool]:
    symbol = str(product_symbol or "TMF").strip().upper() or "TMF"
    attempted_at = datetime.now(app_tz).replace(microsecond=0)
    attempted_at_text = attempted_at.strftime("%Y-%m-%d %H:%M:%S")
    try:
        estimate = await provider.estimate_margin(symbol, lot=1, session="REGULAR")
        margin = _coerce_positive_float((estimate or {}).get("initial_margin_per_contract"))
        if margin is None:
            raise RuntimeError("Fubon margin estimate returned no usable margin")
        update = {
            "initial_margin_per_contract": margin,
            "margin_source": str((estimate or {}).get("source") or "fubon_query_estimate_margin"),
            "margin_reference_symbol": (estimate or {}).get("resolved_symbol"),
            "margin_currency": (estimate or {}).get("currency") or "TWD",
            "margin_synced_at": attempted_at_text,
            "margin_sync_error": None,
            "margin_last_attempt_at": attempted_at_text,
            "margin_last_success_at": attempted_at_text,
            "margin_last_error": None,
            "margin_error_category": None,
            "margin_next_retry_at": None,
        }
        return update, True
    except Exception as exc:
        fallback, source = _fallback_margin(symbol, current_margin)
        message = str(exc)[:1000]
        category = classify_margin_error(exc)
        if category == "configuration_error":
            next_retry_at = None
        else:
            retry_minutes = TRANSIENT_RETRY_MINUTES if category in {
                "transient",
                "heartbeat_timeout",
                "session_invalid",
            } else UNKNOWN_RETRY_MINUTES
            next_retry_at = (attempted_at + timedelta(minutes=retry_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        log.warning("Paper trading margin sync fell back for %s: %s", symbol, message)
        return (
            {
                "initial_margin_per_contract": fallback,
                "margin_source": source,
                "margin_reference_symbol": None,
                "margin_currency": get_product_spec(symbol).currency or "TWD",
                "margin_sync_error": message,
                "margin_last_attempt_at": attempted_at_text,
                "margin_last_error": message,
                "margin_error_category": category,
                "margin_next_retry_at": next_retry_at,
            },
            False,
        )


async def sync_paper_trading_account_margin(
    db,
    provider,
    account: dict,
    *,
    owner_id: int = 1,
    app_tz: tzinfo = APP_TZ,
    manual: bool = True,
) -> dict:
    if not margin_retry_allowed(account, app_tz=app_tz, manual=manual):
        return {
            "ok": False,
            "skipped": True,
            "account": account,
            "margin": account.get("initial_margin_per_contract"),
            "source": account.get("margin_source"),
            "reference_symbol": account.get("margin_reference_symbol"),
            "currency": account.get("margin_currency"),
            "synced_at": account.get("margin_last_success_at") or account.get("margin_synced_at"),
            "next_retry_at": account.get("margin_next_retry_at"),
            "error_category": account.get("margin_error_category"),
            "error": account.get("margin_last_error") or account.get("margin_sync_error"),
        }
    update, ok = await build_margin_update(
        provider,
        str(account.get("product_symbol") or "TMF"),
        current_margin=account.get("initial_margin_per_contract"),
        app_tz=app_tz,
    )
    if not ok and _coerce_positive_float(account.get("initial_margin_per_contract")) is not None:
        # A failed refresh may update attempt/error metadata, but it must never
        # replace the last known-good value, source, reference, or timestamp.
        for key in (
            "initial_margin_per_contract",
            "margin_source",
            "margin_reference_symbol",
            "margin_currency",
            "margin_synced_at",
            "margin_last_success_at",
        ):
            update.pop(key, None)
    updated_account = await db.update_paper_trading_account(
        int(account["id"]),
        update,
        owner_id=owner_id,
    )
    return {
        "ok": ok,
        "account": updated_account,
        "margin": updated_account.get("initial_margin_per_contract"),
        "source": updated_account.get("margin_source"),
        "reference_symbol": updated_account.get("margin_reference_symbol"),
        "currency": updated_account.get("margin_currency"),
        "synced_at": updated_account.get("margin_last_success_at") or updated_account.get("margin_synced_at"),
        "next_retry_at": updated_account.get("margin_next_retry_at"),
        "error_category": updated_account.get("margin_error_category"),
        "error": update.get("margin_sync_error"),
    }


async def sync_all_paper_trading_account_margins(
    db,
    provider,
    *,
    owner_id: int = 1,
    app_tz: tzinfo = APP_TZ,
    reason: str = "manual",
) -> dict:
    accounts = await db.list_paper_trading_accounts(owner_id=owner_id)
    results = []
    manual = str(reason or "").lower().startswith("manual")
    for account in accounts:
        try:
            results.append(
                await sync_paper_trading_account_margin(
                    db,
                    provider,
                    account,
                    owner_id=owner_id,
                    app_tz=app_tz,
                    manual=manual,
                )
            )
        except Exception as exc:
            results.append(
                {
                    "ok": False,
                    "account": account,
                    "error": str(exc)[:1000],
                }
            )

    return {
        "ok": all(item.get("ok") for item in results) if results else True,
        "reason": reason,
        "total": len(results),
        "success": sum(1 for item in results if item.get("ok")),
        "failed": sum(1 for item in results if not item.get("ok")),
        "skipped": sum(1 for item in results if item.get("skipped")),
        "items": results,
    }


async def ensure_account_margin_current(
    db,
    provider,
    account: dict,
    *,
    owner_id: int = 1,
    app_tz: tzinfo = APP_TZ,
) -> dict:
    if margin_synced_today(account, app_tz):
        return account
    if not margin_retry_allowed(account, app_tz=app_tz, manual=False):
        return account
    result = await sync_paper_trading_account_margin(
        db,
        provider,
        account,
        owner_id=owner_id,
        app_tz=app_tz,
        manual=False,
    )
    return result.get("account") or account
