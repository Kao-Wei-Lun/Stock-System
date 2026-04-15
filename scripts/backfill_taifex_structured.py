import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import db, init_db  # noqa: E402


@dataclass(slots=True)
class BackfillStats:
    snapshot_count: int = 0
    overview_rows: int = 0
    futures_rows: int = 0
    options_rows: int = 0
    call_put_rows: int = 0
    cash_summary_rows: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill structured TAIFEX institutional tables from existing institutional_snapshots payload_json rows.",
    )
    parser.add_argument("--start", default="", help="Optional start resolved date in YYYY-MM-DD format.")
    parser.add_argument("--end", default="", help="Optional end resolved date in YYYY-MM-DD format.")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit on number of snapshot days to process, ordered by resolved_date ascending.",
    )
    return parser.parse_args()


async def backfill(args: argparse.Namespace) -> int:
    stats = BackfillStats()
    started = time.time()

    await init_db()
    try:
        payloads = await db.list_institutional_snapshot_payloads(
            start_date=args.start or None,
            end_date=args.end or None,
            limit=args.limit or None,
        )
        if not payloads:
            print("[INFO] No institutional snapshots matched the requested range.")
            return 0

        print(
            f"[INFO] Backfill TAIFEX structured tables: snapshots={len(payloads)} "
            f"start={payloads[0].get('resolved_date')} end={payloads[-1].get('resolved_date')}"
        )
        for payload in payloads:
            resolved_date = payload.get("resolved_date") or "unknown"
            counts = await db.upsert_taifex_structured_snapshot(payload)
            stats.snapshot_count += 1
            stats.overview_rows += counts.get("overview_rows", 0)
            stats.futures_rows += counts.get("futures_rows", 0)
            stats.options_rows += counts.get("options_rows", 0)
            stats.call_put_rows += counts.get("call_put_rows", 0)
            stats.cash_summary_rows += counts.get("cash_summary_rows", 0)
            print(
                f"[SYNC] {resolved_date} "
                f"overview={counts.get('overview_rows', 0)} "
                f"futures={counts.get('futures_rows', 0)} "
                f"options={counts.get('options_rows', 0)} "
                f"call_put={counts.get('call_put_rows', 0)} "
                f"cash={counts.get('cash_summary_rows', 0)}"
            )
    finally:
        await db.close()

    elapsed = time.time() - started
    print("")
    print("[DONE] TAIFEX structured backfill finished")
    print(f"  snapshot_count={stats.snapshot_count}")
    print(f"  overview_rows={stats.overview_rows}")
    print(f"  futures_rows={stats.futures_rows}")
    print(f"  options_rows={stats.options_rows}")
    print(f"  call_put_rows={stats.call_put_rows}")
    print(f"  cash_summary_rows={stats.cash_summary_rows}")
    print(f"  elapsed_seconds={elapsed:.1f}")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(backfill(args))


if __name__ == "__main__":
    raise SystemExit(main())
