# QuantVision Pro — 全球股市監控系統

即時監控系統，整合 Yahoo Finance 真實資料，存入本地 SQLite 資料庫。

## 📁 專案結構

```
quantvision/
├── backend/
│   ├── main.py           # FastAPI 主程式 (API + WebSocket)
│   ├── database.py       # SQLite 資料庫層 (aiosqlite)
│   ├── data_fetcher.py   # Yahoo Finance 資料抓取器
│   ├── ws_manager.py     # WebSocket 連線管理
│   ├── requirements.txt  # Python 依賴
│   └── quantvision.db    # SQLite 資料庫 (自動建立)
├── frontend/
│   └── index.html        # 前端監控介面
└── scripts/
    ├── start.sh          # Mac/Linux 啟動腳本
    └── start.bat         # Windows 啟動腳本
```

## 🚀 快速啟動

### 系統需求
- Python 3.10 或以上
- 網路連線（用於 Yahoo Finance 資料）

### Mac / Linux

```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

### Windows

```
雙擊 scripts\start.bat
```

### 手動啟動

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

然後用瀏覽器開啟 `frontend/index.html`。

---

## 📡 API 文件

啟動後訪問：[http://localhost:8000/docs](http://localhost:8000/docs)

### 主要端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/watchlist` | GET | 取得自選股清單+報價 |
| `/api/kline/{ticker}` | GET | 取得 K 線歷史資料 |
| `/api/quote/{ticker}` | GET | 取得即時報價 |
| `/api/info/{ticker}` | GET | 取得股票基本資訊 |
| `/api/sync/{ticker}` | POST | 手動同步指定股票 |
| `/api/search?q=` | GET | 搜尋股票 |
| `/api/db/stats` | GET | 資料庫統計 |
| `/ws` | WebSocket | 即時推送 |

### WebSocket 協定

```json
// 訂閱
{ "action": "subscribe",   "ticker": "AAPL" }

// 取消訂閱
{ "action": "unsubscribe", "ticker": "AAPL" }

// 收到推送
{ "type": "quote", "ticker": "AAPL", "data": { ... }, "ts": 1700000000000 }
```

---

## 🗄️ 資料庫

SQLite 資料庫位於 `backend/quantvision.db`，包含：

- **ohlcv** — K 線資料（日線 / 週線 / 月線 / 小時線）
- **stock_info** — 股票基本資訊（市值、PE、52週高低點等）
- **sync_log** — 同步記錄
- **alerts** — 警報設定

---

## 📈 功能說明

### 自動資料同步
- 首次啟動自動下載 24 支股票近 2 年歷史資料
- 每 15 秒輪詢有訂閱者的股票最新報價
- 手動點擊「↻ 同步」可立即更新

### 技術指標
- **疊加型**：MA20/50/200、EMA12、布林通道、VWAP
- **副圖**：RSI(14)、MACD(12,26,9)、KD Stochastic

### 回測引擎
- 使用真實歷史 K 線執行策略回測
- 支援 MA/RSI/MACD/布林通道策略
- 輸出：報酬率、勝率、最大回撤、夏普比率

### 警報系統
- 設定條件（價格、RSI 等）
- 即時報價更新時自動觸發
- 通知顯示在右上角

---

## ⚙️ 自訂設定

### 新增監控股票

編輯 `backend/main.py`，在 `DEFAULT_WATCHLIST` 中加入代號：

```python
DEFAULT_WATCHLIST = [
    "AAPL", "TSLA",
    "2330.TW",   # 台積電
    "0700.HK",   # 騰訊
    "BTC-USD",   # 比特幣
    "^GSPC",     # S&P 500
    # 加入更多...
]
```

### 調整更新頻率

在 `main.py` 修改輪詢間隔（預設 15 秒）：

```python
await asyncio.sleep(15)  # 改為你想要的秒數
```

---

## ⚠️ 注意事項

- Yahoo Finance 資料有 15~20 分鐘延遲（非即時）
- 請勿過於頻繁請求，避免被封鎖（已內建速率限制）
- 回測結果僅供參考，不構成投資建議
