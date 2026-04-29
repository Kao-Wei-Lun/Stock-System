"""
QuantVision Pro — Paper Trading Replay Engine

歷史 K 棒回放引擎：
- 逐 bar 迭代 TMF 1m（同步 TX 1m 做方向判斷）
- 策略產生訊號 → 風控檢查 → 模擬委託 → 下一根 bar 撮合
- 收盤前強制平倉（day_only 模式）
- 產出完整回放結果（trades, equity_curve, signals, risk_events, fills, summary）
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

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
    trading_session_key,
)
from paper_trading.simulation_broker import (
    Bar,
    Fill,
    FillReason,
    SimulationBroker,
)
from paper_trading.paper_account import PaperAccount, TradeRecord
from paper_trading.strategy_engine import (
    INDICATOR_STRATEGY_TYPES,
    StrategyConfig,
    StrategyEngine,
    Signal,
    SignalAction,
)

log = logging.getLogger(__name__)


# ─── 回放結果 ─────────────────────────────────────────────────

class ReplayResult:
    """回放結果"""

    def __init__(self):
        self.trades: list[dict] = []
        self.equity_curve: list[dict] = []
        self.signals: list[dict] = []
        self.risk_events: list[dict] = []
        self.fills: list[dict] = []
        self.summary: dict = {}
        self.account_final: dict = {}
        self.bar_count: int = 0
        self.error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "trades": self.trades,
            "equity_curve": self.equity_curve,
            "signals": self.signals,
            "risk_events": self.risk_events,
            "fills": self.fills,
            "summary": self.summary,
            "account_final": self.account_final,
            "bar_count": self.bar_count,
            "error": self.error,
        }


# ─── 回放引擎 ─────────────────────────────────────────────────

class ReplayEngine:
    """
    歷史 K 棒回放引擎。

    使用方式：
        engine = ReplayEngine(config)
        result = engine.run(tx_bars, tmf_bars)
    """

    def __init__(
        self,
        risk_config: Optional[RiskConfig] = None,
        strategy_config: Optional[StrategyConfig] = None,
        cost_model: Optional[CostModel] = None,
        product: FuturesProductSpec = TMF_SPEC,
    ):
        self.risk_config = risk_config or RiskConfig()
        self.strategy_config = strategy_config or StrategyConfig()
        self.cost_model = cost_model or DEFAULT_COST_MODEL
        self.product = product

    def run(
        self,
        tx_bars: list[dict],
        tmf_bars: list[dict],
        *,
        equity_snapshot_interval: int = 5,
    ) -> ReplayResult:
        """
        執行回放。

        Args:
            tx_bars: TX 1m K 棒 [{"time": ..., "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...}]
            tmf_bars: TMF 1m K 棒
            equity_snapshot_interval: 每 N 根 bar 取一次權益快照

        Returns:
            ReplayResult
        """
        result = ReplayResult()

        if not tmf_bars:
            result.error = "No TMF bar data provided"
            return result

        # 初始化元件
        account = PaperAccount(
            starting_equity=self.risk_config.starting_equity,
            cost_model=self.cost_model,
            product=self.product,
            margin_per_contract=self.risk_config.initial_margin_per_contract,
        )
        risk = RiskEngine(self.risk_config, self.cost_model, self.product)
        broker = SimulationBroker(self.cost_model, self.product)
        if self.strategy_config.strategy_type == "v2":
            from paper_trading.strategy_v2 import StrategyEngineV2
            strategy = StrategyEngineV2(self.strategy_config)
        elif self.strategy_config.strategy_type in INDICATOR_STRATEGY_TYPES:
            from paper_trading.indicator_combo_strategy import IndicatorComboStrategyEngine
            strategy = IndicatorComboStrategyEngine(self.strategy_config)
        else:
            strategy = StrategyEngine(self.strategy_config)

        # 建立 TX bar 索引（用時間戳對齊）
        tx_bar_map = self._build_bar_map(tx_bars)

        # 追蹤日曆日與期貨交易時段。夜盤跨午夜時仍屬於同一個策略 session。
        current_date: Optional[str] = None
        current_session_key: Optional[str] = None
        bar_count = 0

        for raw_bar in tmf_bars:
            tmf_bar = self._parse_bar(raw_bar, "TMF")
            if tmf_bar is None:
                continue

            # 判斷時段
            session = determine_session(tmf_bar.time)
            if session is None:
                continue

            bar_count += 1

            # 新的日曆日只重置帳戶單日統計，不重置策略狀態。
            bar_date = tmf_bar.time.strftime("%Y-%m-%d")
            if bar_date != current_date:
                current_date = bar_date
                account.reset_daily()

            session_key = trading_session_key(tmf_bar.time, session)
            if session_key != current_session_key:
                current_session_key = session_key
                strategy.reset_session()

            # 同步 TX bar
            tx_key = tmf_bar.time.strftime("%Y-%m-%d %H:%M")
            tx_raw = tx_bar_map.get(tx_key)
            if tx_raw:
                tx_bar = self._parse_bar(tx_raw, "TXF")
                if tx_bar:
                    strategy.update_tx_bar(tx_bar)

            # 1. 用當前 bar 撮合待成交委託
            fills = broker.process_bar(tmf_bar)
            for fill in fills:
                trade = account.on_fill(fill)
                result.fills.append(fill.to_dict())
                if account.position and account.position.side == fill.side:
                    strategy.set_position_info(fill.fill_price, fill.side)
                if trade:
                    result.trades.append(trade.to_dict())
                    if account.position:
                        reducer = getattr(strategy, "on_position_reduced", None)
                        if callable(reducer):
                            reducer()
                    else:
                        strategy.clear_position_info()

            # 2. 更新帳戶未實現損益
            account.on_bar(tmf_bar.close, tmf_bar.time)

            # 3. 檢查是否需要強制平倉（收盤前 / 風控）
            if account.position and risk.check_must_flatten(tmf_bar.time, session):
                close_side = OrderSide.SELL if account.position.is_long else OrderSide.BUY
                fill = broker.force_flatten_fill(
                    tmf_bar.symbol or "TMF",
                    close_side,
                    account.position.qty,
                    tmf_bar,
                    reason=FillReason.SESSION_CLOSE,
                    session=session,
                )
                trade = account.on_fill(fill)
                result.fills.append(fill.to_dict())
                if trade:
                    result.trades.append(trade.to_dict())
                if account.position:
                    reducer = getattr(strategy, "on_position_reduced", None)
                    if callable(reducer):
                        reducer()
                else:
                    strategy.clear_position_info()
                risk.record_risk_event("session_close_flatten", {
                    "bar_time": tmf_bar.time.isoformat(),
                    "session": session.value,
                })
                continue  # 已平倉，跳過策略判斷

            # 4. 檢查單日虧損 / 回撤限制 → 強制平倉
            if account.position:
                acct_state = account.get_account_state()
                if risk.check_daily_loss_limit(acct_state) or risk.check_drawdown_limit(acct_state):
                    close_side = OrderSide.SELL if account.position.is_long else OrderSide.BUY
                    fill = broker.force_flatten_fill(
                        tmf_bar.symbol or "TMF",
                        close_side,
                        account.position.qty,
                        tmf_bar,
                        reason=FillReason.RISK_FLATTEN,
                        session=session,
                    )
                    trade = account.on_fill(fill)
                    result.fills.append(fill.to_dict())
                    if trade:
                        result.trades.append(trade.to_dict())
                    if account.position:
                        reducer = getattr(strategy, "on_position_reduced", None)
                        if callable(reducer):
                            reducer()
                    else:
                        strategy.clear_position_info()
                    event_type = "daily_loss_limit" if risk.check_daily_loss_limit(acct_state) else "max_drawdown"
                    risk.record_risk_event(event_type, {
                        "bar_time": tmf_bar.time.isoformat(),
                        "equity": acct_state.equity,
                    })
                    continue

            # 5. 策略判斷
            signal = strategy.update_tmf_bar(
                tmf_bar,
                session,
                has_position=account.position is not None,
                position_side=account.position.side if account.position else None,
                position_entry_price=account.position.avg_entry_price if account.position else None,
                position_qty=account.position.qty if account.position else 0,
            )

            if signal:
                result.signals.append(signal.to_dict())

                # 停損/停利出場
                if signal.action in (SignalAction.CLOSE_LONG, SignalAction.CLOSE_SHORT):
                    if account.position:
                        close_side = OrderSide.SELL if signal.action == SignalAction.CLOSE_LONG else OrderSide.BUY
                        close_qty = account.position.qty
                        if self.strategy_config.strategy_type == "v2":
                            close_qty = min(account.position.qty, max(1, int(signal.qty or 1)))
                        broker.create_market_order(
                            symbol=tmf_bar.symbol or "TMF",
                            side=close_side,
                            qty=close_qty,
                            session=session,
                            reason=signal.reason,
                            signal_bar_time=tmf_bar.time,
                        )

                # 進場
                elif signal.action in (SignalAction.BUY, SignalAction.SELL):
                    acct_state = account.get_account_state()
                    risk_check = risk.check_can_open(acct_state, tmf_bar.time)
                    if risk_check.allowed:
                        profile = self.strategy_config.get_profile(tmf_bar.time, session)
                        distance_getter = getattr(strategy, "get_effective_stop_distances", None)
                        if callable(distance_getter):
                            stop_distance = distance_getter(tmf_bar, session, profile).initial_stop
                            remaining_profile_qty = max(0, profile.max_qty - abs(acct_state.open_position_qty))
                            requested_qty = max(1, int(signal.qty or 1))
                            size_check = risk.check_order_size(
                                acct_state,
                                requested_qty,
                                stop_distance,
                                session,
                            )
                            qty = requested_qty if size_check.allowed and requested_qty <= remaining_profile_qty else 0
                            if qty <= 0:
                                risk.record_risk_event("order_size_denied", {
                                    "bar_time": tmf_bar.time.isoformat(),
                                    "signal": signal.reason,
                                    "requested_qty": requested_qty,
                                    "profile_allowed_qty": remaining_profile_qty,
                                    **size_check.details,
                                })
                        else:
                            stop_distance = profile.stop_loss_points
                            sizing = risk.calculate_position_sizing(acct_state, stop_distance, session)
                            remaining_profile_qty = max(0, profile.max_qty - abs(acct_state.open_position_qty))
                            qty = min(sizing.addable_contracts, remaining_profile_qty)
                            if qty <= 0:
                                risk.record_risk_event("order_size_denied", {
                                    "bar_time": tmf_bar.time.isoformat(),
                                    "signal": signal.reason,
                                    "requested_qty": qty,
                                    "profile_allowed_qty": remaining_profile_qty,
                                    "allowed_qty": sizing.addable_contracts,
                                    "sizing": sizing.to_dict(),
                                })
                        if qty > 0:
                            order_side = OrderSide.BUY if signal.action == SignalAction.BUY else OrderSide.SELL
                            broker.create_market_order(
                                symbol=tmf_bar.symbol or "TMF",
                                side=order_side,
                                qty=qty,
                                session=session,
                                reason=signal.reason,
                                signal_bar_time=tmf_bar.time,
                            )
                    else:
                        risk.record_risk_event("open_denied", {
                            "bar_time": tmf_bar.time.isoformat(),
                            "reasons": [r.value for r in risk_check.deny_reasons],
                            "signal": signal.reason,
                        })

            # 6. 權益快照
            if bar_count % equity_snapshot_interval == 0:
                account.take_equity_snapshot(tmf_bar.time, tmf_bar.close)

        # 最終：若仍有持倉則平倉（day_only）
        if account.position and self.risk_config.holding_policy == HoldingPolicy.DAY_ONLY:
            if tmf_bars:
                last_raw = tmf_bars[-1]
                last_bar = self._parse_bar(last_raw, "TMF")
                if last_bar:
                    close_side = OrderSide.SELL if account.position.is_long else OrderSide.BUY
                    fill = broker.force_flatten_fill(
                        "TMF", close_side, account.position.qty, last_bar,
                        reason=FillReason.SESSION_CLOSE,
                    )
                    trade = account.on_fill(fill)
                    result.fills.append(fill.to_dict())
                    if trade:
                        result.trades.append(trade.to_dict())
                    if account.position:
                        reducer = getattr(strategy, "on_position_reduced", None)
                        if callable(reducer):
                            reducer()
                    else:
                        strategy.clear_position_info()

        # 最終權益快照
        if tmf_bars:
            last_raw = tmf_bars[-1]
            last_bar = self._parse_bar(last_raw, "TMF")
            if last_bar:
                account.take_equity_snapshot(last_bar.time, last_bar.close)

        # 組裝結果
        result.equity_curve = [s.to_dict() for s in account.equity_snapshots]
        result.risk_events = risk.get_risk_events()
        result.summary = account.get_summary()
        result.account_final = account.to_dict()
        result.bar_count = bar_count

        return result

    @staticmethod
    def _build_bar_map(bars: list[dict]) -> dict[str, dict]:
        """建立 bar 時間索引"""
        import zoneinfo
        bar_map: dict[str, dict] = {}
        for raw_bar in bars:
            raw_time = raw_bar.get("time") or raw_bar.get("date") or ""
            try:
                dt = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                if dt.tzinfo is not None:
                    dt = dt.astimezone(zoneinfo.ZoneInfo("Asia/Taipei"))
                else:
                    dt = dt.replace(tzinfo=zoneinfo.ZoneInfo("Asia/Taipei"))
                key = dt.strftime("%Y-%m-%d %H:%M")
                bar_map[key] = raw_bar
            except (ValueError, TypeError):
                continue
        return bar_map

    @staticmethod
    def _parse_bar(raw: dict, symbol: str = "") -> Optional[Bar]:
        """解析 K 棒資料"""
        import zoneinfo
        raw_time = raw.get("time") or raw.get("date") or ""
        try:
            dt = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone(zoneinfo.ZoneInfo("Asia/Taipei"))
            else:
                dt = dt.replace(tzinfo=zoneinfo.ZoneInfo("Asia/Taipei"))
        except (ValueError, TypeError):
            return None

        try:
            return Bar(
                time=dt,
                open=float(raw.get("open", 0)),
                high=float(raw.get("high", 0)),
                low=float(raw.get("low", 0)),
                close=float(raw.get("close", 0)),
                volume=int(raw.get("volume", 0)),
                symbol=symbol,
            )
        except (TypeError, ValueError):
            return None
