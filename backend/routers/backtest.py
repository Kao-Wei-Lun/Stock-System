"""Backtest routes."""

import logging

from fastapi import APIRouter, HTTPException, Query

from backtest_engine import list_backtest_strategies, run_backtest
from data_fetcher import normalize_ticker
from database import DEFAULT_OWNER_ID, db
from providers import fetcher
from schemas import BacktestRunCreatePayload
from workload_executor import BoundedWorkloadExecutor, WorkloadTimeoutError

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtests", tags=["backtest"])
workload_executor = BoundedWorkloadExecutor(name="backtest", max_workers=1, timeout_seconds=30)


def configure(*, executor: BoundedWorkloadExecutor) -> None:
    global workload_executor
    workload_executor = executor


@router.get("/strategies")
async def get_backtest_strategies():
    return {"items": list_backtest_strategies()}


@router.get("/runs")
async def list_backtest_runs(
    ticker: str | None = Query(None, description="Optional ticker filter"),
    limit: int = Query(20, ge=1, le=200),
):
    normalized_ticker = normalize_ticker(ticker) if ticker else None
    return {
        "items": await db.list_backtest_runs(
            owner_id=DEFAULT_OWNER_ID,
            ticker=normalized_ticker,
            limit=limit,
        )
    }


@router.get("/runs/{run_id}")
async def get_backtest_run(run_id: int):
    run = await db.get_backtest_run(run_id, owner_id=DEFAULT_OWNER_ID)
    if not run:
        raise HTTPException(404, "Backtest run not found")
    return run


@router.post("/runs")
async def create_backtest_run(payload: BacktestRunCreatePayload):
    ticker = normalize_ticker(payload.ticker)
    start = payload.start.strip()
    end = payload.end.strip()
    if start > end:
        raise HTTPException(400, "Backtest start date must be earlier than end date")

    rows = await db.get_ohlcv_range(
        ticker,
        start_date=start,
        end_date=end,
        interval=payload.interval,
    )
    if len(rows) < 30:
        await fetcher.fetch_and_store(ticker, period="max", interval=payload.interval, include_info=False)
        rows = await db.get_ohlcv_range(
            ticker,
            start_date=start,
            end_date=end,
            interval=payload.interval,
        )

    try:
        result = await workload_executor.run(
            run_backtest,
            rows,
            {
                "ticker": ticker,
                "strategy": payload.strategy,
                "start": start,
                "end": end,
                "interval": payload.interval,
                "capital": payload.capital,
                "fee_rate": payload.fee / 100,
                "slippage_rate": payload.slippage / 100,
                "stop_loss_pct": (payload.sl / 100) if payload.sl not in (None, "") else None,
                "take_profit_pct": (payload.tp / 100) if payload.tp not in (None, "") else None,
                "position_sizing": payload.position_sizing,
            },
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except WorkloadTimeoutError as exc:
        log.warning("Backtest timed out for %s: %s", ticker, exc)
        raise HTTPException(504, "Backtest execution timed out") from exc

    persisted = await db.create_backtest_run(
        {
            "ticker": ticker,
            "strategy_key": result["strategy_key"],
            "strategy_name": result["strategy"],
            "interval": result["interval"],
            "start_date": result["start"],
            "end_date": result["end"],
            "initial_capital": result["capital"],
            "final_equity": result["finalEquity"],
            "total_return_pct": result["totalReturn"],
            "max_drawdown_pct": result["maxDrawdown"],
            "sharpe_ratio": result["sharpe"],
            "trade_count": result["sellTrades"],
            "win_rate_pct": result["winRate"],
            "bars_count": result["bars"],
            "fee_rate": result["feeRate"],
            "slippage_rate": result["slippageRate"],
            "stop_loss_pct": result["stopLoss"],
            "take_profit_pct": result["takeProfit"],
            "position_sizing": result["positionSizing"],
            "summary": {
                key: value
                for key, value in result.items()
                if key not in {"trades", "equity_curve"}
            },
        },
        result["trades"],
        result["equity_curve"],
        owner_id=DEFAULT_OWNER_ID,
    )
    return persisted
