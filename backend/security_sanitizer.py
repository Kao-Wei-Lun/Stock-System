"""Redact credentials before they cross API, database-error, or log boundaries."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping


REDACTED = "****"
SENSITIVE_KEYS = {
    "password", "password_enc", "cert_password", "cert_password_enc",
    "api_key", "api_key_enc", "authorization", "access_token", "refresh_token",
    "token", "secret", "client_secret",
}
LABELED_SECRET_PATTERN = re.compile(
    r"(?i)(\b(?:password|cert_password|api[_-]?key|access[_-]?token|refresh[_-]?token|token|client[_-]?secret|authorization)\b"
    r"\s*[=:]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;}&]+)"
)
BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")


def secret_values_from_account(account: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not account:
        return ()
    return tuple(
        str(account.get(key) or "")
        for key in ("password", "cert_password", "api_key")
        if str(account.get(key) or "")
    )


def redact_sensitive_text(value: Any, *, secrets: Iterable[str] = ()) -> str:
    text = str(value or "")
    for secret in sorted({str(item) for item in secrets if str(item)}, key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    text = BEARER_PATTERN.sub(f"Bearer {REDACTED}", text)
    text = LABELED_SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{REDACTED}", text)
    return text


def redact_sensitive_data(value: Any, *, secrets: Iterable[str] = ()) -> Any:
    if isinstance(value, Mapping):
        return {
            key: REDACTED if str(key).lower() in SENSITIVE_KEYS else redact_sensitive_data(item, secrets=secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_data(item, secrets=secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item, secrets=secrets) for item in value)
    if isinstance(value, str):
        return redact_sensitive_text(value, secrets=secrets)
    return value
