"""
WebSocket connection manager.
Tracks client subscriptions and triggers market-data hooks on first/last subscriber.
"""

import json
import logging
from collections import defaultdict
from typing import Callable, Dict, Set

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._clients: Dict[WebSocket, Set[str]] = {}
        self._ticker_subs: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._on_first_subscribe: Callable[[str], None] | None = None
        self._on_last_unsubscribe: Callable[[str], None] | None = None

    def configure_market_data_hooks(
        self,
        *,
        on_first_subscribe: Callable[[str], None] | None = None,
        on_last_unsubscribe: Callable[[str], None] | None = None,
    ) -> None:
        self._on_first_subscribe = on_first_subscribe
        self._on_last_unsubscribe = on_last_unsubscribe

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients[ws] = set()
        log.info("WS connect: %s clients", len(self._clients))

    def disconnect(self, ws: WebSocket):
        tickers = self._clients.pop(ws, set())
        for ticker in tickers:
            self._ticker_subs[ticker].discard(ws)
            if not self._ticker_subs[ticker]:
                self._ticker_subs.pop(ticker, None)
                self._notify_last_unsubscribe(ticker)
        log.info("WS disconnect: %s clients", len(self._clients))

    def subscribe(self, ws: WebSocket, ticker: str):
        if ws not in self._clients or not ticker:
            return
        is_first_subscriber = not self._ticker_subs[ticker]
        self._clients[ws].add(ticker)
        self._ticker_subs[ticker].add(ws)
        if is_first_subscriber:
            self._notify_first_subscribe(ticker)
        log.debug("Subscribed %s with %s listeners", ticker, len(self._ticker_subs[ticker]))

    def unsubscribe(self, ws: WebSocket, ticker: str):
        if ws not in self._clients or not ticker:
            return
        self._clients[ws].discard(ticker)
        self._ticker_subs[ticker].discard(ws)
        if not self._ticker_subs[ticker]:
            self._ticker_subs.pop(ticker, None)
            self._notify_last_unsubscribe(ticker)

    def get_subscribed_tickers(self) -> Set[str]:
        return {ticker for ticker, subs in self._ticker_subs.items() if subs}

    def get_status(self) -> dict:
        subscribed_tickers = sorted(self.get_subscribed_tickers())
        return {
            "client_count": len(self._clients),
            "subscribed_ticker_count": len(subscribed_tickers),
            "subscription_count": sum(len(subscriptions) for subscriptions in self._clients.values()),
            "subscribed_tickers": subscribed_tickers,
        }

    async def broadcast_to_ticker(self, ticker: str, data: dict):
        message = json.dumps(data)
        dead = set()
        for ws in list(self._ticker_subs.get(ticker, set())):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_all(self, data: dict):
        message = json.dumps(data)
        dead = set()
        for ws in list(self._clients.keys()):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)

    def _notify_first_subscribe(self, ticker: str) -> None:
        if not callable(self._on_first_subscribe):
            return
        try:
            self._on_first_subscribe(ticker)
        except Exception as exc:
            log.warning("First subscribe hook failed for %s: %s", ticker, exc)

    def _notify_last_unsubscribe(self, ticker: str) -> None:
        if not callable(self._on_last_unsubscribe):
            return
        try:
            self._on_last_unsubscribe(ticker)
        except Exception as exc:
            log.warning("Last unsubscribe hook failed for %s: %s", ticker, exc)
