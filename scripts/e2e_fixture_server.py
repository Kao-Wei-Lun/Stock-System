"""Deterministic, synthetic API/WebSocket server for production SPA E2E tests.

This server never imports the production database or trading providers. All
portfolio, quote, paper-trading, and market values are synthetic fixtures.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPOSITORY_ROOT / "backend"
FRONTEND_DIST = REPOSITORY_ROOT / "frontend" / "dist"
sys.path.insert(0, str(BACKEND_DIR))

from frontend_static import SPAStaticFiles  # noqa: E402


TAIPEI = timezone(timedelta(hours=8))
CONTROL: dict[str, Any] = {
    "ohlc_delay_ms": 0,
    "realtime_delay_ms": 600,
    "ready_status": "ready",
}
SOCKETS: set[WebSocket] = set()


def fixture_rows(count: int = 120, base: float = 44_800.0) -> list[dict[str, Any]]:
    start = datetime(2026, 7, 23, 9, 0, tzinfo=TAIPEI)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        center = base + ((index % 18) - 9) * 3 + index * 0.4
        rows.append(
            {
                "date": (start + timedelta(minutes=index)).isoformat(),
                "open": round(center - 2, 2),
                "high": round(center + 8, 2),
                "low": round(center - 9, 2),
                "close": round(center + 1, 2),
                "volume": 100 + index,
            }
        )
    return rows


OHLC_ROWS = fixture_rows()
SYNTHETIC_ACCOUNT = {
    "id": 9001,
    "name": "E2E 合成資產帳戶",
    "account_type": "securities",
    "base_currency": "TWD",
    "is_active": True,
}
PAPER_ACCOUNT = {
    "id": 7001,
    "owner_id": 1,
    "name": "E2E TMF 模擬帳戶",
    "product_symbol": "TMF",
    "starting_equity": 250_000,
    "equity": 250_000,
    "initial_margin_per_contract": 28_900,
    "margin_source": "persisted_fixture",
    "margin_last_success_at": "2026-07-23T09:00:00+08:00",
    "risk_config": {},
    "created_at": "2026-07-23T09:00:00+08:00",
}


def list_payload() -> dict[str, Any]:
    return {"items": [], "count": 0, "total": 0}


def fixture_payload(path: str, method: str, query: dict[str, str]) -> Any:
    normalized = path.strip("/")
    if normalized == "health":
        return {"status": "ok", "source": "synthetic_e2e"}
    if normalized == "ready":
        return {
            "status": CONTROL["ready_status"],
            "source": "synthetic_e2e",
            "components": {},
        }
    if normalized == "settings/fubon-accounts/status":
        return {
            "accounts": [{"id": 1, "is_active": True, "connection_status": "connected"}],
            "warmup": {
                "state": "ready",
                "connected_account_count": 1,
                "configured_account_count": 1,
            },
        }
    if normalized == "system/data-quality":
        return {
            "status": "healthy",
            "summary": {"healthy_count": 3, "idle_count": 0, "warning_count": 0, "error_count": 0},
            "components": {},
            "issues": [],
            "generated_at": "2026-07-23T09:00:00+08:00",
        }
    if normalized == "system/performance":
        return {
            "realtime": {
                "counters": {"ingress": 10, "broadcast": 10, "persistence_flush": 10, "coalesced": 0, "dropped": 0},
                "queue_depth": {"max_ms": 0},
                "persistence_queue_age": {"max_ms": 0},
                "broadcast_latency": {"p95_ms": 5, "max_ms": 8},
            },
            "database": {"wait": {"p95_ms": 1}, "query": {"p95_ms": 2}},
            "quote_persistence": {"pending": 0},
            "backtest_workload": {"active": 0},
            "asset_quote_refresh": {"in_flight": 0},
        }
    if normalized == "search":
        requested = str(query.get("q") or "").strip().upper()
        resolved = "TMFH7" if requested == "*TMFF" else "TXFH7" if requested == "*TXFF" else requested
        return [{
            "ticker": requested,
            "name": f"E2E 期貨（目前 {resolved}）" if requested.startswith("*") else f"E2E {requested}",
            "asset_class": "futopt" if requested.startswith("*") else "stock",
            "resolved_symbol": resolved,
            "source": "synthetic_e2e",
        }]
    if normalized.startswith("futopt/ohlc/") or normalized.startswith("ohlc/"):
        ticker = normalized.rsplit("/", 1)[-1].upper()
        resolved = "TMFH7" if ticker in {"*TMFF", "TMF"} else "TXFH7" if ticker in {"*TXFF", "TXF"} else ticker
        return {
            "ticker": resolved,
            "requested_symbol": ticker,
            "resolved_symbol": resolved,
            "data": OHLC_ROWS,
            "refresh_status": "idle",
            "is_stale": False,
            "source": "synthetic_e2e",
        }
    if normalized.startswith("futopt/quote/") or normalized.startswith("quote/"):
        ticker = normalized.rsplit("/", 1)[-1].upper()
        resolved = "TMFH7" if ticker in {"*TMFF", "TMF"} else "TXFH7" if ticker in {"*TXFF", "TXF"} else ticker
        return {
            "ticker": resolved,
            "resolved_symbol": resolved,
            "price": 44_977,
            "open": 44_900,
            "high": 45_030,
            "low": 44_850,
            "change": 77,
            "change_pct": 0.17,
            "volume": 1200,
            "source": "synthetic_e2e",
            "quote_type": "realtime",
            "is_delayed": False,
            "quote_timestamp": datetime.now(TAIPEI).isoformat(),
        }
    if normalized in {"watchlist", "watchlist/metadata"}:
        return {
            "groups": [{
                "id": 1,
                "name": "E2E 觀察池",
                "color": "#7be7ff",
                "items": [{"id": 1, "ticker": "2330.TW", "name": "E2E 台積電"}],
            }]
        }
    if normalized == "workspaces":
        return {"items": []}
    if normalized in {"alerts", "notifications"}:
        return list_payload()
    if normalized == "paper-trading/accounts":
        return {"items": [PAPER_ACCOUNT]}
    if normalized in {"paper-trading/bots", "paper-trading/replay/runs"}:
        return list_payload()
    if normalized == "paper-trading/risk/position-size":
        return {"sizing": {"addable_contracts": 1, "limiting_factor": "margin"}}
    if normalized == "assets/accounts":
        return {"items": [SYNTHETIC_ACCOUNT]}
    if normalized == "assets/portfolio/current":
        return {
            "base_currency": "TWD",
            "summary": {"total_value": 120_137, "cash": 120_137, "market_value": 0},
            "holdings": [],
            "accounts": [SYNTHETIC_ACCOUNT],
            "source": "synthetic_e2e",
        }
    if normalized.startswith("assets/"):
        return list_payload()
    if normalized.startswith("fubon/snapshot/"):
        return {"market": "TSE", "data": [], "items": [], "summary": {}}
    if normalized == "macro/dashboard":
        return {"items": [], "summary": {}, "snapshot_date": "2026-07-23"}
    if normalized in {"events", "screener/presets"}:
        return list_payload()
    if normalized == "screener/run":
        return {"items": [], "total": 0, "filters": {}, "generated_at": "2026-07-23T09:00:00+08:00"}
    if normalized.startswith("taifex/") or normalized.startswith("tw/"):
        return {"items": [], "data": [], "series": [], "count": 0}
    if normalized.startswith("market-intelligence/") or normalized.startswith("fundamentals/"):
        return {"items": [], "events": [], "news": [], "summary": {}}
    if normalized.startswith("journal/") or normalized.startswith("backtests/"):
        return list_payload()
    return list_payload()


app = FastAPI(title="QuantVision deterministic E2E fixture")


@app.api_route("/api/e2e/control", methods=["GET", "POST"])
async def e2e_control(request: Request):
    if request.method == "POST":
        payload = await request.json()
        for key in ("ohlc_delay_ms", "realtime_delay_ms", "ready_status"):
            if key in payload:
                CONTROL[key] = payload[key]
    return {"ok": True, **CONTROL, "source": "synthetic_e2e"}


@app.post("/api/e2e/ws/drop")
async def e2e_drop_sockets():
    sockets = list(SOCKETS)
    for socket in sockets:
        try:
            await socket.close(code=1012)
        except RuntimeError:
            pass
    return {"ok": True, "closed": len(sockets)}


@app.websocket("/ws")
async def websocket_fixture(websocket: WebSocket):
    await websocket.accept()
    SOCKETS.add(websocket)
    tasks: set[asyncio.Task] = set()

    async def send_realtime(ticker: str):
        await asyncio.sleep(max(0, int(CONTROL["realtime_delay_ms"])) / 1000)
        if websocket not in SOCKETS:
            return
        row = dict(OHLC_ROWS[-1])
        row["close"] = float(row["close"]) + 12
        await websocket.send_json({
            "type": "candle",
            "ticker": ticker,
            "interval": "1m",
            "data": row,
            "source": "synthetic_e2e",
        })

    try:
        while True:
            payload = await websocket.receive_json()
            action = payload.get("action")
            if action == "ping":
                await websocket.send_json({"type": "pong"})
            elif action == "subscribe":
                task = asyncio.create_task(send_realtime(str(payload.get("ticker") or "TMFH7")))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
    except WebSocketDisconnect:
        pass
    finally:
        SOCKETS.discard(websocket)
        for task in tasks:
            task.cancel()


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def synthetic_api(path: str, request: Request):
    if ("ohlc/" in path) and int(CONTROL["ohlc_delay_ms"]) > 0:
        await asyncio.sleep(int(CONTROL["ohlc_delay_ms"]) / 1000)
    return JSONResponse(fixture_payload(path, request.method, dict(request.query_params)))


if not FRONTEND_DIST.joinpath("index.html").exists():
    raise RuntimeError("frontend/dist is missing; run npm run build before E2E")

app.mount("/app", SPAStaticFiles(directory=FRONTEND_DIST), name="frontend")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4174)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
