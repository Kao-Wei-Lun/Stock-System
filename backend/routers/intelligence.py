"""Market intelligence routes — events, news, macro, fundamentals, chips, screener, taifex."""

import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, HTTPException, Query
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
TRADINGVIEW_SCREENER_EMBED_SCRIPT = "https://s3.tradingview.com/external-embedding/embed-widget-screener.js"

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


def _coerce_iso_date(value) -> str | None:
    if value is None or value == "":
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    return str(value).strip() or None


def _sum_chip_metric(points: list[dict], key: str, window: int) -> int:
    return sum(int(item.get(key) or 0) for item in points[-window:])


def _compute_chip_streak(points: list[dict], key: str) -> dict:
    relevant = [int(item.get(key) or 0) for item in points]
    direction = "neutral"
    count = 0
    for value in reversed(relevant):
        if value > 0:
            next_direction = "buy"
        elif value < 0:
            next_direction = "sell"
        else:
            next_direction = "neutral"

        if count == 0:
            if next_direction == "neutral":
                break
            direction = next_direction
            count = 1
            continue

        if next_direction != direction:
            break
        count += 1

    return {"direction": direction, "days": count}


def _build_chip_history_stats(points: list[dict]) -> dict:
    windows = (5, 10, 20, 60)
    stats = {}
    metric_keys = (
        "foreign_net_buy_sell",
        "investment_trust_net_buy_sell",
        "dealer_net_buy_sell",
        "institutional_net_buy_sell",
    )
    for metric_key in metric_keys:
        prefix = metric_key.removesuffix("_net_buy_sell")
        for window in windows:
            stats[f"{prefix}_{window}d_sum"] = _sum_chip_metric(points, metric_key, window)

    institutional_streak = _compute_chip_streak(points, "institutional_net_buy_sell")
    foreign_streak = _compute_chip_streak(points, "foreign_net_buy_sell")
    stats["institutional_streak_days"] = institutional_streak["days"]
    stats["institutional_streak_direction"] = institutional_streak["direction"]
    stats["foreign_streak_days"] = foreign_streak["days"]
    stats["foreign_streak_direction"] = foreign_streak["direction"]
    return stats


def _build_chip_price_series(rows: list[dict], allowed_dates: set[str]) -> list[dict]:
    points = []
    previous_close = None
    for row in rows:
        point_date = _coerce_iso_date(row.get("date"))
        close_price = row.get("close")
        if not point_date or point_date not in allowed_dates or close_price is None:
            if close_price is not None:
                previous_close = close_price
            continue
        change_pct = None
        if previous_close not in (None, 0):
            change_pct = ((float(close_price) - float(previous_close)) / float(previous_close)) * 100
        points.append(
            {
                "date": point_date,
                "close": close_price,
                "change_pct": change_pct,
                "volume": row.get("volume"),
            }
        )
        previous_close = close_price
    return points


