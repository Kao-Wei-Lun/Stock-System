from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TRUTHY_VALUES = {"1", "true", "yes", "on"}
FALSY_VALUES = {"0", "false", "no", "off"}
PLACEHOLDER_PASSWORDS = {
  "your_mysql_password_here",
  "changeme",
  "change_me",
}


def _read_raw_value(name: str, default: str | None = None, *, env: Mapping[str, str] | None = None) -> str:
  source = env if env is not None else os.environ
  if name in source:
    return str(source[name]).strip()
  if default is None:
    return ""
  return str(default).strip()


def read_text_env(name: str, default: str = "", *, env: Mapping[str, str] | None = None) -> str:
  return _read_raw_value(name, default, env=env)


def read_required_text_env(name: str, *, env: Mapping[str, str] | None = None) -> str:
  value = _read_raw_value(name, None, env=env)
  if value:
    return value
  raise RuntimeError(f"Missing required environment variable: {name}")


def read_int_env(
  name: str,
  default: str | int,
  *,
  minimum: int | None = None,
  maximum: int | None = None,
  env: Mapping[str, str] | None = None,
) -> int:
  raw_value = _read_raw_value(name, str(default), env=env)
  try:
    value = int(raw_value)
  except (TypeError, ValueError) as exc:
    raise RuntimeError(f"Invalid integer for {name}: {raw_value}") from exc

  if minimum is not None and value < minimum:
    raise RuntimeError(f"{name} must be >= {minimum}")
  if maximum is not None and value > maximum:
    raise RuntimeError(f"{name} must be <= {maximum}")
  return value


def read_float_env(
  name: str,
  default: str | float,
  *,
  minimum: float | None = None,
  maximum: float | None = None,
  env: Mapping[str, str] | None = None,
) -> float:
  raw_value = _read_raw_value(name, str(default), env=env)
  try:
    value = float(raw_value)
  except (TypeError, ValueError) as exc:
    raise RuntimeError(f"Invalid float for {name}: {raw_value}") from exc

  if minimum is not None and value < minimum:
    raise RuntimeError(f"{name} must be >= {minimum}")
  if maximum is not None and value > maximum:
    raise RuntimeError(f"{name} must be <= {maximum}")
  return value


def read_bool_env(name: str, default: bool = False, *, env: Mapping[str, str] | None = None) -> bool:
  raw_value = _read_raw_value(name, None, env=env)
  if not raw_value:
    return default

  normalized = raw_value.lower()
  if normalized in TRUTHY_VALUES:
    return True
  if normalized in FALSY_VALUES:
    return False
  raise RuntimeError(f"Invalid boolean for {name}: {raw_value}")


def read_timezone_env(name: str, default: str, *, env: Mapping[str, str] | None = None) -> str:
  value = _read_raw_value(name, default, env=env)
  try:
    ZoneInfo(value)
  except ZoneInfoNotFoundError as exc:
    raise RuntimeError(f"Invalid timezone for {name}: {value}") from exc
  return value


def read_hhmm_env(name: str, default: str, *, env: Mapping[str, str] | None = None) -> str:
  value = _read_raw_value(name, default, env=env)
  hour_text, separator, minute_text = value.partition(":")
  if separator != ":":
    raise RuntimeError(f"Invalid HH:MM time for {name}: {value}")
  try:
    hour = int(hour_text)
    minute = int(minute_text)
  except ValueError as exc:
    raise RuntimeError(f"Invalid HH:MM time for {name}: {value}") from exc
  if not (0 <= hour <= 23 and 0 <= minute <= 59):
    raise RuntimeError(f"Invalid HH:MM time for {name}: {value}")
  return f"{hour:02d}:{minute:02d}"


def read_url_env(name: str, default: str, *, env: Mapping[str, str] | None = None) -> str:
  value = _read_raw_value(name, default, env=env).rstrip("/")
  parsed = urlparse(value)
  if parsed.scheme not in {"http", "https"} or not parsed.netloc:
    raise RuntimeError(f"Invalid URL for {name}: {value}")
  return value


