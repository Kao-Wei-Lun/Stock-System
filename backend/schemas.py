"""
QuantVision Pro — Pydantic request/response schemas.

Extracted from main.py to improve modularity.
"""

from pydantic import BaseModel, Field


# ─── Watchlist ───────────────────────────────────────────────

class WatchlistGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    color: str | None = Field(None, max_length=32)


class WatchlistGroupUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    color: str | None = Field(None, max_length=32)


class WatchlistItemCreate(BaseModel):
    group_id: int
    ticker: str = Field(..., min_length=1, max_length=32)
    tags: list[str] = Field(default_factory=list)


class WatchlistItemsOrderUpdate(BaseModel):
    item_ids: list[int] = Field(..., min_length=1)


# ─── Workspace Presets ───────────────────────────────────────

class WorkspacePresetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    chart_layout: str = Field("single", max_length=32)
    active_ticker: str | None = Field(None, max_length=32)
    current_period: str = Field("1y", max_length=16)
    current_interval: str = Field("1d", max_length=16)
    workspace_tab: str = Field("chart", max_length=32)
    comparison_mode: str = Field("percent", max_length=32)
    payload: dict = Field(default_factory=dict)
    is_default: bool = False


class WorkspacePresetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    chart_layout: str | None = Field(None, max_length=32)
    active_ticker: str | None = Field(None, max_length=32)
    current_period: str | None = Field(None, max_length=16)
    current_interval: str | None = Field(None, max_length=16)
    workspace_tab: str | None = Field(None, max_length=32)
    comparison_mode: str | None = Field(None, max_length=32)
    payload: dict | None = None
    is_default: bool | None = None


# ─── Alerts ──────────────────────────────────────────────────

class AlertCreatePayload(BaseModel):
    name: str | None = Field(None, max_length=128)
    ticker: str = Field(..., min_length=1, max_length=32)
    type: str = Field(..., min_length=1, max_length=32)
    condition: str = Field(..., min_length=1, max_length=32)
    value: float | None = None
    value2: float | None = None
    timeframe: str = Field("1d", max_length=16)
    condition_payload: dict = Field(default_factory=dict)
    notification_title: str | None = Field(None, max_length=255)
    note: str | None = None
    active: bool = True
    triggered: bool = False
    triggered_at: str | None = None
    last_evaluated_at: str | None = None


class AlertUpdatePayload(BaseModel):
    name: str | None = Field(None, max_length=128)
    ticker: str | None = Field(None, min_length=1, max_length=32)
    type: str | None = Field(None, min_length=1, max_length=32)
    condition: str | None = Field(None, min_length=1, max_length=32)
    value: float | None = None
    value2: float | None = None
    timeframe: str | None = Field(None, max_length=16)
    condition_payload: dict | None = None
    notification_title: str | None = Field(None, max_length=255)
    note: str | None = None
    active: bool | None = None
    triggered: bool | None = None
    triggered_at: str | None = None
    last_evaluated_at: str | None = None


# ─── Quote ───────────────────────────────────────────────────

class QuoteResponse(BaseModel):
    ticker: str
    source: str
    quote_type: str
    is_delayed: bool
    resolved_symbol: str | None = None
    market: str | None = None
    exchange: str | None = None
    quote_timestamp: str | None = None
    synced_at: str | None = None
    name: str | None = None
    currency: str | None = None
    price: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: int | None = None
    market_cap: int | None = None
    bid: float | None = None
    ask: float | None = None
    bid_size: int | None = None
    ask_size: int | None = None
    bids: list[dict] | None = None
    asks: list[dict] | None = None
    ts: int | None = None


# ─── Backtest ────────────────────────────────────────────────

class BacktestRunCreatePayload(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=32)
    strategy: str = Field(..., min_length=1, max_length=128)
    start: str = Field(..., min_length=10, max_length=32)
    end: str = Field(..., min_length=10, max_length=32)
    interval: str = Field("1d", max_length=16)
    capital: float = Field(..., gt=0)
    fee: float = Field(0.0, ge=0, le=100)
    slippage: float = Field(0.0, ge=0, le=100)
    sl: float | None = Field(None, ge=0, le=100)
    tp: float | None = Field(None, ge=0, le=100)
    position_sizing: str = Field("full_equity", max_length=32)


# ─── Notifications ───────────────────────────────────────────

class NotificationReadStatePayload(BaseModel):
    read: bool = True


# ─── Trade Journal ───────────────────────────────────────────

class TradeJournalAttachmentPayload(BaseModel):
    file_path: str = Field(..., min_length=1, max_length=512)
    file_type: str | None = Field(None, max_length=64)


class TradeJournalEntryCreatePayload(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=32)
    market: str | None = Field(None, max_length=32)
    direction: str = Field("long", max_length=16)
    strategy_code: str | None = Field(None, max_length=64)
    entry_time: str = Field(..., min_length=10, max_length=64)
    entry_price: float = Field(..., gt=0)
    exit_time: str | None = Field(None, max_length=64)
    exit_price: float | None = None
    size: float = Field(..., gt=0)
    stop_loss: float | None = None
    take_profit: float | None = None
    entry_reason: str | None = None
    exit_reason: str | None = None
    emotion_tag: str | None = Field(None, max_length=64)
    review_notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    attachments: list[TradeJournalAttachmentPayload] = Field(default_factory=list)
    result: dict = Field(default_factory=dict)


class TradeJournalEntryUpdatePayload(BaseModel):
    ticker: str | None = Field(None, min_length=1, max_length=32)
    market: str | None = Field(None, max_length=32)
    direction: str | None = Field(None, max_length=16)
    strategy_code: str | None = Field(None, max_length=64)
    entry_time: str | None = Field(None, min_length=10, max_length=64)
    entry_price: float | None = Field(None, gt=0)
    exit_time: str | None = Field(None, max_length=64)
    exit_price: float | None = None
    size: float | None = Field(None, gt=0)
    stop_loss: float | None = None
    take_profit: float | None = None
    entry_reason: str | None = None
    exit_reason: str | None = None
    emotion_tag: str | None = Field(None, max_length=64)
    review_notes: str | None = None
    tags: list[str] | None = None
    attachments: list[TradeJournalAttachmentPayload] | None = None
    result: dict | None = None


# ─── Journal Filter Presets ──────────────────────────────────

class JournalFilterPresetCreatePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(None, max_length=512)
    scope: str = Field("ticker", max_length=32)
    filters: dict = Field(default_factory=dict)


class JournalFilterPresetUpdatePayload(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=512)
    scope: str | None = Field(None, max_length=32)
    filters: dict | None = None


# ─── Screener ────────────────────────────────────────────────

class ScreenerPresetCreatePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(None, max_length=512)
    filters: dict = Field(default_factory=dict)


class ScreenerPresetUpdatePayload(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=512)
    filters: dict | None = None


class ScreenerRunPayload(BaseModel):
    filters: dict = Field(default_factory=dict)