def _build_tradingview_screener_wrapper_html(locale: str) -> str:
    normalized_locale = _normalize_widget_locale(locale)
    locale_literal = json.dumps(normalized_locale)
    embed_script_literal = json.dumps(TRADINGVIEW_SCREENER_EMBED_SCRIPT)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TradingView Screener</title>
  <style>
    html, body {{
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: transparent;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}

    .tradingview-widget-container,
    .tradingview-widget-container__widget {{
      width: 100%;
      height: 100%;
    }}
  </style>
</head>
<body>
  <div id="tv-screener-root" class="tradingview-widget-container">
    <div class="tradingview-widget-container__widget"></div>
  </div>
  <script>
    window.environment = "battle";
    self.environment = "battle";
    window.locale = {locale_literal};
    window.language = {locale_literal};
    window.initData = window.initData || {{}};
    window.initData.snowplowSettings = {{
      enabled: false,
    }};

    const fallbackConfig = {{
      width: "100%",
      height: "100%",
      locale: {locale_literal},
      colorTheme: "dark",
      defaultColumn: "overview",
      defaultScreen: "top_gainers",
      market: "taiwan",
      showToolbar: true,
      utm_source: "",
      utm_medium: "widget",
      utm_campaign: "screener",
    }};

    let parsedConfig = {{}};
    try {{
      const rawHash = window.location.hash ? decodeURIComponent(window.location.hash.slice(1)) : "";
      parsedConfig = rawHash ? JSON.parse(rawHash) : {{}};
    }} catch (_error) {{
      parsedConfig = {{}};
    }}

    const config = {{
      ...fallbackConfig,
      ...parsedConfig,
      locale: parsedConfig.locale || fallbackConfig.locale,
    }};

    const script = document.createElement("script");
    script.type = "text/javascript";
    script.async = true;
    script.src = {embed_script_literal};
    script.text = JSON.stringify(config, null, 2);
    document.getElementById("tv-screener-root").appendChild(script);
  </script>
</body>
</html>"""


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
    ticker: str | None = Query(None),
    market: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    query_args = {"limit": limit}
    if ticker:
        query_args["ticker"] = normalize_ticker(ticker)
    if market:
        query_args["market"] = market
    if date_from:
        query_args["date_from"] = date_from
    if date_to:
        query_args["date_to"] = date_to
    items = await db.list_news_articles(**query_args)
    return {"items": items}


@router.post("/news/articles")
async def upsert_news_articles(
    payload: list[dict] | dict = Body(...),
):
    if isinstance(payload, dict):
        raw_items = payload.get("items")
    else:
        raw_items = payload
    if not isinstance(raw_items, list):
        raise HTTPException(status_code=400, detail="payload must be a list or an object with items")
    items = [item for item in raw_items if isinstance(item, dict)]
    if not items:
        return {"stored": 0}
    try:
        stored = await db.upsert_news_articles(items)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"stored": stored}


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

@router.get("/tw/chips/coverage")
async def get_taiwan_chip_coverage(
    date: str | None = Query(None, description="YYYY-MM-DD"),
):
    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(400, "date must use YYYY-MM-DD") from exc
    return await db.get_taiwan_chip_coverage(target_date.isoformat() if target_date else None)


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


@router.get("/tw/chips/{ticker}/history")
async def get_taiwan_chip_history(
    ticker: str,
    days: int = Query(20, ge=5, le=120),
    refresh: bool = Query(False),
):
    normalized = normalize_ticker(ticker)

    if refresh:
        try:
            await taiwan_chip_provider.sync_ticker_snapshot(
                normalized,
                force_refresh=True,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            log.warning("taiwan chip history refresh failed for %s: %s", normalized, exc)

    history_limit = max(days, 60)
    snapshots = await db.list_taiwan_chip_snapshots(normalized, limit=history_limit)
    if not snapshots:
        try:
            snapshot = await taiwan_chip_provider.sync_ticker_snapshot(normalized)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            log.warning("taiwan chip history sync failed for %s: %s", normalized, exc)
            snapshot = None
        if snapshot:
            snapshots = await db.list_taiwan_chip_snapshots(normalized, limit=history_limit)
    if not snapshots:
        raise HTTPException(404, f"No Taiwan chip history available for {normalized}")

    ordered_snapshots = sorted(
        snapshots,
        key=lambda item: (
            str(item.get("snapshot_date") or ""),
            int(item.get("id") or 0),
        ),
    )
    series = [
        {
            "snapshot_date": item.get("snapshot_date"),
            "foreign_net_buy_sell": item.get("foreign_net_buy_sell"),
            "investment_trust_net_buy_sell": item.get("investment_trust_net_buy_sell"),
            "dealer_net_buy_sell": item.get("dealer_net_buy_sell"),
            "institutional_net_buy_sell": item.get("institutional_net_buy_sell"),
            "source": item.get("source"),
        }
        for item in ordered_snapshots[-days:]
    ]
    latest_snapshot = ordered_snapshots[-1]
    latest_summary = build_taiwan_chip_summary(latest_snapshot)
    series_dates = {item["snapshot_date"] for item in series if item.get("snapshot_date")}

    price_rows = []
    try:
        price_rows = await db.get_recent_ohlcv_rows(normalized, limit=max(days * 3, 90))
    except Exception as exc:
        log.warning("chip history price lookup failed for %s: %s", normalized, exc)

    return {
        "ticker": normalized,
        "days": days,
        "resolved_range": {
            "from": series[0]["snapshot_date"] if series else None,
            "to": series[-1]["snapshot_date"] if series else None,
        },
        "latest": {
            "snapshot_date": latest_snapshot.get("snapshot_date"),
            "source": latest_snapshot.get("source"),
            "detail": latest_snapshot,
            "summary": latest_summary,
        },
        "series": series,
        "price_series": _build_chip_price_series(price_rows, series_dates),
        "stats": _build_chip_history_stats(ordered_snapshots),
    }


@router.get("/tradingview/widgets/screener")
async def get_tradingview_screener_wrapper(
    locale: str = Query("en"),
):
    return HTMLResponse(
        content=_build_tradingview_screener_wrapper_html(locale),
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
