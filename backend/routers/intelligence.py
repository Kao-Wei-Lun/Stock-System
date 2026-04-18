"""Market intelligence routes — events, news, macro, fundamentals, chips, screener, taifex."""

import logging
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from data_fetcher import normalize_ticker
from database import db
from fundamentals_provider import build_fundamental_summary
from macro_regime import build_macro_dashboard_payload
from providers import (
    fundamentals_provider,
    macro_snapshot_provider,
    market_event_provider,
    news_provider,
    taiwan_chip_provider,
    screener_engine,
)
from schemas import (
    ScreenerPresetCreatePayload,
    ScreenerPresetUpdatePayload,
    ScreenerRunPayload,
)
from screener_engine import build_screener_presets, normalize_screener_filters
from taifex_fetcher import taifex_fetcher
from taiwan_chip_provider import build_taiwan_chip_summary

log = logging.getLogger(__name__)

# Injected from main.py
_sync_market_intelligence_snapshot = None
_fetch_and_store_quote_snapshot = None
_APP_TZ = ZoneInfo("Asia/Taipei")
TAIFEX_SPOT_REFERENCE = []
TRADINGVIEW_SCREENER_WRAPPER_URL = "https://www.tradingview-widget.com/embed-widget/screener/"

router = APIRouter(prefix="/api", tags=["intelligence"])


def configure(
    *,
    sync_market_intelligence_snapshot,
    fetch_and_store_quote_snapshot,
    app_tz,
    taifex_spot_reference,
):
    """Inject helpers from main.py to avoid circular imports."""
    global _sync_market_intelligence_snapshot, _fetch_and_store_quote_snapshot
    global _APP_TZ, TAIFEX_SPOT_REFERENCE
    _sync_market_intelligence_snapshot = sync_market_intelligence_snapshot
    _fetch_and_store_quote_snapshot = fetch_and_store_quote_snapshot
    _APP_TZ = app_tz
    TAIFEX_SPOT_REFERENCE = taifex_spot_reference


