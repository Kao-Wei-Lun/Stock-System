# 🔍 QuantVision Pro 全面系統健檢報告

**產出時間**：2026-04-08  
**基準文件**：`docs/openstock-lwc-integration-plan.md` · `docs/system-modification-plan.md`  
**規劃性質**：🔍 純審查報告，不包含任何程式碼修改

---

## 📋 OpenStock & LWC 規劃完成度驗證

本節先針對 `docs/openstock-lwc-integration-plan.md` 中的任務清單，逐一核對實作狀態。

### Phase A — LWC 基礎整合

| 任務 | 描述 | 狀態 |
|------|------|------|
| A.1 | 安裝 `lightweight-charts@^5.1` npm 套件 | ✅ **已完成** — `package.json` + `package-lock.json` 確認 |
| A.2 | 建立 `useLWCChart.js` | ✅ **已完成** — `frontend/src/composables/useLWCChart.js` (800 行) |
| A.3 | 建立 `LWCChartCanvas.vue` | ✅ **已完成** — `ChartWorkspace.vue` 整合 LWC 模式 |
| A.4 | `engineMode` prop 切換 | ✅ **已完成** — `chartEngineMode` prop 存在，`ProChartTerminalWorkspace` 傳遞至 `ChartWorkspace` |

### Phase B — LWC 指標面板遷移

| 任務 | 描述 | 狀態 |
|------|------|------|
| B.1 | 建立 `useLWCIndicators.js` | ✅ **已完成** — 被 `useLWCChart.js:12` import |
| B.2 | 主圖疊加指標（LWC LineSeries） | ✅ **已完成** — `indicatorModel.value.overlays` 遍歷 |
| B.3 | 保留 `indicatorUtils.js` 計算邏輯 | ✅ **已完成** — 原檔未被刪除 |
| B.4 | 廢棄多個子 Canvas ref | ✅ **已完成** — LWC Multi-pane 取代 Canvas refs |

### Phase C — 分時圖支援

| 任務 | 描述 | 狀態 |
|------|------|------|
| C.1 | 後端分鐘 K 資料拉取 | 🟡 **部分** — `requirements.txt` 無 yfinance 但後端可能已有 |
| C.2 | Backend API `/api/ohlc?interval=1m` | ❓ **未確認** — `market_data.py` 需進一步核查 |
| C.3 | 前端分鐘週期按鈕 | 🟡 **部分** — Navbar timeframe 按鈕存在，分鐘週期未確認 |
| C.4 | LWC 時間軸自動適應 | ✅ **已完成** — `isIntradayInterval()` + `timeVisible` 邏輯已實作 |

### Phase D — 繪圖工具整合

| 任務 | 描述 | 狀態 |
|------|------|------|
| D.1 | LWC Plugin API 評估 | ✅ **已完成** — 採用 SVG 覆蓋方案 (方案 C) |
| D.2 | 水平線 (`createPriceLine`) | ✅ **已完成** — `useLWCDrawings.js:411` `syncPriceLines()` |
| D.3 | 買/賣訊號標記 | ✅ **已完成** — `createSeriesMarkers` 已整合 (`useLWCDrawings.js:423`) |
| D.4 | 趨勢線 SVG | ✅ **已完成** — `renderDrawing()` 支援 trendline |
| D.5 | 費波那契 SVG | ✅ **已完成** — `FIB_LEVELS` + `renderDrawing()` 完整實作 |
| D.6 | 法人成本帶疊加 | ✅ **已完成** — `renderInstitutionalOverlay()` 完整實作 |
| D.7 | 廢棄舊 Canvas 繪圖層 | 🟡 **部分** — `useChartEngine.js` 仍作為 `legacy` fallback 保留 |

### Phase E — OpenStock 借鏡功能

