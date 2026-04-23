"""
QuantVision Pro — Paper Trading Bot Runner

即時模擬交易 Bot：
- 註冊為 FubonRealtimePool 的 message handler
- 接收 TX/TMF 的即時 candle（1m）
- 每收到新 K 棒就驅動一次 策略 → 風控 → 模擬成交閉環
- 支援自動在盤前啟動、收盤停止

共用同一套策略引擎/風控/模擬券商/Paper Account，
與 ReplayEngine 的差異僅在資料驅動方式（即時 WS vs 歷史陣列）。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from paper_trading.cost_model import (
    CostModel,
    FuturesProductSpec,
    OrderSide,
    SessionType,
    TMF_SPEC,
    DEFAULT_COST_MODEL,
)
from paper_trading.risk_engine import (
    RiskConfig,
    RiskEngine,
    HoldingPolicy,
    determine_session,
)
from paper_trading.simulation_broker import (
    Bar,
    FillReason,
    SimulationBroker,
)
from paper_trading.paper_account import PaperAccount
from paper_trading.strategy_engine import (
    StrategyConfig,
    StrategyEngine,
    SignalAction,
)

log = logging.getLogger(__name__)


class BotStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class PaperTradingBot:
    """
    即時模擬交易 Bot。

    使用方式：
        bot = PaperTradingBot(bot_id=1, config=...)
        bot.start(fubon_realtime_pool)  # 註冊 handler
        # ... bot 自動接收 WS candle 並執行策略
        bot.stop()                       # 取消註冊
    """

    def __init__(
        self,
        bot_id: int,
        *,
        risk_config: Optional[RiskConfig] = None,
        strategy_config: Optional[StrategyConfig] = None,
        cost_model: Optional[CostModel] = None,
        product: FuturesProductSpec = TMF_SPEC,
        tx_symbol: str = "TXF",
        tmf_symbol: str = "TMF",
        on_trade: Optional[Callable] = None,
        on_signal: Optional[Callable] = None,
        on_equity_update: Optional[Callable] = None,
        on_risk_event: Optional[Callable] = None,
    ):
        self.bot_id = bot_id
        self.risk_config = risk_config or RiskConfig()
        self.strategy_config = strategy_config or StrategyConfig()
        self.cost_model = cost_model or DEFAULT_COST_MODEL
        self.product = product

        # 商品別名 → 用來比對 WS 訊息
        self.tx_symbol = tx_symbol.upper()
        self.tmf_symbol = tmf_symbol.upper()

        # 回調
        self._on_trade = on_trade
        self._on_signal = on_signal
        self._on_equity_update = on_equity_update
        self._on_risk_event = on_risk_event

        # 核心元件
        self.account = PaperAccount(
            starting_equity=self.risk_config.starting_equity,
            cost_model=self.cost_model,
            product=self.product,
            margin_per_contract=self.risk_config.initial_margin_per_contract,
        )
        self.risk = RiskEngine(self.risk_config, self.cost_model, self.product)
        self.broker = SimulationBroker(self.cost_model, self.product)
        self.strategy = StrategyEngine(self.strategy_config)

        # 狀態
        self.status = BotStatus.IDLE
        self._handler_ref = None
        self._current_date: Optional[str] = None
        self._bar_count = 0

        # 統計
        self.started_at: Optional[datetime] = None
        self.stopped_at: Optional[datetime] = None

    def start(self, realtime_pool=None) -> bool:
        """
        啟動 Bot。

        如果提供 realtime_pool，則註冊 message handler 接收即時 candle。
        """
        if self.status == BotStatus.RUNNING:
            return True

        self.status = BotStatus.RUNNING
        self.started_at = datetime.now()
        self._current_date = None
        self._bar_count = 0

        if realtime_pool is not None:
            self._handler_ref = lambda msg: self._on_ws_message(msg)
            realtime_pool.register_message_handler(self._handler_ref)
            log.info(
                "Paper trading bot %s started, listening for %s / %s",
                self.bot_id, self.tx_symbol, self.tmf_symbol,
            )

        return True

    def stop(self, realtime_pool=None) -> None:
        """停止 Bot"""
        self.status = BotStatus.STOPPED
        self.stopped_at = datetime.now()

        if realtime_pool and self._handler_ref:
            realtime_pool.unregister_message_handler(self._handler_ref)
            self._handler_ref = None

        log.info("Paper trading bot %s stopped", self.bot_id)

    def process_candle(self, symbol: str, candle_data: dict) -> None:
        """
        處理一根新的 candle。

        可由 WS handler 或手動呼叫（用於測試）。
        """
        if self.status != BotStatus.RUNNING:
            return

        bar = self._parse_candle(candle_data, symbol)
        if bar is None:
            return

        normalized_symbol = symbol.upper()

        # 判斷是 TX 還是 TMF
        is_tx = any(normalized_symbol.startswith(prefix) for prefix in ("TXF", "TX"))
        is_tmf = any(normalized_symbol.startswith(prefix) for prefix in ("TMF",))

        if is_tx:
            self._process_tx_candle(bar)
        elif is_tmf:
            self._process_tmf_candle(bar)

    def get_state(self) -> dict:
        """取得 Bot 目前狀態"""
        return {
            "bot_id": self.bot_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "bar_count": self._bar_count,
            "account": self.account.to_dict(),
            "pending_orders": len(self.broker.pending_orders),
            "total_fills": len(self.broker.all_fills),
            "direction": self.strategy.current_direction.value,
        }

    # ─── Private ──────────────────────────────────────────────

    def _on_ws_message(self, message: dict) -> None:
        """處理來自 FubonRealtimePool 的 WS 訊息"""
        try:
            event = str(message.get("event") or "").strip().lower()
            if event != "data":
                return

            channel = str(message.get("channel") or "").strip().lower()
            if channel != "candles":
                return

            data = message.get("data")
            if not isinstance(data, dict):
                return

            symbol = str(data.get("symbol") or "").strip().upper()
            if not symbol:
                return

            self.process_candle(symbol, data)

        except Exception as exc:
            log.warning("Paper trading bot %s WS handler error: %s", self.bot_id, exc)

    def _process_tx_candle(self, bar: Bar) -> None:
        """處理 TX candle → 更新方向判斷"""
        self.strategy.update_tx_bar(bar)

    def _process_tmf_candle(self, bar: Bar) -> None:
        """處理 TMF candle → 完整交易閉環"""
        self._bar_count += 1

        # 新的交易日重置
        bar_date = bar.time.strftime("%Y-%m-%d")
        if bar_date != self._current_date:
            self._current_date = bar_date
            self.account.reset_daily()
            self.strategy.reset_session()

        # 判斷時段
        session = determine_session(bar.time)
        if session is None:
            return

        # 1. 用當前 bar 撮合待成交委託
        fills = self.broker.process_bar(bar)
        for fill in fills:
            trade = self.account.on_fill(fill)
            if trade:
                self.strategy.clear_position_info()
                if self._on_trade:
                    try:
                        self._on_trade(self.bot_id, trade.to_dict())
                    except Exception:
                        pass

        # 2. 更新帳戶
        self.account.on_bar(bar.close, bar.time)

        # 3. 收盤前強制平倉
        if self.account.position and self.risk.check_must_flatten(bar.time, session):
            self._force_flatten(bar, session, FillReason.SESSION_CLOSE)
            return

        # 4. 風控強制平倉
        if self.account.position:
            acct_state = self.account.get_account_state()
            if self.risk.check_daily_loss_limit(acct_state) or self.risk.check_drawdown_limit(acct_state):
                self._force_flatten(bar, session, FillReason.RISK_FLATTEN)
                return

        # 5. 策略判斷
        signal = self.strategy.update_tmf_bar(
            bar,
            session,
            has_position=self.account.position is not None,
            position_side=self.account.position.side if self.account.position else None,
            position_entry_price=self.account.position.avg_entry_price if self.account.position else None,
        )

        if signal:
            if self._on_signal:
                try:
                    self._on_signal(self.bot_id, signal.to_dict())
                except Exception:
                    pass

            # 出場
            if signal.action in (SignalAction.CLOSE_LONG, SignalAction.CLOSE_SHORT):
                if self.account.position:
                    close_side = OrderSide.SELL if signal.action == SignalAction.CLOSE_LONG else OrderSide.BUY
                    self.broker.create_market_order(
                        symbol=bar.symbol or self.tmf_symbol,
                        side=close_side,
                        qty=self.account.position.qty,
                        session=session,
                        reason=signal.reason,
                        signal_bar_time=bar.time,
                    )

            # 進場
            elif signal.action in (SignalAction.BUY, SignalAction.SELL):
                acct_state = self.account.get_account_state()
                risk_check = self.risk.check_can_open(acct_state, bar.time)
                if risk_check.allowed:
                    profile = self.strategy_config.get_profile(bar.time, session)
                    stop_distance = profile.stop_loss_points
                    qty = self.risk.calculate_position_size(acct_state, stop_distance, session)
                    qty = min(qty, profile.max_qty)
                    if qty > 0:
                        order_side = OrderSide.BUY if signal.action == SignalAction.BUY else OrderSide.SELL
                        self.broker.create_market_order(
                            symbol=bar.symbol or self.tmf_symbol,
                            side=order_side,
                            qty=qty,
                            session=session,
                            reason=signal.reason,
                            signal_bar_time=bar.time,
                        )
                        self.strategy.set_position_info(
                            signal.entry_price or bar.close,
                            order_side,
                        )
                else:
                    self.risk.record_risk_event("open_denied", {
                        "bar_time": bar.time.isoformat(),
                        "reasons": [r.value for r in risk_check.deny_reasons],
                    })
                    if self._on_risk_event:
                        try:
                            self._on_risk_event(self.bot_id, {
                                "type": "open_denied",
                                "reasons": [r.value for r in risk_check.deny_reasons],
                            })
                        except Exception:
                            pass

        # 6. 權益更新回調
        if self._on_equity_update and self._bar_count % 5 == 0:
            try:
                self._on_equity_update(self.bot_id, self.account.to_dict())
            except Exception:
                pass

    def _force_flatten(self, bar: Bar, session: SessionType, reason: FillReason) -> None:
        """強制平倉"""
        if not self.account.position:
            return

        close_side = OrderSide.SELL if self.account.position.is_long else OrderSide.BUY
        fill = self.broker.force_flatten_fill(
            bar.symbol or self.tmf_symbol,
            close_side,
            self.account.position.qty,
            bar,
            reason=reason,
            session=session,
        )
        trade = self.account.on_fill(fill)
        if trade:
            self.strategy.clear_position_info()
            if self._on_trade:
                try:
                    self._on_trade(self.bot_id, trade.to_dict())
                except Exception:
                    pass

        self.risk.record_risk_event(reason.value, {
            "bar_time": bar.time.isoformat(),
            "session": session.value,
        })

    @staticmethod
    def _parse_candle(data: dict, symbol: str) -> Optional[Bar]:
        """解析 WS candle 或 dict 格式的 K 棒"""
        raw_time = data.get("date") or data.get("time") or ""
        try:
            time_str = str(raw_time).replace("Z", "+00:00").replace(" ", "T")
            dt = datetime.fromisoformat(time_str)
        except (ValueError, TypeError):
            return None

        try:
            return Bar(
                time=dt,
                open=float(data.get("open", 0)),
                high=float(data.get("high", 0)),
                low=float(data.get("low", 0)),
                close=float(data.get("close", 0)),
                volume=int(data.get("volume", 0)),
                symbol=symbol.upper(),
            )
        except (TypeError, ValueError):
            return None
