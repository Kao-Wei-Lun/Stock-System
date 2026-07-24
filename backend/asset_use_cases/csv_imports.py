"""CSV and journal mapping helpers for asset imports."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Any, Dict, List

from data_fetcher import normalize_ticker
from database.helpers import (
    _normalize_asset_cash_ledger_payload,
    _normalize_asset_trade_payload,
    _parse_datetime_value,
)


def normalize_csv_text(value: str) -> str:
    return str(value or "").replace("\ufeff", "").strip()


def normalize_csv_row(row: Dict[str, Any]) -> Dict[str, str]:
    normalized = {}
    for key, value in (row or {}).items():
        normalized_key = str(key or "").strip().lower()
        if normalized_key:
            normalized[normalized_key] = str(value or "").strip()
    return normalized


def csv_import_error_message(exc: Exception) -> str:
    message = str(exc)
    if message.startswith("Asset account ") and message.endswith(" does not exist"):
        account_id = message.removeprefix("Asset account ").removesuffix(" does not exist")
        return f"資產帳戶 {account_id} 不存在"
    translations = (
        ("Asset trade quantity must be greater than 0", "交易數量必須大於 0"),
        ("Asset trade price must be greater than 0", "交易價格必須大於 0"),
        ("Asset trade side must be buy or sell", "交易方向必須為 buy 或 sell"),
        ("Asset trade ticker is required", "交易商品代號不可空白"),
        ("Asset trade trade_date is required", "交易日期不可空白"),
        ("Asset cash ledger amount is required", "現金金額不可空白"),
        ("Asset cash ledger flow_type is required", "現金流向類型不可空白"),
        ("Asset cash ledger flow_date is required", "現金日期不可空白"),
        ("Unable to parse trade_date", "無法解析交易日期"),
        ("Unable to parse flow_date", "無法解析現金日期"),
        ("Unable to parse account_id", "無法解析帳戶代號"),
        (
            "CSV row is missing account_id/account_name and no default_account_id was provided",
            "CSV 列缺少 account_id/account_name，且未選擇預設帳戶",
        ),
        ("Unable to resolve account_name", "無法依帳戶名稱找到資產帳戶"),
    )
    for source, translated in translations:
        if source in message:
            return f"{translated}{message.split(source, 1)[1]}"
    return f"資料格式錯誤：{message}"


def build_account_lookups(
    accounts: List[Dict[str, Any]],
) -> tuple[Dict[int, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    by_id = {int(account["id"]): account for account in accounts if account.get("id") is not None}
    by_name = {
        str(account.get("name") or "").strip().lower(): account
        for account in accounts
        if account.get("name")
    }
    return by_id, by_name


def resolve_account_id_from_csv(
    row: Dict[str, str],
    *,
    default_account_id: int | None,
    accounts_by_id: Dict[int, Dict[str, Any]],
    accounts_by_name: Dict[str, Dict[str, Any]],
) -> int:
    raw_account_id = row.get("account_id") or row.get("account")
    if raw_account_id:
        try:
            account_id = int(raw_account_id)
        except ValueError as exc:
            raise ValueError(f"Unable to parse account_id {raw_account_id!r}") from exc
        if account_id not in accounts_by_id:
            raise ValueError(f"Asset account {account_id} does not exist")
        return account_id

    raw_account_name = (row.get("account_name") or row.get("account") or "").strip().lower()
    if raw_account_name:
        account = accounts_by_name.get(raw_account_name)
        if not account:
            raise ValueError(f"Unable to resolve account_name {raw_account_name!r}")
        return int(account["id"])
    if default_account_id is None:
        raise ValueError("CSV row is missing account_id/account_name and no default_account_id was provided")
    if default_account_id not in accounts_by_id:
        raise ValueError(f"Asset account {default_account_id} does not exist")
    return int(default_account_id)


def resolve_trade_currency_for_market(market: str) -> str:
    return "USD" if str(market or "").strip().upper() == "US" else "TWD"


def infer_trade_market(raw_ticker: str) -> str:
    normalized = normalize_ticker(raw_ticker)
    if normalized.endswith(".TW") or normalized.endswith(".TWO"):
        return "TW"
    if normalized.endswith(".HK"):
        return "HK"
    return "US"


def parse_trade_csv_payload(
    row: Dict[str, str],
    *,
    default_account_id: int | None,
    accounts_by_id: Dict[int, Dict[str, Any]],
    accounts_by_name: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    account_id = resolve_account_id_from_csv(
        row,
        default_account_id=default_account_id,
        accounts_by_id=accounts_by_id,
        accounts_by_name=accounts_by_name,
    )
    raw_ticker = row.get("ticker") or row.get("symbol")
    market = row.get("market") or infer_trade_market(raw_ticker or "")
    return {
        "account_id": account_id,
        "trade_date": row.get("trade_date") or row.get("date") or row.get("datetime"),
        "ticker": normalize_ticker(raw_ticker or ""),
        "display_name": row.get("display_name") or row.get("name") or None,
        "market": market,
        "asset_type": row.get("asset_type") or "stock",
        "currency": (row.get("currency") or resolve_trade_currency_for_market(market)).upper(),
        "side": (row.get("side") or row.get("direction") or "").lower(),
        "quantity": row.get("quantity") or row.get("size"),
        "price": row.get("price") or row.get("trade_price"),
        "fee_amount": row.get("fee_amount") or row.get("fee") or 0,
        "tax_amount": row.get("tax_amount") or row.get("tax") or 0,
        "fx_rate_to_base": row.get("fx_rate_to_base") or row.get("fx_rate") or 1,
        "source": row.get("source") or "csv_import",
        "note": row.get("note") or None,
    }


def parse_cash_csv_payload(
    row: Dict[str, str],
    *,
    default_account_id: int | None,
    accounts_by_id: Dict[int, Dict[str, Any]],
    accounts_by_name: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    account_id = resolve_account_id_from_csv(
        row,
        default_account_id=default_account_id,
        accounts_by_id=accounts_by_id,
        accounts_by_name=accounts_by_name,
    )
    account = accounts_by_id[account_id]
    return {
        "account_id": account_id,
        "flow_date": row.get("flow_date") or row.get("date") or row.get("datetime"),
        "flow_type": (row.get("flow_type") or row.get("type") or "").lower(),
        "amount": row.get("amount"),
        "currency": (row.get("currency") or account.get("base_currency") or "TWD").upper(),
        "fx_rate_to_base": row.get("fx_rate_to_base") or row.get("fx_rate") or 1,
        "counterparty": row.get("counterparty") or row.get("from_to") or None,
        "note": row.get("note") or None,
    }


def run_csv_import(
    csv_text: str,
    *,
    default_account_id: int | None,
    accounts: List[Dict[str, Any]],
    parser,
    item_type: str,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    normalized_csv = normalize_csv_text(csv_text)
    if not normalized_csv:
        raise ValueError("CSV text is required")
    reader = csv.DictReader(io.StringIO(normalized_csv))
    if not reader.fieldnames:
        raise ValueError("CSV must include a header row")

    accounts_by_id, accounts_by_name = build_account_lookups(accounts)
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for index, raw_row in enumerate(reader, start=2):
        row = normalize_csv_row(raw_row)
        if not any(row.values()):
            continue
        try:
            parsed = parser(
                row,
                default_account_id=default_account_id,
                accounts_by_id=accounts_by_id,
                accounts_by_name=accounts_by_name,
            )
            normalized = (
                _normalize_asset_trade_payload(parsed)
                if item_type == "trade"
                else _normalize_asset_cash_ledger_payload(parsed)
            )
            date_field = "trade_date" if item_type == "trade" else "flow_date"
            if _parse_datetime_value(normalized.get(date_field)) is None:
                raise ValueError(f"Unable to parse {date_field} {normalized.get(date_field)!r}")
            reference = next(
                (
                    row.get(key)
                    for key in ("external_id", "transaction_id", "trade_id", "order_id", "reference_id")
                    if row.get(key)
                ),
                None,
            )
            normalized["import_key"] = build_asset_import_key(item_type, normalized, reference=reference)
            normalized["import_row"] = index
            normalized["import_reference"] = reference
            normalized["import_status"] = "importable"
            items.append(normalized)
        except Exception as exc:  # noqa: BLE001 - collect row-level import issues
            errors.append({"row": index, "message": csv_import_error_message(exc), "payload": row})

    seen_rows: Dict[str, int] = {}
    for item in items:
        import_key = str(item.get("import_key") or "")
        if import_key in seen_rows:
            item["import_status"] = "duplicate_in_file"
            item["duplicate_of_row"] = seen_rows[import_key]
        else:
            seen_rows[import_key] = int(item["import_row"])
    return items, errors


def canonical_import_number(value: Any) -> str:
    return format(float(value or 0), ".12g")


def canonical_import_datetime(value: Any) -> str:
    parsed = _parse_datetime_value(value)
    return "" if parsed is None else parsed.isoformat(timespec="microseconds")


def build_asset_import_key(item_type: str, item: Dict[str, Any], *, reference: str | None = None) -> str:
    if reference:
        identity: Dict[str, Any] = {
            "type": item_type,
            "account_id": int(item.get("account_id") or 0),
            "reference": str(reference).strip(),
        }
    elif item_type == "trade":
        identity = {
            "type": "trade",
            "account_id": int(item.get("account_id") or 0),
            "date": canonical_import_datetime(item.get("trade_date")),
            "ticker": str(item.get("ticker") or "").strip().upper(),
            "side": str(item.get("side") or "").strip().lower(),
            "quantity": canonical_import_number(item.get("quantity")),
            "price": canonical_import_number(item.get("price")),
            "fee": canonical_import_number(item.get("fee_amount")),
            "tax": canonical_import_number(item.get("tax_amount")),
            "currency": str(item.get("currency") or "").strip().upper(),
        }
    else:
        identity = {
            "type": "cash",
            "account_id": int(item.get("account_id") or 0),
            "date": canonical_import_datetime(item.get("flow_date")),
            "flow_type": str(item.get("flow_type") or "").strip().lower(),
            "amount": canonical_import_number(item.get("amount")),
            "currency": str(item.get("currency") or "").strip().upper(),
            "counterparty": str(item.get("counterparty") or "").strip().lower(),
        }
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def mark_database_duplicates(
    items: List[Dict[str, Any]],
    existing_items: List[Dict[str, Any]],
    *,
    item_type: str,
    stored_import_keys: Dict[str, int] | None = None,
) -> None:
    existing_keys: Dict[str, Any] = dict(stored_import_keys or {})
    for existing in existing_items:
        import_key = str(existing.get("import_key") or "") or build_asset_import_key(item_type, existing)
        existing_keys.setdefault(import_key, existing.get("id"))
    for item in items:
        if item.get("import_status") != "importable":
            continue
        existing_id = existing_keys.get(str(item.get("import_key") or ""))
        if existing_id is not None:
            item["import_status"] = "duplicate_in_database"
            item["existing_id"] = existing_id


def csv_import_summary(
    items: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
    **extra: Any,
) -> Dict[str, Any]:
    file_duplicates = sum(1 for item in items if item.get("import_status") == "duplicate_in_file")
    database_duplicates = sum(1 for item in items if item.get("import_status") == "duplicate_in_database")
    return {
        "input_count": len(items) + len(errors),
        "row_count": len(items),
        "valid_count": len(items),
        "importable_count": sum(1 for item in items if item.get("import_status") == "importable"),
        "duplicate_count": file_duplicates + database_duplicates,
        "file_duplicate_count": file_duplicates,
        "database_duplicate_count": database_duplicates,
        "error_count": len(errors),
        **extra,
    }


def asset_import_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    metadata_fields = {
        "import_row",
        "import_reference",
        "import_status",
        "duplicate_of_row",
        "existing_id",
    }
    return {key: value for key, value in item.items() if key not in metadata_fields}


async def run_atomic_asset_import(
    *,
    repository,
    owner_id: int,
    import_type: str,
    source_name: str | None,
    items: List[Dict[str, Any]],
    duplicates: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
    create_item,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Persist one import as an auditable all-or-nothing transaction."""
    importable = [item for item in items if item.get("import_status") == "importable"]
    batch = await repository.create_asset_import_batch(
        {
            "import_type": import_type,
            "source_name": source_name,
            "row_count": len(items) + len(errors),
            "skipped_count": len(duplicates),
            "error_count": len(errors),
            "metadata": {"importable_count": len(importable), "duplicate_count": len(duplicates)},
        },
        owner_id=owner_id,
    )
    batch_id = int(batch["id"])
    if errors:
        batch = await repository.finalize_asset_import_batch(
            batch_id,
            {
                **batch,
                "status": "failed",
                "created_count": 0,
                "error_count": len(errors),
                "error_message": "CSV validation failed; no rows were imported.",
            },
            owner_id=owner_id,
        )
        return [], list(errors), batch

    created: List[Dict[str, Any]] = []
    current_item: Dict[str, Any] | None = None
    try:
        async with repository.transaction():
            for current_item in importable:
                item_payload = asset_import_payload(current_item)
                item_payload["import_batch_id"] = batch_id
                created.append(await create_item(item_payload))
            batch = await repository.finalize_asset_import_batch(
                batch_id,
                {**batch, "status": "committed", "created_count": len(created), "error_count": 0},
                owner_id=owner_id,
            )
    except Exception as exc:  # noqa: BLE001 - repository transaction owns rollback
        failure = {
            "row": (current_item or {}).get("import_row"),
            "message": str(exc),
            "payload": current_item,
        }
        batch = await repository.finalize_asset_import_batch(
            batch_id,
            {
                **batch,
                "status": "failed",
                "created_count": 0,
                "error_count": 1,
                "error_message": str(exc),
            },
            owner_id=owner_id,
        )
        return [], [failure], batch
    return created, [], batch