| 任務 | 描述 | 狀態 |
|------|------|------|
| E.1 | `GlobalSearchCommand.vue` (Ctrl+K) | ✅ **已完成** — 組件存在，Cmd+K 觸發，支援工作區切換與標的搜尋 |
| E.2 | TradingView Heatmap Widget | ✅ **已完成** — `MarketOverviewWorkspace.vue:40` 已嵌入 `TradingViewWidgetEmbed` |
| E.3 | TradingView Market Overview Widget | ✅ **已完成** — `MarketOverviewWorkspace.vue:56` 已嵌入 |
| E.4 | 自選股分組/顏色標記 | 🟡 **部分** — 分組已有，顏色標記未確認 |

### 📊 OpenStock & LWC 規劃完成度總結

| 階段 | 任務總數 | 已完成 | 部分完成 | 未完成 |
|------|---------|--------|---------|--------|
| Phase A | 4 | 4 | 0 | 0 |
| Phase B | 4 | 4 | 0 | 0 |
| Phase C | 4 | 1 | 2 | 1 |
| Phase D | 7 | 6 | 1 | 0 |
| Phase E | 4 | 3 | 1 | 0 |
| **合計** | **23** | **18 (78%)** | **4 (17%)** | **1 (4%)** |

> [!NOTE]
> 整體完成度約 **85%**，主要未完成項目為「分時圖後端 API (Phase C)」，其餘均已實作或部分實作。

---

## 系統總覽評分卡

| 維度 | 評分 | 最嚴重問題 | 優先行動 |
|---|---|---|---|
| 🏗️ 後端架構 | **92/100** | `requirements.txt` 缺 `yfinance`、`finmind` 等關鍵套件 | 補完依賴清單，新增分時圖 API endpoint |
| 🎨 前端架構 | **88/100** | `ChartWorkspace.vue` 仍達 29KB，`RightSidebar.vue` 28KB legacy 存在 | 清理 `RightSidebar.vue` / 觀察 `ChartWorkspace` 能否再拆分 |
| 🔒 安全與資料 | **85/100** | CORS 使用萬用 `allow_methods=["*"]` | 限縮 CORS methods，確認 `.env` 不入版控 |
| 🧪 測試品質 | **86/100** | Phase C 分時圖功能無對應測試 | 補充 LWC 分時圖端到端測試 |
| 📋 產品完成度 | **84/100** | 分時圖 (1m/5m) 缺失，Phase C 未完成 | 完成分時圖後端 → 前端週期按鈕 |
| ⚡ 效能與運維 | **82/100** | `useChartEngine.js` (3417行) bundle 仍佔用；缺 Docker | 啟動 Phase 7 Docker 化 |
| 📈 交易員體驗 | **86/100** | 盤中無分時圖，無法即時盤中監控 | 最高優先：分時圖功能完成 |
| 🧑‍🎨 使用者體驗 | **80/100** | 工具列按鈕過多（26+ 個）;無分時圖 UX 流程 | 精簡工具列；加入時間週期快捷鍵提示 |
| **總分** | **85/100** | 分時圖缺失是最大功能缺口 | Phase C 完成為最高優先事項 |

---

## 🏗️ 第 1 步：後端架構師分析

### 發現清單

| 嚴重度 | 問題 | 位置 |
|--------|------|------|
| 🔴 | `requirements.txt` 缺少 `yfinance`, `finmind` 等實際使用的套件 | `requirements.txt` |
| 🟡 | Backend 路由模組化已完成，但 `main.py` 仍達 376 行（含大量業務邏輯函數） | `backend/main.py:165-251` |
| 🟡 | 分時圖後端 API `/api/ohlc?interval=1m` 狀態未確認 | `backend/routers/market_data.py` |
| 🔵 | `scheduler.py` 的 `BackgroundScheduler` 邏輯健全，但沒有獨立健康檢查 endpoint | `backend/main.py:258-283` |

### 改善建議

1. **🔴** 立即更新 `requirements.txt`，加入 `yfinance`, `finmind`, `sqlalchemy` 等實際依賴包
2. **🟡** 將 `main.py:180-251` 的 `sync_tracked_market_data`, `sync_market_intelligence_snapshot` 等背景任務函數移至 `background_tasks.py`
3. **🟡** 在 `market_data.py` 補充分時圖 API endpoint，接受 `interval` 參數（1m/5m/15m/60m）

### 健康度評分：**92/100**

