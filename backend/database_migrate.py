"""Inspect or apply versioned QuantVision MySQL schema migrations."""

from __future__ import annotations

import argparse
import asyncio
import json

from database import db


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "plan", "apply"))
    return parser


def _public_plan(status: dict) -> dict:
    return {
        **status,
        "pending": [
            {
                "version": item["version"],
                "description": item["description"],
                "checksum": item["checksum"],
                "statement_count": item["statement_count"],
                "statements": item["statements"],
            }
            for item in status["pending"]
        ],
    }


async def run(command: str) -> dict:
    await db.connect()
    try:
        if command == "apply":
            before = await db.get_migration_status()
            await db.create_tables(auto_apply=True)
            after = await db.get_migration_status()
            return {
                "command": command,
                "applied_versions": [item["version"] for item in before["pending"]],
                "status": _public_plan(after),
            }
        status = await db.get_migration_status()
        return {"command": command, "status": _public_plan(status)}
    finally:
        await db.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = asyncio.run(run(args.command))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