def _parse_iso_date_param(value: str | None, label: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(400, f"{label} must use YYYY-MM-DD") from exc


def _normalize_widget_locale(value: str | None) -> str:
    raw = str(value or "").strip()
    return raw if raw and len(raw) <= 16 else "en"


def _inject_tradingview_environment(html: str) -> str:
    injection = (
        "<script>"
        "window.environment='battle';"
        "self.environment='battle';"
        "</script>"
    )
    if injection in html:
        return html
    if "</head>" in html:
        return html.replace("</head>", f"{injection}</head>", 1)
    return f"{injection}{html}"


# ─── Events ──────────────────────────────────────────────────

@router.get("/events/calendar")
async def get_events_calendar(
    days: int = Query(21, ge=1, le=180),
    limit: int = Query(100, ge=1, le=500),
    refresh: bool = Query(False),
):
    today = datetime.now(_APP_TZ).date()
    date_from = today.isoformat()
    date_to = (today + timedelta(days=days)).isoformat()
    items = await db.list_market_events(date_from=date_from, date_to=date_to, limit=limit)
    if refresh or not items:
        await _sync_market_intelligence_snapshot(reason="events-calendar")
        items = await db.list_market_events(date_from=date_from, date_to=date_to, limit=limit)
    return {"items": items, "date_from": date_from, "date_to": date_to}


@router.get("/events/{ticker}")
async def get_ticker_events(
    ticker: str,
    refresh: bool = Query(False),
):
    normalized = normalize_ticker(ticker)
    items = await db.list_market_events(ticker=normalized, limit=20)
    if refresh or not items:
        try:
            items = await market_event_provider.sync_ticker_events(normalized)
        except Exception as exc:
            log.warning("ticker events sync failed for %s: %s", normalized, exc)
    return {"ticker": normalized, "items": items}


# ─── News ────────────────────────────────────────────────────

@router.get("/news")
async def get_news_feed(
    limit: int = Query(20, ge=1, le=100),
):
    items = await db.list_news_articles(limit=limit)
    return {"items": items}


@router.get("/news/{ticker}")
async def get_ticker_news(
    ticker: str,
    limit: int = Query(10, ge=1, le=30),
    refresh: bool = Query(False),
):
    normalized = normalize_ticker(ticker)
    items = await db.list_news_articles(ticker=normalized, limit=limit)
    if refresh or not items:
        try:
            items = await news_provider.sync_ticker_news(normalized, limit=limit)
        except Exception as exc:
            log.warning("ticker news sync failed for %s: %s", normalized, exc)
    return {"ticker": normalized, "items": items}


# ─── Macro ───────────────────────────────────────────────────

@router.get("/market/macro")
async def get_macro_dashboard(
    refresh: bool = Query(False),
):
    items = await db.list_macro_snapshots()
    if refresh or not items:
        items = await macro_snapshot_provider.sync_macro_snapshots()
    return build_macro_dashboard_payload(items)


# ─── Fundamentals ────────────────────────────────────────────

@router.get("/fundamentals/{ticker}")
async def get_fundamentals_detail(
    ticker: str,
    refresh: bool = Query(False),
):
    normalized = normalize_ticker(ticker)
    info = await db.get_stock_info(normalized)
    if refresh or not info or not info.get("sector") or not info.get("industry"):
        try:
            info = await fundamentals_provider.sync_ticker_fundamentals(normalized)
        except Exception as exc:
            log.warning("fundamentals sync failed for %s: %s", normalized, exc)
            info = await db.get_stock_info(normalized)
    events = await db.list_market_events(ticker=normalized, limit=10)
    return {
        "ticker": normalized,
        "detail": info,
        "summary": build_fundamental_summary(info, events),
    }


@router.get("/fundamentals/{ticker}/events")
async def get_fundamental_events(
    ticker: str,
    refresh: bool = Query(False),
):
    normalized = normalize_ticker(ticker)
    items = await db.list_market_events(ticker=normalized, limit=20)
    if refresh or not items:
        try:
            items = await market_event_provider.sync_ticker_events(normalized)
        except Exception as exc:
            log.warning("fundamental event sync failed for %s: %s", normalized, exc)
    return {"ticker": normalized, "items": items}


# ─── Taiwan Chips ────────────────────────────────────────────

@router.get("/tw/chips/{ticker}")
async def get_taiwan_chip_detail(
    ticker: str,
    date: str | None = Query(None, description="YYYY-MM-DD"),
    refresh: bool = Query(False),
):
    normalized = normalize_ticker(ticker)
    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(400, "date must use YYYY-MM-DD") from exc

    snapshot = await db.get_taiwan_chip_snapshot(normalized, target_date.isoformat() if target_date else None)
    if refresh or not snapshot:
        try:
            snapshot = await taiwan_chip_provider.sync_ticker_snapshot(
                normalized,
                target_date=target_date,
                force_refresh=refresh,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            log.warning("taiwan chip sync failed for %s: %s", normalized, exc)
            snapshot = await db.get_taiwan_chip_snapshot(normalized, target_date.isoformat() if target_date else None)
    if not snapshot:
        raise HTTPException(404, f"No official Taiwan chip data available for {normalized}")
    return {
        "ticker": normalized,
        "requested_date": target_date.isoformat() if target_date else None,
        "resolved_date": snapshot.get("snapshot_date") if snapshot else None,
        "detail": snapshot,
        "summary": build_taiwan_chip_summary(snapshot),
    }


@router.get("/tradingview/widgets/screener")
async def get_tradingview_screener_wrapper(
    locale: str = Query("en"),
):
    normalized_locale = _normalize_widget_locale(locale)
    remote_url = f"{TRADINGVIEW_SCREENER_WRAPPER_URL}?locale={quote_plus(normalized_locale)}"
    try:
        response = requests.get(
            remote_url,
            timeout=10,
            headers={"User-Agent": "QuantVision Pro/1.0"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(502, "Unable to load TradingView screener wrapper") from exc

    return HTMLResponse(
        content=_inject_tradingview_environment(response.text),
        headers={"Cache-Control": "no-store"},
    )


# ─── Screener ────────────────────────────────────────────────

@router.get("/screener/presets")
async def list_screener_presets():
    presets = await db.list_screener_presets()
    built_in = [
        {
            "id": f"builtin-{index + 1}",
            "owner_id": 0,
            "name": preset["name"],
            "description": preset.get("description"),
            "filters": normalize_screener_filters(preset.get("filters")),
            "created_at": None,
            "updated_at": None,
            "builtin": True,
        }
        for index, preset in enumerate(build_screener_presets())
    ]
    return {"items": built_in + presets}


@router.post("/screener/presets")
async def create_screener_preset(payload: ScreenerPresetCreatePayload):
    try:
        created = await db.create_screener_preset(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return created


@router.put("/screener/presets/{preset_id}")
async def update_screener_preset(preset_id: int, payload: ScreenerPresetUpdatePayload):
    try:
        updated = await db.update_screener_preset(preset_id, payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not updated:
        raise HTTPException(404, "Screener preset not found")
    return updated


@router.delete("/screener/presets/{preset_id}")
async def delete_screener_preset(preset_id: int):
    deleted = await db.delete_screener_preset(preset_id)
    if not deleted:
        raise HTTPException(404, "Screener preset not found")
    return {"ok": True}


@router.post("/screener/run")
async def run_screener(payload: ScreenerRunPayload):
    return await screener_engine.run(payload.filters)


# ─── TAIFEX ──────────────────────────────────────────────────

@router.get("/taifex/structured/{section}")
async def get_taifex_structured_rows(
    section: str,
    date: str | None = Query(None, description="Exact resolved date YYYY-MM-DD"),
    start_date: str | None = Query(None, description="Start resolved date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End resolved date YYYY-MM-DD"),
    commodity: str | None = Query(None, description="期貨/選擇權商品名稱"),
    institution: str | None = Query(None, description="法人名稱"),
    option_side: str | None = Query(None, description="買權 / 賣權"),
    limit: int = Query(200, ge=1, le=1000),
):
    exact_date = _parse_iso_date_param(date, "date")
    start = _parse_iso_date_param(start_date, "start_date")
    end = _parse_iso_date_param(end_date, "end_date")

    if exact_date and (start or end):
        raise HTTPException(400, "date cannot be combined with start_date or end_date")
    if start and end and end < start:
        raise HTTPException(400, "end_date must be on or after start_date")

    try:
        items = await db.list_taifex_structured_rows(
            section,
            resolved_date=exact_date.isoformat() if exact_date else None,
            start_date=start.isoformat() if start else None,
            end_date=end.isoformat() if end else None,
            commodity=commodity.strip() if commodity else None,
            institution=institution.strip() if institution else None,
            option_side=option_side.strip() if option_side else None,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return {
        "section": section,
        "count": len(items),
        "filters": {
            "date": exact_date.isoformat() if exact_date else None,
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
            "commodity": commodity.strip() if commodity else None,
            "institution": institution.strip() if institution else None,
            "option_side": option_side.strip() if option_side else None,
            "limit": limit,
        },
        "items": items,
    }

@router.get("/taifex/institutional")
async def get_taifex_institutional(
    date: str | None = Query(None, description="YYYY-MM-DD"),
    refresh: bool = Query(False, description="Force refresh from remote sources"),
):
    target_date = _parse_iso_date_param(date, "date")

    payload = await taifex_fetcher.fetch_dashboard(target_date, force_refresh=refresh)

    spot_cards = []
    for item in TAIFEX_SPOT_REFERENCE:
        quote = await _fetch_and_store_quote_snapshot(item["ticker"])
        if not quote:
            quote = await db.get_market_quote(item["ticker"])
        if not quote:
            continue
        spot_cards.append(
            {
                "ticker": item["ticker"],
                "label": item["label"],
                "price": quote.get("price"),
                "change": quote.get("change"),
                "change_pct": quote.get("change_pct"),
                "open": quote.get("open"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "volume": quote.get("volume"),
            }
        )

    payload["spot_reference"] = spot_cards
    return payload


@router.get("/taifex/institutional/insights")
async def get_taifex_institutional_insights(
    date: str | None = Query(None, description="YYYY-MM-DD"),
    futures_commodity: str | None = Query(None, description="期貨商品名稱"),
    options_commodity: str | None = Query(None, description="選擇權商品名稱"),
    days: int = Query(30, description="10 20 30 60 90"),
    refresh: bool = Query(False, description="Force refresh from remote sources"),
):
    target_date = _parse_iso_date_param(date, "date")

    return await taifex_fetcher.fetch_insights(
        target_date,
        futures_commodity.strip() if futures_commodity else None,
        options_commodity.strip() if options_commodity else None,
        days,
        force_refresh=refresh,
    )
