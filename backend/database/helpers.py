import aiomysql
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from dotenv import load_dotenv

from env_validation import read_int_env, read_text_env

load_dotenv()

MYSQL_HOST = read_text_env("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = read_int_env("MYSQL_PORT", "3306", minimum=1, maximum=65535)
MYSQL_USER = read_text_env("MYSQL_USER", "root")
MYSQL_PASSWORD = read_text_env("MYSQL_PASSWORD", "")
MYSQL_DATABASE = read_text_env("MYSQL_DATABASE", "quantvision")

from journal_service import build_journal_stats, compute_trade_result
from display_name_resolver import resolve_display_name

def _serialize_user_profile(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "username": row.get("username"),
        "display_name": row.get("display_name"),
        "timezone": row.get("timezone"),
        "is_active": bool(row.get("is_active", True)),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_workspace_preset(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "name": row.get("name"),
        "chart_layout": row.get("chart_layout"),
        "active_ticker": row.get("active_ticker"),
        "current_period": row.get("current_period"),
        "current_interval": row.get("current_interval"),
        "workspace_tab": row.get("workspace_tab"),
        "comparison_mode": row.get("comparison_mode"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "is_default": bool(row.get("is_default", False)),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _normalize_watchlist_tags(tags: Any) -> List[str]:
    source = tags if isinstance(tags, list) else []
    normalized: List[str] = []
    seen = set()
    for item in source:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value[:48])
    return normalized[:6]

def _deserialize_watchlist_item(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        **row,
        "tags": _normalize_watchlist_tags(_json_loads(row.get("tags_json"), [])),
    }

def _deserialize_alert(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "name": row.get("name"),
        "ticker": row.get("ticker"),
        "type": row.get("type"),
        "condition": row.get("condition"),
        "value": row.get("value"),
        "value2": row.get("value2"),
        "timeframe": row.get("timeframe") or "1d",
        "condition_payload": _json_loads(row.get("condition_json"), {}),
        "notification_title": row.get("notification_title"),
        "note": row.get("note"),
        "active": bool(row.get("active", True)),
        "triggered": bool(row.get("triggered", False)),
        "triggered_at": _datetime_to_iso(row.get("triggered_at")),
        "last_evaluated_at": _datetime_to_iso(row.get("last_evaluated_at")),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_notification(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "category": row.get("category"),
        "level": row.get("level"),
        "title": row.get("title"),
        "message": row.get("message"),
        "related_entity_type": row.get("related_entity_type"),
        "related_entity_id": row.get("related_entity_id"),
        "link_url": row.get("link_url"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "read_at": _datetime_to_iso(row.get("read_at")),
        "created_at": _datetime_to_iso(row.get("created_at")),
    }

def _deserialize_alert_trigger_log(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "alert_id": row.get("alert_id"),
        "owner_id": row.get("owner_id"),
        "ticker": row.get("ticker"),
        "trigger_value": row.get("trigger_value"),
        "threshold_value": row.get("threshold_value"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
    }

def _deserialize_market_quote(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    payload = _json_loads(row.get("payload_json"), {})
    payload.update(
        {
            "ticker": row.get("ticker"),
            "source": row.get("source"),
            "quote_type": row.get("quote_type"),
            "is_delayed": bool(row.get("is_delayed", True)),
            "name": row.get("name"),
            "currency": row.get("currency"),
            "price": row.get("price"),
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "prev_close": row.get("prev_close"),
            "change": row.get("change_amount"),
            "change_pct": row.get("change_pct"),
            "volume": row.get("volume"),
            "market_cap": row.get("market_cap"),
            "quote_timestamp": _datetime_to_iso(row.get("quote_timestamp")),
            "synced_at": _datetime_to_iso(row.get("synced_at")),
        }
    )
    return payload

def _deserialize_backtest_run(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    summary = _json_loads(row.get("summary_json"), {})
    summary.update(
        {
            "id": row.get("id"),
            "owner_id": row.get("owner_id"),
            "ticker": row.get("ticker"),
            "strategy_key": row.get("strategy_key"),
            "strategy": row.get("strategy_name"),
            "interval": row.get("interval") or "1d",
            "start": _date_to_iso(row.get("start_date")),
            "end": _date_to_iso(row.get("end_date")),
            "capital": row.get("initial_capital"),
            "finalEquity": row.get("final_equity"),
            "totalReturn": row.get("total_return_pct"),
            "maxDrawdown": row.get("max_drawdown_pct"),
            "sharpe": row.get("sharpe_ratio"),
            "sellTrades": row.get("trade_count"),
            "winRate": row.get("win_rate_pct"),
            "bars": row.get("bars_count"),
            "feeRate": row.get("fee_rate"),
            "slippageRate": row.get("slippage_rate"),
            "stopLoss": row.get("stop_loss_pct"),
            "takeProfit": row.get("take_profit_pct"),
            "positionSizing": row.get("position_sizing"),
            "created_at": _datetime_to_iso(row.get("created_at")),
        }
    )
    return summary

def _deserialize_backtest_trade(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "backtest_run_id": row.get("backtest_run_id"),
        "owner_id": row.get("owner_id"),
        "ticker": row.get("ticker"),
        "side": row.get("side"),
        "entry_date": _datetime_to_iso(row.get("entry_date")),
        "entry_price": row.get("entry_price"),
        "exit_date": _datetime_to_iso(row.get("exit_date")),
        "exit_price": row.get("exit_price"),
        "quantity": row.get("quantity"),
        "gross_pnl": row.get("gross_pnl"),
        "net_pnl": row.get("net_pnl"),
        "return_pct": row.get("return_pct"),
        "fee_amount": row.get("fee_amount"),
        "holding_bars": row.get("holding_bars"),
        "exit_reason": row.get("exit_reason"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
    }

def _deserialize_backtest_equity_point(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "backtest_run_id": row.get("backtest_run_id"),
        "owner_id": row.get("owner_id"),
        "date": _datetime_to_iso(row.get("point_date")),
        "equity": row.get("equity"),
        "cash": row.get("cash"),
        "position_qty": row.get("position_qty"),
        "close_price": row.get("close_price"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
    }

def _deserialize_trade_journal_entry(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "ticker": row.get("ticker"),
        "market": row.get("market"),
        "direction": row.get("direction"),
        "strategy_code": row.get("strategy_code"),
        "entry_time": _datetime_to_iso(row.get("entry_time")),
        "entry_price": row.get("entry_price"),
        "exit_time": _datetime_to_iso(row.get("exit_time")),
        "exit_price": row.get("exit_price"),
        "size": row.get("size"),
        "stop_loss": row.get("stop_loss"),
        "take_profit": row.get("take_profit"),
        "entry_reason": row.get("entry_reason"),
        "exit_reason": row.get("exit_reason"),
        "emotion_tag": row.get("emotion_tag"),
        "review_notes": row.get("review_notes"),
        "result": _json_loads(row.get("result_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
        "tags": [],
        "attachments": [],
    }

def _deserialize_market_event(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "event_type": row.get("event_type"),
        "market": row.get("market"),
        "ticker": row.get("ticker"),
        "title": row.get("title"),
        "description": row.get("description"),
        "event_date": _date_to_iso(row.get("event_date")),
        "event_time": _datetime_to_iso(row.get("event_time")),
        "importance": row.get("importance"),
        "source": row.get("source"),
        "url": row.get("url"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_news_article(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "ticker": row.get("ticker"),
        "market": row.get("market"),
        "title": row.get("title"),
        "summary": row.get("summary"),
        "published_at": _datetime_to_iso(row.get("published_at")),
        "source": row.get("source"),
        "url": row.get("url"),
        "sentiment": row.get("sentiment"),
        "payload": _json_loads(row.get("payload_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_macro_snapshot(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    payload = _json_loads(row.get("payload_json"), {})
    payload.update(
        {
            "id": row.get("id"),
            "metric_code": row.get("metric_code"),
            "metric_name": row.get("metric_name"),
            "value": row.get("value"),
            "date": _date_to_iso(row.get("snapshot_date")),
            "source": row.get("source"),
            "created_at": _datetime_to_iso(row.get("created_at")),
            "updated_at": _datetime_to_iso(row.get("updated_at")),
        }
    )
    return payload

def _deserialize_taiwan_chip_snapshot(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "ticker": row.get("ticker"),
        "market": row.get("market"),
        "snapshot_date": _date_to_iso(row.get("snapshot_date")),
        "margin_balance": row.get("margin_balance"),
        "short_balance": row.get("short_balance"),
        "securities_lending_balance": row.get("securities_lending_balance"),
        "foreign_net_buy_sell": row.get("foreign_net_buy_sell"),
        "investment_trust_net_buy_sell": row.get("investment_trust_net_buy_sell"),
        "dealer_net_buy_sell": row.get("dealer_net_buy_sell"),
        "institutional_net_buy_sell": row.get("institutional_net_buy_sell"),
        "source": row.get("source"),
        "branch_payload": _json_loads(row.get("branch_payload_json"), {}),
        "summary": _json_loads(row.get("summary_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_institutional_snapshot(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    payload = _json_loads(row.get("payload_json"), {})
    if not isinstance(payload, dict):
        payload = {}
    payload.update(
        {
            "resolved_date": _date_to_iso(row.get("resolved_date")),
            "query_date": _date_to_iso(row.get("query_date")),
        }
    )
    return payload

def _deserialize_screener_preset(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "name": row.get("name"),
        "description": row.get("description"),
        "filters": _json_loads(row.get("filters_json"), {}),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_journal_filter_preset(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "name": row.get("name"),
        "description": row.get("description"),
        "scope": row.get("scope") or "ticker",
        "filters": _json_loads(row.get("filters_json"), {}),
        "use_count": int(row.get("use_count") or 0),
        "last_used_at": _datetime_to_iso(row.get("last_used_at")),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_asset_account(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "name": row.get("name"),
        "institution": row.get("institution"),
        "account_type": row.get("account_type"),
        "base_currency": row.get("base_currency") or "TWD",
        "settlement_account_id": row.get("settlement_account_id"),
        "auto_sync_trade_settlement": bool(row.get("auto_sync_trade_settlement", False)),
        "include_in_total": bool(row.get("include_in_total", True)),
        "sort_order": int(row.get("sort_order") or 0),
        "notes": row.get("notes"),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_asset_cash_ledger_entry(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "account_id": row.get("account_id"),
        "flow_date": _datetime_to_iso(row.get("flow_date")),
        "flow_type": row.get("flow_type"),
        "amount": row.get("amount"),
        "currency": row.get("currency"),
        "fx_rate_to_base": row.get("fx_rate_to_base"),
        "is_initial_balance": bool(row.get("is_initial_balance", False)),
        "source": row.get("source") or "manual",
        "import_key": row.get("import_key"),
        "linked_trade_id": row.get("linked_trade_id"),
        "linked_trade_role": row.get("linked_trade_role"),
        "counterparty": row.get("counterparty"),
        "note": row.get("note"),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_asset_trade_entry(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "account_id": row.get("account_id"),
        "trade_date": _datetime_to_iso(row.get("trade_date")),
        "ticker": row.get("ticker"),
        "display_name": row.get("display_name"),
        "market": row.get("market"),
        "asset_type": row.get("asset_type"),
        "currency": row.get("currency"),
        "side": row.get("side"),
        "quantity": row.get("quantity"),
        "price": row.get("price"),
        "gross_amount": row.get("gross_amount"),
        "fee_amount": row.get("fee_amount"),
        "tax_amount": row.get("tax_amount"),
        "net_amount": row.get("net_amount"),
        "fx_rate_to_base": row.get("fx_rate_to_base"),
        "is_initial_balance": bool(row.get("is_initial_balance", False)),
        "source": row.get("source"),
        "import_key": row.get("import_key"),
        "note": row.get("note"),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_asset_position_current(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "account_id": row.get("account_id"),
        "ticker": row.get("ticker"),
        "display_name": row.get("display_name"),
        "market": row.get("market"),
        "asset_type": row.get("asset_type"),
        "currency": row.get("currency"),
        "quantity": row.get("quantity"),
        "avg_cost": row.get("avg_cost"),
        "cost_basis": row.get("cost_basis"),
        "realized_pnl": row.get("realized_pnl"),
        "trade_count": row.get("trade_count"),
        "last_trade_at": _datetime_to_iso(row.get("last_trade_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_asset_valuation_current(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "account_id": row.get("account_id"),
        "ticker": row.get("ticker"),
        "quote_source": row.get("quote_source"),
        "quote_type": row.get("quote_type"),
        "is_delayed": bool(row.get("is_delayed", True)),
        "quote_timestamp": _datetime_to_iso(row.get("quote_timestamp")),
        "last_price": row.get("last_price"),
        "market_value": row.get("market_value"),
        "market_value_base": row.get("market_value_base"),
        "unrealized_pnl": row.get("unrealized_pnl"),
        "unrealized_pnl_base": row.get("unrealized_pnl_base"),
        "fx_rate_to_base": row.get("fx_rate_to_base"),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_asset_reconciliation_snapshot(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "account_id": row.get("account_id"),
        "snapshot_date": _datetime_to_iso(row.get("snapshot_date")),
        "cash_actual": row.get("cash_actual"),
        "cash_system": row.get("cash_system"),
        "market_value_actual": row.get("market_value_actual"),
        "market_value_system": row.get("market_value_system"),
        "positions_payload": _json_loads(row.get("positions_payload_json"), []),
        "note": row.get("note"),
        "created_at": _datetime_to_iso(row.get("created_at")),
    }

def _deserialize_asset_price_override(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "account_id": row.get("account_id"),
        "ticker": row.get("ticker"),
        "effective_at": _datetime_to_iso(row.get("effective_at")),
        "price": row.get("price"),
        "currency": row.get("currency") or "TWD",
        "fx_rate_to_base": row.get("fx_rate_to_base"),
        "force_override": bool(row.get("force_override", False)),
        "note": row.get("note"),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_asset_fx_rate(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "snapshot_date": _date_to_iso(row.get("snapshot_date")),
        "from_currency": row.get("from_currency") or "USD",
        "to_currency": row.get("to_currency") or "TWD",
        "rate": row.get("rate"),
        "source": row.get("source") or "manual",
        "note": row.get("note"),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _deserialize_asset_position_adjustment(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "owner_id": row.get("owner_id"),
        "account_id": row.get("account_id"),
        "event_date": _datetime_to_iso(row.get("event_date")),
        "ticker": row.get("ticker"),
        "event_type": row.get("event_type") or "adjustment",
        "quantity_delta": row.get("quantity_delta"),
        "cost_basis_delta": row.get("cost_basis_delta"),
        "cash_delta": row.get("cash_delta"),
        "currency": row.get("currency"),
        "split_ratio": row.get("split_ratio"),
        "target_ticker": row.get("target_ticker"),
        "target_display_name": row.get("target_display_name"),
        "target_market": row.get("target_market"),
        "target_asset_type": row.get("target_asset_type"),
        "note": row.get("note"),
        "created_at": _datetime_to_iso(row.get("created_at")),
        "updated_at": _datetime_to_iso(row.get("updated_at")),
    }

def _normalize_workspace_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})

    name = _required_string(source.get("name"), "Workspace name is required", max_length=128)
    data_payload = source.get("payload")
    if data_payload is None:
        data_payload = (existing or {}).get("payload", {})
    if data_payload is None:
        data_payload = {}
    if not isinstance(data_payload, dict):
        raise ValueError("Workspace payload must be an object")

    return {
        "name": name,
        "chart_layout": _optional_string(source.get("chart_layout"), max_length=32) or "single",
        "active_ticker": _optional_string(source.get("active_ticker"), max_length=32),
        "current_period": _optional_string(source.get("current_period"), max_length=16) or "1y",
        "current_interval": _optional_string(source.get("current_interval"), max_length=16) or "1d",
        "workspace_tab": _optional_string(source.get("workspace_tab"), max_length=32) or "chart",
        "comparison_mode": _optional_string(source.get("comparison_mode"), max_length=32) or "percent",
        "payload": data_payload,
        "is_default": _coerce_bool(source.get("is_default"), False),
    }

def _normalize_alert_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})

    ticker = _required_string(source.get("ticker"), "Alert ticker is required", max_length=32).upper()
    alert_type = _required_string(source.get("type"), "Alert type is required", max_length=32)
    condition = _required_string(source.get("condition"), "Alert condition is required", max_length=32)
    condition_payload = source.get("condition_payload")
    if condition_payload is None:
        condition_payload = (existing or {}).get("condition_payload", {})
    if condition_payload is None:
        condition_payload = {}
    if not isinstance(condition_payload, dict):
        raise ValueError("Alert condition payload must be an object")

    name = _optional_string(source.get("name"), max_length=128)
    notification_title = _optional_string(source.get("notification_title"), max_length=255)

    return {
        "name": name or f"{ticker} {condition}",
        "ticker": ticker,
        "type": alert_type,
        "condition": condition,
        "value": _optional_float(source.get("value")),
        "value2": _optional_float(source.get("value2")),
        "timeframe": _optional_string(source.get("timeframe"), max_length=16) or "1d",
        "condition_payload": condition_payload,
        "notification_title": notification_title or name or f"{ticker} {condition}",
        "note": _optional_string(source.get("note"), max_length=4000),
        "active": _coerce_bool(source.get("active"), True),
        "triggered": _coerce_bool(source.get("triggered"), False),
        "triggered_at": source.get("triggered_at"),
        "last_evaluated_at": source.get("last_evaluated_at"),
    }

def _normalize_notification_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(payload or {})
    title = _required_string(source.get("title"), "Notification title is required", max_length=255)
    message = _required_string(source.get("message"), "Notification message is required", max_length=4000)
    extra_payload = source.get("payload") or {}
    if not isinstance(extra_payload, dict):
        raise ValueError("Notification payload must be an object")

    return {
        "category": _optional_string(source.get("category"), max_length=64) or "system",
        "level": _optional_string(source.get("level"), max_length=32) or "info",
        "title": title,
        "message": message,
        "related_entity_type": _optional_string(source.get("related_entity_type"), max_length=64),
        "related_entity_id": _optional_int(source.get("related_entity_id")),
        "link_url": _optional_string(source.get("link_url"), max_length=255),
        "payload": extra_payload,
        "read_at": source.get("read_at"),
    }

def _normalize_quote_payload(quote: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(quote or {})
    ticker = _required_string(source.get("ticker"), "Quote ticker is required", max_length=32).upper()
    quote_timestamp = source.get("quote_timestamp")
    if quote_timestamp is None and source.get("ts") is not None:
        quote_timestamp = source.get("ts")

    return {
        "ticker": ticker,
        "source": _optional_string(source.get("source"), max_length=64) or "local_cache",
        "quote_type": _optional_string(source.get("quote_type"), max_length=64) or "delayed_snapshot",
        "is_delayed": _coerce_bool(source.get("is_delayed"), True),
        "resolved_symbol": _optional_string(source.get("resolved_symbol"), max_length=32),
        "market": _optional_string(source.get("market"), max_length=16),
        "exchange": _optional_string(source.get("exchange"), max_length=32),
        "name": _optional_string(source.get("name"), max_length=255) or ticker,
        "currency": _optional_string(source.get("currency"), max_length=16),
        "price": _optional_float(source.get("price")),
        "open": _optional_float(source.get("open")),
        "high": _optional_float(source.get("high")),
        "low": _optional_float(source.get("low")),
        "prev_close": _optional_float(source.get("prev_close")),
        "change": _optional_float(source.get("change")),
        "change_pct": _optional_float(source.get("change_pct")),
        "volume": _optional_int(source.get("volume")),
        "market_cap": _optional_int(source.get("market_cap")),
        "bid": _optional_float(source.get("bid")),
        "ask": _optional_float(source.get("ask")),
        "bid_size": _optional_int(source.get("bid_size")),
        "ask_size": _optional_int(source.get("ask_size")),
        "bids": source.get("bids") if isinstance(source.get("bids"), list) else [],
        "asks": source.get("asks") if isinstance(source.get("asks"), list) else [],
        "quote_timestamp": quote_timestamp,
        "ts": _optional_int(source.get("ts")),
    }

def _normalize_backtest_run_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(payload or {})
    summary = source.get("summary") or {}
    if not isinstance(summary, dict):
        raise ValueError("Backtest summary must be an object")

    ticker = _required_string(source.get("ticker"), "Backtest ticker is required", max_length=32).upper()
    strategy_key = _required_string(source.get("strategy_key"), "Backtest strategy key is required", max_length=64)
    strategy_name = _required_string(source.get("strategy_name"), "Backtest strategy name is required", max_length=128)
    start_date = _required_date_string(source.get("start_date"), "Backtest start date is required")
    end_date = _required_date_string(source.get("end_date"), "Backtest end date is required")

    return {
        "ticker": ticker,
        "strategy_key": strategy_key,
        "strategy_name": strategy_name,
        "interval": _optional_string(source.get("interval"), max_length=16) or "1d",
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": _optional_float(source.get("initial_capital")) or 0.0,
        "final_equity": _optional_float(source.get("final_equity")) or 0.0,
        "total_return_pct": _optional_float(source.get("total_return_pct")) or 0.0,
        "max_drawdown_pct": _optional_float(source.get("max_drawdown_pct")) or 0.0,
        "sharpe_ratio": _optional_float(source.get("sharpe_ratio")) or 0.0,
        "trade_count": _optional_int(source.get("trade_count")) or 0,
        "win_rate_pct": _optional_float(source.get("win_rate_pct")) or 0.0,
        "bars_count": _optional_int(source.get("bars_count")) or 0,
        "fee_rate": _optional_float(source.get("fee_rate")) or 0.0,
        "slippage_rate": _optional_float(source.get("slippage_rate")) or 0.0,
        "stop_loss_pct": _optional_float(source.get("stop_loss_pct")),
        "take_profit_pct": _optional_float(source.get("take_profit_pct")),
        "position_sizing": _optional_string(source.get("position_sizing"), max_length=32) or "full_equity",
        "summary": summary,
    }

def _normalize_trade_journal_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})

    tags = source.get("tags")
    if tags is None:
        tags = (existing or {}).get("tags", [])
    attachments = source.get("attachments")
    if attachments is None:
        attachments = (existing or {}).get("attachments", [])

    normalized_tags = [
        tag
        for tag in dict.fromkeys(
            _optional_string(item, max_length=64)
            for item in (tags or [])
        )
        if tag
    ]

    normalized_attachments = []
    for item in attachments or []:
        if not isinstance(item, dict):
            raise ValueError("Trade journal attachments must be objects")
        file_path = _required_string(item.get("file_path"), "Attachment file_path is required", max_length=512)
        normalized_attachments.append(
            {
                "file_path": file_path,
                "file_type": _optional_string(item.get("file_type"), max_length=64),
            }
        )

    ticker = _required_string(source.get("ticker"), "Trade journal ticker is required", max_length=32).upper()
    entry_time = source.get("entry_time") or (existing or {}).get("entry_time")
    entry_price = source.get("entry_price") if "entry_price" in source else (existing or {}).get("entry_price")
    size = source.get("size") if "size" in source else (existing or {}).get("size", 0)
    entry_price_value = _optional_float(entry_price)
    size_value = _optional_float(size)
    if entry_price_value is None or entry_price_value <= 0:
        raise ValueError("Trade journal entry_price must be greater than 0")
    if size_value is None or size_value <= 0:
        raise ValueError("Trade journal size must be greater than 0")

    normalized = {
        "ticker": ticker,
        "market": _optional_string(source.get("market"), max_length=32),
        "direction": _optional_string(source.get("direction"), max_length=16) or "long",
        "strategy_code": _optional_string(source.get("strategy_code"), max_length=64),
        "entry_time": _required_string(entry_time, "Trade journal entry_time is required", max_length=64),
        "entry_price": entry_price_value,
        "exit_time": _optional_string(source.get("exit_time"), max_length=64),
        "exit_price": _optional_float(source.get("exit_price")),
        "size": size_value,
        "stop_loss": _optional_float(source.get("stop_loss")),
        "take_profit": _optional_float(source.get("take_profit")),
        "entry_reason": _optional_string(source.get("entry_reason"), max_length=8000),
        "exit_reason": _optional_string(source.get("exit_reason"), max_length=8000),
        "emotion_tag": _optional_string(source.get("emotion_tag"), max_length=64),
        "review_notes": _optional_string(source.get("review_notes"), max_length=20000),
        "tags": normalized_tags,
        "attachments": normalized_attachments,
    }
    explicit_result = source.get("result")
    if explicit_result is not None and not isinstance(explicit_result, dict):
        raise ValueError("Trade journal result must be an object")
    normalized["result"] = dict(explicit_result or compute_trade_result(normalized))
    return normalized

def _normalize_market_event_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(payload or {})
    return {
        "event_type": _required_string(source.get("event_type"), "Market event type is required", max_length=64),
        "market": _optional_string(source.get("market"), max_length=32),
        "ticker": _optional_string(source.get("ticker"), max_length=32),
        "title": _required_string(source.get("title"), "Market event title is required", max_length=255),
        "description": _optional_string(source.get("description"), max_length=4000),
        "event_date": _required_date_string(source.get("event_date"), "Market event date is required"),
        "event_time": source.get("event_time"),
        "importance": _optional_string(source.get("importance"), max_length=32),
        "source": _optional_string(source.get("source"), max_length=128),
        "url": _optional_string(source.get("url"), max_length=512),
        "payload": source.get("payload") if isinstance(source.get("payload"), dict) else {},
    }

def _normalize_news_article_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(payload or {})
    return {
        "ticker": _optional_string(source.get("ticker"), max_length=32),
        "market": _optional_string(source.get("market"), max_length=32),
        "title": _required_string(source.get("title"), "News article title is required", max_length=255),
        "summary": _optional_string(source.get("summary"), max_length=4000),
        "published_at": _required_string(source.get("published_at"), "News article published_at is required", max_length=64),
        "source": _optional_string(source.get("source"), max_length=128),
        "url": _optional_string(source.get("url"), max_length=512),
        "sentiment": _optional_string(source.get("sentiment"), max_length=32),
        "payload": source.get("payload") if isinstance(source.get("payload"), dict) else {},
    }

def _normalize_macro_snapshot_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(payload or {})
    return {
        "metric_code": _required_string(source.get("metric_code"), "Macro snapshot metric_code is required", max_length=64),
        "metric_name": _required_string(source.get("metric_name"), "Macro snapshot metric_name is required", max_length=128),
        "value": _optional_float(source.get("value")),
        "snapshot_date": _required_date_string(source.get("date") or source.get("snapshot_date"), "Macro snapshot date is required"),
        "source": _optional_string(source.get("source"), max_length=128),
        "payload": source.get("payload") if isinstance(source.get("payload"), dict) else {
            key: value
            for key, value in source.items()
            if key not in {"metric_code", "metric_name", "value", "date", "snapshot_date", "source"}
        },
    }

def _normalize_taiwan_chip_snapshot_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(payload or {})
    return {
        "ticker": _required_string(source.get("ticker"), "Taiwan chip ticker is required", max_length=32).upper(),
        "market": _optional_string(source.get("market"), max_length=32),
        "snapshot_date": _required_date_string(source.get("snapshot_date") or source.get("date"), "Taiwan chip snapshot date is required"),
        "margin_balance": _optional_int(source.get("margin_balance")),
        "short_balance": _optional_int(source.get("short_balance")),
        "securities_lending_balance": _optional_int(source.get("securities_lending_balance")),
        "foreign_net_buy_sell": _optional_int(source.get("foreign_net_buy_sell")),
        "investment_trust_net_buy_sell": _optional_int(source.get("investment_trust_net_buy_sell")),
        "dealer_net_buy_sell": _optional_int(source.get("dealer_net_buy_sell")),
        "institutional_net_buy_sell": _optional_int(source.get("institutional_net_buy_sell")),
        "source": _optional_string(source.get("source"), max_length=128),
        "branch_payload": source.get("branch_payload") if isinstance(source.get("branch_payload"), dict) else {},
        "summary": source.get("summary") if isinstance(source.get("summary"), dict) else {},
    }

def _normalize_screener_preset_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})
    filters = source.get("filters")
    if filters is None:
        filters = (existing or {}).get("filters", {})
    if not isinstance(filters, dict):
        raise ValueError("Screener preset filters must be an object")
    return {
        "name": _required_string(source.get("name"), "Screener preset name is required", max_length=128),
        "description": _optional_string(source.get("description"), max_length=512),
        "filters": filters,
    }

def _normalize_journal_filter_preset_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})
    filters = source.get("filters")
    if filters is None:
        filters = (existing or {}).get("filters", {})
    if not isinstance(filters, dict):
        raise ValueError("Journal filter preset filters must be an object")

    normalized_scope = _optional_string(source.get("scope"), max_length=32) or "ticker"
    if normalized_scope not in {"ticker", "all"}:
        raise ValueError("Journal filter preset scope must be ticker or all")

    normalized_filters = {
        key: _optional_string(filters.get(key), max_length=128) or ""
        for key in ["market", "strategy_code", "tag", "search"]
    }

    return {
        "name": _required_string(source.get("name"), "Journal filter preset name is required", max_length=128),
        "description": _optional_string(source.get("description"), max_length=512),
        "scope": normalized_scope,
        "filters": normalized_filters,
    }

def _normalize_asset_account_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})
    account_type = _optional_string(source.get("account_type"), max_length=64) or "brokerage"
    settlement_account_id = _optional_int(source.get("settlement_account_id"))
    if settlement_account_id is not None and settlement_account_id <= 0:
        settlement_account_id = None
    auto_sync_trade_settlement = _coerce_bool(source.get("auto_sync_trade_settlement"), False)
    if auto_sync_trade_settlement and account_type != "brokerage":
        raise ValueError("Auto trade settlement sync requires a brokerage account")
    if auto_sync_trade_settlement and settlement_account_id is None:
        raise ValueError("Settlement account is required when auto trade settlement sync is enabled")
    return {
        "name": _required_string(source.get("name"), "Asset account name is required", max_length=128),
        "institution": _optional_string(source.get("institution"), max_length=128),
        "account_type": account_type,
        "base_currency": (_optional_string(source.get("base_currency"), max_length=16) or "TWD").upper(),
        "settlement_account_id": settlement_account_id,
        "auto_sync_trade_settlement": auto_sync_trade_settlement,
        "include_in_total": _coerce_bool(source.get("include_in_total"), True),
        "sort_order": _optional_int(source.get("sort_order")) or 0,
        "notes": _optional_string(source.get("notes"), max_length=4000),
    }

def _normalize_asset_cash_ledger_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})
    account_id = _optional_int(source.get("account_id"))
    if account_id is None or account_id <= 0:
        raise ValueError("Asset cash ledger account_id is required")
    flow_type = (_required_string(source.get("flow_type"), "Asset cash ledger flow_type is required", max_length=32)).lower()
    amount = _optional_float(source.get("amount"))
    if amount is None:
        raise ValueError("Asset cash ledger amount is required")
    fx_rate_to_base = _optional_float(source.get("fx_rate_to_base"))
    if fx_rate_to_base is not None and fx_rate_to_base <= 0:
        raise ValueError("Asset cash ledger fx_rate_to_base must be greater than 0")
    return {
        "account_id": account_id,
        "flow_date": _required_string(source.get("flow_date"), "Asset cash ledger flow_date is required", max_length=64),
        "flow_type": flow_type,
        "amount": amount,
        "currency": (_optional_string(source.get("currency"), max_length=16) or "TWD").upper(),
        "fx_rate_to_base": fx_rate_to_base or 1.0,
        "is_initial_balance": _coerce_bool(source.get("is_initial_balance"), False),
        "source": _optional_string(source.get("source"), max_length=64) or "manual",
        "import_key": _optional_string(source.get("import_key"), max_length=64),
        "linked_trade_id": _optional_int(source.get("linked_trade_id")),
        "linked_trade_role": _optional_string(source.get("linked_trade_role"), max_length=32),
        "counterparty": _optional_string(source.get("counterparty"), max_length=128),
        "note": _optional_string(source.get("note"), max_length=4000),
    }

def _normalize_asset_trade_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})
    account_id = _optional_int(source.get("account_id"))
    if account_id is None or account_id <= 0:
        raise ValueError("Asset trade account_id is required")
    quantity = _optional_float(source.get("quantity"))
    price = _optional_float(source.get("price"))
    if quantity is None or quantity <= 0:
        raise ValueError("Asset trade quantity must be greater than 0")
    if price is None or price <= 0:
        raise ValueError("Asset trade price must be greater than 0")

    side = (_required_string(source.get("side"), "Asset trade side is required", max_length=16)).lower()
    if side not in {"buy", "sell"}:
        raise ValueError("Asset trade side must be buy or sell")

    fee_amount = _optional_float(source.get("fee_amount")) or 0.0
    tax_amount = _optional_float(source.get("tax_amount")) or 0.0
    fx_rate_to_base = _optional_float(source.get("fx_rate_to_base"))
    if fx_rate_to_base is not None and fx_rate_to_base <= 0:
        raise ValueError("Asset trade fx_rate_to_base must be greater than 0")
    gross_amount = quantity * price
    net_amount = gross_amount + fee_amount + tax_amount if side == "buy" else gross_amount - fee_amount - tax_amount

    return {
        "account_id": account_id,
        "trade_date": _required_string(source.get("trade_date"), "Asset trade trade_date is required", max_length=64),
        "ticker": _required_string(source.get("ticker"), "Asset trade ticker is required", max_length=32).upper(),
        "display_name": _optional_string(source.get("display_name"), max_length=255),
        "market": _optional_string(source.get("market"), max_length=32),
        "asset_type": _optional_string(source.get("asset_type"), max_length=32) or "stock",
        "currency": (_optional_string(source.get("currency"), max_length=16) or "TWD").upper(),
        "side": side,
        "quantity": quantity,
        "price": price,
        "gross_amount": gross_amount,
        "fee_amount": fee_amount,
        "tax_amount": tax_amount,
        "net_amount": net_amount,
        "fx_rate_to_base": fx_rate_to_base or 1.0,
        "is_initial_balance": _coerce_bool(source.get("is_initial_balance"), False),
        "source": _optional_string(source.get("source"), max_length=64) or "manual",
        "import_key": _optional_string(source.get("import_key"), max_length=64),
        "note": _optional_string(source.get("note"), max_length=4000),
    }

def _normalize_asset_reconciliation_snapshot_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})

    account_id = _optional_int(source.get("account_id"))
    if account_id is None or account_id <= 0:
        raise ValueError("Asset reconciliation snapshot account_id is required")

    cash_actual = _optional_float(source.get("cash_actual"))
    market_value_actual = _optional_float(source.get("market_value_actual"))
    if cash_actual is None and market_value_actual is None:
        raise ValueError("Asset reconciliation snapshot requires cash_actual or market_value_actual")

    positions_payload = source.get("positions_payload")
    if positions_payload is None:
        positions_payload = (existing or {}).get("positions_payload", [])
    if not isinstance(positions_payload, (list, dict)):
        raise ValueError("Asset reconciliation positions_payload must be a list or object")

    return {
        "account_id": account_id,
        "snapshot_date": _required_string(
            source.get("snapshot_date"),
            "Asset reconciliation snapshot_date is required",
            max_length=64,
        ),
        "cash_actual": cash_actual,
        "cash_system": _optional_float(source.get("cash_system")),
        "market_value_actual": market_value_actual,
        "market_value_system": _optional_float(source.get("market_value_system")),
        "positions_payload": positions_payload,
        "note": _optional_string(source.get("note"), max_length=4000),
    }

def _normalize_asset_price_override_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})

    account_id = _optional_int(source.get("account_id"))
    if account_id is not None and account_id <= 0:
        raise ValueError("Asset price override account_id must be greater than 0")

    price = _optional_float(source.get("price"))
    if price is None or price <= 0:
        raise ValueError("Asset price override price must be greater than 0")

    fx_rate_to_base = _optional_float(source.get("fx_rate_to_base"))
    if fx_rate_to_base is not None and fx_rate_to_base <= 0:
        raise ValueError("Asset price override fx_rate_to_base must be greater than 0")

    return {
        "account_id": account_id,
        "ticker": _required_string(source.get("ticker"), "Asset price override ticker is required", max_length=32).upper(),
        "effective_at": _required_string(source.get("effective_at"), "Asset price override effective_at is required", max_length=64),
        "price": price,
        "currency": (_optional_string(source.get("currency"), max_length=16) or "TWD").upper(),
        "fx_rate_to_base": fx_rate_to_base,
        "force_override": _coerce_bool(source.get("force_override"), False),
        "note": _optional_string(source.get("note"), max_length=4000),
    }

def _normalize_asset_fx_rate_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})

    rate = _optional_float(source.get("rate"))
    if rate is None or rate <= 0:
        raise ValueError("Asset FX rate must be greater than 0")

    return {
        "snapshot_date": _required_date_string(source.get("snapshot_date"), "Asset FX rate snapshot_date is required"),
        "from_currency": (_required_string(source.get("from_currency"), "Asset FX rate from_currency is required", max_length=16)).upper(),
        "to_currency": (_required_string(source.get("to_currency"), "Asset FX rate to_currency is required", max_length=16)).upper(),
        "rate": rate,
        "source": _optional_string(source.get("source"), max_length=64) or "manual",
        "note": _optional_string(source.get("note"), max_length=4000),
    }

def _normalize_asset_position_adjustment_payload(
    payload: Optional[Dict[str, Any]],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = dict(existing or {})
    source.update(payload or {})

    account_id = _optional_int(source.get("account_id"))
    if account_id is None or account_id <= 0:
        raise ValueError("Asset position adjustment account_id is required")

    event_type = (_optional_string(source.get("event_type"), max_length=32) or "adjustment").lower()
    if event_type not in {"adjustment", "split", "symbol_change"}:
        raise ValueError("Asset position adjustment event_type must be adjustment, split, or symbol_change")

    quantity_delta = _optional_float(source.get("quantity_delta"))
    cost_basis_delta = _optional_float(source.get("cost_basis_delta"))
    cash_delta = _optional_float(source.get("cash_delta"))
    split_ratio = _optional_float(source.get("split_ratio"))
    if split_ratio is not None and split_ratio <= 0:
        raise ValueError("Asset position adjustment split_ratio must be greater than 0")
    if event_type == "split" and (split_ratio is None or split_ratio <= 0):
        raise ValueError("Asset split adjustment requires split_ratio")
    target_ticker = _optional_string(source.get("target_ticker"), max_length=32)
    if event_type == "symbol_change" and not target_ticker:
        raise ValueError("Asset symbol_change adjustment requires target_ticker")
    if event_type == "adjustment" and quantity_delta is None and cost_basis_delta is None and cash_delta is None:
        raise ValueError("Asset adjustment requires quantity_delta, cost_basis_delta, or cash_delta")

    return {
        "account_id": account_id,
        "event_date": _required_string(source.get("event_date"), "Asset position adjustment event_date is required", max_length=64),
        "ticker": _required_string(source.get("ticker"), "Asset position adjustment ticker is required", max_length=32).upper(),
        "event_type": event_type,
        "quantity_delta": quantity_delta,
        "cost_basis_delta": cost_basis_delta,
        "cash_delta": cash_delta,
        "currency": (_optional_string(source.get("currency"), max_length=16) or "").upper() or None,
        "split_ratio": split_ratio,
        "target_ticker": target_ticker.upper() if target_ticker else None,
        "target_display_name": _optional_string(source.get("target_display_name"), max_length=255),
        "target_market": _optional_string(source.get("target_market"), max_length=32),
        "target_asset_type": _optional_string(source.get("target_asset_type"), max_length=32),
        "note": _optional_string(source.get("note"), max_length=4000),
    }

def _required_string(value: Any, error_message: str, max_length: Optional[int] = None) -> str:
    normalized = _optional_string(value, max_length=max_length)
    if not normalized:
        raise ValueError(error_message)
    return normalized

def _required_date_string(value: Any, error_message: str) -> str:
    normalized = _optional_date_string(value)
    if not normalized:
        raise ValueError(error_message)
    return normalized

def _optional_date_string(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            return datetime.fromisoformat(normalized).date().isoformat()
        except ValueError:
            try:
                return date.fromisoformat(normalized).isoformat()
            except ValueError:
                return None
    return None

def _optional_string(value: Any, max_length: Optional[int] = None) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if max_length:
        return text[:max_length]
    return text

def _optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Unable to parse float from {value!r}")

def _optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Unable to parse int from {value!r}")

def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)

def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)

def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default

def _parse_datetime_value(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        if value.tzinfo:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
        return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    return None

def _period_to_date(period: str) -> str:
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    if not period:
        return (now_utc - timedelta(days=365)).strftime("%Y-%m-%d")
    if period == "max":
        return "1900-01-01"
    n, unit = int(period[:-2]) if period[:-2].isdigit() else int(period[:-1]), period[-1]
    if period[:-2].isdigit():
        n, unit = int(period[:-2]), period[-2:]
        if unit == "mo":
            d = now_utc - timedelta(days=n * 30)
        elif unit == "yr" or unit == "y":
            d = now_utc - timedelta(days=n * 365)
        else:
            d = now_utc - timedelta(days=30)
    else:
        n = int(period[:-1])
        unit = period[-1]
        if unit == "y":
            d = now_utc - timedelta(days=n * 365)
        elif unit == "m":
            d = now_utc - timedelta(days=n * 30)
        elif unit == "d":
            d = now_utc - timedelta(days=n)
        else:
            d = now_utc - timedelta(days=365)
    return d.strftime("%Y-%m-%d")

def _build_mysql_error_message(exc: Exception) -> str:
    return (
        "MySQL 連線失敗。\n"
        f"目前設定: host={MYSQL_HOST}, port={MYSQL_PORT}, user={MYSQL_USER}, "
        f"database={MYSQL_DATABASE}, password={'已設定' if MYSQL_PASSWORD else '未設定'}。\n"
        "請在專案根目錄建立 `.env`，至少設定 `MYSQL_USER`、`MYSQL_PASSWORD`，必要時也設定 "
        "`MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_DATABASE`。\n"
        "你可以直接複製 `.env.example` 成 `.env` 再修改。\n"
        f"原始錯誤: {exc}"
    )

def _build_mysql_connection_error_message(exc: Exception) -> str:
    message = str(exc)
    if "cryptography" in message and ("caching_sha2_password" in message or "sha256_password" in message):
        return (
            "MySQL 連線失敗：目前 MySQL 使用 `caching_sha2_password` / `sha256_password` 驗證，"
            "但 Python 環境缺少 `cryptography` 套件。\n"
            "請重新安裝 backend dependencies，或手動執行：\n"
            "`venv\\Scripts\\python.exe -m pip install cryptography`\n"
            f"原始錯誤: {exc}"
        )
    return _build_mysql_error_message(exc)

def _escape_identifier(value: str) -> str:
    return value.replace("`", "``")

def _date_to_iso(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)

def _datetime_to_iso(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).isoformat()
    return str(value)

def _deserialize_fubon_market_snapshot(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    payload = _json_loads(row.get("payload_json"), {})
    payload.update(
        {
            "id": row.get("id"),
            "market": row.get("market"),
            "snapshot_date": _date_to_iso(row.get("snapshot_date")),
            "created_at": _datetime_to_iso(row.get("created_at")),
        }
    )
    return payload

__all__ = [name for name in globals() if not name.startswith("__")]

