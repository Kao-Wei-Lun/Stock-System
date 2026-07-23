"""Low-overhead HTTP timing headers for local performance diagnostics."""

from __future__ import annotations

import logging
import re
import time
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


log = logging.getLogger(__name__)
_METRIC_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_CURRENT_SERVER_TIMINGS: ContextVar[dict[str, float] | None] = ContextVar(
    "quantvision_server_timings",
    default=None,
)


def _normalize_metric(metric: str) -> str:
    name = str(metric or "").strip().lower()
    if not _METRIC_NAME_RE.fullmatch(name):
        raise ValueError("Server timing metric names must be short lowercase identifiers")
    return name


def record_server_timing(metric: str, duration_ms: float) -> None:
    """Accumulate a timing component for the active HTTP request, if any."""

    name = _normalize_metric(metric)
    timings = _CURRENT_SERVER_TIMINGS.get()
    if timings is None:
        return
    duration = max(float(duration_ms), 0.0)
    timings[name] = timings.get(name, 0.0) + duration


def add_server_timing(target: Any, metric: str, duration_ms: float) -> None:
    """Record a safe timing component on a request/scope for the response header."""

    name = _normalize_metric(metric)
    duration = max(float(duration_ms), 0.0)
    scope = getattr(target, "scope", target)
    state = scope.setdefault("state", {})
    state.setdefault("server_timings", {})[name] = duration


def _timing_header(scope: Scope, total_ms: float) -> str:
    state = scope.get("state") or {}
    metrics = dict(state.get("server_timings") or {})
    metrics["total"] = max(float(total_ms), 0.0)
    return ", ".join(f"{name};dur={duration:.2f}" for name, duration in metrics.items())


class RequestTimingMiddleware:
    """Attach a locally generated request ID and non-sensitive server timings."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = time.perf_counter()
        request_id = str(uuid4())
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        timings = state.setdefault("server_timings", {})
        timing_token = _CURRENT_SERVER_TIMINGS.set(timings)
        response_started = False

        async def send_with_timing(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                elapsed_ms = (time.perf_counter() - started_at) * 1000
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", request_id.encode("ascii")))
                headers.append((b"server-timing", _timing_header(scope, elapsed_ms).encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_timing)
        except Exception:
            # Once headers have been sent the connection must be allowed to fail normally.
            if response_started:
                raise
            log.exception("Unhandled HTTP request error (request_id=%s)", request_id)
            response = JSONResponse(
                {"detail": "Internal Server Error", "request_id": request_id},
                status_code=500,
            )
            await response(scope, receive, send_with_timing)
        finally:
            _CURRENT_SERVER_TIMINGS.reset(timing_token)