def map_journal_entry_to_asset_trades(entry: Dict[str, Any], account_id: int) -> Dict[str, Any]:
    direction = str(entry.get("direction") or "long").strip().lower()
    if direction != "long":
        return {
            "entry_id": entry.get("id"),
            "importable": False,
            "reason": "Only long journal trades can be imported.",
        }

    normalized_ticker = normalize_ticker(entry.get("ticker"))
    market = entry.get("market") or infer_trade_market(normalized_ticker)
    currency = resolve_trade_currency_for_market(market)
    base_note = f"Imported from journal #{entry.get('id')}"

    def payload_for(side: str, trade_date: Any, price: Any, source_suffix: str) -> Dict[str, Any]:
        return {
            "account_id": account_id,
            "trade_date": trade_date,
            "ticker": normalized_ticker,
            "display_name": entry.get("ticker"),
            "market": market,
            "asset_type": "stock",
            "currency": currency,
            "side": side,
            "quantity": entry.get("size"),
            "price": price,
            "fee_amount": 0,
            "tax_amount": 0,
            "fx_rate_to_base": 1,
            "source": f"journal:{entry.get('id')}:{source_suffix}",
            "note": base_note,
        }

    payloads = [payload_for("buy", entry.get("entry_time"), entry.get("entry_price"), "entry")]
    if entry.get("exit_time") and entry.get("exit_price"):
        payloads.append(payload_for("sell", entry.get("exit_time"), entry.get("exit_price"), "exit"))
    return {"entry_id": entry.get("id"), "importable": True, "payloads": payloads, "entry": entry}
