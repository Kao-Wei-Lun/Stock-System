from typing import Any, Dict, List, Optional
from database.helpers import *
from database.core import DEFAULT_OWNER_ID
# Import common serialization helpers here if needed

class BacktestMixin:
    async def create_backtest_run(
        self,
        payload: Dict[str, Any],
        trades: List[Dict[str, Any]],
        equity_points: List[Dict[str, Any]],
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Dict[str, Any]:
        normalized = _normalize_backtest_run_payload(payload)

        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO `backtest_runs`
                            (`owner_id`, `ticker`, `strategy_key`, `strategy_name`, `interval`,
                             `start_date`, `end_date`, `initial_capital`, `final_equity`,
                             `total_return_pct`, `max_drawdown_pct`, `sharpe_ratio`, `trade_count`,
                             `win_rate_pct`, `bars_count`, `fee_rate`, `slippage_rate`,
                             `stop_loss_pct`, `take_profit_pct`, `position_sizing`, `summary_json`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            owner_id,
                            normalized["ticker"],
                            normalized["strategy_key"],
                            normalized["strategy_name"],
                            normalized["interval"],
                            normalized["start_date"],
                            normalized["end_date"],
                            normalized["initial_capital"],
                            normalized["final_equity"],
                            normalized["total_return_pct"],
                            normalized["max_drawdown_pct"],
                            normalized["sharpe_ratio"],
                            normalized["trade_count"],
                            normalized["win_rate_pct"],
                            normalized["bars_count"],
                            normalized["fee_rate"],
                            normalized["slippage_rate"],
                            normalized["stop_loss_pct"],
                            normalized["take_profit_pct"],
                            normalized["position_sizing"],
                            _json_dumps(normalized["summary"]),
                        ),
                    )
                    run_id = cur.lastrowid

                    if trades:
                        await cur.executemany(
                            """
                            INSERT INTO `backtest_trades`
                                (`backtest_run_id`, `owner_id`, `ticker`, `side`, `entry_date`,
                                 `entry_price`, `exit_date`, `exit_price`, `quantity`, `gross_pnl`,
                                 `net_pnl`, `return_pct`, `fee_amount`, `holding_bars`, `exit_reason`,
                                 `payload_json`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    run_id,
                                    owner_id,
                                    normalized["ticker"],
                                    _optional_string(trade.get("side"), max_length=16) or "long",
                                    _parse_datetime_value(trade.get("entry_date")),
                                    _optional_float(trade.get("entry_price")) or 0.0,
                                    _parse_datetime_value(trade.get("exit_date")),
                                    _optional_float(trade.get("exit_price")) or 0.0,
                                    _optional_float(trade.get("quantity")) or 0.0,
                                    _optional_float(trade.get("gross_pnl")) or 0.0,
                                    _optional_float(trade.get("net_pnl")) or 0.0,
                                    _optional_float(trade.get("return_pct")) or 0.0,
                                    _optional_float(trade.get("fee_amount")) or 0.0,
                                    _optional_int(trade.get("holding_bars")) or 0,
                                    _optional_string(trade.get("exit_reason"), max_length=64),
                                    _json_dumps(trade.get("payload") or {}),
                                )
                                for trade in trades
                            ],
                        )

                    if equity_points:
                        await cur.executemany(
                            """
                            INSERT INTO `backtest_equity_points`
                                (`backtest_run_id`, `owner_id`, `point_date`, `equity`, `cash`,
                                 `position_qty`, `close_price`, `payload_json`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    run_id,
                                    owner_id,
                                    _parse_datetime_value(point.get("date")),
                                    _optional_float(point.get("equity")) or 0.0,
                                    _optional_float(point.get("cash")) or 0.0,
                                    _optional_float(point.get("position_qty")) or 0.0,
                                    _optional_float(point.get("close_price")),
                                    _json_dumps(point.get("payload") or {}),
                                )
                                for point in equity_points
                            ],
                        )

        run = await self.get_backtest_run(run_id, owner_id=owner_id)
        if not run:
            raise RuntimeError("Backtest run was not persisted")
        return run

    async def list_backtest_runs(
        self,
        owner_id: int = DEFAULT_OWNER_ID,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        clean_limit = max(1, min(limit, 200))
        filters = ["`owner_id`=%s"]
        params: List[Any] = [owner_id]
        if ticker:
            filters.append("`ticker`=%s")
            params.append(ticker)

        rows = await self._fetchall(
            f"""
            SELECT *
            FROM `backtest_runs`
            WHERE {' AND '.join(filters)}
            ORDER BY `created_at` DESC, `id` DESC
            LIMIT %s
            """,
            tuple(params + [clean_limit]),
        )
        return [_deserialize_backtest_run(row) for row in rows]

    async def get_backtest_run(
        self,
        run_id: int,
        owner_id: int = DEFAULT_OWNER_ID,
    ) -> Optional[Dict[str, Any]]:
        row = await self._fetchone(
            """
            SELECT *
            FROM `backtest_runs`
            WHERE `id`=%s AND `owner_id`=%s
            LIMIT 1
            """,
            (run_id, owner_id),
        )
        run = _deserialize_backtest_run(row)
        if not run:
            return None

        trade_rows = await self._fetchall(
            """
            SELECT *
            FROM `backtest_trades`
            WHERE `backtest_run_id`=%s AND `owner_id`=%s
            ORDER BY `entry_date` ASC, `id` ASC
            """,
            (run_id, owner_id),
        )
        equity_rows = await self._fetchall(
            """
            SELECT *
            FROM `backtest_equity_points`
            WHERE `backtest_run_id`=%s AND `owner_id`=%s
            ORDER BY `point_date` ASC, `id` ASC
            """,
            (run_id, owner_id),
        )
        run["trades"] = [_deserialize_backtest_trade(item) for item in trade_rows]
        run["equity_curve"] = [_deserialize_backtest_equity_point(item) for item in equity_rows]
        return run

