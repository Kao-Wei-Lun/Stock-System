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


class AssetAccountCreatePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    institution: str | None = Field(None, max_length=128)
    account_type: str = Field("brokerage", min_length=1, max_length=64)
    base_currency: str = Field("TWD", min_length=1, max_length=16)
    settlement_account_id: int | None = None
    auto_sync_trade_settlement: bool = False
    include_in_total: bool = True
    sort_order: int = 0
    notes: str | None = None


class AssetAccountUpdatePayload(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    institution: str | None = Field(None, max_length=128)
    account_type: str | None = Field(None, min_length=1, max_length=64)
    base_currency: str | None = Field(None, min_length=1, max_length=16)
    settlement_account_id: int | None = None
    auto_sync_trade_settlement: bool | None = None
    include_in_total: bool | None = None
    sort_order: int | None = None
    notes: str | None = None


class AssetCashLedgerCreatePayload(BaseModel):
    account_id: int
    flow_date: str = Field(..., min_length=10, max_length=64)
    flow_type: str = Field(..., min_length=1, max_length=32)
    amount: float
    currency: str = Field("TWD", min_length=1, max_length=16)
    fx_rate_to_base: float = 1.0
    is_initial_balance: bool = False
    counterparty: str | None = Field(None, max_length=128)
    note: str | None = None


class AssetCashLedgerUpdatePayload(BaseModel):
    account_id: int | None = None
    flow_date: str | None = Field(None, min_length=10, max_length=64)
    flow_type: str | None = Field(None, min_length=1, max_length=32)
    amount: float | None = None
    currency: str | None = Field(None, min_length=1, max_length=16)
    fx_rate_to_base: float | None = None
    is_initial_balance: bool | None = None
    counterparty: str | None = Field(None, max_length=128)
    note: str | None = None


class AssetTradeCreatePayload(BaseModel):
    account_id: int
    trade_date: str = Field(..., min_length=10, max_length=64)
    ticker: str = Field(..., min_length=1, max_length=32)
    display_name: str | None = Field(None, max_length=255)
    market: str | None = Field(None, max_length=32)
    asset_type: str = Field("stock", min_length=1, max_length=32)
    currency: str = Field("TWD", min_length=1, max_length=16)
    side: str = Field(..., min_length=1, max_length=16)
    quantity: float
    price: float
    fee_amount: float = 0.0
    tax_amount: float = 0.0
    fx_rate_to_base: float = 1.0
    is_initial_balance: bool = False
    source: str = Field("manual", min_length=1, max_length=64)
    note: str | None = None


class AssetTradeUpdatePayload(BaseModel):
    account_id: int | None = None
    trade_date: str | None = Field(None, min_length=10, max_length=64)
    ticker: str | None = Field(None, min_length=1, max_length=32)
    display_name: str | None = Field(None, max_length=255)
    market: str | None = Field(None, max_length=32)
    asset_type: str | None = Field(None, min_length=1, max_length=32)
    currency: str | None = Field(None, min_length=1, max_length=16)
    side: str | None = Field(None, min_length=1, max_length=16)
    quantity: float | None = None
    price: float | None = None
    fee_amount: float | None = None
    tax_amount: float | None = None
    fx_rate_to_base: float | None = None
    is_initial_balance: bool | None = None
    source: str | None = Field(None, min_length=1, max_length=64)
    note: str | None = None


class AssetReconciliationCreatePayload(BaseModel):
    account_id: int
    snapshot_date: str = Field(..., min_length=10, max_length=64)
    cash_actual: float | None = None
    market_value_actual: float | None = None
    positions_payload: list[dict] | None = None
    note: str | None = None


class AssetPriceOverrideCreatePayload(BaseModel):
    account_id: int | None = None
    ticker: str = Field(..., min_length=1, max_length=32)
    effective_at: str = Field(..., min_length=10, max_length=64)
    price: float = Field(..., gt=0)
    currency: str = Field("TWD", min_length=1, max_length=16)
    fx_rate_to_base: float | None = Field(None, gt=0)
    force_override: bool = False
    note: str | None = None


class AssetPriceOverrideUpdatePayload(BaseModel):
    account_id: int | None = None
    ticker: str | None = Field(None, min_length=1, max_length=32)
    effective_at: str | None = Field(None, min_length=10, max_length=64)
    price: float | None = Field(None, gt=0)
    currency: str | None = Field(None, min_length=1, max_length=16)
    fx_rate_to_base: float | None = Field(None, gt=0)
    force_override: bool | None = None
    note: str | None = None


class AssetFxRateCreatePayload(BaseModel):
    snapshot_date: str = Field(..., min_length=10, max_length=32)
    from_currency: str = Field(..., min_length=1, max_length=16)
    to_currency: str = Field(..., min_length=1, max_length=16)
    rate: float = Field(..., gt=0)
    source: str = Field("manual", min_length=1, max_length=64)
    note: str | None = None


class AssetFxRateUpdatePayload(BaseModel):
    snapshot_date: str | None = Field(None, min_length=10, max_length=32)
    from_currency: str | None = Field(None, min_length=1, max_length=16)
    to_currency: str | None = Field(None, min_length=1, max_length=16)
    rate: float | None = Field(None, gt=0)
    source: str | None = Field(None, min_length=1, max_length=64)
    note: str | None = None


class AssetPositionAdjustmentCreatePayload(BaseModel):
    account_id: int
    event_date: str = Field(..., min_length=10, max_length=64)
    ticker: str = Field(..., min_length=1, max_length=32)
    event_type: str = Field("adjustment", min_length=1, max_length=32)
    quantity_delta: float | None = None
    cost_basis_delta: float | None = None
    cash_delta: float | None = None
    currency: str | None = Field(None, max_length=16)
    split_ratio: float | None = Field(None, gt=0)
    target_ticker: str | None = Field(None, max_length=32)
    target_display_name: str | None = Field(None, max_length=255)
    target_market: str | None = Field(None, max_length=32)
    target_asset_type: str | None = Field(None, max_length=32)
    note: str | None = None


class AssetPositionAdjustmentUpdatePayload(BaseModel):
    account_id: int | None = None
    event_date: str | None = Field(None, min_length=10, max_length=64)
    ticker: str | None = Field(None, min_length=1, max_length=32)
    event_type: str | None = Field(None, min_length=1, max_length=32)
    quantity_delta: float | None = None
    cost_basis_delta: float | None = None
    cash_delta: float | None = None
    currency: str | None = Field(None, max_length=16)
    split_ratio: float | None = Field(None, gt=0)
    target_ticker: str | None = Field(None, max_length=32)
    target_display_name: str | None = Field(None, max_length=255)
    target_market: str | None = Field(None, max_length=32)
    target_asset_type: str | None = Field(None, max_length=32)
    note: str | None = None


class AssetCsvImportPayload(BaseModel):
    csv_text: str = Field(..., min_length=1)
    default_account_id: int | None = None
    dry_run: bool = False


class AssetJournalImportPayload(BaseModel):
    account_id: int
    ticker: str | None = Field(None, max_length=32)
    market: str | None = Field(None, max_length=32)
    strategy_code: str | None = Field(None, max_length=64)
    tag: str | None = Field(None, max_length=128)
    search: str | None = Field(None, max_length=128)
    limit: int = Field(50, ge=1, le=200)


class AssetRecomputePayload(BaseModel):
    refresh: bool = True
    performance_range: str = Field("1y", min_length=2, max_length=16)


# ─── Paper Trading ───────────────────────────────────────────

class PaperTradingAccountCreate(BaseModel):
    name: str = Field("TMF Paper Account", min_length=1, max_length=128)
    product_symbol: str = Field("TMF", max_length=32)
    starting_equity: float = Field(100_000, gt=0)
    initial_margin_per_contract: float | None = Field(None, gt=0)
    risk_config: dict = Field(default_factory=dict)
    cost_model: dict = Field(default_factory=dict)
    strategy_config: dict | None = None


class PaperTradingMarginEstimatePayload(BaseModel):
    product_symbol: str = Field("TMF", max_length=32)


class PaperTradingBotCreate(BaseModel):
    account_id: int
    name: str = Field("TMF Trading Bot", min_length=1, max_length=128)
    mode: str = Field("realtime", pattern="^(realtime|replay)$")
    product_symbol: str = Field("TMF", max_length=32)
    direction_symbol: str = Field("TXF", max_length=32)
    session_mode: str = Field("day_session_only")
    holding_policy: str = Field("day_only", pattern="^(day_only|overnight_allowed)$")
    strategy_config: dict | None = None


class PaperTradingBotUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    status: str | None = Field(None, pattern="^(idle|running|stopped|error)$")
    session_mode: str | None = None
    holding_policy: str | None = None
    strategy_config: dict | None = None
    error_message: str | None = None


class PaperTradingReplayPayload(BaseModel):
    account_id: int = Field(..., gt=0)
    product_symbol: str = Field("TMF", max_length=32)
    direction_symbol: str = Field("TXF", max_length=32)
    start_date: str = Field(..., min_length=10, max_length=10)
    end_date: str = Field(..., min_length=10, max_length=10)
    starting_equity: float | None = Field(None, gt=0)
    initial_margin_per_contract: float | None = Field(None, gt=0)
    risk_config: dict = Field(default_factory=dict)
    strategy_config: dict = Field(default_factory=dict)
    cost_model: dict = Field(default_factory=dict)


class FuturesPositionSizePayload(BaseModel):
    account_id: int | None = None
    product_symbol: str = Field("TMF", max_length=32)
    futures_capital: float | None = Field(None, gt=0)
    point_value: float | None = Field(None, gt=0)
    initial_margin: float | None = Field(None, gt=0)
    maintenance_margin: float | None = Field(None, ge=0)
    stop_loss_points: float = Field(..., gt=0)
    stress_points: float = Field(2_000, gt=0)
    margin_usage_limit: float = Field(0.6, ge=0)
    single_trade_risk_pct: float = Field(0.02, ge=0)
    total_position_risk_pct: float = Field(0.2, ge=0)
    user_max_contracts: int = Field(10, ge=0)
    open_contracts: int | None = Field(None, ge=0)
    margin_used: float | None = Field(None, ge=0)


class FuturesOrderValidatePayload(FuturesPositionSizePayload):
    requested_qty: int = Field(..., ge=1)
