"""System routes — health checks, websocket, and frontend redirects."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse

from data_fetcher import normalize_ticker
from providers import ws_manager

log = logging.getLogger(__name__)

_FRONTEND_DEV_URL = "http://localhost:5173"
_FRONTEND_DIST_DIR: Path | None = None

router = APIRouter(tags=["system"])


def configure(*, frontend_dev_url: str, frontend_dist_dir: Path):
    global _FRONTEND_DEV_URL, _FRONTEND_DIST_DIR
    _FRONTEND_DEV_URL = frontend_dev_url.rstrip("/")
    _FRONTEND_DIST_DIR = frontend_dist_dir


def _frontend_ready() -> bool:
    return _FRONTEND_DIST_DIR is not None and _FRONTEND_DIST_DIR.exists()


@router.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            action = data.get("action")
            if action == "subscribe":
                ticker = normalize_ticker(data.get("ticker", ""))
                ws_manager.subscribe(websocket, ticker)
            elif action == "unsubscribe":
                ticker = normalize_ticker(data.get("ticker", ""))
                ws_manager.unsubscribe(websocket, ticker)
            elif action == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        log.error("WS error: %s", exc)
        ws_manager.disconnect(websocket)


@router.get("/")
async def root():
    if _frontend_ready():
        return RedirectResponse(url="/app/", status_code=307)
    return RedirectResponse(url=_FRONTEND_DEV_URL, status_code=307)


@router.get("/app")
async def frontend_entry():
    if _frontend_ready():
        return RedirectResponse(url="/app/", status_code=307)
    return RedirectResponse(url=_FRONTEND_DEV_URL, status_code=307)
