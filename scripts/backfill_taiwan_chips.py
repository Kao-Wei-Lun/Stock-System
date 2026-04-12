from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import db, init_db  # noqa: E402
from taiwan_chip_provider import TaiwanChipProvider, TWSE_T86_EARLIEST_DATE  # noqa: E402


@dataclass(slots=True)
class BackfillStats:
    processed_days: int = 0
    synced_days: int = 0
    skipped_existing_days: int = 0
    skipped_nodata_days: int = 0
    failed_days: int = 0
    total_rows: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill Taiwan chip snapshots (TWSE/TPEX) into the local MySQL database.",
    )
    parser.add_argument(
        "--start",
        default=TWSE_T86_EARLIEST_DATE.isoformat(),
        help=f"Start date in YYYY-MM-DD format. Default: {TWSE_T86_EARLIEST_DATE.isoformat()}",
    )
    parser.add_argument(
        "--end",
        default=date.today().isoformat(),
        help="End date in YYYY-MM-DD format. Default: today.",
    )
    parser.add_argument(
        "--sources",
        default="all",
        choices=("all", "twse", "tpex"),
        help="Which official source(s) to backfill. Default: all.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.15,
        help="Delay in seconds between days. Default: 0.15",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore existing local rows and refetch each day.",
    )
    parser.add_argument(
        "--include-weekends",
        action="store_true",
        help="Also try Saturday/Sunday dates. Default skips weekends.",
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=0,
        help="Optional cap on processed calendar days, useful for testing.",
    )
    return parser.parse_args()


def parse_iso_date(value: str, label: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"{label} must use YYYY-MM-DD, got: {value}") from exc


def iter_dates(start_date: date, end_date: date) -> Iterable[date]:
    cursor = start_date
    while cursor <= end_date:
        yield cursor
        cursor += timedelta(days=1)


def normalize_sources(value: str) -> tuple[str, ...]:
    if value == "all":
        return ("twse", "tpex")
    return (value,)


async def backfill(args: argparse.Namespace) -> int:
    start_date = parse_iso_date(args.start, "start")
    end_date = parse_iso_date(args.end, "end")
    if end_date < start_date:
        raise SystemExit("end must be on or after start")

    sources = normalize_sources(args.sources)
    if "twse" in sources and start_date < TWSE_T86_EARLIEST_DATE:
        print(
            f"[INFO] start adjusted from {start_date.isoformat()} to {TWSE_T86_EARLIEST_DATE.isoformat()} "
            "because TWSE T86 starts at 2012-05-02."
        )
        start_date = TWSE_T86_EARLIEST_DATE

    provider = TaiwanChipProvider()
    stats = BackfillStats()
    started = time.time()

    await init_db()
    try:
        print(
            f"[INFO] Backfill Taiwan chips: start={start_date.isoformat()} "
            f"end={end_date.isoformat()} sources={','.join(sources)}"
        )
        for cursor in iter_dates(start_date, end_date):
            if args.max_days and stats.processed_days >= args.max_days:
                print(f"[INFO] Reached --max-days={args.max_days}, stopping early.")
                break
            if not args.include_weekends and cursor.weekday() >= 5:
                continue

            stats.processed_days += 1
            label = cursor.isoformat()
            try:
                result = await provider.ensure_daily_snapshot(
                    cursor,
                    force_refresh=args.force_refresh,
                    allow_fallback=False,
                    sources=sources,
                )
            except ValueError as exc:
                stats.failed_days += 1
                print(f"[FAIL] {label} {exc}")
                continue
            except RuntimeError as exc:
                message = str(exc)
                lowered = message.lower()
                if "no rows" in lowered or "no data" in lowered or "no taiwan chip data" in lowered:
                    stats.skipped_nodata_days += 1
                    print(f"[SKIP] {label} no official data")
                else:
                    stats.failed_days += 1
                    print(f"[FAIL] {label} {message}")
                continue
            except Exception as exc:
                stats.failed_days += 1
                print(f"[FAIL] {label} {exc}")
                continue

            rows = int(result.get("row_count") or 0)
            stats.total_rows += rows
            if result.get("source") == "local_db":
                stats.skipped_existing_days += 1
                print(f"[HIT ] {label} local_db rows={rows}")
            else:
                stats.synced_days += 1
                resolved = result.get("resolved_date") or label
                source = result.get("source") or "unknown"
                print(f"[SYNC] {label} resolved={resolved} source={source} rows={rows}")

            if args.sleep > 0:
                await asyncio.sleep(args.sleep)
    finally:
        await db.close()

    elapsed = time.time() - started
    print("")
    print("[DONE] Taiwan chip backfill finished")
    print(f"  processed_days={stats.processed_days}")
    print(f"  synced_days={stats.synced_days}")
    print(f"  skipped_existing_days={stats.skipped_existing_days}")
    print(f"  skipped_nodata_days={stats.skipped_nodata_days}")
    print(f"  failed_days={stats.failed_days}")
    print(f"  accumulated_rows={stats.total_rows}")
    print(f"  elapsed_seconds={elapsed:.1f}")
    return 0 if stats.failed_days == 0 else 1


def main() -> int:
    args = parse_args()
    return asyncio.run(backfill(args))


if __name__ == "__main__":
    raise SystemExit(main())
