"""Fail-closed authentication, CSRF, and throttling for intentional LAN access."""

from __future__ import annotations

import base64
import hmac
import ipaddress
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable


PUBLIC_LAN_API_PATHS = frozenset({"/api/health", "/api/ready"})
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_HEADER_VALUE = "QuantVision"


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    path_markers: tuple[str, ...]
    limit: int
    window_seconds: float


DEFAULT_RATE_LIMIT_RULES = (
    RateLimitRule("login", ("/login", "/session"), 10, 300),
    RateLimitRule("reconnect", ("/reconnect",), 10, 60),
    RateLimitRule("sync", ("/sync", "/recompute", "/refresh"), 20, 60),
    RateLimitRule("import", ("/import",), 10, 60),
)


def _header_map(scope) -> dict[str, str]:
    return {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }


def _client_host(scope) -> str:
    client = scope.get("client")
    return str(client[0] if client else "")


def _is_loopback_client(client_host: str) -> bool:
    if client_host in {"", "testclient"}:
        return True
    try:
        return ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        return False


def encode_websocket_token_protocol(token: str) -> str:
    encoded = base64.urlsafe_b64encode(str(token).encode("utf-8")).decode("ascii").rstrip("=")
    return f"qv-token.{encoded}"


def decode_websocket_token_protocol(protocol: str) -> str | None:
    prefix = "qv-token."
    if not str(protocol).startswith(prefix):
        return None
    encoded = str(protocol)[len(prefix):]
    try:
        padded = encoded + ("=" * (-len(encoded) % 4))
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


class BoundedRateLimiter:
    """Small in-memory sliding-window limiter for sensitive local workflows."""

    def __init__(
        self,
        rules: Iterable[RateLimitRule] = DEFAULT_RATE_LIMIT_RULES,
        *,
        max_buckets: int = 2048,
        clock=time.monotonic,
    ) -> None:
        self.rules = tuple(rules)
        self.max_buckets = max(32, int(max_buckets))
        self.clock = clock
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def _rule_for(self, path: str) -> RateLimitRule | None:
        normalized = str(path or "").lower()
        return next(
            (
                rule
                for rule in self.rules
                if any(marker in normalized for marker in rule.path_markers)
            ),
            None,
        )

    def allow(self, client_host: str, path: str) -> tuple[bool, int | None]:
        rule = self._rule_for(path)
        if rule is None:
            return True, None
        now = float(self.clock())
        key = (str(client_host or "unknown"), rule.name)
        events = self._events[key]
        cutoff = now - rule.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= rule.limit:
            retry_after = max(1, int(rule.window_seconds - (now - events[0])))
            return False, retry_after
        events.append(now)
        if len(self._events) > self.max_buckets:
            self._prune(now)
        return True, None

    def _prune(self, now: float) -> None:
        stale_keys = []
        longest_window = max((rule.window_seconds for rule in self.rules), default=300)
        cutoff = now - longest_window
        for key, events in self._events.items():
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                stale_keys.append(key)
        for key in stale_keys:
            self._events.pop(key, None)
        if len(self._events) <= self.max_buckets:
            return
        oldest = sorted(
            self._events,
            key=lambda key: self._events[key][-1] if self._events[key] else 0,
        )
        for key in oldest[: len(self._events) - self.max_buckets]:
            self._events.pop(key, None)


