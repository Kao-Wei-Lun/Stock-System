"""Trade journal routes."""

from fastapi import APIRouter, HTTPException, Query

from data_fetcher import normalize_ticker
from database import DEFAULT_OWNER_ID, db
from schemas import (
    JournalFilterPresetCreatePayload,
    JournalFilterPresetUpdatePayload,
    TradeJournalEntryCreatePayload,
    TradeJournalEntryUpdatePayload,
)

router = APIRouter(prefix="/api/journal", tags=["journal"])


@router.get("/trades")
async def list_trade_journal_entries(
    ticker: str | None = Query(None),
    market: str | None = Query(None),
    strategy_code: str | None = Query(None),
    tag: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    normalized_ticker = normalize_ticker(ticker) if ticker else None
    return {
        "items": await db.list_trade_journal_entries(
            owner_id=DEFAULT_OWNER_ID,
            ticker=normalized_ticker,
            market=market.strip() if market else None,
            strategy_code=strategy_code.strip() if strategy_code else None,
            tag=tag.strip() if tag else None,
            search=search.strip() if search else None,
            limit=limit,
        )
    }


@router.get("/trades/stats")
async def get_trade_journal_stats(
    ticker: str | None = Query(None),
    market: str | None = Query(None),
    strategy_code: str | None = Query(None),
    tag: str | None = Query(None),
    search: str | None = Query(None),
):
    normalized_ticker = normalize_ticker(ticker) if ticker else None
    return await db.get_trade_journal_stats(
        owner_id=DEFAULT_OWNER_ID,
        ticker=normalized_ticker,
        market=market.strip() if market else None,
        strategy_code=strategy_code.strip() if strategy_code else None,
        tag=tag.strip() if tag else None,
        search=search.strip() if search else None,
    )


@router.post("/trades")
async def create_trade_journal_entry(payload: TradeJournalEntryCreatePayload):
    try:
        return await db.create_trade_journal_entry(payload.model_dump(), owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/trades/{entry_id}")
async def get_trade_journal_entry(entry_id: int):
    entry = await db.get_trade_journal_entry(entry_id, owner_id=DEFAULT_OWNER_ID)
    if not entry:
        raise HTTPException(404, "Trade journal entry not found")
    return entry


@router.patch("/trades/{entry_id}")
async def update_trade_journal_entry(entry_id: int, payload: TradeJournalEntryUpdatePayload):
    try:
        entry = await db.update_trade_journal_entry(
            entry_id,
            payload.model_dump(exclude_unset=True),
            owner_id=DEFAULT_OWNER_ID,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not entry:
        raise HTTPException(404, "Trade journal entry not found")
    return entry


@router.delete("/trades/{entry_id}")
async def delete_trade_journal_entry(entry_id: int):
    deleted = await db.delete_trade_journal_entry(entry_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Trade journal entry not found")
    return {"ok": True, "entry_id": entry_id}


# ─── Filter Presets ──────────────────────────────────────────

@router.get("/presets")
async def list_journal_filter_presets():
    return {"items": await db.list_journal_filter_presets(owner_id=DEFAULT_OWNER_ID)}


@router.post("/presets")
async def create_journal_filter_preset(payload: JournalFilterPresetCreatePayload):
    try:
        return await db.create_journal_filter_preset(payload.model_dump(), owner_id=DEFAULT_OWNER_ID)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/presets/{preset_id}")
async def get_journal_filter_preset(preset_id: int):
    preset = await db.get_journal_filter_preset(preset_id, owner_id=DEFAULT_OWNER_ID)
    if not preset:
        raise HTTPException(404, "Journal filter preset not found")
    return preset


@router.put("/presets/{preset_id}")
async def update_journal_filter_preset(preset_id: int, payload: JournalFilterPresetUpdatePayload):
    try:
        preset = await db.update_journal_filter_preset(
            preset_id,
            payload.model_dump(exclude_unset=True),
            owner_id=DEFAULT_OWNER_ID,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not preset:
        raise HTTPException(404, "Journal filter preset not found")
    return preset


@router.delete("/presets/{preset_id}")
async def delete_journal_filter_preset(preset_id: int):
    deleted = await db.delete_journal_filter_preset(preset_id, owner_id=DEFAULT_OWNER_ID)
    if not deleted:
        raise HTTPException(404, "Journal filter preset not found")
    return {"ok": True, "preset_id": preset_id}


@router.post("/presets/{preset_id}/use")
async def mark_journal_filter_preset_used(preset_id: int):
    preset = await db.mark_journal_filter_preset_used(preset_id, owner_id=DEFAULT_OWNER_ID)
    if not preset:
        raise HTTPException(404, "Journal filter preset not found")
    return preset