def validate_runtime_environment(*, env: Mapping[str, str] | None = None) -> dict[str, object]:
  source = env if env is not None else os.environ
  errors: list[str] = []
  validated: dict[str, object] = {}

  def capture(name: str, resolver) -> None:
    try:
      validated[name] = resolver()
    except RuntimeError as exc:
      errors.append(str(exc))

  capture("MYSQL_HOST", lambda: read_required_text_env("MYSQL_HOST", env=source))
  capture("MYSQL_PORT", lambda: read_int_env("MYSQL_PORT", "3306", minimum=1, maximum=65535, env=source))
  capture("MYSQL_USER", lambda: read_required_text_env("MYSQL_USER", env=source))
  capture("MYSQL_DATABASE", lambda: read_required_text_env("MYSQL_DATABASE", env=source))
  capture("MYSQL_CHARSET", lambda: read_required_text_env("MYSQL_CHARSET", env=source))
  capture("APP_PORT", lambda: read_int_env("APP_PORT", "8001", minimum=1, maximum=65535, env=source))
  capture("APP_TIMEZONE", lambda: read_timezone_env("APP_TIMEZONE", "Asia/Taipei", env=source))
  capture("DAILY_LATEST_SYNC_TIME", lambda: read_hhmm_env("DAILY_LATEST_SYNC_TIME", "18:10", env=source))
  capture("TW_FULL_HISTORY_SYNC_START", lambda: read_hhmm_env("TW_FULL_HISTORY_SYNC_START", "15:30", env=source))
  capture("TW_FULL_HISTORY_SYNC_STOP", lambda: read_hhmm_env("TW_FULL_HISTORY_SYNC_STOP", "08:00", env=source))
  capture("FRONTEND_DEV_URL", lambda: read_url_env("FRONTEND_DEV_URL", "http://localhost:5173", env=source))

  for key, default in (
    ("STARTUP_DOWNLOAD_ENABLED", False),
    ("INSTITUTIONAL_AUTO_SYNC_ENABLED", True),
    ("LATEST_DATA_SYNC_ON_STARTUP", True),
    ("TW_FULL_HISTORY_SYNC_ENABLED", False),
    ("TW_FULL_HISTORY_INCLUDE_ETF", True),
    ("ALERT_EVALUATOR_ENABLED", True),
    ("MARKET_INTELLIGENCE_SYNC_ENABLED", True),
    ("MARKET_INTELLIGENCE_STARTUP_SYNC", True),
  ):
    capture(key, lambda key=key, default=default: read_bool_env(key, default, env=source))

  capture(
    "ALERT_POLL_INTERVAL_SECONDS",
    lambda: read_int_env("ALERT_POLL_INTERVAL_SECONDS", "30", minimum=10, env=source),
  )
  capture(
    "TW_FULL_HISTORY_DELAY_SECONDS",
    lambda: read_float_env("TW_FULL_HISTORY_DELAY_SECONDS", "0.8", minimum=0, env=source),
  )

  encrypt_key = _read_raw_value("APP_ENCRYPT_KEY", None, env=source)
  if not encrypt_key:
    errors.append(
      "Missing required environment variable: APP_ENCRYPT_KEY\n"
      "  Generate one with: python -c \"from cryptography.fernet import Fernet; "
      "print(Fernet.generate_key().decode())\""
    )
  else:
    validated["APP_ENCRYPT_KEY"] = encrypt_key

  password = _read_raw_value("MYSQL_PASSWORD", None, env=source)
  if not password:
    errors.append("Missing required environment variable: MYSQL_PASSWORD")
  elif password.lower() in PLACEHOLDER_PASSWORDS:
    errors.append("MYSQL_PASSWORD still uses the example placeholder")
  else:
    validated["MYSQL_PASSWORD"] = password

  if errors:
    detail = "\n- ".join(errors)
    raise RuntimeError(f"Invalid runtime environment configuration:\n- {detail}")

  return validated