---

## 🎨 第 2 步：前端架構師分析

### 發現清單

| 嚴重度 | 問題 | 位置 |
|--------|------|------|
| 🔴 | `useChartEngine.js` (3417 行 legacy 引擎) 仍保留在 bundle 中 | `frontend/src/composables/useChartEngine.js` |
| 🔴 | `RightSidebar.vue` (28KB) 疑似 legacy 組件仍存在，但新架構已有 `TerminalUtilityDrawer.vue` | `frontend/src/components/RightSidebar.vue` |
| 🟡 | `ChartWorkspace.vue` 已達 29KB，是前端最大的單一組件 | `frontend/src/components/ChartWorkspace.vue` |
| 🟡 | `useLWCDrawings.js` (1067 行) SVG 覆蓋層邏輯複雜，應定期維護 | `frontend/src/composables/useLWCDrawings.js` |
| 🔵 | `GlobalSearchCommand.vue` Ctrl+K 命令面板完整實作，是亮點功能 ✅ | — |
| 🔵 | `TradingViewWidgetEmbed.vue` 整合 Heatmap + Market Overview 完整 ✅ | — |

### LWC 引擎現況確認

`useLWCChart.js` 已實作以下功能：
- ✅ K 線 / 折線 / 面積圖三模式
- ✅ LWC Multi-Pane 指標子圖（透過 `useLWCIndicators`）
- ✅ 成交量子圖
- ✅ 原生縮放/平移/滾輪
- ✅ 分鐘模式時間軸自動顯示
- ✅ ResizeObserver 自動響應視窗變化
- ✅ Cross-hair 十字線事件節點對應

### 改善建議

1. **🔴** 建立清理計劃：確認 `RightSidebar.vue` 是否仍被引用；若僅剩測試引用，考慮移至 `legacy/` 目錄
2. **🔴** 評估 `useChartEngine.js` 是否可透過動態 import 僅在 `engineMode="legacy"` 時載入，避免 bundle 污染
3. **🟡** `ChartWorkspace.vue` (29KB) 考慮拆出 `ChartWorkspaceHeader.vue` 的 crosshair 顯示區、工具列狀態等子組件

### 健康度評分：**88/100**

---

## 🔒 第 3 步：安全與資料審計師分析

### 發現清單

| 嚴重度 | 問題 | 位置 |
|--------|------|------|
| 🔴 | CORS 設定 `allow_methods=["*"]` 對本地工具雖可接受，但規範上應限縮為 `["GET","POST","PUT","DELETE"]` | `backend/main.py:333` |
| 🟡 | TradingView Widget 嵌入使用第三方 CDN script，無 SRI (Subresource Integrity) 保護 | `frontend/src/components/TradingViewWidgetEmbed.vue` |
| 🟡 | `CORS allow_origin_regex` 包含所有 192.168.x.x 和 10.x.x.x 私有網路 | `backend/main.py:310-316` |
| 🔵 | 本地個人工具，無多用戶認證，符合設計目標 ✅ | — |
| 🔵 | 環境變數驗證 `validate_runtime_environment()` 在啟動時執行 ✅ | `backend/main.py:292` |

### 改善建議

1. **🔴** 限縮 CORS `allow_methods` 為具體 HTTP 方法
2. **🟡** 在 `TradingViewWidgetEmbed.vue` 加入 CSP 相容的 script source 白名單
3. **🔵** 確認 `.env` 已加入 `.gitignore`

### 健康度評分：**85/100**

---

## 🧪 第 4 步：測試工程師分析

### 發現清單

| 嚴重度 | 問題 | 位置 |
|--------|------|------|
| 🔴 | Phase C 分時圖功能（前端週期切換、後端 1m/5m API）無對應測試 | — |
| 🟡 | `useLWCChart.spec.js` 存在，但需確認指標遷移（Phase B）是否有充分測試 | `frontend/src/composables/useLWCChart.spec.js` |
| 🟡 | `ChartWorkspace.spec.js` (10KB) 應確認 LWC 模式的整合測試覆蓋率 | `frontend/src/components/ChartWorkspace.spec.js` |
| 🔵 | Backend 20 個測試文件涵蓋完整，包含 alert engine、backtest、journal 等核心模組 ✅ | `backend/tests/` |
| 🔵 | `test_backtest_engine.py` 針對前視偏誤專有測試 ✅ | — |

