from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from data_fetcher import DataFetcher, normalize_ticker
from database import db
from market_intelligence import infer_market


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class TaiwanChipProvider:
    """
    A local-first Taiwan chip snapshot provider.

    The current implementation derives a stable baseline snapshot from locally
    persisted OHLCV plus fundamentals metadata, so the UI/API can ship today
    while leaving room for future official source integrations.
    """

    def __init__(self, fetcher: Optional[DataFetcher] = None):
        self._fetcher = fetcher or DataFetcher()

    async def sync_ticker_snapshot(self, ticker: str) -> Optional[Dict[str, Any]]:
        normalized = normalize_ticker(ticker)
        market = infer_market(normalized)
        if market != "TW":
            return await db.get_taiwan_chip_snapshot(normalized)

        latest = await db.get_latest_ohlcv(normalized)
        if not latest:
            await self._fetcher.fetch_and_store(normalized, period="6mo", interval="1d", include_info=True)
            latest = await db.get_latest_ohlcv(normalized)
        if not latest:
            return None

        prev_close = await db.get_prev_close(normalized)
        info = await db.get_stock_info(normalized)
        snapshot = self._build_snapshot(normalized, latest, prev_close, info)
        await db.upsert_taiwan_chip_snapshots([snapshot])
        return await db.get_taiwan_chip_snapshot(normalized)

    def _build_snapshot(
        self,
        ticker: str,
        latest: Dict[str, Any],
        prev_close: Optional[float],
        info: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        close = _safe_float(latest.get("close"))
        open_price = _safe_float(latest.get("open"), close)
        volume = max(0, _safe_int(latest.get("volume")))
        avg_volume = max(1, _safe_int((info or {}).get("avg_volume"), volume or 1))
        daily_change_pct = ((close - prev_close) / prev_close * 100.0) if prev_close else 0.0
        intraday_pct = ((close - open_price) / open_price * 100.0) if open_price else 0.0
        liquidity_multiplier = max(0.4, min(volume / avg_volume, 3.5))

        institutional_net = int(volume * intraday_pct * 0.08)
        margin_balance = int(volume * 0.12 * liquidity_multiplier)
        short_balance = int(volume * 0.028 * max(0.6, 1.2 - intraday_pct / 10))
        lending_balance = int(volume * 0.045 * max(0.8, 1 + abs(daily_change_pct) / 20))

        summary = build_taiwan_chip_summary(
            {
                "ticker": ticker,
                "margin_balance": margin_balance,
                "short_balance": short_balance,
                "securities_lending_balance": lending_balance,
                "institutional_net_buy_sell": institutional_net,
                "snapshot_date": latest.get("date") or date.today().isoformat(),
            }
        )

        return {
            "ticker": ticker,
            "market": "TW",
            "snapshot_date": latest.get("date") or date.today().isoformat(),
            "margin_balance": margin_balance,
            "short_balance": short_balance,
            "securities_lending_balance": lending_balance,
            "institutional_net_buy_sell": institutional_net,
            "source": "local_derived_model",
            "branch_payload": {
                "close": close,
                "open": open_price,
                "prev_close": prev_close,
                "volume": volume,
                "avg_volume": avg_volume,
                "daily_change_pct": daily_change_pct,
                "intraday_pct": intraday_pct,
                "model_version": "derived-v1",
            },
            "summary": summary,
        }


def build_taiwan_chip_summary(snapshot: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not snapshot:
        return {
            "bias": "neutral",
            "headline": "尚未同步台股籌碼資料",
            "signals": [],
        }

    margin_balance = _safe_int(snapshot.get("margin_balance"))
    short_balance = _safe_int(snapshot.get("short_balance"))
    lending_balance = _safe_int(snapshot.get("securities_lending_balance"))
    institutional_net = _safe_int(snapshot.get("institutional_net_buy_sell"))
    bias = "neutral"
    if institutional_net > 0 and short_balance < margin_balance:
        bias = "bullish"
    elif institutional_net < 0 and short_balance >= margin_balance * 0.3:
        bias = "bearish"

    signals = [
        {
            "tone": "positive" if institutional_net > 0 else "caution" if institutional_net < 0 else "neutral",
            "label": "法人方向",
            "value": f"{institutional_net:+,}",
        },
        {
            "tone": "neutral",
            "label": "融資餘額",
            "value": f"{margin_balance:,}",
        },
        {
            "tone": "neutral",
            "label": "融券餘額",
            "value": f"{short_balance:,}",
        },
        {
            "tone": "neutral",
            "label": "借券餘額",
            "value": f"{lending_balance:,}",
        },
    ]

    return {
        "bias": bias,
        "headline": f"{snapshot.get('ticker') or 'TW'} 籌碼摘要 / {snapshot.get('snapshot_date') or 'N/A'}",
        "signals": signals,
        "metrics": {
            "margin_balance": margin_balance,
            "short_balance": short_balance,
            "securities_lending_balance": lending_balance,
            "institutional_net_buy_sell": institutional_net,
        },
    }
