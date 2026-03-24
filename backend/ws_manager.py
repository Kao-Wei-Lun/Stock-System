"""
WebSocket 連線管理器
管理多個客戶端的訂閱關係
"""

import json
import logging
from collections import defaultdict
from typing import Dict, Set

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # websocket -> set of subscribed tickers
        self._clients: Dict[WebSocket, Set[str]] = {}
        # ticker -> set of websockets
        self._ticker_subs: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients[ws] = set()
        log.info(f"WS 連線：共 {len(self._clients)} 個客戶端")

    def disconnect(self, ws: WebSocket):
        tickers = self._clients.pop(ws, set())
        for t in tickers:
            self._ticker_subs[t].discard(ws)
        log.info(f"WS 斷線：剩 {len(self._clients)} 個客戶端")

    def subscribe(self, ws: WebSocket, ticker: str):
        if ws in self._clients:
            self._clients[ws].add(ticker)
            self._ticker_subs[ticker].add(ws)
            log.debug(f"訂閱 {ticker}，共 {len(self._ticker_subs[ticker])} 個訂閱者")

    def unsubscribe(self, ws: WebSocket, ticker: str):
        if ws in self._clients:
            self._clients[ws].discard(ticker)
            self._ticker_subs[ticker].discard(ws)

    def get_subscribed_tickers(self) -> Set[str]:
        """取得目前有人訂閱的所有 ticker"""
        return {t for t, subs in self._ticker_subs.items() if subs}

    async def broadcast_to_ticker(self, ticker: str, data: dict):
        """廣播給所有訂閱該 ticker 的客戶端"""
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
        """廣播給所有連線的客戶端"""
        message = json.dumps(data)
        dead = set()
        for ws in list(self._clients.keys()):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)