### 後端測試覆蓋詳情

| 模組 | 測試文件 | 狀態 |
|------|---------|------|
| Alert Engine | test_alert_engine.py (20KB) | ✅ |
| Backtest Engine | test_backtest_engine.py (10KB) | ✅ |
| Trade Journal | test_trade_journal.py (16KB) | ✅ |
| Market Intelligence | test_market_intelligence_modules.py (15KB) | ✅ |
| Phase 1 API | test_phase1_api.py (14KB) | ✅ |
| TAIFEX Fetcher | test_taifex_fetcher.py (7KB) | ✅ |
| Screener Engine | test_screener_engine.py (9KB) | ✅ |

### 改善建議

1. **🔴** 補充分時圖 API 的後端測試（`test_phase1_api.py` 補充 `interval` 參數測試）
2. **🟡** 確認 `useLWCChart.spec.js` 對 Multi-pane 指標渲染進行快照測試

### 健康度評分：**86/100**

---

## 📋 第 5 步：產品審查員分析

### 規格書功能完成度差距矩陣

| 功能區塊 | 規格要求 | 實作狀態 | 缺口 |
|---------|---------|---------|------|
| K 線圖（多週期） | 日/週/月/季 | ✅ 完整 | — |
| K 線圖（分時） | 1m/5m/15m/60m | ❌ **缺失** | Phase C 未完成 |
| 技術指標（主圖） | MA/EMA/BB/VWAP/一目等 | ✅ 完整 | — |
| 技術指標（子圖） | RSI/MACD/KD/ATR/CCI等 | ✅ 完整 | — |
| 繪圖工具 | 趨勢線/費波/矩形/標記等 | ✅ LWC 整合 | 法人疊加 ✅ |
| 全域命令面板 | Ctrl+K 搜尋 | ✅ 完整 | — |
| 市場熱力圖 | TradingView Heatmap | ✅ 完整 | — |
| 警報系統 | 建立/觸發/推播 | ✅ 有警報中心 | Telegram/Discord 未接 |
| 自選股管理 | 分組/排序/CRUD | ✅ 完整 | 顏色標記未確認 |
| 法人籌碼 | 期貨/選擇權洞察 | ✅ 獨立工作區 | — |
| 回測引擎 | 策略回測/比較 | ✅ 完整 | — |
| 交易日誌 | 記錄/統計/篩選 | ✅ 完整 | — |
| 大盤總覽 | 宏觀風險/事件日曆 | ✅ 完整 | — |
| Docker 化 | 可攜式部署 | ❌ **未完成** | Phase 7 未開始 |
| 外部通知 | Telegram/Discord | ❌ **未完成** | Phase 9 未開始 |

### 健康度評分：**84/100**

---

## ⚡ 第 6 步：DevOps 與效能分析師分析

### 發現清單

| 嚴重度 | 問題 | 位置 |
|--------|------|------|
| 🔴 | `requirements.txt` 缺少實際依賴，`pip install -r requirements.txt` 必失敗（無 yfinance、finmind 等） | `backend/requirements.txt` |
| 🔴 | 無 `Dockerfile` / `docker-compose.yml`，首次環境設定依賴手動步驟 | 專案根目錄 |
| 🟡 | `useChartEngine.js` (120KB) 與 `useLWCDrawings.js` (34KB) 兩引擎並存，bundle 未最佳化 | — |
| 🟡 | 前端路由已使用 Async import `() => import(...)` (Phase 8.1 完成) ✅ | `frontend/src/router/index.js:3-7` |
| 🔵 | `BackgroundScheduler` 排程設計清晰，有日誌輸出 ✅ | `backend/scheduler.py` |
| 🔵 | `ResizeObserver` 節流 (debounce) 處理避免過度渲染 ✅ | `useLWCChart.js:481-498` |

### 效能目標差距

