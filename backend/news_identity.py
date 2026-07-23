"""Stable news URL/provider identities used for future-safe deduplication."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}


def canonicalize_news_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = urlsplit(text)
    except ValueError:
        return text[:512]
    if not parsed.scheme or not parsed.netloc:
        return text[:512]
    host = parsed.netloc.lower()
    if host.endswith(":80") and parsed.scheme.lower() == "http":
        host = host[:-3]
    elif host.endswith(":443") and parsed.scheme.lower() == "https":
        host = host[:-4]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in TRACKING_QUERY_KEYS
    ]
    filtered_query.sort()
    canonical = urlunsplit(
        (
            parsed.scheme.lower(),
            host,
            path,
            urlencode(filtered_query, doseq=True),
            "",
        )
    )
    return canonical[:512]


def news_url_hash(value: Any) -> str | None:
    canonical = canonicalize_news_url(value)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest() if canonical else None


def resolve_news_provider_id(payload: Mapping[str, Any]) -> str | None:
    nested = payload.get("payload") if isinstance(payload.get("payload"), Mapping) else {}
    for candidate in (
        payload.get("provider_id"),
        payload.get("article_id"),
        payload.get("guid"),
        nested.get("provider_id"),
        nested.get("article_id"),
        nested.get("guid"),
        nested.get("id"),
    ):
        normalized = str(candidate or "").strip()
        if normalized:
            return normalized[:128]
    return None