class LanSecurityMiddleware:
    """Require LAN credentials while preserving password-free loopback use."""

    def __init__(
        self,
        app,
        *,
        allow_lan: bool,
        access_token: str = "",
        allowed_origins: str | Iterable[str] | None = None,
        rate_limiter: BoundedRateLimiter | None = None,
    ) -> None:
        self.app = app
        self.allow_lan = bool(allow_lan)
        self.access_token = str(access_token or "")
        if isinstance(allowed_origins, str):
            origins = [item.strip() for item in allowed_origins.split(",") if item.strip()]
        else:
            origins = [str(item).strip() for item in (allowed_origins or []) if str(item).strip()]
        self.allowed_origins = frozenset(origin.rstrip("/") for origin in origins)
        self.rate_limiter = rate_limiter or BoundedRateLimiter()

    def _provided_http_token(self, headers: dict[str, str]) -> str:
        authorization = headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        return headers.get("x-quantvision-token", "").strip()

    def _provided_websocket_token(self, headers: dict[str, str]) -> str:
        direct = self._provided_http_token(headers)
        if direct:
            return direct
        for protocol in headers.get("sec-websocket-protocol", "").split(","):
            decoded = decode_websocket_token_protocol(protocol.strip())
            if decoded is not None:
                return decoded
        return ""

    def _authorized(self, provided: str) -> bool:
        return bool(self.access_token) and hmac.compare_digest(
            provided.encode("utf-8"),
            self.access_token.encode("utf-8"),
        )

    async def _http_error(
        self,
        send,
        status: int,
        detail: str,
        *,
        retry_after: int | None = None,
        origin: str = "",
    ) -> None:
        payload = json.dumps({"detail": detail}).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(payload)).encode("ascii")),
            (b"cache-control", b"no-store"),
        ]
        normalized_origin = str(origin or "").rstrip("/")
        if normalized_origin in self.allowed_origins:
            headers.extend(
                [
                    (b"access-control-allow-origin", normalized_origin.encode("latin-1")),
                    (b"access-control-allow-credentials", b"true"),
                    (b"vary", b"Origin"),
                ]
            )
        if retry_after is not None:
            headers.append((b"retry-after", str(retry_after).encode("ascii")))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": payload})

    async def __call__(self, scope, receive, send):
        scope_type = scope.get("type")
        if scope_type not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        client_host = _client_host(scope)
        path = str(scope.get("path") or "")
        headers = _header_map(scope)
        external_lan_client = self.allow_lan and not _is_loopback_client(client_host)

        # Starlette's synthetic ``testclient`` address is exempt so unrelated
        # test cases cannot share and exhaust this process-local limiter.
        if client_host != "testclient":
            allowed, retry_after = self.rate_limiter.allow(client_host, path)
            if not allowed:
                if scope_type == "websocket":
                    await send({"type": "websocket.close", "code": 4429, "reason": "Rate limit exceeded"})
                else:
                    await self._http_error(
                        send,
                        429,
                        "Too many requests",
                        retry_after=retry_after,
                        origin=headers.get("origin", ""),
                    )
                return

        if not external_lan_client:
            await self.app(scope, receive, send)
            return

        if scope_type == "websocket":
            if not self._authorized(self._provided_websocket_token(headers)):
                await send({"type": "websocket.close", "code": 4401, "reason": "LAN authentication required"})
                return

            offered = {
                protocol.strip()
                for protocol in headers.get("sec-websocket-protocol", "").split(",")
                if protocol.strip()
            }

            async def websocket_send(message):
                if message.get("type") == "websocket.accept" and "qv-access" in offered:
                    message["subprotocol"] = "qv-access"
                await send(message)

            await self.app(scope, receive, websocket_send)
            return

        if not path.startswith("/api") or path in PUBLIC_LAN_API_PATHS:
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method") or "GET").upper()
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return
        if not self._authorized(self._provided_http_token(headers)):
            await self._http_error(
                send,
                401,
                "LAN authentication required",
                origin=headers.get("origin", ""),
            )
            return

        if method in MUTATING_METHODS:
            origin = headers.get("origin", "").rstrip("/")
            csrf_header = headers.get("x-requested-with", "")
            if csrf_header != CSRF_HEADER_VALUE or origin not in self.allowed_origins:
                await self._http_error(
                    send,
                    403,
                    "LAN CSRF validation failed",
                    origin=headers.get("origin", ""),
                )
                return

        await self.app(scope, receive, send)