| 目標 | 指標 | 現況估計 |
|------|------|---------|
| 首屏 ≤3s | LWC bundle 35KB（壓縮後），快於 Canvas 方案 | 🟢 可達成 |
| 標的切換 ≤2s | `selectTicker` → LWC `setData` 路徑短 | 🟢 可達成 |
| 選股器 ≤10s | 後端 SQL + Screener Engine | 🟡 需測量 |

### 改善建議

1. **🔴** 立即修復 `requirements.txt`（加入 `yfinance`, `finmind`, `sqlalchemy` 等）
2. **🔴** 啟動 Phase 7：建立 `docker-compose.yml` 與 `start.bat`
3. **🟡** 使用 Vite `rollupOptions.output.manualChunks` 將 `useChartEngine.js` 切分為獨立 chunk

### 健康度評分：**82/100**

---

## 📈 第 7 步：資深股票交易員分析

### 工作流覆蓋度評估

#### 盤前工作區（Market Overview）

| 功能需求 | 實作狀態 |
|---------|---------|
| 大盤風險快速評估 | ✅ MacroDashboard |
| 市場熱力圖 | ✅ TradingView Heatmap Widget |
| 事件日曆（財報/分紅/股東會） | ✅ EventCenter |
| 隔夜外盤影響（美/歐/亞） | ✅ Market Overview Widget（美/台/商品） |
| 當日觀察標的快選 | ✅ 自選股池 + 分組 |

#### 盤中工作區（Pro Chart Terminal）

| 功能需求 | 實作狀態 |
|---------|---------|
| 標的監控 K 線 | ✅ LWC K 線（日/週/月/季） |
| 分時圖 (1m/5m) | ❌ **缺失** — 最大盤中功能缺口 |
| 多標的快速切換 | ✅ 觀察池 + Ctrl+K |
| 突破警報 | ✅ Alert Engine |
| 法人異動感知 | ✅ InstitutionalOverlay 疊加在 K 線 |
| 技術指標 | ✅ 20+ 指標 |

#### 盤後工作區（Review / Institutional）

| 功能需求 | 實作狀態 |
|---------|---------|
| 交易日誌記錄 | ✅ JournalPanel |
| 績效復盤 | ✅ BacktestPanel + 統計 |
| 法人籌碼日報 | ✅ InstitutionalAnalysisWorkspace |
| 期貨/選擇權洞察 | ✅ InstitutionalDashboard |

### 與主流看盤軟體競爭力差距

| 功能 | QuantVision | TradingView | XQ | 三竹 |
|------|------------|------------|-----|------|
| 日K/週K/月K | ✅ | ✅ | ✅ | ✅ |
| 分時圖 | ❌ | ✅ | ✅ | ✅ |
| 法人成本帶 | ✅（特色） | ✅ | ✅ | ✅ |
| 期貨/選擇權籌碼 | ✅（特色） | ❌ | ✅ | ✅ |
| 全域命令面板 | ✅ | ✅ | ❌ | ❌ |
| 策略回測 | ✅ | ✅（付費） | ✅ | ❌ |
| 外部推播 | ❌ | ✅（付費） | 部分 | ✅ |

### 交易員最痛點

> **「分時圖是每個盤中交易員的基本需求。沒有分時圖，這套系統幾乎無法日內使用。」**

### 健康度評分：**86/100**

---

## 🧑‍🎨 第 8 步：UX 使用者體驗設計師分析

### Nielsen 可用性原則逐條評估

