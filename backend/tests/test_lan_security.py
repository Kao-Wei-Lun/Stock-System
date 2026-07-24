from __future__ import annotations

import asyncio

from lan_security import (
    BoundedRateLimiter,
    LanSecurityMiddleware,
    RateLimitRule,
    encode_websocket_token_protocol,
)


TOKEN = "test-lan-token-0123456789-ABCDEFGHIJKLMN"
ORIGIN = "http://192.168.50.10:8001"


async def _inner_app(scope, _receive, send):
    if scope["type"] == "websocket":
        await send({"type": "websocket.accept"})
        return
    payload = b'{"ok":true}'
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": payload})


def _headers(values: dict[str, str]) -> list[tuple[bytes, bytes]]:
    return [(key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in values.items()]


def _run_http(
    middleware,
    *,
    path="/api/assets/accounts",
    query_string="",
    method="GET",
    client="192.168.50.20",
    headers=None,
):
    messages = []

    async def run():
        async def send(message):
            messages.append(message)

        await middleware(
            {
                "type": "http",
                "path": path,
                "query_string": query_string.encode("ascii"),
                "method": method,
                "client": (client, 50000),
                "headers": _headers({"Host": "192.168.50.10:8001", **(headers or {})}),
            },
            lambda: None,
            send,
        )

    asyncio.run(run())
    return messages


def _run_websocket(middleware, *, client="192.168.50.20", headers=None):
    messages = []

    async def run():
        async def send(message):
            messages.append(message)

        await middleware(
            {
                "type": "websocket",
                "path": "/ws",
                "client": (client, 50000),
                "headers": _headers({"Host": "192.168.50.10:8001", **(headers or {})}),
            },
            lambda: None,
            send,
        )

    asyncio.run(run())
    return messages


def _middleware(*, rate_limiter=None):
    return LanSecurityMiddleware(
        _inner_app,
        allow_lan=True,
        access_token=TOKEN,
        allowed_origins=[ORIGIN],
        rate_limiter=rate_limiter,
    )


def test_loopback_keeps_password_free_personal_use():
    messages = _run_http(_middleware(), client="127.0.0.1")
    assert messages[0]["status"] == 200


def test_lan_static_and_health_load_but_private_api_requires_header_token():
    middleware = _middleware()
    static_messages = _run_http(middleware, path="/app/assets/index.js")
    health_messages = _run_http(middleware, path="/api/health")
    private_messages = _run_http(middleware)
    query_token_messages = _run_http(middleware, query_string=f"token={TOKEN}")
    authorized_messages = _run_http(
        middleware,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert static_messages[0]["status"] == 200
    assert health_messages[0]["status"] == 200
    assert private_messages[0]["status"] == 401
    assert query_token_messages[0]["status"] == 401
    assert authorized_messages[0]["status"] == 200


def test_lan_auth_error_exposes_only_exact_allowed_origin_to_browser():
    allowed_origin = _run_http(_middleware(), headers={"Origin": ORIGIN})
    denied_origin = _run_http(
        _middleware(),
        headers={"Origin": "http://192.168.50.99:8001"},
    )

    assert allowed_origin[0]["status"] == 401
    assert (b"access-control-allow-origin", ORIGIN.encode("latin-1")) in allowed_origin[0]["headers"]
    assert denied_origin[0]["status"] == 401
    assert not any(key == b"access-control-allow-origin" for key, _value in denied_origin[0]["headers"])


def test_lan_mutation_requires_token_exact_origin_and_csrf_header():
    middleware = _middleware()
    token_header = {"Authorization": f"Bearer {TOKEN}"}
    no_csrf = _run_http(middleware, method="POST", headers=token_header)
    wrong_origin = _run_http(
        middleware,
        method="POST",
        headers={
            **token_header,
            "Origin": "http://192.168.50.99:8001",
            "X-Requested-With": "QuantVision",
        },
    )
    allowed = _run_http(
        middleware,
        method="POST",
        headers={
            **token_header,
            "Origin": ORIGIN,
            "X-Requested-With": "QuantVision",
        },
    )

    assert no_csrf[0]["status"] == 403
    assert wrong_origin[0]["status"] == 403
    assert allowed[0]["status"] == 200


def test_lan_websocket_requires_header_or_encoded_subprotocol():
    middleware = _middleware()
    unauthorized = _run_websocket(middleware)
    protocol = encode_websocket_token_protocol(TOKEN)
    authorized = _run_websocket(
        middleware,
        headers={"Sec-WebSocket-Protocol": f"qv-access, {protocol}"},
    )

    assert unauthorized == [
        {"type": "websocket.close", "code": 4401, "reason": "LAN authentication required"}
    ]
    assert authorized[0] == {"type": "websocket.accept", "subprotocol": "qv-access"}


def test_sensitive_workflow_rate_limit_is_bounded():
    clock = iter([0.0, 1.0, 2.0])
    limiter = BoundedRateLimiter(
        (RateLimitRule("import", ("/import",), 2, 60),),
        clock=lambda: next(clock),
    )
    middleware = _middleware(rate_limiter=limiter)
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Origin": ORIGIN,
        "X-Requested-With": "QuantVision",
    }

    first = _run_http(middleware, path="/api/assets/import/trades-csv", method="POST", headers=headers)
    second = _run_http(middleware, path="/api/assets/import/trades-csv", method="POST", headers=headers)
    limited = _run_http(middleware, path="/api/assets/import/trades-csv", method="POST", headers=headers)

    assert first[0]["status"] == 200
    assert second[0]["status"] == 200
    assert limited[0]["status"] == 429
    assert (b"retry-after", b"58") in limited[0]["headers"]
