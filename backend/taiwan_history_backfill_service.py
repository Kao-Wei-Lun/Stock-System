from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, tzinfo
from typing import Any, Dict, Iterable, List, Optional

from data_fetcher import normalize_ticker


SUPPORTED_HISTORY_INTERVALS = {"1d", "1wk", "1mo"}
DEFAULT_HISTORY_START_DATE = date(2010, 1, 1)
TAIWAN_MARKETS = ("TSE", "OTC")


def _normalize_intervals(intervals: Iterable[str] | str | None) -> tuple[str, ...]:
    if intervals is None:
        return ("1d", "1wk", "1mo")
    source = intervals.split(",") if isinstance(intervals, str) else list(intervals)
    normalized = []
    for item in source:
        value = str(item or "").strip().lower()
        if value in SUPPORTED_HISTORY_INTERVALS and value not in normalized:
            normalized.append(value)
    return tuple(normalized or ["1d"])


def _looks_like_etf(row: Dict[str, Any]) -> bool:
    ticker = str(row.get("ticker") or "").upper()
    name = str(row.get("name") or "").upper()
    security_type = str(row.get("type") or row.get("security_type") or "").upper()
    return (
        ticker.startswith("00")
        or "ETF" in name
        or "ETN" in name
        or "ETF" in security_type
        or "FUND" in security_type
    )


def _row_snapshot_date(payload: Dict[str, Any]) -> str:
    raw_date = payload.get("date") or payload.get("snapshot_date")
    if raw_date:
        return str(raw_date)[:10]
    return date.today().isoformat()


def _latest_row_date(row: Optional[Dict[str, Any]]) -> Optional[str]:
    if not row:
        return None
    value = row.get("date")
    return str(value)[:10] if value else None


