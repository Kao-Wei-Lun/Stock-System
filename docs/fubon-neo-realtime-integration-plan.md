# 富邦 Neo API 即時行情整合規劃

**產出時間**：2026-04-10  
**SDK 版本**：fubon_neo v2.2.8  
**API 類型**：僅行情（Market Data）— 不含下單  
**規劃性質**：🔍 完整實作規劃，包含程式碼雛形

---

## 📑 目錄

1. [富邦 Neo API 功能總覽](#api-overview)
2. [整合架構設計](#architecture)
3. [分階段實作計畫](#phases)
4. [環境設定與安全](#environment)
5. [後端修改詳細規格](#backend-spec)
6. [前端修改詳細規格](#frontend-spec)
7. [資料流圖](#data-flow)
8. [風險與限制說明](#risks)
9. [驗收測試項目](#acceptance)

---

## 1. 富邦 Neo API 功能總覽 {#api-overview}

### 1.1 開放权限（您目前申請到的）

| 功能分類 | 権限 | 說明 |
|---------|------|------|
| 行情 | ✅ 開放 | 台股即時/歷史行情（含 WebSocket） |
| 證券業務 | ✅ 開放 | 帳戶查詢（持倉、現金）|
| 期貨業務 | ✅ 開放 | 期貨帳戶查詢 |
| 下單 | ❌ 未開放 | 本次整合不涉及 |

### 1.2 行情 API 能力矩陣

#### REST API（Web API）

| API 端點 | 功能 | 速率限制 | QuantVision 用途 |
|---------|------|---------|-----------------|
| `GET /intraday/quote/{symbol}` | 個股即時報價（含五檔） | 300/min | 取代 Yahoo Finance quote 輪詢 |
| `GET /intraday/candles/{symbol}` | 盤中分 K（1m/5m/10m/15m/30m/60m） | 300/min | 盤中分時圖資料 |
| `GET /intraday/trades/{symbol}` | 即時成交明細 | 300/min | 逐筆明細顯示 |
| `GET /intraday/volumes/{symbol}` | 分價量表 | 300/min | 委買委賣分布 |
| `GET /snapshot/quotes/{market}` | 全市場快照（TSE/OTC） | 300/min | 市場總覽熱力圖 |
| `GET /snapshot/movers/{market}` | 漲跌幅排行 | 300/min | 強弱勢股篩選 |
| `GET /snapshot/actives/{market}` | 成交量值排行 | 300/min | 熱門股清單 |
| `GET /historical/candles/{symbol}` | 歷史 K 線（最遠 2010） | 60/min | 取代 Yahoo Finance 歷史資料（台股）|
| `GET /historical/stats/{symbol}` | 近 52 週統計 | 60/min | 個股基本統計 |
| `GET /corporate-actions/dividends/` | 除權息資料 | 60/min | 事件標記 |
| `GET /corporate-actions/capital-changes/` | 資本變動（減資/分割） | 60/min | 股務事件 |
| `GET /technical/bb/{symbol}` | 布林通道（API 端計算） | — | 可選用，節省前端計算 |

> **速率限制彙整**：日內行情 300/min、歷史行情 60/min、WebSocket 最多 5 條連線×200 訂閱

#### WebSocket API

| 頻道 | 說明 | QuantVision 用途 |
|------|------|-----------------|
| `trades` | 即時成交 tick | 報價更新、K 棒更新 |
| `candles` | 即時分 K bar | 盤中圖表即時追加 |
| `books` | 最佳五檔委買委賣 | 盤口顯示 |
| `aggregates` | 聚合行情（OHLC + 五檔） | 報價面板完整資訊 |
| `indices` | 指數行情（大盤） | 大盤指數實時更新 |

#### 期貨行情

| API 端點 | 功能 | QuantVision 用途 |
|---------|------|-----------------|
| `GET /futopt/intraday/quote/{symbol}` | 期權即時報價 | 台指期、小台期報價 |
| `GET /futopt/intraday/candles/{symbol}` | 期貨分 K | 台指期分時圖 |
| `GET /futopt/intraday/products` | 期權契約列表 | 可用合約查詢 |

### 1.3 SDK 登入方式（v2.2.7+）

您持有的是 **API Key**，登入程式碼為：

```python
from fubon_neo.sdk import FubonSDK

sdk = FubonSDK()
# API Key 登入（v2.2.7+）
accounts = sdk.login(
    id="您的身分證字號",
    password="您的電子平台密碼",
    cert_path="憑證路徑（若憑證已匯出）",
    cert_password="憑證密碼",
    api_key="YOUR_FUBON_API_KEY"
)
sdk.init_realtime()  # 建立行情連線（WebSocket + REST）
```

> [!IMPORTANT]
> **憑證問題**：v2.2.7 的 API Key 登入仍需要「初次」用一般帳密+憑證進行連線測試。請確認是否已有憑證檔案。若尚未有憑證，需先以富邦網頁憑證匯出功能取得（v2.2.8 起支援）。

---

## 2. 整合架構設計 {#architecture}

### 2.1 現有架構 vs 目標架構

```
【現有架構】
前端 → FastAPI → YahooFinanceQuoteProvider → Yahoo Finance HTTP (30秒 polling)
                ↓
             ConnectionManager WS → 廣播前端

【目標架構（整合後）】
     富邦 SDK WebSocket ──────────────────────────────────────╮
         │ trades / candles / aggregates push                   │
         ↓                                                       │
FubonSDKManager (新增) ──→ FubonQuoteProvider (新增)           │
         │                        │                              │
         │                  QuoteProvider 抽象層 (現有)          │
         │                        ↓                              │
         ↓                  /api/quote/{ticker}                  │
ConnectionManager (現有) ← FubonRealtimeAdapter (新增) ←────────╯
         │
         ↓ WebSocket push (現有管道)
      前端 Vue (現有)
         │ 收到 is_delayed=false，顯示「即時」標記
```

### 2.2 模組依賴關係

```
backend/
├── fubon_provider.py          【新增】富邦 SDK 核心封裝
├── fubon_quote_provider.py    【新增】繼承 QuoteProvider 的富邦實作
├── fubon_futopt_provider.py   【新增】期貨行情模組（可選）
├── quote_provider.py          【保留】擴充 is_realtime 屬性
├── providers.py               【修改】加入富邦 provider 條件切換
├── scheduler.py               【修改】支援富邦 WS push 取代 polling
├── scheduler.py               【修改】加入 fubon_ws_listener_loop
├── background_tasks.py        【修改】加入富邦初始化任務
├── env_validation.py          【修改】新增富邦相關環境變數驗證
├── requirements.txt           【修改】加入 fubon_neo .whl 依賴
├── main.py                    【小修改】啟動時條件載入富邦
└── routers/
    └── market_data.py         【小修改】加入 /api/fubon/snapshot 端點
```

---

## 3. 分階段實作計畫 {#phases}

### Phase F1：SDK 環境建立（預估工時：1-2 小時）

**目標**：讓富邦 SDK 可在後端成功載入並登入。

- [ ] **F1.1** 安裝 SDK
  ```bash
  # 在 backend/ 目錄下
  pip install fubon_neo-2.2.8-cp37-abi3-win_amd64.whl
  # 也需同步更新 requirements.txt
  ```

- [ ] **F1.2** 在 `.env` 新增富邦相關環境變數
  ```env
  # 富邦 Neo API
  FUBON_USER_ID=您的身分證字號
  FUBON_PASSWORD=您的電子平台密碼
  FUBON_CERT_PATH=./certs/fubon.pfx
  FUBON_CERT_PASSWORD=您的登入ID（預設密碼）
  FUBON_API_KEY=YOUR_FUBON_API_KEY
  FUBON_ENABLED=true
  FUBON_WS_MODE=Speed
  ```
  > [!CAUTION]
  > API Key 已寫入 Key.txt，整合後請確保 `.env` 加入 `.gitignore`，API Key 不得提交版控！

- [ ] **F1.3** 在 `env_validation.py` 新增富邦環境變數讀取

- [ ] **F1.4** 建立 `backend/fubon_provider.py`（SDK 生命週期管理）

- [ ] **F1.5** 對 `backend/requirements.txt` 說明 .whl 安裝方式

---

### Phase F2：REST 報價整合（預估工時：2-3 小時）

**目標**：用富邦 REST API 取代 Yahoo Finance 台股個股報價。

- [ ] **F2.1** 建立 `backend/fubon_quote_provider.py`
  - 繼承 `QuoteProvider` 抽象類
  - 實作 `fetch_quote()` 呼叫富邦 `intraday/quote/{symbol}`
  - `is_delayed = False`、`quote_type = "realtime"`
  - 台股代碼轉換：`2330.TW` → `2330`（去掉 `.TW` 後綴）

- [ ] **F2.2** 在 `providers.py` 條件切換 QuoteProvider
  ```python
  if os.getenv("FUBON_ENABLED") == "true":
      from fubon_quote_provider import FubonQuoteProvider
      quote_provider = FubonQuoteProvider(fubon_manager)
  else:
      quote_provider = YahooFinanceQuoteProvider(fetcher)  # 原有
  ```

- [ ] **F2.3** 更新 `schemas.py` 的 `QuoteResponse`
  - `is_delayed: bool` → 富邦即時時為 `False`
  - 新增 `bid: float | None`（最佳買價）
  - 新增 `ask: float | None`（最佳賣價）
  - 新增 `bid_size: int | None`
  - 新增 `ask_size: int | None`

---

### Phase F3：WebSocket 即時推播（預估工時：3-4 小時）

**目標**：透過富邦 WS 接收即時 tick，推播給前端（取代 15 秒 polling）。

- [ ] **F3.1** 在 `fubon_provider.py` 實作 WebSocket 連線管理
  ```python
  class FubonSDKManager:
      def init(self):
          self.sdk = FubonSDK()
          self.accounts = self.sdk.login(...)
          self.sdk.init_realtime(Mode.Speed)
          self.ws_stock = self.sdk.marketdata.websocket_client.stock
          self.ws_futopt = self.sdk.marketdata.websocket_client.futopt
      
      def subscribe_stock(self, symbol: str, channel: str = "aggregates"):
          self.ws_stock.subscribe({"channel": channel, "symbol": symbol})
      
      def unsubscribe_stock(self, symbol: str, channel_id: str):
          self.ws_stock.unsubscribe({"id": channel_id})
  ```

- [ ] **F3.2** 在 `scheduler.py` 新增 `fubon_ws_listener_loop()`
  - 監聽富邦 WS `message` 事件
  - 解析 `event == "data"` 的行情訊息
  - 轉換格式後呼叫 `await ws_manager.broadcast_to_ticker(ticker, quote_payload)`
  - 同步尾盤報價到資料庫（呼叫 `db.upsert_market_quote()`）
  - 支援 `aggregates` / `trades` / `candles` 頻道路由分發

- [ ] **F3.3** 修改 `scheduler.py` 的 `realtime_polling_loop()`
  - 新增 `use_fubon_ws: bool` 參數
  - 若 `use_fubon_ws=True`：改為監控 WS 訂閱健康狀態（而非 polling）
  - 若 `use_fubon_ws=False`：保持原有 Yahoo Finance 輪詢行為（fallback）

- [ ] **F3.4** 修改 `ws_manager.py` 支援動態訂閱觸發富邦 WS
  - 當前端訂閱某 ticker 時，自動觸發富邦 WS 訂閱對應的 aggregates 頻道
  - 當前端取消訂閱時，取消富邦 WS 對應頻道（管理 channel_id 映射）

---

### Phase F4：歷史 K 線資料整合（預估工時：2-3 小時）

**目標**：用富邦歷史 API 取代台股的 Yahoo Finance/FinMind K 線資料來源。

- [ ] **F4.1** 在 `data_fetcher.py` 新增 `FubonDataFetcher` 類（或擴充現有 `DataFetcher`）
  - 實作 `fetch_tw_historical()` 調用富邦 `historical/candles/{symbol}`
  - 支援 timeframe 映射：`1d` → `D`、`1wk` → `W`、`1mo` → `M`、`1m` → `1`、`5m` → `5`
  - 處理分 K 資料限制（分 K 最多近 5 日，不可指定日期範圍）
  - 啟用 `adjusted=true` 取得還原股價

- [ ] **F4.2** 台股 K 線資料來源路由邏輯
  ```python
  async def fetch_and_store(ticker, period, interval):
      if fubon_enabled and ticker.endswith(".TW"):
          # 優先使用富邦 API
          return await fubon_fetcher.fetch_tw(ticker, period, interval)
      else:
          # fallback: Yahoo Finance（美股、其他）
          return await yahoo_fetcher.fetch(ticker, period, interval)
  ```

- [ ] **F4.3** 盤中分 K 資料整合
  - `interval == "1m"` 時：呼叫富邦 `intraday/candles/{symbol}?timeframe=1`
  - 返回今日即時 1 分 K 資料
  - 存入 DB（`interval="1m"` 分區）

---

### Phase F5：期貨行情整合（預估工時：2 小時）

**目標**：加入台指期/小台期的即時報價與分 K。

- [ ] **F5.1** 建立 `backend/fubon_futopt_provider.py`
  - 查詢台指期近月合約（`TXFB6` 格式，需自動識別近月）
  - 回傳台指期即時報價

- [ ] **F5.2** 新增後端 API endpoint `/api/futopt/quote/{symbol}`
  - 回傳期貨即時報價

- [ ] **F5.3** 期貨 WebSocket 訂閱
  - 使用 `sdk.marketdata.websocket_client.futopt` 訂閱台指期 `trades` 頻道
  - 廣播至前端

---

### Phase F6：前端顯示即時標記（預估工時：1-2 小時）

**目標**：前端能正確顯示「即時」vs「延遲」標記，符合規格書 §6.5 規範。

- [ ] **F6.1** 在 `AppNavbar.vue` 根據 `is_delayed` 顯示資料狀態標籤
  ```
  is_delayed = false → 顯示「🟢 即時」（綠點）
  is_delayed = true  → 顯示「🟡 盤後快照」（黃點）
  ```
  > [!IMPORTANT]
  > 規格書 §規範：禁止使用「即時」字樣用於非即時資料。僅 `is_delayed=false` 時才可顯示「即時」。

- [ ] **F6.2** 在 `ChartWorkspaceHeader.vue` 顯示資料時間戳
  - `quote_timestamp` 格式化為「HH:mm:ss」
  - 搭配「即時 / 快照 / 盤後」標籤

- [ ] **F6.3** 更新 `useChartEngine.js` / `useLWCChart.js`
  - 盤中接收到 WS `candles` 推播時，追加最新 K 棒到圖表
  - 接收 `aggregates` 時，更新當前 K 棒的 close/high/low/volume

- [ ] **F6.4** 五檔/盤口面板（新增）
  - 在 `ProChartTerminalWorkspace.vue` 右側新增一個迷你五檔面板
  - 顯示 `bids[0..4]` 和 `asks[0..4]`（來自 `books` 頻道）

---

### Phase F7：市場快照整合（預估工時：1-2 小時）

**目標**：在「市場總覽」頁面顯示整市場即時快照資料。

- [ ] **F7.1** 新增後端 API `/api/fubon/snapshot/{market}`
  - 查詢 `snapshot/quotes/{market}`（market: TSE / OTC）
  - 快取 60 秒，避免頻繁查詢

- [ ] **F7.2** 新增後端 API `/api/fubon/movers/{market}`
  - 查詢 `snapshot/movers/{market}?direction=up&change=percent`
  - 提供漲跌幅排行

- [ ] **F7.3** `MarketOverviewWorkspace.vue` 整合快照資料
  - 新增「盤中強勢股」、「盤中弱勢股」各 10 檔清單
  - 顯示即時漲跌幅

---

## 4. 環境設定與安全 {#environment}

### 4.1 .env 環境變數（新增）

```env
# ===========================
# Fubon Neo API 設定
# ===========================
FUBON_ENABLED=true

# 登入憑證（請勿提交版控）
FUBON_USER_ID=          # 身分證字號
FUBON_PASSWORD=         # 電子平台密碼
FUBON_CERT_PATH=./certs/fubon.pfx       # 憑證檔路徑（需先匯出）
FUBON_CERT_PASSWORD=    # 憑證密碼（預設為登入 ID）
FUBON_API_KEY=YOUR_FUBON_API_KEY

# 行情設定
FUBON_WS_MODE=Speed     # Speed（低延遲）| Normal（完整資訊）
FUBON_MARKET_SCOPE=TW   # TW（僅台股）| ALL（含期貨）
```

### 4.2 .gitignore 安全確認

> [!CAUTION]
> 執行前請確認以下項目已在 `.gitignore`：
> ```
> .env
> certs/
> *.pfx
> *.p12
> ```

### 4.3 .env.example 更新

在現有 `.env.example` 新增富邦設定的佔位符（不含實際金鑰）。

### 4.4 docker-compose.yml 環境變數

在 `docker-compose.yml` 的 backend service 新增：
```yaml
FUBON_ENABLED: ${FUBON_ENABLED:-false}
FUBON_USER_ID: ${FUBON_USER_ID:-}
FUBON_PASSWORD: ${FUBON_PASSWORD:-}
FUBON_CERT_PATH: ${FUBON_CERT_PATH:-}
FUBON_CERT_PASSWORD: ${FUBON_CERT_PASSWORD:-}
FUBON_API_KEY: ${FUBON_API_KEY:-}
FUBON_WS_MODE: ${FUBON_WS_MODE:-Speed}
```

> [!NOTE]
> Docker 部署時需要將憑證檔案掛載進容器：
> ```yaml
> volumes:
>   - ./certs:/app/certs:ro
> ```

---

## 5. 後端修改詳細規格 {#backend-spec}

### 5.1 新增：`backend/fubon_provider.py`

```python
"""
富邦 Neo SDK 生命週期管理器
封裝 SDK 登入、行情連線、WebSocket 訂閱
"""
import asyncio
import logging
import os
from typing import Callable, Dict, Optional

log = logging.getLogger(__name__)


class FubonSDKManager:
    """
    管理富邦 SDK 的登入、行情連線與 WebSocket 訂閱。
    設計為單例，由 providers.py 創建並注入各模組。
    """
    
    def __init__(self):
        self._sdk = None
        self._accounts = None
        self._ws_stock = None
        self._ws_futopt = None
        self._subscriptions: Dict[str, str] = {}  # ticker -> channel_id
        self._message_handlers: list[Callable] = []
        self.connected = False

    @property
    def enabled(self) -> bool:
        return os.getenv("FUBON_ENABLED", "false").lower() == "true"

    def init_sdk(self) -> bool:
        """初始化 SDK 並登入。回傳是否成功。"""
        if not self.enabled:
            log.info("富邦 SDK 未啟用 (FUBON_ENABLED=false)")
            return False
        try:
            from fubon_neo.sdk import FubonSDK, Mode
            self._sdk = FubonSDK()
            self._accounts = self._sdk.login(
                id=os.environ["FUBON_USER_ID"],
                password=os.environ["FUBON_PASSWORD"],
                cert_path=os.environ.get("FUBON_CERT_PATH", ""),
                cert_password=os.environ.get("FUBON_CERT_PASSWORD", ""),
                # api_key 參數（v2.2.7+）
            )
            mode_str = os.getenv("FUBON_WS_MODE", "Speed")
            mode = Mode.Normal if mode_str == "Normal" else Mode.Speed
            self._sdk.init_realtime(mode)
            self._ws_stock = self._sdk.marketdata.websocket_client.stock
            self.connected = True
            log.info("富邦 SDK 初始化成功 (帳號數: %s)", len(self._accounts or []))
            return True
        except Exception as exc:
            log.error("富邦 SDK 初始化失敗: %s", exc)
            self.connected = False
            return False

    def register_message_handler(self, handler: Callable):
        """註冊行情訊息處理器（支援多個）"""
        self._message_handlers.append(handler)

    def start_ws_stock(self):
        """啟動股票 WebSocket 連線並註冊 callback"""
        if not self._ws_stock:
            return
        def _on_message(message: str):
            import json
            try:
                data = json.loads(message)
                for handler in self._message_handlers:
                    handler(data)
            except Exception as e:
                log.debug("WS message parse error: %s", e)

        self._ws_stock.on("message", _on_message)
        self._ws_stock.on("connect", lambda: log.info("富邦 WS 連線成功"))
        self._ws_stock.on("disconnect", lambda code, msg: log.warning("富邦 WS 斷線: %s %s", code, msg))
        self._ws_stock.on("error", lambda err: log.error("富邦 WS 錯誤: %s", err))
        self._ws_stock.connect()

    def subscribe_stock(self, symbol: str, channel: str = "aggregates") -> Optional[str]:
        """訂閱個股頻道，回傳 channel_id"""
        if not self._ws_stock or not self.connected:
            return None
        key = f"{symbol}:{channel}"
        if key in self._subscriptions:
            return self._subscriptions[key]
        self._ws_stock.subscribe({"channel": channel, "symbol": symbol})
        log.debug("訂閱富邦 WS: %s / %s", symbol, channel)
        return key

    def unsubscribe_stock(self, symbol: str, channel: str = "aggregates"):
        """取消訂閱個股頻道"""
        key = f"{symbol}:{channel}"
        channel_id = self._subscriptions.pop(key, None)
        if channel_id and self._ws_stock:
            self._ws_stock.unsubscribe({"id": channel_id})

    def get_rest_stock(self):
        """取得 REST client（台股）"""
        if not self._sdk:
            return None
        return self._sdk.marketdata.rest_client.stock

    def get_rest_futopt(self):
        """取得 REST client（期貨）"""
        if not self._sdk:
            return None
        return self._sdk.marketdata.rest_client.futopt

    def shutdown(self):
        """優雅關閉 SDK 連線"""
        if self._ws_stock:
            try:
                self._ws_stock.disconnect()
            except Exception:
                pass
        self.connected = False
        log.info("富邦 SDK 已關閉")
```

### 5.2 新增：`backend/fubon_quote_provider.py`

```python
"""
富邦即時報價 Provider
實作 QuoteProvider 抽象類，提供台股真實即時報價。
"""
from __future__ import annotations
import logging
import time
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from quote_provider import QuoteProvider

log = logging.getLogger(__name__)


def _tw_ticker_to_fubon(ticker: str) -> Optional[str]:
    """將 QuantVision 台股 ticker 格式轉換為富邦格式
    2330.TW → 2330
    2330.TWO → 2330（上櫃亦可查）
    ^TWII → IR0001（加權指數）
    """
    if ticker.endswith(".TW"):
        return ticker[:-3]
    if ticker.endswith(".TWO"):
        return ticker[:-4]
    if ticker == "^TWII":
        return "IR0001"  # 加權指數
    return None  # 非台股，不支援


class FubonQuoteProvider(QuoteProvider):
    provider_name = "fubon_neo"
    quote_type = "realtime"
    is_delayed = False

    def __init__(self, fubon_manager):
        self._fubon = fubon_manager

    async def fetch_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        fubon_symbol = _tw_ticker_to_fubon(ticker)
        if not fubon_symbol:
            # 非台股（美股等），回傳 None 讓上層 fallback 到 Yahoo Finance
            return None
        
        rest = self._fubon.get_rest_stock()
        if not rest:
            return None

        try:
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: rest.intraday.quote(symbol=fubon_symbol)
            )
            if not response or not response.data:
                return None
            data = response.data

            # 轉換為 QuantVision QuoteResponse 格式
            synced_at = datetime.now(timezone.utc).isoformat()
            last_updated_ts = getattr(data, "lastUpdated", None)
            quote_timestamp = None
            if last_updated_ts:
                # 富邦時間為微秒級 Unix timestamp
                quote_timestamp = datetime.fromtimestamp(
                    last_updated_ts / 1e6, tz=timezone.utc
                ).isoformat()

            return {
                "ticker": ticker,
                "name": getattr(data, "name", None),
                "source": self.provider_name,
                "quote_type": self.quote_type,
                "is_delayed": self.is_delayed,
                "price": getattr(data, "closePrice", None),
                "open": getattr(data, "openPrice", None),
                "high": getattr(data, "highPrice", None),
                "low": getattr(data, "lowPrice", None),
                "prev_close": getattr(data, "previousClose", None),
                "change": getattr(data, "change", None),
                "change_pct": getattr(data, "changePercent", None),
                "volume": getattr(data, "total", {}).get("tradeVolume") if hasattr(data, "total") else None,
                "bid": data.bids[0]["price"] if hasattr(data, "bids") and data.bids else None,
                "ask": data.asks[0]["price"] if hasattr(data, "asks") and data.asks else None,
                "bid_size": data.bids[0]["size"] if hasattr(data, "bids") and data.bids else None,
                "ask_size": data.asks[0]["size"] if hasattr(data, "asks") and data.asks else None,
                "market_cap": None,
                "currency": "TWD",
                "quote_timestamp": quote_timestamp,
                "synced_at": synced_at,
                "ts": int(time.time() * 1000),
            }
        except Exception as exc:
            log.warning("富邦 quote 查詢失敗 %s: %s", ticker, exc)
            return None


class HybridQuoteProvider(QuoteProvider):
    """
    混合 Provider：台股用富邦即時，美股等用 Yahoo Finance。
    """
    provider_name = "hybrid"
    quote_type = "mixed"
    is_delayed = True  # 預設，依實際回傳覆蓋

    def __init__(self, fubon_provider: FubonQuoteProvider, yahoo_provider: QuoteProvider):
        self._fubon = fubon_provider
        self._yahoo = yahoo_provider

    async def fetch_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        # 嘗試富邦（台股）
        result = await self._fubon.fetch_quote(ticker)
        if result:
            return result
        # Fallback: Yahoo Finance（美股、無法識別的代碼）
        return await self._yahoo.fetch_quote(ticker)
```

### 5.3 修改：`backend/providers.py`

```python
# 在現有 providers.py 底部新增：

from fubon_provider import FubonSDKManager
from fubon_quote_provider import FubonQuoteProvider, HybridQuoteProvider
import os

# 富邦 SDK 管理器（單例）
fubon_manager = FubonSDKManager()

# 條件切換 quote provider
if fubon_manager.enabled:
    _fubon_qp = FubonQuoteProvider(fubon_manager)
    quote_provider = HybridQuoteProvider(_fubon_qp, YahooFinanceQuoteProvider(fetcher))
else:
    quote_provider = YahooFinanceQuoteProvider(fetcher)

# 重新初始化 alert_engine 使用新的 quote_provider
alert_engine = AlertEngine(db, quote_provider, external_notifier=external_notifier)
```

### 5.4 修改：`backend/scheduler.py`

新增 `fubon_ws_listener_loop()` coroutine：

```python
async def fubon_ws_listener_loop(
    fubon_manager,
    broadcast_to_ticker,
    store_quote_to_db,
    logger=None,
) -> None:
    """
    啟動富邦 WS 連線，接收 push 行情並廣播給前端。
    等同於取代 realtime_polling_loop 的角色（台股部分）。
    """
    log = logger or logging.getLogger(__name__)
    if not fubon_manager.enabled or not fubon_manager.connected:
        log.info("富邦 WS 未啟用，略過行情監聽迴圈")
        return

    import asyncio
    queue: asyncio.Queue = asyncio.Queue()

    def _on_fubon_message(data: dict):
        asyncio.get_event_loop().call_soon_threadsafe(queue.put_nowait, data)

    fubon_manager.register_message_handler(_on_fubon_message)
    fubon_manager.start_ws_stock()

    log.info("富邦 WS 行情監聽迴圈啟動")
    while True:
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=60)
            event = msg.get("event")
            channel = msg.get("channel")
            
            if event != "data":
                continue
            
            raw = msg.get("data", {})
            symbol = raw.get("symbol")
            if not symbol:
                continue

            # 轉換為台股 ticker 格式
            ticker = f"{symbol}.TW"  # 簡化，實際需判斷 OTC

            if channel == "aggregates":
                payload = _transform_aggregates_to_quote(ticker, raw)
                if payload:
                    await store_quote_to_db(payload)
                    await broadcast_to_ticker(ticker, {
                        "type": "quote",
                        "ticker": ticker,
                        "data": payload,
                        "ts": int(time.time() * 1000),
                    })
            elif channel == "candles":
                # 推播即時 K 棒更新
                await broadcast_to_ticker(ticker, {
                    "type": "candle",
                    "ticker": ticker,
                    "data": raw,
                    "ts": int(time.time() * 1000),
                })
        except asyncio.TimeoutError:
            log.debug("富邦 WS 60 秒無資料（正常，非交易時段）")
        except Exception as exc:
            log.warning("富邦 WS 行情處理失敗: %s", exc)
            await asyncio.sleep(5)


def _transform_aggregates_to_quote(ticker: str, raw: dict) -> dict | None:
    """將富邦 aggregates 格式轉換為 QuantVision QuoteResponse 格式"""
    import time
    close_price = raw.get("closePrice")
    if close_price is None:
        return None
    
    bids = raw.get("bids") or []
    asks = raw.get("asks") or []
    total = raw.get("total") or {}
    last_updated = raw.get("lastUpdated")

    return {
        "ticker": ticker,
        "source": "fubon_neo",
        "quote_type": "realtime",
        "is_delayed": False,
        "price": close_price,
        "open": raw.get("openPrice"),
        "high": raw.get("highPrice"),
        "low": raw.get("lowPrice"),
        "prev_close": raw.get("previousClose"),
        "change": raw.get("change"),
        "change_pct": raw.get("changePercent"),
        "volume": total.get("tradeVolume"),
        "bid": bids[0]["price"] if bids else None,
        "ask": asks[0]["price"] if asks else None,
        "bid_size": bids[0]["size"] if bids else None,
        "ask_size": asks[0]["size"] if asks else None,
        "currency": "TWD",
        "quote_timestamp": str(last_updated) if last_updated else None,
        "synced_at": __import__("datetime").datetime.utcnow().isoformat(),
        "ts": int(time.time() * 1000),
    }
```

### 5.5 修改：`backend/requirements.txt`

```
# 現有依賴（保留）
fastapi==0.115.0
uvicorn[standard]==0.30.6
requests==2.32.3
aiomysql==0.2.0
pandas==2.2.3
numpy==2.1.3
python-multipart==0.0.12
python-dotenv==1.0.1
pytest==8.3.5
httpx==0.27.2
cryptography==44.0.2
yfinance>=0.2.55,<0.3.0
FinMind>=1.7.0,<2.0.0
SQLAlchemy>=2.0.0,<3.0.0

# 富邦 Neo SDK（需手動安裝 .whl，不可透過 PyPI 安裝）
# 安裝指令：pip install fubon_neo-2.2.8-cp37-abi3-win_amd64.whl
# 注意：fubon_neo 不在 PyPI，請確保 .whl 檔案存在
```

---

## 6. 前端修改詳細規格 {#frontend-spec}

### 6.1 修改：即時狀態標籤（`AppNavbar.vue`）

在 Navbar 報價區塊加入資料來源標籤：

```vue
<template>
  <!-- 現有的搜尋和工具區塊之後加入 -->
  <div class="quote-source-badge" :class="quoteSourceClass">
    <span class="source-dot"></span>
    <span>{{ quoteSourceLabel }}</span>
  </div>
</template>

<script setup>
// 根據 quote.is_delayed 決定顯示
const quoteSourceLabel = computed(() => {
  if (props.activeQuote?.is_delayed === false) return '即時';
  if (props.activeQuote?.quote_type === 'delayed_snapshot') return '延遲快照';
  return '盤後';
});
const quoteSourceClass = computed(() => ({
  'realtime': props.activeQuote?.is_delayed === false,
  'delayed': props.activeQuote?.is_delayed !== false,
}));
</script>
```

### 6.2 新增：五檔盤口組件（`BidAskPanel.vue`）

```
frontend/src/components/terminal/
└── BidAskPanel.vue    【新增】五檔買賣盤顯示
```

核心功能：
- 顯示 `bids[0..4]`（委買）和 `asks[0..4]`（委賣）
- 買賣量以視覺進度條顯示（紅綠對比）
- 即時更新（透過現有 WS 接收 `books` 頻道資料）

### 6.3 修改：K 棒即時追加（`useLWCChart.js`）

新增 `appendRealtimeCandle()` 方法：

```javascript
// 處理從後端 WS 接收到的即時 candle push
function appendRealtimeCandle(candleData) {
  if (!candleSeries.value) return;
  // 富邦 candle 格式轉換
  const bar = {
    time: Math.floor(new Date(candleData.date).getTime() / 1000),
    open: candleData.open,
    high: candleData.high,
    low: candleData.low,
    close: candleData.close,
  };
  candleSeries.value.update(bar);  // LWC update() 自動處理追加或更新
}
```

### 6.4 修改：WS 訊息處理（`useDashboard.js`）

在現有 WebSocket 訊息處理器中新增 `candle` 類型：

```javascript
// 現有 quote 處理
case 'quote':
  updateQuote(msg.ticker, msg.data);
  break;
// 新增 candle 處理
case 'candle':
  if (msg.ticker === currentTicker.value) {
    lwcChart.appendRealtimeCandle(msg.data);
  }
  break;
```

---

## 7. 資料流圖 {#data-flow}

### 7.1 即時報價流程

```
富邦 WebSocket ──→ FubonSDKManager._ws_stock
    │ channel=aggregates push
    ▼
fubon_ws_listener_loop()（scheduler.py）
    │ 解析行情 → 標準化為 QuoteResponse 格式
    ├──→ db.upsert_market_quote()（落地到 DB）
    └──→ ws_manager.broadcast_to_ticker()
              │
              ▼（FastAPI WebSocket）
           前端 Vue（現有 WS 連線）
              │ 收到 type="quote"（is_delayed=false）
              ▼
         更新報價面板、K 棒、警報評估
```

### 7.2 歷史 K 線流程

```
前端請求 /api/kline/2330.TW?interval=1d
    │
    ▼
market_data.py: _get_ohlc_payload()
    │ 台股 + fubon_enabled?
    ├──→ YES → FubonDataFetcher.fetch_tw_historical()
    │              │ 富邦 historical/candles/2330
    │              ▼ 存入 DB
    └──→ NO  → DataFetcher.fetch_and_store()（Yahoo Finance，原有）
    │
    ▼
db.get_ohlcv() → 回傳前端
```

### 7.3 盤中分 K 流程

```
前端請求 /api/kline/2330.TW?interval=1m
    │ 台股 + fubon_enabled?
    ▼
FubonDataFetcher.fetch_tw_intraday_candles("2330", timeframe="1")
    │ 富邦 intraday/candles/2330?timeframe=1
    │ 返回今日近 5 日 1 分 K
    ▼
存入 DB（interval=1m 資料）→ 回傳前端
    │
    ▼
前端 LWC 圖表顯示
    │
    ▼（盤中實時更新）
富邦 WS candles push → appendRealtimeCandle() → LWC.update() 追加最新 K 棒
```

---

## 8. 風險與限制說明 {#risks}

### 8.1 技術限制

| 風險項目 | 說明 | 緩解策略 |
|---------|------|---------|
| **SDK 僅支援 Windows** | `fubon_neo-2.2.8-cp37-abi3-win_amd64.whl` | Docker 需用 Windows 容器，或用 Linux 版本 `.whl` |
| **憑證問題** | 首次登入需一般帳密+憑證，API Key 無法繞過 | 先完成憑證匯出步驟再整合 |
| **SDK 阻塞 I/O** | 富邦 SDK 為同步 API，需包裝在 `asyncio.to_thread()` 或 `executor` 中 | 使用 `loop.run_in_executor()` 包裝所有 SDK 呼叫 |
| **WebSocket 斷線重連** | 富邦文件指出斷線後需手動重連並重新訂閱 | 在 `handle_disconnect` 中實作自動重連 + 重訂閱邏輯 |
| **速率限制** | 日內行情 300/min，歷史 60/min | 加入 token bucket 限速器，自動降速 |
| **分 K 歷史限制** | 分 K 最多只能查近 5 日，無法補充更長歷史 | 超過 5 日的分 K 歷史仍依賴 Yahoo（美股）或保留空白 |
| **美股不支援** | 富邦行情僅台股，美股仍依賴 Yahoo Finance | HybridQuoteProvider 自動 fallback |
| **API Key 安全** | Key 一旦洩漏需立即到富邦後台停用 | 嚴格管理 `.env`，不提交版控 |

### 8.2 資料規範（規格書 §6.5）

富邦 Neo 的行情資料由**時報資訊**與**群馥科技**提供，使用規範：
- 資料僅供「個人」參考，不得轉售或轉授權
- 顯示時需明確區分「即時 (`is_delayed=false`)」與「延遲」
- 成交量不含零股及鉅額交易

### 8.3 盤中/盤後行為

| 時段 | 富邦提供 | 系統行為 |
|------|---------|---------|
| 盤中（09:00~13:30）| WebSocket push | 即時更新 |
| 收盤後 | REST 最後快照 | `quote_type = "snapshot"` |
| 盤前/休市 | 無推播 | 使用本地 DB 最後快照 |

---

## 9. 驗收測試項目 {#acceptance}

### 9.1 後端驗收測試

```python
# tests/test_fubon_integration.py
import pytest

class TestFubonProvider:
    def test_sdk_init_success(self):
        """SDK 可正常登入"""
        from fubon_provider import FubonSDKManager
        manager = FubonSDKManager()
        if manager.enabled:
            assert manager.init_sdk() == True
            assert manager.connected == True

    def test_fubon_quote_fetch_tw_stock(self):
        """富邦 quote 可正確回傳台股報價（2330）"""
        quote = fubon_quote_provider.fetch_quote("2330.TW")
        assert quote is not None
        assert quote["is_delayed"] == False
        assert quote["price"] is not None
        assert quote["source"] == "fubon_neo"

    def test_hybrid_provider_fallback_us_stock(self):
        """美股 AAPL 自動 fallback 至 Yahoo Finance"""
        quote = hybrid_provider.fetch_quote("AAPL")
        assert quote is not None
        assert quote["source"] == "yahoo_finance"  # fallback

    def test_tw_ticker_conversion(self):
        """代碼格式轉換正確"""
        from fubon_quote_provider import _tw_ticker_to_fubon
        assert _tw_ticker_to_fubon("2330.TW") == "2330"
        assert _tw_ticker_to_fubon("6505.TW") == "6505"
        assert _tw_ticker_to_fubon("^TWII") == "IR0001"
        assert _tw_ticker_to_fubon("AAPL") is None
```

### 9.2 前端驗收標準

- [ ] 台股標的的報價面板顯示「🟢 即時」標籤（非「延遲快照」）
- [ ] 盤中切換到台股標的時，K 棒每分鐘更新（WS push）
- [ ] 美股標的（AAPL 等）仍正常顯示（Yahoo Finance fallback）
- [ ] WS 斷線後 30 秒內自動重連
- [ ] `QuoteResponse.is_delayed = false` 時，前端不顯示「延遲」字樣

### 9.3 效能驗收目標

| 指標 | 目標值 |
|------|-------|
| 台股報價延遲（收到 WS push → 前端顯示） | < 500ms |
| 台股 K 棒即時更新延遲 | < 1s |
| API 回應時間（/api/quote） | < 200ms |
| WS 斷線重連時間 | < 30s |

---

## 📎 相關文件

| 文件 | 路徑 |
|------|------|
| 富邦 SDK 完整文件 | `docs/llms-full.txt` |
| 富邦 SDK 安裝包 | `docs/fubon_neo-2.2.8-cp37-abi3-win_amd64.whl` |
| API Key | `docs/API Key.txt`（**請勿提交版控**） |
| LWC 整合規劃 | `docs/openstock-lwc-integration-plan.md` |
| 系統修改計畫 | `docs/system-modification-plan.md` |
| 產品規格書 | `docs/quantvision-product-spec.md` |

---

## ⚠️ 執行前必要準備事項

> [!CAUTION]
> **執行實作前請先完成以下確認**：
>
> 1. **憑證匯出（必要）**：
>    - 登入富邦網頁平台 → 金鑰申請頁面 → 匯出憑證
>    - 將 `.pfx` 憑證檔放入 `backend/certs/fubon.pfx`
>
> 2. **連線測試（必要）**：
>    - 使用富邦提供的「連線測試小幫手」確認帳密+憑證可連線
>    - 首次連線**必須使用一般帳密+憑證**，不可直接使用 API Key
>
> 3. **API Key 安全（必要）**：
>    - `docs/API Key.txt` 的 Key 確認已加入 `.gitignore`（請勿提交）
>    - Key 寫入 `.env` 後刪除或隔離原始文字檔
>
> 4. **Python 版本確認**：
>    - SDK 支援 Python 3.8–3.13（不支援 3.14）
>    - `python --version` 確認版本

---

*最後更新：2026-04-10 | 規劃版本：v1.0 | 基於 fubon_neo v2.2.8 文件*