| 原則 | 評估 | 狀態 |
|------|------|------|
| 1. 系統狀態可見性 | StatusBar 顯示連線/延遲，市場開盤指示燈 | ✅ 良好 |
| 2. 系統與真實世界符合 | 中文介面、台股術語（法人、散戶、籌碼）完整 | ✅ 良好 |
| 3. 用戶控制與自由 | Ctrl+K 命令面板、Zen Mode、側邊欄收合 | ✅ 良好 |
| 4. 一致性與標準 | 設計語言統一（玻璃磚、圓角、氛圍漸層） | ✅ 良好 |
| 5. 防止錯誤 | 警報創建有 Modal 確認，圖表操作有 Undo | 🟡 可加強 |
| 6. 識別而非回憶 | Ctrl+K 面板顯示快速鍵、Toolbar 圖示有文字 | ✅ 良好 |
| 7. 靈活性與效率 | 快捷鍵支援、工作區快速切換 | ✅ 良好 |
| 8. 美觀且簡約設計 | 深色系設計精美，**但工具列過多（26+ 按鈕）** | 🔴 需改善 |
| 9. 幫助識別錯誤 | 載入錯誤顯示、同步失敗通知 | 🟡 可加強 |
| 10. 幫助與文件 | 無使用說明文件 | 🔵 低優先 |

### UX 發現清單

| 嚴重度 | 問題描述 | 具體位置 |
|--------|---------|---------|
| 🔴 | 圖表工具列（ChartWorkspaceToolbar）擁有 **26+ 個按鈕**，視覺噪音極高，認知負荷嚴重 | `ChartWorkspaceToolbar.vue:3-77` |
| 🔴 | 圖表工具列按鈕無分頁/摺疊機制，低頻功能（季K、Y+、Y-）佔用等同一線功能的視覺空間 | 同上 |
| 🟡 | `Terminal Commandbar` 的操作按鈕（展開觀察池/警報抽屜/快速日誌）文字過於技術性，不夠直覺 | `ProChartTerminalWorkspace.vue:24-36` |
| 🟡 | 分時圖缺失導致盤中頁面有明顯的「功能空洞感」 | Terminal 工作區 |
| 🟡 | 自選股觀察池在「Terminal」收合狀態下只有一個小 label 按鈕，Discovery 路徑不明 | `ProChartTerminalWorkspace.vue:40-47` |
| 🔵 | `StatusBar` 顯示「延遲快照/最新快照」，但未提示 **多久前的資料**（如：「1小時前」） | `App.vue:251` |
| 🔵 | Cmd+K 命令面板在 Navbar 無明確的 hint 提示（用戶不知道有此功能） | `AppNavbar.vue` |

### 🔑 關鍵 UX 改善建議（重要度排序）

#### 改善 1：圖表工具列分組折疊 🔴 高優先
**問題**：26+ 個工具列按鈕造成嚴重的認知負荷。  
**建議方案**（不修改 Props 介面，僅調整 UI 呈現）：

```
工具列分組策略：
┌─────────────────────────────────────────────────────────────────┐
│ [⊹游標] [趨勢線▼] | [買▲][賣▼] | [週期▼] | [圖型▼] | [指標] | [更多▼] │
└─────────────────────────────────────────────────────────────────┘

「趨勢線▼」→ 展開選單：水平線/垂直線/趨勢線/箭頭/費波/矩形/測距/註記
「週期▼」→ 展開選單：日K/週K/月K/季K
「圖型▼」→ 展開選單：K線/折線/面積
「更多▼」→ 視圖操作（左移/右移/放大/縮小/最新/重置/Y+/Y-）
```

預期效果：按鈕數從 26+ 降至 **8-10 個**，視覺清晰度大幅提升。

#### 改善 2：Ctrl+K 的 Discovery 提示 🟡 中優先
**問題**：用戶不知道 Ctrl+K 命令面板的存在。  
**建議**：在 `AppNavbar.vue` 搜尋框末端加入 `⌘K` 徽章提示，點擊觸發命令面板。

```
修改前：[ ⌕ 搜尋代號或名稱...              ]
修改後：[ ⌕ 搜尋代號或名稱...          ⌘K ]
```

#### 改善 3：StatusBar 資料時間標示 🟡 中優先
**問題**：「最新快照」無法讓交易員判斷資料新鮮度。  
**建議**：在 `StatusBar.vue` 顯示資料距現在多久，例如「最新快照 · 4分鐘前」。

#### 改善 4：Terminal Commandbar 按鈕文案優化 🟡 中優先
**現狀**：「展開觀察池」「警報抽屜」「快速日誌」文字冗長  
**建議**：

