"""
QuantVision Pro — Paper Trading Repository Mixin

資料庫 CRUD 方法，對應 paper_trading_* 資料表。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class PaperTradingMixin:
    """Paper Trading 資料庫操作 mixin，混入 Database 類別"""

    # ─── Accounts ─────────────────────────────────────────────

    async def create_paper_trading_account(self, data: dict, owner_id: int = 1) -> dict:
        sql = """
            INSERT INTO `paper_trading_accounts`
            (`owner_id`, `name`, `product_symbol`, `starting_equity`,
             `initial_margin_per_contract`, `risk_config_json`,
             `cost_model_json`, `strategy_config_json`, `is_active`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        row_id = await self._execute_insert(sql, (
            owner_id,
            data.get("name", "Default Account"),
            data.get("product_symbol", "TMF"),
            data.get("starting_equity", 100000),
            data.get("initial_margin_per_contract", 26300),
            json.dumps(data.get("risk_config", {}), ensure_ascii=False),
            json.dumps(data.get("cost_model", {}), ensure_ascii=False),
            json.dumps(data.get("strategy_config", {}), ensure_ascii=False) if data.get("strategy_config") else None,
            1,
        ))
        return await self.get_paper_trading_account(row_id, owner_id)

    async def get_paper_trading_account(self, account_id: int, owner_id: int = 1) -> Optional[dict]:
        row = await self._fetchone(
            "SELECT * FROM `paper_trading_accounts` WHERE `id`=%s AND `owner_id`=%s",
            (account_id, owner_id),
        )
        return self._decode_paper_trading_account(row) if row else None

    async def list_paper_trading_accounts(self, owner_id: int = 1) -> List[dict]:
        rows = await self._fetchall(
            "SELECT * FROM `paper_trading_accounts` WHERE `owner_id`=%s ORDER BY `id` DESC",
            (owner_id,),
        )
        return [self._decode_paper_trading_account(r) for r in rows]

    async def delete_paper_trading_account(self, account_id: int, owner_id: int = 1) -> bool:
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT `id` FROM `paper_trading_accounts` WHERE `id`=%s AND `owner_id`=%s",
                        (account_id, owner_id),
                    )
                    if not await cur.fetchone():
                        return False

                    for table in (
                        "paper_trading_positions",
                        "paper_trading_orders",
                        "paper_trading_fills",
                        "paper_trading_equity_snapshots",
                        "paper_trading_risk_events",
                        "paper_trading_replay_runs",
                        "paper_trading_bots",
                    ):
                        await cur.execute(
                            f"DELETE FROM `{table}` WHERE `account_id`=%s AND `owner_id`=%s",
                            (account_id, owner_id),
                        )

                    await cur.execute(
                        "DELETE FROM `paper_trading_accounts` WHERE `id`=%s AND `owner_id`=%s",
                        (account_id, owner_id),
                    )
                    return cur.rowcount > 0

    @staticmethod
    def _decode_paper_trading_account(row: dict) -> dict:
        result = dict(row)
        for key in ("risk_config_json", "cost_model_json", "strategy_config_json"):
            raw = result.pop(key, None)
            decoded_key = key.replace("_json", "")
            if raw and isinstance(raw, str):
                try:
                    result[decoded_key] = json.loads(raw)
                except json.JSONDecodeError:
                    result[decoded_key] = {}
            else:
                result[decoded_key] = raw or {}
        return result

    # ─── Bots ─────────────────────────────────────────────────

    async def create_paper_trading_bot(self, data: dict, owner_id: int = 1) -> dict:
        sql = """
            INSERT INTO `paper_trading_bots`
            (`owner_id`, `account_id`, `name`, `mode`, `product_symbol`,
             `direction_symbol`, `session_mode`, `holding_policy`,
             `status`, `strategy_config_json`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        row_id = await self._execute_insert(sql, (
            owner_id,
            data["account_id"],
            data.get("name", "Untitled Bot"),
            data.get("mode", "realtime"),
            data.get("product_symbol", "TMF"),
            data.get("direction_symbol", "TXF"),
            data.get("session_mode", "day_session_only"),
            data.get("holding_policy", "day_only"),
            "idle",
            json.dumps(data.get("strategy_config", {}), ensure_ascii=False) if data.get("strategy_config") else None,
        ))
        return await self.get_paper_trading_bot(row_id, owner_id)

    async def get_paper_trading_bot(self, bot_id: int, owner_id: int = 1) -> Optional[dict]:
        row = await self._fetchone(
            "SELECT * FROM `paper_trading_bots` WHERE `id`=%s AND `owner_id`=%s",
            (bot_id, owner_id),
        )
        return self._decode_paper_trading_bot(row) if row else None

    async def list_paper_trading_bots(self, owner_id: int = 1, account_id: Optional[int] = None) -> List[dict]:
        if account_id:
            rows = await self._fetchall(
                "SELECT * FROM `paper_trading_bots` WHERE `owner_id`=%s AND `account_id`=%s ORDER BY `id` DESC",
                (owner_id, account_id),
            )
        else:
            rows = await self._fetchall(
                "SELECT * FROM `paper_trading_bots` WHERE `owner_id`=%s ORDER BY `id` DESC",
                (owner_id,),
            )
        return [self._decode_paper_trading_bot(r) for r in rows]

    async def update_paper_trading_bot(self, bot_id: int, data: dict, owner_id: int = 1) -> Optional[dict]:
        updates = []
        params = []
        for col in ("name", "mode", "status", "session_mode", "holding_policy",
                     "error_message", "bar_count"):
            if col in data:
                updates.append(f"`{col}`=%s")
                params.append(data[col])
        for col in ("started_at", "stopped_at", "last_signal_at"):
            if col in data:
                updates.append(f"`{col}`=%s")
                params.append(data[col])
        if "strategy_config" in data:
            updates.append("`strategy_config_json`=%s")
            params.append(json.dumps(data["strategy_config"], ensure_ascii=False) if data["strategy_config"] else None)
        if not updates:
            return await self.get_paper_trading_bot(bot_id, owner_id)
        sql = f"UPDATE `paper_trading_bots` SET {', '.join(updates)} WHERE `id`=%s AND `owner_id`=%s"
        params.extend([bot_id, owner_id])
        await self._execute(sql, tuple(params))
        return await self.get_paper_trading_bot(bot_id, owner_id)

    async def delete_paper_trading_bot(self, bot_id: int, owner_id: int = 1) -> bool:
        async with self._lock:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    for table in (
                        "paper_trading_positions",
                        "paper_trading_orders",
                        "paper_trading_fills",
                        "paper_trading_equity_snapshots",
                        "paper_trading_risk_events",
                        "paper_trading_replay_runs",
                    ):
                        await cur.execute(
                            f"DELETE FROM `{table}` WHERE `bot_id`=%s AND `owner_id`=%s",
                            (bot_id, owner_id),
                        )

                    await cur.execute(
                        "DELETE FROM `paper_trading_bots` WHERE `id`=%s AND `owner_id`=%s",
                        (bot_id, owner_id),
                    )
                    return cur.rowcount > 0

    @staticmethod
    def _decode_paper_trading_bot(row: dict) -> dict:
        result = dict(row)
        raw = result.pop("strategy_config_json", None)
        if raw and isinstance(raw, str):
            try:
                result["strategy_config"] = json.loads(raw)
            except json.JSONDecodeError:
                result["strategy_config"] = {}
        else:
            result["strategy_config"] = raw or {}
        return result

    # ─── Replay Runs ──────────────────────────────────────────

    async def save_paper_trading_replay_run(self, data: dict, owner_id: int = 1) -> dict:
        sql = """
            INSERT INTO `paper_trading_replay_runs`
            (`owner_id`, `account_id`, `bot_id`, `product_symbol`, `direction_symbol`,
             `start_date`, `end_date`, `bar_count`, `trade_count`,
             `starting_equity`, `final_equity`, `total_return_pct`,
             `max_drawdown_pct`, `win_rate_pct`, `profit_factor`,
             `total_pnl`, `total_fees`,
             `risk_config_json`, `strategy_config_json`, `cost_model_json`, `summary_json`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        summary = data.get("summary", {})
        row_id = await self._execute_insert(sql, (
            owner_id,
            data.get("account_id"),
            data.get("bot_id"),
            data.get("product_symbol", "TMF"),
            data.get("direction_symbol", "TXF"),
            data["start_date"],
            data["end_date"],
            data.get("bar_count", 0),
            summary.get("trade_count", 0),
            data.get("starting_equity", 100000),
            summary.get("total_pnl", 0) + data.get("starting_equity", 100000),
            summary.get("total_return_pct", 0),
            summary.get("max_drawdown_pct", 0),
            summary.get("win_rate", 0),
            summary.get("profit_factor", 0),
            summary.get("total_pnl", 0),
            data.get("total_fees", 0),
            json.dumps(data.get("risk_config", {}), ensure_ascii=False),
            json.dumps(data.get("strategy_config", {}), ensure_ascii=False),
            json.dumps(data.get("cost_model", {}), ensure_ascii=False),
            json.dumps(summary, ensure_ascii=False),
        ))
        return await self.get_paper_trading_replay_run(row_id, owner_id)

    async def get_paper_trading_replay_run(self, run_id: int, owner_id: int = 1) -> Optional[dict]:
        row = await self._fetchone(
            "SELECT * FROM `paper_trading_replay_runs` WHERE `id`=%s AND `owner_id`=%s",
            (run_id, owner_id),
        )
        return self._decode_replay_run(row) if row else None

    async def list_paper_trading_replay_runs(self, owner_id: int = 1, limit: int = 50) -> List[dict]:
        rows = await self._fetchall(
            "SELECT * FROM `paper_trading_replay_runs` WHERE `owner_id`=%s ORDER BY `id` DESC LIMIT %s",
            (owner_id, limit),
        )
        return [self._decode_replay_run(r) for r in rows]

    @staticmethod
    def _decode_replay_run(row: dict) -> dict:
        result = dict(row)
        for key in ("risk_config_json", "strategy_config_json", "cost_model_json", "summary_json"):
            raw = result.pop(key, None)
            decoded_key = key.replace("_json", "")
            if raw and isinstance(raw, str):
                try:
                    result[decoded_key] = json.loads(raw)
                except json.JSONDecodeError:
                    result[decoded_key] = {}
            else:
                result[decoded_key] = raw or {}
        return result

    # ─── Fills ────────────────────────────────────────────────

    async def save_paper_trading_fills(
        self,
        fills: List[dict],
        account_id: int,
        owner_id: int = 1,
        bot_id: Optional[int] = None,
    ) -> int:
        if not fills:
            return 0
        sql = """
            INSERT INTO `paper_trading_fills`
            (`owner_id`, `account_id`, `bot_id`, `order_id`, `fill_id`,
             `symbol`, `side`, `fill_qty`, `fill_price`,
             `slippage_ticks`, `fee_amount`, `fill_reason`,
             `session`, `bar_open`, `bar_high`, `bar_low`, `bar_close`, `fill_time`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        count = 0
        for f in fills:
            await self._execute_insert(sql, (
                owner_id, account_id, bot_id,
                f.get("order_id"), f.get("fill_id"),
                f.get("symbol", ""), f.get("side", ""),
                f.get("fill_qty", 0), f.get("fill_price", 0),
                f.get("slippage_ticks", 0), f.get("fee_amount", 0),
                f.get("fill_reason", ""), f.get("session", "day"),
                f.get("bar_open"), f.get("bar_high"), f.get("bar_low"), f.get("bar_close"),
                f.get("fill_time"),
            ))
            count += 1
        return count

    async def list_paper_trading_fills(
        self,
        account_id: int,
        owner_id: int = 1,
        bot_id: Optional[int] = None,
        limit: int = 200,
    ) -> List[dict]:
        if bot_id:
            return await self._fetchall(
                """SELECT * FROM `paper_trading_fills`
                   WHERE `account_id`=%s AND `owner_id`=%s AND `bot_id`=%s
                   ORDER BY `id` DESC LIMIT %s""",
                (account_id, owner_id, bot_id, limit),
            )
        return await self._fetchall(
            """SELECT * FROM `paper_trading_fills`
               WHERE `account_id`=%s AND `owner_id`=%s
               ORDER BY `id` DESC LIMIT %s""",
            (account_id, owner_id, limit),
        )

    # ─── Equity Snapshots ─────────────────────────────────────

    async def save_paper_trading_equity_snapshots(
        self,
        snapshots: List[dict],
        account_id: int,
        owner_id: int = 1,
        bot_id: Optional[int] = None,
        replay_run_id: Optional[int] = None,
    ) -> int:
        if not snapshots:
            return 0
        sql = """
            INSERT INTO `paper_trading_equity_snapshots`
            (`owner_id`, `account_id`, `bot_id`, `replay_run_id`,
             `snapshot_time`, `equity`, `cash`, `margin_used`,
             `unrealized_pnl`, `realized_pnl`, `position_qty`,
             `position_side`, `close_price`, `drawdown_pct`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        count = 0
        for s in snapshots:
            await self._execute_insert(sql, (
                owner_id, account_id, bot_id, replay_run_id,
                s.get("timestamp"), s.get("equity", 0), s.get("cash", 0),
                s.get("margin_used", 0), s.get("unrealized_pnl", 0),
                s.get("realized_pnl", 0), s.get("position_qty", 0),
                s.get("position_side"), s.get("close_price"),
                s.get("drawdown_pct", 0),
            ))
            count += 1
        return count

    async def list_paper_trading_equity_snapshots(
        self,
        account_id: int,
        owner_id: int = 1,
        replay_run_id: Optional[int] = None,
        limit: int = 500,
    ) -> List[dict]:
        if replay_run_id:
            return await self._fetchall(
                """SELECT * FROM `paper_trading_equity_snapshots`
                   WHERE `replay_run_id`=%s AND `owner_id`=%s
                   ORDER BY `snapshot_time` ASC LIMIT %s""",
                (replay_run_id, owner_id, limit),
            )
        return await self._fetchall(
            """SELECT * FROM `paper_trading_equity_snapshots`
               WHERE `account_id`=%s AND `owner_id`=%s
               ORDER BY `snapshot_time` DESC LIMIT %s""",
            (account_id, owner_id, limit),
        )

    # ─── Risk Events ─────────────────────────────────────────

    async def save_paper_trading_risk_events(
        self,
        events: List[dict],
        account_id: int,
        owner_id: int = 1,
        bot_id: Optional[int] = None,
        replay_run_id: Optional[int] = None,
    ) -> int:
        if not events:
            return 0
        sql = """
            INSERT INTO `paper_trading_risk_events`
            (`owner_id`, `account_id`, `bot_id`, `replay_run_id`,
             `event_type`, `details_json`, `event_time`)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        count = 0
        for e in events:
            details = e.get("details", {})
            await self._execute_insert(sql, (
                owner_id, account_id, bot_id, replay_run_id,
                e.get("event_type", "unknown"),
                json.dumps(details, ensure_ascii=False) if details else None,
                e.get("timestamp") or details.get("bar_time"),
            ))
            count += 1
        return count

    async def list_paper_trading_risk_events(
        self,
        account_id: int,
        owner_id: int = 1,
        limit: int = 100,
    ) -> List[dict]:
        rows = await self._fetchall(
            """SELECT * FROM `paper_trading_risk_events`
               WHERE `account_id`=%s AND `owner_id`=%s
               ORDER BY `id` DESC LIMIT %s""",
            (account_id, owner_id, limit),
        )
        for row in rows:
            raw = row.get("details_json")
            if raw and isinstance(raw, str):
                try:
                    row["details"] = json.loads(raw)
                except json.JSONDecodeError:
                    row["details"] = {}
            else:
                row["details"] = {}
        return rows

    # ─── Orders ───────────────────────────────────────────────

    async def save_paper_trading_orders(
        self,
        orders: List[dict],
        account_id: int,
        owner_id: int = 1,
        bot_id: Optional[int] = None,
    ) -> int:
        if not orders:
            return 0
        sql = """
            INSERT INTO `paper_trading_orders`
            (`owner_id`, `account_id`, `bot_id`, `order_id`,
             `symbol`, `requested_symbol`, `resolved_symbol`,
             `side`, `qty`, `order_type`, `price`, `stop_price`,
             `session`, `status`, `reason`, `signal_bar_time`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        count = 0
        for o in orders:
            await self._execute_insert(sql, (
                owner_id, account_id, bot_id,
                o.get("order_id", ""),
                o.get("symbol", ""), o.get("requested_symbol"), o.get("resolved_symbol"),
                o.get("side", ""), o.get("qty", 0),
                o.get("order_type", "market"),
                o.get("price"), o.get("stop_price"),
                o.get("session", "day"), o.get("status", "filled"),
                o.get("reason"), o.get("signal_bar_time"),
            ))
            count += 1
        return count

    async def list_paper_trading_orders(
        self,
        account_id: int,
        owner_id: int = 1,
        limit: int = 200,
    ) -> List[dict]:
        return await self._fetchall(
            """SELECT * FROM `paper_trading_orders`
               WHERE `account_id`=%s AND `owner_id`=%s
               ORDER BY `id` DESC LIMIT %s""",
            (account_id, owner_id, limit),
        )

    # ─── Positions ────────────────────────────────────────────

    async def save_paper_trading_position(
        self,
        data: dict,
        account_id: int,
        owner_id: int = 1,
        bot_id: Optional[int] = None,
    ) -> int:
        # Upsert: delete old position then insert
        await self._execute(
            "DELETE FROM `paper_trading_positions` WHERE `account_id`=%s AND `owner_id`=%s AND `symbol`=%s",
            (account_id, owner_id, data.get("symbol", "")),
        )
        if data.get("qty", 0) == 0:
            return 0
        sql = """
            INSERT INTO `paper_trading_positions`
            (`owner_id`, `account_id`, `bot_id`, `symbol`,
             `requested_symbol`, `resolved_symbol`,
             `side`, `qty`, `avg_entry_price`,
             `unrealized_pnl`, `realized_pnl`, `last_price`, `entry_time`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        return await self._execute_insert(sql, (
            owner_id, account_id, bot_id,
            data.get("symbol", ""), data.get("requested_symbol"), data.get("resolved_symbol"),
            data.get("side", ""), data.get("qty", 0), data.get("avg_entry_price", 0),
            data.get("unrealized_pnl", 0), data.get("realized_pnl", 0),
            data.get("last_price"), data.get("entry_time"),
        ))

    async def get_paper_trading_positions(
        self,
        account_id: int,
        owner_id: int = 1,
    ) -> List[dict]:
        return await self._fetchall(
            """SELECT * FROM `paper_trading_positions`
               WHERE `account_id`=%s AND `owner_id`=%s
               ORDER BY `id`""",
            (account_id, owner_id),
        )

    # ─── Contract Resolutions ────────────────────────────────

    async def save_paper_trading_contract_resolution(self, data: dict) -> int:
        sql = """
            INSERT INTO `paper_trading_contract_resolutions`
            (`requested_symbol`, `resolved_symbol`, `resolution_date`,
             `contract_type`, `end_date`, `instrument_type`, `source`)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            AS `incoming`
            ON DUPLICATE KEY UPDATE
                `resolved_symbol`=`incoming`.`resolved_symbol`,
                `contract_type`=`incoming`.`contract_type`,
                `end_date`=`incoming`.`end_date`,
                `instrument_type`=`incoming`.`instrument_type`,
                `source`=`incoming`.`source`
        """
        return await self._execute_insert(sql, (
            data.get("requested_symbol", ""),
            data.get("resolved_symbol", ""),
            data.get("resolution_date"),
            data.get("contract_type"),
            data.get("end_date"),
            data.get("instrument_type", "future"),
            data.get("source", "fubon_neo"),
        ))
