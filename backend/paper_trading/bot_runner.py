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
from datetime import datetime, timezone
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
        if self.strategy_config.strategy_type == "v2":
            from paper_trading.strategy_v2 import StrategyEngineV2
            self.strategy = StrategyEngineV2(self.strategy_config)
        else:
            self.strategy = StrategyEngine(self.strategy_config)

        # 狀態
        self.status = BotStatus.IDLE
        self._handler_ref = None
        self._current_date: Optional[str] = None
        self._bar_count = 0
        self._tick_aggregator: dict[str, dict] = {}
        self._last_processed_minute: dict[str, str] = {}

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
            
            # 讓 realtime_pool 知道我們需要這兩檔商品的報價
            source_id = f"paper_bot_{self.bot_id}"
            realtime_pool.track_ticker(self.tx_symbol, source=source_id)
            realtime_pool.track_ticker(self.tmf_symbol, source=source_id)
            
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
            
            # 解除追蹤
            source_id = f"paper_bot_{self.bot_id}"
            realtime_pool.untrack_ticker(self.tx_symbol, source=source_id)
            realtime_pool.untrack_ticker(self.tmf_symbol, source=source_id)

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
            # TMF 虛擬商品（或微台指）若無獨立 WS 報價，可直接以 TXF 報價做為 TMF 價格
            if self.tmf_symbol.upper() == "TMF":
                from paper_trading.simulation_broker import Bar
                tmf_bar = Bar(
                    time=bar.time,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    symbol="TMF",
                )
                self._process_tmf_candle(tmf_bar)
        elif is_tmf:
            self._process_tmf_candle(bar)

    def get_state(self) -> dict:
        """取得 Bot 目前狀態"""
        # 最近 50 筆成交
        recent_fills = []
        for f in self.broker.all_fills[-50:]:
            try:
                recent_fills.append(f.to_dict())
            except Exception:
                pass

        # 已完成的交易紀錄
        trades = []
        for t in self.account.trades[-50:]:
            try:
                trades.append(t.to_dict())
            except Exception:
                pass

        # 風控事件
        risk_events = self.risk.get_risk_events()[-20:]

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
            "recent_fills": recent_fills,
            "trades": trades,
            "risk_events": risk_events,
        }

    # ─── Private ──────────────────────────────────────────────

    def _on_ws_message(self, message: dict) -> None:
        """處理來自 FubonRealtimePool 的 WS 訊息"""
        try:
            event = str(message.get("event") or "").strip().lower()
            if event != "data":
                return

            channel = str(message.get("channel") or "").strip().lower()
            
            data = message.get("data")
            if not isinstance(data, dict):
                return

            symbol = str(data.get("symbol") or "").strip().upper()
            if not symbol:
                return

            if "open" in data and "close" in data:
                # 判斷是否為 K 棒資料: Fubon WS aggregates/candles
                self.process_candle(symbol, data)
            elif channel == "trades" and "price" in data:
                # Fubon WS Mode = Speed 時，僅推播 trades。需在此自行合成 1m K棒。
                price = float(data["price"])
                volume = float(data.get("volume", 0))
                time_val = data.get("time")
                if not time_val:
                    return
                # time_val 為 microseconds
                trade_dt = datetime.fromtimestamp(time_val / 1000000.0, tz=timezone.utc)
                trade_minute = trade_dt.strftime("%Y-%m-%d %H:%M")

                agg = self._tick_aggregator.get(symbol)
                if agg and agg["minute"] != trade_minute:
                    # 分鐘切換，送出上一分鐘的合成 K 棒
                    candle_payload = {
                        "date": agg["minute"] + ":00+00:00",
                        "open": agg["open"],
                        "high": agg["high"],
                        "low": agg["low"],
                        "close": agg["close"],
                        "volume": agg["volume"],
                    }
                    self.process_candle(symbol, candle_payload)
                    agg = None

                if not agg:
                    agg = {
                        "minute": trade_minute,
                        "open": price,
                        "high": price,
                        "low": price,
                        "close": price,
                        "volume": volume,
                    }
                else:
                    agg["high"] = max(agg["high"], price)
                    agg["low"] = min(agg["low"], price)
                    agg["close"] = price
                    agg["volume"] += volume

                self._tick_aggregator[symbol] = agg

                # 同時我們也將「當前未完成的 K 棒」送出，讓策略能即時反應（Strategy 支援 partial bar 更新）
                candle_payload = {
                    "date": trade_minute + ":00+00:00",
                    "open": agg["open"],
                    "high": agg["high"],
                    "low": agg["low"],
                    "close": agg["close"],
                    "volume": agg["volume"],
                }
                self.process_candle(symbol, candle_payload)

        except Exception as exc:
            log.warning("Paper trading bot %s WS handler error: %s", self.bot_id, exc)

    def _process_tx_candle(self, bar: Bar) -> None:
        """處理 TX candle → 更新方向判斷"""
        self.strategy.update_tx_bar(bar)

    def _process_tmf_candle(self, bar: Bar) -> None:
        """處理 TMF candle → 完整交易閉環"""
        bar_minute = bar.time.strftime("%Y-%m-%d %H:%M")

        # 防止同一分鐘內收到多次更新導致 bar_count 狂飆
        if self._last_processed_minute.get(bar.symbol or self.tmf_symbol) != bar_minute:
            self._bar_count += 1
            self._last_processed_minute[bar.symbol or self.tmf_symbol] = bar_minute

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
            if self.account.position and self.account.position.side == fill.side:
                self.strategy.set_position_info(fill.fill_price, fill.side)
            if trade:
                if self.account.position:
                    reducer = getattr(self.strategy, "on_position_reduced", None)
                    if callable(reducer):
                        reducer()
                else:
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
            position_qty=self.account.position.qty if self.account.position else 0,
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
                    close_qty = self.account.position.qty
                    if self.strategy_config.strategy_type == "v2":
                        close_qty = min(self.account.position.qty, max(1, int(signal.qty or 1)))
                    self.broker.create_market_order(
                        symbol=bar.symbol or self.tmf_symbol,
                        side=close_side,
                        qty=close_qty,
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
                    if self.strategy_config.strategy_type == "v2":
                        current_atr = max(1.0, float(getattr(self.strategy, "current_atr", 0.0) or 1.0))
                        stop_distance = current_atr * 1.5
                        remaining_profile_qty = max(0, profile.max_qty - abs(acct_state.open_position_qty))
                        requested_qty = max(1, int(signal.qty or 1))
                        size_check = self.risk.check_order_size(
                            acct_state,
                            requested_qty,
                            stop_distance,
                            session,
                        )
                        qty = requested_qty if size_check.allowed and requested_qty <= remaining_profile_qty else 0
                        if qty <= 0:
                            details = {
                                "bar_time": bar.time.isoformat(),
                                "signal": signal.reason,
                                "requested_qty": requested_qty,
                                "profile_allowed_qty": remaining_profile_qty,
                                **size_check.details,
                            }
                            self.risk.record_risk_event("order_size_denied", details)
                            if self._on_risk_event:
                                try:
                                    self._on_risk_event(self.bot_id, {
                                        "type": "order_size_denied",
                                        "details": details,
                                    })
                                except Exception:
                                    pass
                    else:
                        stop_distance = profile.stop_loss_points
                        sizing = self.risk.calculate_position_sizing(acct_state, stop_distance, session)
                        remaining_profile_qty = max(0, profile.max_qty - abs(acct_state.open_position_qty))
                        qty = min(sizing.addable_contracts, remaining_profile_qty)
                        if qty <= 0:
                            details = {
                                "bar_time": bar.time.isoformat(),
                                "signal": signal.reason,
                                "requested_qty": qty,
                                "profile_allowed_qty": remaining_profile_qty,
                                "allowed_qty": sizing.addable_contracts,
                                "sizing": sizing.to_dict(),
                            }
                            self.risk.record_risk_event("order_size_denied", details)
                            if self._on_risk_event:
                                try:
                                    self._on_risk_event(self.bot_id, {
                                        "type": "order_size_denied",
                                        "details": details,
                                    })
                                except Exception:
                                    pass
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
            if self.account.position:
                reducer = getattr(self.strategy, "on_position_reduced", None)
                if callable(reducer):
                    reducer()
            else:
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
            # 確保時區轉換為台北時間，避免影響 determine_session 時段判斷
            import zoneinfo
            if dt.tzinfo is not None:
                dt = dt.astimezone(zoneinfo.ZoneInfo("Asia/Taipei"))
            else:
                dt = dt.replace(tzinfo=zoneinfo.ZoneInfo("Asia/Taipei"))
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
