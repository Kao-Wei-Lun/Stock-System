from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable

import requests

from env_validation import read_text_env, read_url_env

log = logging.getLogger(__name__)


HttpPost = Callable[[str, dict[str, Any]], None]


def _default_http_post(url: str, payload: dict[str, Any]) -> None:
    response = requests.post(url, json=payload, timeout=8)
    response.raise_for_status()


@dataclass(slots=True)
class ExternalNotificationDispatcher:
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    http_post: HttpPost = _default_http_post

    @classmethod
    def from_env(cls) -> "ExternalNotificationDispatcher":
        discord_url = read_text_env("DISCORD_WEBHOOK_URL", "")
        if discord_url:
            discord_url = read_url_env("DISCORD_WEBHOOK_URL", discord_url)
        return cls(
            telegram_bot_token=read_text_env("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=read_text_env("TELEGRAM_CHAT_ID", ""),
            discord_webhook_url=discord_url,
        )

    @property
    def enabled(self) -> bool:
        return bool(
            (self.telegram_bot_token and self.telegram_chat_id)
            or self.discord_webhook_url
        )

    async def send_alert(self, notification: dict[str, Any]) -> list[str]:
        if not self.enabled:
            return []

        message = build_external_alert_message(notification)
        delivered: list[str] = []

        if self.telegram_bot_token and self.telegram_chat_id:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "disable_web_page_preview": True,
            }
            await asyncio.to_thread(self.http_post, url, payload)
            delivered.append("telegram")

        if self.discord_webhook_url:
            await asyncio.to_thread(self.http_post, self.discord_webhook_url, {"content": message})
            delivered.append("discord")

        return delivered


class NullExternalNotificationDispatcher:
    enabled = False

    async def send_alert(self, notification: dict[str, Any]) -> list[str]:
        return []


def build_external_alert_message(notification: dict[str, Any]) -> str:
    title = str(notification.get("title") or "QuantVision Alert").strip()
    message = str(notification.get("message") or "").strip()
    payload = notification.get("payload") or {}
    quote = payload.get("quote") or {}
    ticker = payload.get("ticker") or quote.get("ticker")
    source = payload.get("source") or quote.get("source")

    lines = [f"[QuantVision] {title}"]
    if ticker:
        lines.append(f"Ticker: {ticker}")
    if message:
        lines.append(message)
    if payload.get("trigger_value") is not None:
        lines.append(f"Trigger: {payload.get('trigger_value')}")
    if payload.get("threshold_value") is not None:
        lines.append(f"Threshold: {payload.get('threshold_value')}")
    if source:
        lines.append(f"Source: {source}")
    return "\n".join(lines)
