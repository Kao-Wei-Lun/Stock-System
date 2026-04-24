"""
QuantVision Pro — Paper Trading API Routes

TMF 模擬交易 API：
- Bot 管理（CRUD）
- 帳戶管理
- 回放執行
- 狀態查詢（部位、委託、成交、權益、風控事件）
- 即時 Bot 啟動/停止
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import DEFAULT_OWNER_ID, db
from futopt_history_service import (
    date_range_to_futopt_period,
    intraday_end_bound,
    sync_futopt_intraday_ohlc,
)
from providers import fubon_futopt_provider
from schemas import (
    PaperTradingAccountCreate,
    PaperTradingBotCreate,
    PaperTradingBotUpdate,
    PaperTradingReplayPayload,
)
from paper_trading.cost_model import CostModel, get_product_spec
from paper_trading.risk_engine import RiskConfig
from paper_trading.strategy_engine import StrategyConfig
from paper_trading.replay_engine import ReplayEngine

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/paper-trading", tags=["paper-trading"])

# 全域 bot 實例管理
_active_bots: dict[int, "PaperTradingBot"] = {}


# ─── Accounts ─────────────────────────────────────────────────

@router.post("/accounts")
async def create_paper_trading_account(payload: PaperTradingAccountCreate):
    data = payload.model_dump()
    account = await db.create_paper_trading_account(data, owner_id=DEFAULT_OWNER_ID)
    return account


@router.get("/accounts")
async def list_paper_trading_accounts():
    return {"items": await db.list_paper_trading_accounts(owner_id=DEFAULT_OWNER_ID)}


@router.get("/accounts/{account_id}")
async def get_paper_trading_account(account_id: int):
    account = await db.get_paper_trading_account(account_id, owner_id=DEFAULT_OWNER_ID)
    if not account:
        raise HTTPException(404, "Paper trading account not found")
    return account


# ─── Bots ─────────────────────────────────────────────────────

@router.post("/bots")
async def create_paper_trading_bot(payload: PaperTradingBotCreate):
    data = payload.model_dump()
    # 驗證帳戶存在
    account = await db.get_paper_trading_account(data["account_id"], owner_id=DEFAULT_OWNER_ID)
    if not account:
        raise HTTPException(400, "Paper trading account not found")
    bot = await db.create_paper_trading_bot(data, owner_id=DEFAULT_OWNER_ID)
    return bot


@router.get("/bots")
async def list_paper_trading_bots(
    account_id: int | None = Query(None),
):
    return {
        "items": await db.list_paper_trading_bots(
            owner_id=DEFAULT_OWNER_ID,
            account_id=account_id,
        )
    }


@router.get("/bots/{bot_id}")
async def get_paper_trading_bot(bot_id: int):
    bot = await db.get_paper_trading_bot(bot_id, owner_id=DEFAULT_OWNER_ID)
    if not bot:
        raise HTTPException(404, "Paper trading bot not found")
    return bot


@router.patch("/bots/{bot_id}")
async def update_paper_trading_bot(bot_id: int, payload: PaperTradingBotUpdate):
    existing = await db.get_paper_trading_bot(bot_id, owner_id=DEFAULT_OWNER_ID)
    if not existing:
        raise HTTPException(404, "Paper trading bot not found")
    data = payload.model_dump(exclude_none=True)
    updated = await db.update_paper_trading_bot(bot_id, data, owner_id=DEFAULT_OWNER_ID)
    return updated


# ─── Bot Start/Stop ───────────────────────────────────────────

@router.post("/bots/{bot_id}/start")
async def start_paper_trading_bot(bot_id: int):
    """啟動即時模擬交易 Bot"""
    from paper_trading.bot_runner import PaperTradingBot, BotStatus

    bot_record = await db.get_paper_trading_bot(bot_id, owner_id=DEFAULT_OWNER_ID)
    if not bot_record:
        raise HTTPException(404, "Paper trading bot not found")

    if bot_id in _active_bots and _active_bots[bot_id].status == BotStatus.RUNNING:
        return {"status": "already_running", "bot": _active_bots[bot_id].get_state()}

    # 取得帳戶設定
    account = await db.get_paper_trading_account(
        bot_record["account_id"], owner_id=DEFAULT_OWNER_ID,
    )
    if not account:
        raise HTTPException(400, "Associated account not found")

    # 建立 bot 實例
    risk_config = RiskConfig.from_dict(account.get("risk_config", {}))
    # 用帳戶層級的 starting_equity / initial_margin_per_contract 覆蓋 risk_config 預設值
    risk_config.starting_equity = float(account.get("starting_equity", risk_config.starting_equity))
    risk_config.initial_margin_per_contract = float(
        account.get("initial_margin_per_contract", risk_config.initial_margin_per_contract)
    )
    strategy_config = StrategyConfig.from_dict(
        bot_record.get("strategy_config") or account.get("strategy_config") or {},
    )
    cost_model = CostModel.from_dict(account.get("cost_model", {}))
    product = get_product_spec(bot_record.get("product_symbol", "TMF"))

    bot_instance = PaperTradingBot(
        bot_id=bot_id,
        risk_config=risk_config,
        strategy_config=strategy_config,
        cost_model=cost_model,
        product=product,
        tx_symbol=bot_record.get("direction_symbol", "TXF"),
        tmf_symbol=bot_record.get("product_symbol", "TMF"),
    )

    # 嘗試連結 realtime_pool
    try:
        from main import fubon_realtime_pool
        bot_instance.start(fubon_realtime_pool)
    except (ImportError, AttributeError):
        # 沒有 realtime pool，bot 仍可啟動但不接收 WS
        bot_instance.start(None)

    _active_bots[bot_id] = bot_instance

    # 更新 DB 狀態
    await db.update_paper_trading_bot(bot_id, {
        "status": "running",
        "started_at": bot_instance.started_at.isoformat() if bot_instance.started_at else None,
    }, owner_id=DEFAULT_OWNER_ID)

    return {"status": "started", "bot": bot_instance.get_state()}


@router.post("/bots/{bot_id}/stop")
async def stop_paper_trading_bot(bot_id: int):
    """停止即時模擬交易 Bot"""
    bot_instance = _active_bots.get(bot_id)
    if not bot_instance:
        raise HTTPException(404, "Bot is not running")

    try:
        from main import fubon_realtime_pool
        bot_instance.stop(fubon_realtime_pool)
    except (ImportError, AttributeError):
        bot_instance.stop(None)

    # 更新 DB 狀態
    await db.update_paper_trading_bot(bot_id, {
        "status": "stopped",
        "stopped_at": bot_instance.stopped_at.isoformat() if bot_instance.stopped_at else None,
        "bar_count": bot_instance._bar_count,
    }, owner_id=DEFAULT_OWNER_ID)

    # 儲存 bot 的 fills 和 equity
    account_id = (await db.get_paper_trading_bot(bot_id, owner_id=DEFAULT_OWNER_ID) or {}).get("account_id")
    if account_id:
        fills = [f.to_dict() for f in bot_instance.broker.all_fills]
        await db.save_paper_trading_fills(fills, account_id, DEFAULT_OWNER_ID, bot_id)
        equity = [s.to_dict() for s in bot_instance.account.equity_snapshots]
        await db.save_paper_trading_equity_snapshots(equity, account_id, DEFAULT_OWNER_ID, bot_id)
        risk_events = bot_instance.risk.get_risk_events()
        await db.save_paper_trading_risk_events(risk_events, account_id, DEFAULT_OWNER_ID, bot_id)

    state = bot_instance.get_state()
    _active_bots.pop(bot_id, None)

    return {"status": "stopped", "bot": state}


@router.get("/bots/{bot_id}/state")
async def get_paper_trading_bot_state(bot_id: int):
    """取得即時 Bot 的當前狀態"""
    bot_instance = _active_bots.get(bot_id)
    if not bot_instance:
        return {"status": "not_running", "bot_id": bot_id}
    return bot_instance.get_state()


# ─── Positions / Orders / Fills ───────────────────────────────

@router.get("/positions")
async def list_paper_trading_positions(account_id: int = Query(...)):
    return {"items": await db.get_paper_trading_positions(account_id, owner_id=DEFAULT_OWNER_ID)}


@router.get("/orders")
async def list_paper_trading_orders(
    account_id: int = Query(...),
    limit: int = Query(200, ge=1, le=1000),
):
    return {"items": await db.list_paper_trading_orders(account_id, owner_id=DEFAULT_OWNER_ID, limit=limit)}


@router.get("/fills")
async def list_paper_trading_fills(
    account_id: int = Query(...),
    bot_id: int | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    return {
        "items": await db.list_paper_trading_fills(
            account_id, owner_id=DEFAULT_OWNER_ID, bot_id=bot_id, limit=limit,
        )
    }


@router.get("/equity")
async def list_paper_trading_equity(
    account_id: int = Query(...),
    replay_run_id: int | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
):
    return {
        "items": await db.list_paper_trading_equity_snapshots(
            account_id, owner_id=DEFAULT_OWNER_ID,
            replay_run_id=replay_run_id, limit=limit,
        )
    }


@router.get("/risk-events")
async def list_paper_trading_risk_events(
    account_id: int = Query(...),
    limit: int = Query(100, ge=1, le=500),
):
    return {
        "items": await db.list_paper_trading_risk_events(
            account_id, owner_id=DEFAULT_OWNER_ID, limit=limit,
        )
    }


# ─── Replay ──────────────────────────────────────────────────

@router.post("/replay/run")
async def run_paper_trading_replay(payload: PaperTradingReplayPayload):
    """
    執行歷史回放模擬交易。

    需要 DB 中有 TMF 和 TXF 的 1m K 棒資料。
    """
    if payload.start_date > payload.end_date:
        raise HTTPException(400, "start_date must be before end_date")

    replay_end_bound = intraday_end_bound(payload.end_date)

    # 從 DB 取得 K 棒資料
    tmf_bars = await db.get_ohlcv_range(
        payload.product_symbol,
        start_date=payload.start_date,
        end_date=replay_end_bound,
        interval="1m",
    )
    tx_bars = await db.get_ohlcv_range(
        payload.direction_symbol,
        start_date=payload.start_date,
        end_date=replay_end_bound,
        interval="1m",
    )

    # 若資料庫缺少期貨分鐘 K，先嘗試用富邦 futopt intraday candles 補齊近期資料。
    sync_period = date_range_to_futopt_period(payload.start_date, payload.end_date)
    if not tmf_bars:
        try:
            await sync_futopt_intraday_ohlc(
                fubon_futopt_provider,
                db,
                payload.product_symbol,
                period=sync_period,
                interval="1m",
            )
            tmf_bars = await db.get_ohlcv_range(
                payload.product_symbol,
                start_date=payload.start_date,
                end_date=replay_end_bound,
                interval="1m",
            )
        except Exception as exc:
            log.warning("paper replay futopt sync failed for %s: %s", payload.product_symbol, exc)

    if not tx_bars:
        try:
            await sync_futopt_intraday_ohlc(
                fubon_futopt_provider,
                db,
                payload.direction_symbol,
                period=sync_period,
                interval="1m",
            )
            tx_bars = await db.get_ohlcv_range(
                payload.direction_symbol,
                start_date=payload.start_date,
                end_date=replay_end_bound,
                interval="1m",
            )
        except Exception as exc:
            log.warning("paper replay futopt sync failed for %s: %s", payload.direction_symbol, exc)

    if not tmf_bars:
        raise HTTPException(400, f"No {payload.product_symbol} 1m bar data found for the given date range")
    if not tx_bars:
        raise HTTPException(400, f"No {payload.direction_symbol} 1m bar data found for the given date range")

    # 轉換 bar 格式
    def _to_bar_dict(row):
        return {
            "time": str(row.get("date") or row.get("timestamp") or ""),
            "open": float(row.get("open", 0)),
            "high": float(row.get("high", 0)),
            "low": float(row.get("low", 0)),
            "close": float(row.get("close", 0)),
            "volume": int(row.get("volume", 0)),
        }

    tmf_bar_dicts = [_to_bar_dict(r) for r in tmf_bars]
    tx_bar_dicts = [_to_bar_dict(r) for r in tx_bars]

    # 建立回放引擎
    risk_config = RiskConfig.from_dict(payload.risk_config)
    risk_config.starting_equity = payload.starting_equity
    risk_config.initial_margin_per_contract = payload.initial_margin_per_contract
    strategy_config = StrategyConfig.from_dict(payload.strategy_config)
    cost_model = CostModel.from_dict(payload.cost_model)
    product = get_product_spec(payload.product_symbol)

    engine = ReplayEngine(
        risk_config=risk_config,
        strategy_config=strategy_config,
        cost_model=cost_model,
        product=product,
    )

    result = engine.run(tx_bar_dicts, tmf_bar_dicts)

    if result.error:
        raise HTTPException(400, result.error)

    # 儲存回放結果
    run_data = {
        "account_id": payload.account_id,
        "product_symbol": payload.product_symbol,
        "direction_symbol": payload.direction_symbol,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "bar_count": result.bar_count,
        "starting_equity": payload.starting_equity,
        "total_fees": result.account_final.get("total_fees", 0),
        "summary": result.summary,
        "risk_config": risk_config.to_dict(),
        "strategy_config": strategy_config.to_dict(),
        "cost_model": cost_model.to_dict(),
    }
    saved_run = await db.save_paper_trading_replay_run(run_data, owner_id=DEFAULT_OWNER_ID)

    # 儲存相關紀錄
    run_id = saved_run.get("id")
    if run_id and payload.account_id:
        await db.save_paper_trading_fills(
            result.fills, payload.account_id, DEFAULT_OWNER_ID,
        )
        await db.save_paper_trading_equity_snapshots(
            result.equity_curve, payload.account_id, DEFAULT_OWNER_ID,
            replay_run_id=run_id,
        )
        await db.save_paper_trading_risk_events(
            result.risk_events, payload.account_id, DEFAULT_OWNER_ID,
            replay_run_id=run_id,
        )

    return {
        "run": saved_run,
        "result": result.to_dict(),
    }


@router.get("/replay/runs")
async def list_paper_trading_replay_runs(
    limit: int = Query(50, ge=1, le=200),
):
    return {
        "items": await db.list_paper_trading_replay_runs(
            owner_id=DEFAULT_OWNER_ID, limit=limit,
        )
    }


@router.get("/replay/runs/{run_id}")
async def get_paper_trading_replay_run(run_id: int):
    run = await db.get_paper_trading_replay_run(run_id, owner_id=DEFAULT_OWNER_ID)
    if not run:
        raise HTTPException(404, "Replay run not found")

    # 附加 equity curve 和 risk events
    equity = await db.list_paper_trading_equity_snapshots(
        run.get("account_id", 0), owner_id=DEFAULT_OWNER_ID,
        replay_run_id=run_id, limit=2000,
    )
    run["equity_curve"] = equity
    return run