@dataclass(slots=True)
class TaiwanHistoryBackfillService:
    db: Any
    fetcher: Any
    market_snapshot_provider: Any
    app_tz: tzinfo
    history_period: str = "max"
    incremental_period: str = "5d"
    intervals: tuple[str, ...] = field(default_factory=lambda: ("1d", "1wk", "1mo"))
    request_delay_seconds: float = 0.8
    include_etf: bool = True
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))

    def __post_init__(self) -> None:
        self.intervals = _normalize_intervals(self.intervals)

    async def sync_universe(self, *, refresh: bool = True) -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        market_counts: Dict[str, int] = {}
        snapshot_dates: List[str] = []

        for market in TAIWAN_MARKETS:
            payload = await self.market_snapshot_provider.fetch_snapshot(market, refresh=refresh)
            if not payload or not isinstance(payload.get("data"), list):
                market_counts[market] = 0
                continue
            snapshot_date = _row_snapshot_date(payload)
            snapshot_dates.append(snapshot_date)
            normalized_rows = []
            for item in payload.get("data") or []:
                ticker = normalize_ticker(item.get("ticker"))
                if not ticker:
                    continue
                symbol = str(item.get("symbol") or ticker.split(".", 1)[0]).strip().upper()
                normalized_rows.append(
                    {
                        "ticker": ticker,
                        "symbol": symbol,
                        "market": str(item.get("market") or market).strip().upper() or market,
                        "name": item.get("name") or ticker,
                        "sector": item.get("sector"),
                        "security_type": item.get("type"),
                        "is_etf": _looks_like_etf(item),
                        "is_active": True,
                        "source": "fubon_neo",
                        "latest_snapshot_date": snapshot_date,
                    }
                )
            if normalized_rows:
                await self.db.upsert_tw_equity_universe(normalized_rows)
                await self._upsert_stock_info_from_universe(normalized_rows)
            market_counts[market] = len(normalized_rows)
            rows.extend(normalized_rows)

        latest_snapshot_date = max(snapshot_dates) if snapshot_dates else date.today().isoformat()
        if rows and len(set(snapshot_dates)) == 1:
            await self.db.deactivate_stale_tw_equities(latest_snapshot_date)
        elif rows:
            self.logger.warning(
                "Skipped stale Taiwan universe deactivation because market snapshots use different dates: %s",
                sorted(set(snapshot_dates)),
            )

        return {
            "source": "fubon_neo",
            "snapshot_date": latest_snapshot_date,
            "markets": market_counts,
            "count": len(rows),
        }

    async def sync_history(
        self,
        *,
        reason: str = "scheduled",
        force_universe: bool = False,
        force_full: bool = False,
        max_tickers: Optional[int] = None,
        stop_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        universe = await self.sync_universe(refresh=force_universe)
        tickers = await self.db.list_tw_equity_universe(active_only=True, include_etf=self.include_etf)
        tickers = await self._prioritize_tickers_for_sync(tickers)
        if max_tickers is not None:
            tickers = tickers[: max(0, int(max_tickers))]

        started_at = datetime.now(self.app_tz)
        results: List[Dict[str, Any]] = []
        failures: List[Dict[str, Any]] = []
        skipped = 0

        for ticker_row in tickers:
            if stop_at is not None and datetime.now(self.app_tz) >= stop_at:
                skipped += 1
                break
            ticker = normalize_ticker(ticker_row.get("ticker"))
            if not ticker:
                continue
            for interval in self.intervals:
                if stop_at is not None and datetime.now(self.app_tz) >= stop_at:
                    skipped += 1
                    break
                result = await self.sync_ticker_interval(
                    ticker,
                    interval=interval,
                    reason=reason,
                    force_full=force_full,
                )
                results.append(result)
                if result.get("status") == "failed":
                    failures.append(result)
                if self.request_delay_seconds > 0:
                    await asyncio.sleep(self.request_delay_seconds)

        coverage = await self.db.get_tw_universe_coverage("1d")
        return {
            "reason": reason,
            "source": "fubon_neo",
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(self.app_tz).isoformat(),
            "universe": universe,
            "intervals": list(self.intervals),
            "ticker_count": len(tickers),
            "result_count": len(results),
            "success_count": sum(1 for item in results if item.get("status") in {"success", "empty"}),
            "failure_count": len(failures),
            "skipped_count": skipped,
            "total_rows": sum(int(item.get("rows_synced") or 0) for item in results),
            "coverage": coverage,
            "failures": failures[:20],
        }

    async def sync_ticker_interval(
        self,
        ticker: str,
        *,
        interval: str,
        reason: str,
        force_full: bool = False,
    ) -> Dict[str, Any]:
        normalized_ticker = normalize_ticker(ticker)
        normalized_interval = str(interval or "1d").strip().lower()
        if normalized_interval not in SUPPORTED_HISTORY_INTERVALS:
            raise ValueError(f"Unsupported Taiwan history interval: {interval}")

        status = await self.db.get_tw_history_sync_status(normalized_ticker, normalized_interval)
        has_success = bool(status and status.get("last_success_date"))
        period = self.history_period if force_full or not has_success else self.incremental_period
        requested_start = DEFAULT_HISTORY_START_DATE.isoformat() if period == "max" else None
        requested_end = date.today().isoformat()

        await self.db.record_tw_history_sync_status(
            ticker=normalized_ticker,
            interval=normalized_interval,
            status="running",
            requested_start_date=requested_start,
            requested_end_date=requested_end,
            rows_synced=0,
        )

        try:
            rows_synced = await self.fetcher.fetch_and_store(
                normalized_ticker,
                period=period,
                interval=normalized_interval,
                include_info=False,
            )
            latest_row = await self.db.get_latest_ohlcv(normalized_ticker, normalized_interval)
            latest_date = _latest_row_date(latest_row)
            next_status = "success" if rows_synced or latest_date else "empty"
            await self.db.record_tw_history_sync_status(
                ticker=normalized_ticker,
                interval=normalized_interval,
                status=next_status,
                requested_start_date=requested_start,
                requested_end_date=requested_end,
                last_success_date=latest_date,
                rows_synced=rows_synced,
            )
            return {
                "ticker": normalized_ticker,
                "interval": normalized_interval,
                "period": period,
                "status": next_status,
                "rows_synced": rows_synced,
                "latest_date": latest_date,
            }
        except Exception as exc:
            message = str(exc)
            await self.db.record_tw_history_sync_status(
                ticker=normalized_ticker,
                interval=normalized_interval,
                status="failed",
                requested_start_date=requested_start,
                requested_end_date=requested_end,
                rows_synced=0,
                error=f"{reason}:{message}",
            )
            self.logger.warning("Taiwan history sync failed for %s/%s: %s", normalized_ticker, normalized_interval, exc)
            return {
                "ticker": normalized_ticker,
                "interval": normalized_interval,
                "period": period,
                "status": "failed",
                "rows_synced": 0,
                "message": message,
            }

    async def _prioritize_tickers_for_sync(self, tickers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            statuses = await self.db.list_tw_history_sync_status(limit=10000)
        except Exception as exc:
            self.logger.debug("Unable to load Taiwan history sync statuses for prioritization: %s", exc)
            return tickers

        status_by_pair = {
            (normalize_ticker(row.get("ticker")), str(row.get("interval") or "1d").lower()): row
            for row in statuses or []
            if row.get("ticker")
        }

        def rank(row: Dict[str, Any]) -> tuple[int, str, str]:
            ticker = normalize_ticker(row.get("ticker"))
            interval_statuses = [status_by_pair.get((ticker, interval)) for interval in self.intervals]
            if any(self._needs_initial_or_repair_sync(status) for status in interval_statuses):
                return (0, "", ticker)
            oldest_success = min(
                (str(status.get("last_success_date") or "9999-12-31") for status in interval_statuses if status),
                default="9999-12-31",
            )
            return (1, oldest_success, ticker)

        return sorted(tickers, key=rank)

    @staticmethod
    def _needs_initial_or_repair_sync(status: Optional[Dict[str, Any]]) -> bool:
        if not status:
            return True
        if not status.get("last_success_date"):
            return True
        return str(status.get("status") or "").lower() in {"failed", "pending", "running"}

    async def _upsert_stock_info_from_universe(self, rows: List[Dict[str, Any]]) -> None:
        for row in rows:
            await self.db.upsert_stock_info(
                row["ticker"],
                {
                    "longName": row.get("name") or row["ticker"],
                    "shortName": row.get("name") or row["ticker"],
                    "sector": row.get("sector"),
                    "industry": row.get("sector"),
                    "currency": "TWD",
                    "exchange": row.get("market"),
                    "country": "Taiwan",
                },
            )
