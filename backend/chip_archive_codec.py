"""Deterministic gzip JSONL codec for archived Taiwan branch payloads."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from typing import Any, Iterable, Mapping


ARCHIVE_FORMAT = "gzip_jsonl_v1"


class ChipArchiveError(RuntimeError):
    pass


def _normalize_branch_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ChipArchiveError("Invalid branch payload JSON") from exc
        if isinstance(parsed, dict):
            return parsed
    if value in (None, ""):
        return {}
    raise ChipArchiveError("Branch payload must be a JSON object")


def encode_chip_branch_archive(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized_rows = []
    for row in rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        source_id = int(row.get("id") or 0)
        if not ticker or source_id <= 0:
            raise ChipArchiveError("Archive rows require positive id and ticker")
        normalized_rows.append(
            {
                "id": source_id,
                "ticker": ticker,
                "branch_payload": _normalize_branch_payload(
                    row.get("branch_payload_json")
                    if "branch_payload_json" in row
                    else row.get("branch_payload")
                ),
            }
        )
    normalized_rows.sort(key=lambda item: (item["id"], item["ticker"]))
    raw = b"".join(
        (
            json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
        for item in normalized_rows
    )
    compressed_buffer = io.BytesIO()
    with gzip.GzipFile(
        filename="taiwan-chip-branch.jsonl",
        mode="wb",
        fileobj=compressed_buffer,
        mtime=0,
    ) as handle:
        handle.write(raw)
    compressed = compressed_buffer.getvalue()
    return {
        "archive_format": ARCHIVE_FORMAT,
        "payload_blob": compressed,
        "payload_sha256": hashlib.sha256(raw).hexdigest(),
        "source_row_count": len(normalized_rows),
        "original_size_bytes": len(raw),
        "compressed_size_bytes": len(compressed),
        "min_source_id": normalized_rows[0]["id"] if normalized_rows else None,
        "max_source_id": normalized_rows[-1]["id"] if normalized_rows else None,
    }


def decode_chip_branch_archive(
    payload_blob: bytes,
    *,
    expected_sha256: str | None = None,
    expected_row_count: int | None = None,
) -> list[dict[str, Any]]:
    try:
        raw = gzip.decompress(bytes(payload_blob))
    except (OSError, EOFError) as exc:
        raise ChipArchiveError("Archived branch payload gzip is corrupted") from exc
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if expected_sha256 and actual_sha256 != expected_sha256:
        raise ChipArchiveError("Archived branch payload checksum mismatch")
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ChipArchiveError("Archived branch payload JSONL is invalid") from exc
        if not isinstance(parsed, dict):
            raise ChipArchiveError("Archived branch payload row must be an object")
        rows.append(parsed)
    if expected_row_count is not None and len(rows) != int(expected_row_count):
        raise ChipArchiveError("Archived branch payload row count mismatch")
    return rows


def find_archived_branch_payload(
    archive: Mapping[str, Any] | None,
    ticker: str,
) -> dict[str, Any] | None:
    if not archive or not archive.get("payload_blob"):
        return None
    normalized = str(ticker or "").strip().upper()
    rows = decode_chip_branch_archive(
        archive["payload_blob"],
        expected_sha256=archive.get("payload_sha256"),
        expected_row_count=archive.get("source_row_count"),
    )
    for row in rows:
        if str(row.get("ticker") or "").upper() == normalized:
            payload = row.get("branch_payload")
            return payload if isinstance(payload, dict) else {}
    return None
