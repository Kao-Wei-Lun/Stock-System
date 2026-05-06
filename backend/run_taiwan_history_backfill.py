from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

from database import db, init_db
from env_validation import validate_runtime_environment
from main import tw_history_backfill_service
from providers import fubon_manager
from taiwan_history_backfill_service import _normalize_intervals


def _json_default(value: Any) -> str:
    return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manually backfill Taiwan stock history from Fubon API into the local database.",
    )
    parser.add_argument(
        "--force-full",
        action="store_true",
        help="Fetch full Fubon history for every ticker/interval, even if sync status already exists.",
    )
    parser.add_argument(
        "--max-tickers",
        type=int,
        default=None,
        help="Limit ticker count for smoke tests, for example --max-tickers 5.",
    )
    parser.add_argument(
        "--intervals",
        default=None,
        help="Comma-separated intervals to sync. Supported: 1d,1wk,1mo.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=None,
        help="Override the delay between Fubon history requests.",
    )
    parser.add_argument(
        "--skip-universe-refresh",
        action="store_true",
        help="Use the existing local Taiwan universe instead of refreshing it from Fubon first.",
    )
    parser.add_argument(
        "--exclude-etf",
        action="store_true",
        help="Sync common stocks only and skip ETF/ETN-like symbols.",
    )
    return parser


async def run_backfill(args: argparse.Namespace) -> dict[str, Any]:
    validate_runtime_environment()
    await init_db()
    try:
        connected = await fubon_manager.init_from_db(db)
        if not connected:
            raise RuntimeError("Fubon SDK is not connected. Configure and activate a Fubon account before backfill.")

        if args.intervals:
            tw_history_backfill_service.intervals = _normalize_intervals(args.intervals)
        if args.delay_seconds is not None:
            tw_history_backfill_service.request_delay_seconds = max(0.0, float(args.delay_seconds))
        if args.exclude_etf:
            tw_history_backfill_service.include_etf = False

        return await tw_history_backfill_service.sync_history(
            reason="manual-cli-tw-full-history",
            force_universe=not args.skip_universe_refresh,
            force_full=bool(args.force_full),
            max_tickers=args.max_tickers,
        )
    finally:
        fubon_manager.shutdown()
        await db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args()
    payload = asyncio.run(run_backfill(args))
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
