"""Safe launcher preflight that reports validation errors without printing secrets."""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from env_validation import validate_runtime_environment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate QuantVision runtime environment")
    parser.add_argument(
        "--bind-host",
        action="store_true",
        help="Print only the validated backend bind host for launcher integration.",
    )
    args = parser.parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")
    try:
        validated = validate_runtime_environment()
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 2
    if args.bind_host:
        print(validated.get("APP_BIND_HOST") or "127.0.0.1")
    else:
        lan_mode = "enabled" if validated.get("ALLOW_LAN_ACCESS") else "disabled"
        print(f"[INFO] Runtime environment validation passed; LAN access is {lan_mode}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