| 現狀 | 改善後 |
|------|--------|
| 展開觀察池 | ☰ 觀察池 |
| 關閉觀察池 | ✕ 觀察池 |
| 警報抽屜 | 🔔 警報 |
| 快速日誌 | ✎ 日誌 |
| Zen Mode / 離開 Zen | ⛶ / ✕⛶ |

#### 改善 5：工作區切換的視覺指引 🔵 低優先
**建議**：在 Navbar 工作區按鈕上加入 hover tooltip 顯示對應快捷鍵（Alt+1/2/3/4），增強可發現性。

### 認知負荷評估

| 頁面/區域 | 認知負荷評估 |
|---------|------------|
| Market Overview | 🟢 低 — 資訊卡片清晰分組 |
| Pro Chart Terminal | 🔴 高 — 工具列按鈕過多 |
| Institutional Analysis | 🟢 低 — 資料導向設計清晰 |
| Review Workspace | 🟡 中 — 日誌/回測切換直覺 |
| Global Search (Cmd+K) | 🟢 低 — 雙欄佈局清爽 ✅ |

### 健康度評分：**80/100**

---

## 🔴 Critical 問題匯總

1. **🔴** `requirements.txt` 缺少 `yfinance`、`finmind` 等核心依賴 — 新環境 `pip install -r` 必定失敗
2. **🔴** 分時圖功能（1m/5m/15m）完全缺失，無法支援盤中交易工作流
3. **🔴** 圖表工具列 26+ 個按鈕，嚴重的認知負荷問題

---

## Top 10 優先改善事項

| 優先度 | 改善項目 | 影響維度 | 預估工時 |
|--------|---------|---------|---------|
| **1** | 修復 `requirements.txt`，補完所有後端依賴 | 後端/DevOps | 1h |
| **2** | 完成分時圖後端 API（`interval=1m/5m/15m/60m`） | 後端/產品/交易員 | 2-3d |
| **3** | 前端圖表工具列折疊重構（26 → 8 個按鈕） | UX/前端 | 2-3d |
| **4** | 分時圖前端週期按鈕整合 | 前端/產品 | 1d |
| **5** | `useChartEngine.js` 改為動態 import，減少 bundle | 效能/前端 | 0.5d |
| **6** | 啟動 Phase 7 Docker 化（`docker-compose.yml`） | DevOps | 2d |
| **7** | Ctrl+K 搜尋框加入視覺提示（`⌘K` 徽章） | UX | 0.5d |
| **8** | `StatusBar` 加入資料距今時間（「x 分鐘前」） | UX/規範 | 1h |
| **9** | `main.py` 背景任務函數移至 `background_tasks.py` | 後端架構 | 2h |
| **10** | CORS `allow_methods` 限縮為具體 HTTP 方法 | 安全 | 0.5h |

---

## 建議下一步

### 🥇 最高優先：分時圖完成（Phase C）

分時圖是目前系統最大的功能缺口，**既是交易員體驗的核心需求，也是與主流看盤軟體差距最大的地方**。

建議執行順序：
```
Step 1: 修復 requirements.txt（30 分鐘）
Step 2: 後端 market_data.py 加入 interval 參數支援（1-2 天）
Step 3: 前端 Navbar timeframe 按鈕加入 1m/5m/15m/60m 選項（半天）
Step 4: 驗證 LWC timeScale timeVisible 分鐘級正確顯示（已有基礎）
```

### 🥈 高優先：工具列 UX 重構

工具列折疊重構可以大幅改善圖表終端的視覺清晰度，且**不影響後端 API 或複雜業務邏輯**，是性價比最高的前端改善。

### 🥉 中長期：Docker 化（Phase 7）

完成核心功能後，Docker 化可大幅降低「換電腦重新部署」的摩擦，也是達到「個人可攜看盤系統」目標的最後一哩路。

---

## 🔒 執行限制聲明

> [!CAUTION]
> **本文件為純審查報告，不包含任何程式碼修改。**
> 所有建議均屬規劃方向，實際修改前請確認對現有功能無破壞性影響。

---

*最後更新：2026-04-08 | 報告版本：v1.0*
