"""Network boundary guard for the personal-use API server."""

from __future__ import annotations

import ipaddress
import json
from typing import Iterable


def split_csv(value: str | None) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in str(value or "").split(",") if item.strip()))


def is_loopback_bind_host(host: str) -> bool:
    value = str(host or "").strip().lower().strip("[]")
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def parse_allowed_networks(values: str | Iterable[str] | None) -> tuple[ipaddress._BaseNetwork, ...]:
    items = split_csv(values) if isinstance(values, (str, type(None))) else list(values)
    try:
        return tuple(ipaddress.ip_network(item, strict=False) for item in items)
    except ValueError as exc:
        raise RuntimeError(f"Invalid LAN_ALLOWED_NETWORKS entry: {exc}") from exc


def _host_without_port(host_header: str) -> str:
    value = str(host_header or "").strip().lower()
    if value.startswith("[") and "]" in value:
        return value[1:value.index("]")]
    if value.count(":") == 1:
        return value.split(":", 1)[0]
    return value


def _safe_host_header(host_header: str, *, allow_lan: bool) -> bool:
    host = _host_without_port(host_header)
    if host in {"localhost", "testserver"}:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or (allow_lan and address.is_private)


class LocalAccessMiddleware:
    def __init__(self, app, *, allow_lan: bool = False, allowed_networks: str | Iterable[str] | None = None):
        self.app = app
        self.allow_lan = bool(allow_lan)
        self.allowed_networks = parse_allowed_networks(allowed_networks)

    def _client_allowed(self, client_host: str | None) -> bool:
        if not client_host or client_host == "testclient":
            return True
        try:
            address = ipaddress.ip_address(client_host)
        except ValueError:
            return False
        if address.is_loopback:
            return True
        if not self.allow_lan or not address.is_private:
            return False
        return not self.allowed_networks or any(address in network for network in self.allowed_networks)

    async def __call__(self, scope, receive, send):
        if scope.get("type") not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        client = scope.get("client")
        client_host = client[0] if client else None
        allowed = self._client_allowed(client_host) and _safe_host_header(
            headers.get("host", ""),
            allow_lan=self.allow_lan,
        )
        if not allowed:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008, "reason": "Local network access denied"})
                return
            payload = json.dumps({"detail": "Local network access denied"}).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())],
            })
            await send({"type": "http.response.body", "body": payload})
            return

        async def security_headers_send(message):
            if message.get("type") == "http.response.start":
                response_headers = list(message.get("headers") or [])
                response_headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                ])
                if str(scope.get("path") or "").startswith("/api/settings/fubon-accounts"):
                    response_headers.append((b"cache-control", b"no-store"))
                message["headers"] = response_headers
            await send(message)

        await self.app(scope, receive, security_headers_send)
