# 🚀 QuantVision Pro — OpenStock 參考優化 & TradingView Lightweight Charts 整合規劃

**產出時間**：2026-04-08  
**參考來源**：[OpenStock (GitHub)](https://github.com/Open-Dev-Society/OpenStock) · [TradingView Lightweight Charts v5.1](https://tradingview.github.io/lightweight-charts/)  
**規劃性質**：🔍 純規劃文件，不包含任何程式碼修改

---

## 📑 目錄

1. [OpenStock 專案分析](#openstock-analysis)
2. [當前 K 線系統現狀盤點](#current-chart-audit)
3. [TradingView Lightweight Charts v5 功能評估](#lwc-evaluation)
4. [OpenStock 啟發之功能優化建議](#openstock-inspiration)
5. [K 線引擎遷移規劃](#chart-migration)
6. [整合架構設計](#architecture)
7. [分階段執行計畫](#phases)
8. [風險與限制評估](#risks)
9. [決策建議](#decision)

---

## 1. OpenStock 專案分析 {#openstock-analysis}

### 1.1 OpenStock 技術棧

| 維度 | OpenStock | QuantVision Pro |
|------|-----------|-----------------|
| 框架 | Next.js 15 (App Router) + React 19 | Vue 3 + Vite |
| 樣式 | Tailwind CSS v4 + shadcn/ui | Vanilla CSS |
| 資料庫 | MongoDB + Mongoose | MySQL + SQLAlchemy |
| 圖表 | TradingView **Embeddable Widgets** (iframe) | 自製 Canvas 引擎 |
| 資料來源 | Finnhub API | Yahoo Finance, TAIFEX, TWSE, FinMind |
| 認證 | Better Auth (email/password) | 無 (本地工具) |
| AI 整合 | Gemini / MiniMax (email 摘要) | 無 |
| 部署 | Docker + Vercel | 本地開發環境 |
| Stars | ⭐ 10.3k | — |

### 1.2 OpenStock 核心功能清單

OpenStock 的亮點功能（可借鏡）：

| 功能 | OpenStock 實作方式 | 借鏡優先度 |
|------|-------------------|-----------|
| **⌨️ 全域命令面板 (Cmd+K)** | `cmdk` 套件，支援模糊搜尋標的 | 🔴 高優先 |
| **🔍 快速標的搜尋** | Finnhub 搜尋 + 閒置時顯示熱門標的 | 🔴 高優先 |
| **📋 個人自選股** | 每位用戶獨立 Watchlist，MongoDB 儲存 | 🟡 中優先 |
| **📊 市場熱力圖 Heatmap** | TradingView Widget 嵌入 | 🟡 中優先 |
| **📰 即時新聞流** | TradingView Widget 嵌入 | 🟡 中優先 |
| **📈 K 線 & 技術分析圖** | TradingView **進階圖表 Widget** | 🔴 高優先 |
| **🏢 公司基本面面板** | TradingView Symbol Info Widget | 🟡 中優先 |
| **😊 情緒分析** | Adanos API (Reddit/X/新聞/Polymarket) | 🔵 低優先 |
| **DockerCompose** | mongodb + Next.js app | 🟡 中優先 (Phase 7) |
| **AI 每日摘要郵件** | Gemini via Inngest cron | 🔵 低優先 |

### 1.3 OpenStock 使用 TradingView 的方式

OpenStock 採用的是 TradingView **Embeddable Widgets（可嵌入小工具）**，本質是透過 `<script>` 注入的 **iframe 式嵌入**：

```
TradingView Widgets 使用方式：
- 圖表：TradingView Advanced Chart Widget
- 熱力圖：Market Overview / Heatmap widget
- 新聞：Timeline widget
- 公司資訊：Symbol Info widget
```

> [!IMPORTANT]
> **OpenStock 用的是「TradingView Widgets」，而本規劃要評估的是「TradingView Lightweight Charts」，兩者是完全不同的技術路徑！**
> - **TradingView Widgets**：免費但封閉的 iframe 嵌入，無法控制資料、無法客製化，有 TradingView 浮水印
> - **TradingView Lightweight Charts**：開源 JavaScript 圖表程式庫，可完全控制資料與 UI，是本文件的評估重點

---

## 2. 當前 K 線系統現狀盤點 {#current-chart-audit}

### 2.1 現有架構摘要

目前 QuantVision Pro 的 K 線圖系統是 **100% 自製 Canvas 2D 渲染引擎**：

```
frontend/src/
├── composables/
│   ├── useChartEngine.js      ← 核心引擎 (3,417 行，~120KB)
│   └── useChartSyncPanes.js   ← 多視窗同步 (229 行)
├── components/
│   ├── ChartWorkspace.vue     ← 主容器 (653 行)
│   └── chart/
│       ├── ChartCanvasArea.vue       ← Canvas 渲染區
│       ├── ChartWorkspaceToolbar.vue ← 工具列 (127 行)
│       ├── ChartWorkspaceHeader.vue  ← 標題欄
│       ├── ChartWorkspaceMetaBar.vue ← 元資料列
│       ├── ChartWorkspaceControls.vue← 工作區控制
│       ├── ChartDrawingManager.vue   ← 繪圖管理
│       └── ChartIndicatorPanel.vue   ← 指標面板
└── utils/
    └── indicatorUtils.js      ← 技術指標計算 (~41KB)
```

### 2.2 現有引擎功能盤點

#### ✅ 已實作功能（自製引擎）

| 功能類別 | 功能項目 |
|---------|---------|
| **圖表類型** | K線圖 / 折線圖 / 面積圖 |
| **K 線週期** | 日K / 週K / 月K / 季K |
| **技術指標 (主圖)** | MA, EMA, BB, VWAP, Parabolic SAR, Ichimoku, SuperTrend, Donchian, Keltner |
| **技術指標 (子圖)** | RSI, MACD, KD Stochastic, ATR, CCI, ADX, OBV, CMF, Aroon, TRIX, Williams %R, MFI, ROC, BBPercent, BBWidth |
| **繪圖工具** | 水平線, 垂直線, 趨勢線, 箭頭線, 費波那契, 區間框, 測距尺, 買賣點標記, 文字註記 |
| **互動功能** | 縮放(滾輪), 平移(拖曳), 框選縮放, Y軸手動控制, 十字線, 對數/線性尺度 |
| **視圖管理** | 視圖歷史記錄(Undo/Redo), 工作區預設存檔, 視窗同步(1/2/4圖) |
| **疊加圖層** | 法人成本帶顯示, 比較疊加圖 (%) |
| **其他** | 快捷鍵支援, 事件標記, 宏觀旗幟橫幅, 延遲標記 |

#### ⚠️ 現有痛點

| 問題類別 | 具體描述 | 嚴重度 |
|---------|---------|------|
| **程式碼複雜度** | `useChartEngine.js` 單檔 3,417 行，是整個前端最大的維護負擔 | 🔴 Critical |
| **缺少分時圖** | 無分鐘 K，無法支援盤中即時監控 | 🔴 Critical |
| **繪圖持久化** | 繪圖資料目前本地端管理，頁面重整後是否保留需確認 | 🟡 Warning |
| **手機響應式** | Canvas 尺寸管理複雜，手機端體驗差 | 🟡 Warning |
| **多指標效能** | 多個子圖同時開啟時，每次渲染循環重算所有指標 | 🟡 Warning |
| **缺少 Plugin 機制** | 新增自定義圖表類型需修改核心引擎 | 🔵 Info |

---

## 3. TradingView Lightweight Charts v5.1 功能評估 {#lwc-evaluation}

### 3.1 核心能力

TradingView Lightweight Charts (LWC) 是 TradingView 開源的圖表程式庫：
- **授權**：Apache License 2.0 (完全免費、商用可用)
- **最新版本**：v5.1 (2026 年)
- **套件大小**：~35KB (gzip 後)
- **NPM**：`lightweight-charts`

### 3.2 v5.1 主要功能

| 功能 | 描述 | QuantVision 相關性 |
|------|------|-------------------|
| **多面板 (Multi-pane)** | 多個獨立子圖區（含各自 Y 軸），v5.0 正式引入 | 🔴 直接取代自製子圖 |
| **K 線/蠟燭圖** | 原生 CandlestickSeries | 🔴 核心功能 |
| **折線/面積圖** | LineSeries, AreaSeries, BaselineSeries | 🔴 直接支援 |
| **成交量直方圖** | HistogramSeries | 🔴 取代自製成交量圖 |
| **十字線** | 原生內建，可同步多個圖表 | 🔴 直接支援 |
| **資料衝突合併 (Conflation v5.1)** | 超大資料集自動合併顯示 | 🟡 效能優化 |
| **Plugin 系統** | 可開發自定義 Series/Primitive | 🔴 繪圖工具實作基礎 |
| **Watermark Plugin** | 圖表浮水印 (已移至 plugin) | 🔵 可加 Logo |
| **Series Markers** | 買賣訊號標記 (已移至 plugin) | 🔴 取代自製訊號標記 |
| **時區支援** | 正確處理 UTC+8 台灣時區 | 🔴 台股資料重要 |
| **對數/線性尺度** | `PriceScaleMode` 選項 | 🔴 已有對應功能 |
| **觸控支援** | 原生行動裝置觸控縮放/平移 | 🟡 改善手機端 |
| **TypeScript 完整支援** | 全型別定義 | 🔵 未來重構參考 |
| **Vue 3 整合範例** | 官方 tutorial 有 Vue 整合指引 | 🔴 技術可行 |

### 3.3 LWC 的能力邊界（不支援項目）

> [!WARNING]
> LWC 是**圖表渲染程式庫**，以下功能需要自行實作或整合其他方案：

| 不支援項目 | 現有自製解法 | 遷移後方案 |
|-----------|------------|-----------|
| 技術指標計算 (EMA/RSI/MACD等) | `indicatorUtils.js` 自製 | **保留現有計算邏輯，只改渲染層** |
| 法人成本帶疊加圖層 | `drawInstitutionalCostBand()` | 用 LWC Plugin 自製 Primitive |
| 趨勢線/費波/箭頭繪圖工具 | Canvas 直接繪製 | 用 LWC Plugin 或保留 Canvas 覆蓋層 |
| 框選縮放 (Box Zoom) | 自製 selection box | 需自實作 |
| 多圖同步 (quad layout) | `useChartSyncPanes.js` | LWC 支援 crosshair sync |

### 3.4 LWC vs 自製引擎 對比總結

| 評估維度 | 自製 Canvas 引擎 | LWC v5.1 |
|---------|---------------|---------|
| **初始渲染效能** | 🟡 尚可 | 🟢 更優 (WebGL 加速) |
| **大量資料表現** | 🟡 可能卡頓 | 🟢 資料衝突合併優化 |
| **多面板子圖** | 🔴 需自行管理 Canvas | 🟢 原生 Multi-pane |
| **觸控/行動端** | 🔴 體驗差 | 🟢 原生觸控 |
| **繪圖工具客製化** | 🟢 完全可控 | 🟡 需透過 Plugin API |
| **技術指標覆蓋** | 🟢 完整 20+ 指標 | 🔴 需自行計算 |
| **維護成本** | 🔴 3417 行单文件 | 🟢 業界維護 |
| **自訂法人疊加** | 🟢 已支援 | 🟡 需 Plugin |
| **分時圖支援** | 🔴 無 | 🟢 LineSeries 可支援 |
| **週期切換** | 🟢 日/週/月/季 | 🟢 由後端資料決定 |
| **台股中文介面** | 🟢 完整中文化 | 🟡 需自建 UI 層 |

---

## 4. OpenStock 啟發之功能優化建議 {#openstock-inspiration}

### 4.1 借鏡 OpenStock 的設計理念

參考 OpenStock 的架構與 UX 設計，以下功能值得引入 QuantVision Pro：

#### 🔴 高優先級借鏡項目

**A. 全域命令面板 (Global Command Palette)**
- OpenStock 使用 `cmdk` 實作 `Cmd/Ctrl + K` 觸發
- QuantVision Pro 的建議實作：使用 Vue 原生實作彈出式搜尋框
- 功能：快速搜尋標的、快速跳轉工作區、快速執行常用操作
- 受益場景：盤中快速切換標的，不需要用滑鼠點擊側欄

**B. 快速標的搜尋增強**
- OpenStock：閒置顯示「熱門標的」；輸入時防抖動查詢
- QuantVision Pro 現狀：目前搜尋功能可再優化
- 建議：加入「最近瀏覽」紀錄、「熱門台股」快選清單

**C. 市場熱力圖整合**
- OpenStock 整合 TradingView 市場概覽 Widget
- QuantVision Pro：在「市場總覽頁」加入 TradingView Heatmap Widget（不是 LWC）
- 相容性：這是嵌入型 Widget，對現有架構零侵入

#### 🟡 中優先級借鏡項目

**D. 系統化的 Watchlist 管理**
- OpenStock：每個用戶自己的 Watchlist 控制邏輯清晰
- QuantVision Pro：可強化 Watchlist 的串列顯示與快速操作 (更改顏色分組、備注)

**E. 公司基本面快速面板**
- OpenStock 整合 TradingView Symbol Info Widget 顯示公司基本面
- QuantVision Pro：可加入 TradingView Symbol Info 嵌入，搭配現有 fundamentals_provider.py 的資料

**F. 個人化入門引導 (Onboarding Flow)**
- OpenStock 有使用者首次登入的偏好設定流程
- QuantVision Pro：可加入「交易偏好設定」步驟 (台股/美股, 短線/長線)

### 4.2 OpenStock 不適合直接複製的部分

| 項目 | 原因 |
|------|------|
| Next.js + MongoDB 架構 | QuantVision 已用 FastAPI + MySQL，技術棧不同 |
| Better Auth + 帳號系統 | 個人工具無需多用戶認證 |
| Inngest AI 郵件摘要 | 可未來評估，優先級低 |
| Adanos 情緒分析 API | 付費第三方 API，不在核心優先 |
| TradingView Widgets 圖表 | 本計畫改用 LWC 自製圖表 |

---

## 5. K 線引擎遷移規劃 {#chart-migration}

### 5.1 遷移策略選擇

> [!IMPORTANT]
> **關鍵設計決策：漸進式遷移 vs 完全替換**

#### 方案 A：完全替換（Big Bang Migration）
- 一次性將 `useChartEngine.js` 全部替換為 LWC
- 風險：高（現有功能可能缺失，繪圖工具需重寫）
- 工期：估計 4-6 週

#### 方案 B：漸進式遷移（Incremental Migration）⭐ **建議採用**
- 保留現有自製引擎，新建 `useLWCChart.js` 作為 LWC 封裝層
- 透過 `chartEngine` prop 切換渲染後端（`legacy` | `lwc`）
- 優先遷移主 K 線、成交量、指標子圖
- 繪圖工具最後遷移（或保留 Canvas 覆蓋層）
- 風險：低，可分批測試驗證
- 工期：估計 2-3 週 (Phase 1) → 持續進行

#### 方案 C：共存整合（Bridge Pattern）
- 主圖使用 LWC，複雜繪圖工具保留自製 Canvas 疊加層
- 優點：充分利用各自優勢
- 風險：雙引擎協調複雜度
- 適合：中長期最終架構

> [!NOTE]
> 建議從**方案 B → 方案 C** 漸進演化，避免一次性風險。

### 5.2 LWC 安裝與基礎設定

```bash
# 安裝 LWC（在 frontend/ 目錄）
npm install lightweight-charts
# 目前最新版：5.1.x
```

```javascript
// 基礎 Vue 3 整合範例（useLWCChart.js）
import { createChart } from 'lightweight-charts';
import { onMounted, onBeforeUnmount, ref } from 'vue';

export function useLWCChart(containerRef, options = {}) {
  let chart = null;
  let candleSeries = null;
  let volumeSeries = null;

  const initChart = () => {
    chart = createChart(containerRef.value, {
      layout: {
        background: { color: '#080c12' },
        textColor: '#8ba3c0',
      },
      grid: {
        vertLines: { color: 'rgba(30,45,61,0.55)' },
        horzLines: { color: 'rgba(30,45,61,0.55)' },
      },
      crosshair: {
        mode: 1, // CrosshairMode.Normal
      },
      rightPriceScale: {
        borderColor: 'rgba(30,45,61,0.9)',
      },
      timeScale: {
        borderColor: 'rgba(30,45,61,0.9)',
        timeVisible: true,
      },
    });

    // 主面板：K 線
    candleSeries = chart.addCandlestickSeries({
      upColor: '#00d9a3',
      downColor: '#ff4d6a',
      borderUpColor: '#00d9a3',
      borderDownColor: '#ff4d6a',
      wickUpColor: '#00d9a3',
      wickDownColor: '#ff4d6a',
    });

    // 子面板：成交量（Multi-pane v5）
    const volumePane = chart.addPane();
    volumeSeries = volumePane.addHistogramSeries({
      color: 'rgba(0,217,163,0.3)',
    });
  };

  onMounted(() => initChart());
  onBeforeUnmount(() => chart?.remove());

  return { chart, candleSeries, volumeSeries };
}
```

### 5.3 指標子圖遷移方案（LWC Multi-Pane）

LWC v5 的 Multi-Pane API 可取代目前的多 Canvas 架構：

```javascript
// LWC v5 Multi-Pane 範例
const rsiPane = chart.addPane({ height: 120 });
const rsiSeries = rsiPane.addLineSeries({ color: '#9b6dff' });

const macdPane = chart.addPane({ height: 120 });
const macdHistSeries = macdPane.addHistogramSeries();
const macdLineSeries = macdPane.addLineSeries({ color: '#00d4ff' });
const signalLineSeries = macdPane.addLineSeries({ color: '#ff8c42' });
```

**遷移對照表：**

| 現有自製子圖 Canvas | LWC 對應方案 |
|-------------------|------------|
| `rsiCanvas` (RSI) | `chart.addPane()` + `LineSeries` |
| `macdCanvas` (MACD) | `chart.addPane()` + `HistogramSeries` + `LineSeries` |
| `stochCanvas` (KD) | `chart.addPane()` + `LineSeries` × 2 |
| `volumeCanvas` (成交量) | `chart.addPane()` + `HistogramSeries` |
| `aroonCanvas` (Aroon) | `chart.addPane()` + `LineSeries` × 2 |
| `atrCanvas` (ATR) | `chart.addPane()` + `LineSeries` |
| `cciCanvas` (CCI) | `chart.addPane()` + `LineSeries` |
| `obvCanvas` (OBV) | `chart.addPane()` + `LineSeries` |
| `adxCanvas` (ADX) | `chart.addPane()` + `LineSeries` × 3 |
| `cmfCanvas` (CMF) | `chart.addPane()` + `LineSeries` |

### 5.4 繪圖工具遷移方案

LWC 的 Plugin API 支援自定義 `ISeriesPrimitive`，可實作繪圖工具：

| 繪圖工具 | LWC 實作方式 |
|---------|------------|
| **水平線** | `createPriceLine()` (內建 API) |
| **買/賣訊號標記** | Series Markers Plugin (v5 後移至 plugin) |
| **趨勢線** | `ISeriesPrimitive` 自定義 Primitive |
| **費波那契** | `ISeriesPrimitive` 自定義 Primitive |
| **區間框** | `ISeriesPrimitive` 自定義 Primitive |
| **文字註記** | `ISeriesPrimitive` 自定義 Primitive |
| **法人成本帶** | `ISeriesPrimitive` 自定義 Primitive |

> [!WARNING]
> 繪圖工具的 Plugin 實作是最複雜的部分。建議**最後遷移**，或在 LWC Canvas 上疊加一個透明 Canvas 層保留現有繪圖邏輯（方案 C）。

### 5.5 資料格式轉換

LWC 要求主圖時間為 Unix Timestamp（秒級整數）：

```javascript
// 後端現有格式（date string）→ LWC 格式
const transformOHLC = (rawData) => rawData.map(row => ({
  time: Math.floor(new Date(row.date).getTime() / 1000), // Unix 秒
  open: row.open,
  high: row.high,
  low: row.low,
  close: row.close,
}));

// 台股時區注意：需確保 new Date() 以 UTC+8 正確解析
// 建議後端統一回傳 ISO 8601 格式且含時區資訊
```

---

## 6. 整合架構設計 {#architecture}

### 6.1 目標架構圖

```
前端 (Vue 3 + Vite)
├── pages/
│   ├── MarketOverviewView.vue          # 市場總覽
│   │   ├── TradingView Heatmap Widget  # OpenStock 借鏡
│   │   ├── WatchlistPanel.vue
│   │   └── ScreenerWorkspace.vue
│   ├── ProChartTerminalView.vue        # 專業看盤終端
│   │   └── ChartWorkspace.vue (重構)
│   │       ├── useLWCChart.js          # 新：LWC 封裝層
│   │       ├── indicatorUtils.js       # 保留：指標計算
│   │       └── drawingPlugin/          # 新：LWC Plugin 繪圖工具
│   ├── InstitutionalView.vue           # 法人籌碼
│   └── JournalBacktestView.vue         # 績效復盤
│
├── composables/
│   ├── useLWCChart.js                  # 【新增】LWC 核心封裝
│   ├── useLWCIndicators.js             # 【新增】LWC 指標映射
│   ├── useLWCDrawings.js               # 【新增】LWC 繪圖工具
│   ├── useChartEngine.js               # 【保留】漸進式廢棄
│   └── useDashboard.js                 # 【保留（重構）】
│
└── components/
    ├── GlobalSearchCommand.vue         # 【新增】Cmd+K 命令面板
    └── chart/
        ├── LWCChartCanvas.vue          # 【新增】LWC 渲染容器
        ├── ChartWorkspaceToolbar.vue   # 【保留改造】
        └── ChartWorkspaceHeader.vue    # 【保留改造】
```

### 6.2 新增 Vue 3 組件：GlobalSearchCommand

借鏡 OpenStock 的命令面板概念，為 QuantVision 加入全域搜尋：

```
功能規格：
- 觸發鍵：Ctrl+K（Windows）/ Cmd+K（Mac）
- 搜尋來源：
  * 後端 API `/api/tw_symbols` + `/api/us_symbols`（已有）
  * 本地 Watchlist 快選
  * 最近瀏覽標的（localStorage）
- 選取後動作：切換至「專業看盤終端」並載入該標的
- UI 樣式：毛玻璃欄框，深色系，動態搜尋結果
```

---

## 7. 分階段執行計畫 {#phases}

> [!NOTE]
> 以下階段可在 Phase 0（UX 路由重構，已規劃於 `system-modification-plan.md`）完成後依序啟動。

### Phase A：LWC 基礎整合（預估工時：1-2 週）

**目標**：讓 LWC 可在 `ProChartTerminalView` 中渲染 K 線，與原有引擎並存。

- [ ] **A.1** 安裝 `lightweight-charts@^5.1` npm 套件
- [ ] **A.2** 建立 `frontend/src/composables/useLWCChart.js`
  - 封裝 `createChart()` 生命週期（mount/unmount）
  - 實作深色主題樣式配置（與現有色系一致）
  - 實作 OHLCV 資料格式轉換（date string → Unix timestamp）
- [ ] **A.3** 建立 `frontend/src/components/chart/LWCChartCanvas.vue`
  - 接受 `ohlcData` prop，渲染 K 線 + 成交量
  - 支援 K 線 / 折線 / 面積圖三種模式
  - 實作 resize 響應
- [ ] **A.4** 在 `ChartWorkspace.vue` 加入 `engineMode` prop
  - `engineMode="legacy"` 使用現有 Canvas 引擎
  - `engineMode="lwc"` 使用新 LWC 引擎
  - 加入切換按鈕供測試對比

### Phase B：LWC 指標面板遷移（預估工時：2-3 週）

**目標**：將現有多 Canvas 子圖面板全部遷移至 LWC Multi-Pane 架構。

- [ ] **B.1** 建立 `frontend/src/composables/useLWCIndicators.js`
  - 映射現有 `indicatorUtils.js` 的計算結果 → LWC Custom Series
  - 實作：RSI, MACD, KD Stochastic, ATR, CCI, OBV, ADX, CMF
  - 實作：Aroon, TRIX, Williams %R, MFI, ROC, BB%B, BBWidth
- [ ] **B.2** 實作主圖疊加指標（LWC LineSeries / AreaSeries）
  - MA 均線組（MA5/10/20/60/120/240）
  - EMA 均線組
  - 布林通道（上中下軌）
  - VWAP（當日計算）
  - 一目均衡表（含多條線）
  - SuperTrend（含方向色）
- [ ] **B.3** 保留 `indicatorUtils.js` 的計算邏輯（不修改，只改渲染層）
- [ ] **B.4** 廢棄多個子 Canvas ref（rsiCanvas, macdCanvas...等），由 LWC Multi-Pane 取代

### Phase C：分時圖支援（預估工時：1 週）

**目標**：新增分鐘 K 線週期，支援盤中即時分析（現有系統缺失）。

- [ ] **C.1** 後端：在 `data_fetcher.py` 加入分鐘 K 資料拉取
  - 美股：Yahoo Finance `yf.Ticker().history(period='1d', interval='1m')`
  - 台股：評估 FinMind API 的分鐘資料端點
- [ ] **C.2** 後端：新增 API endpoint `/api/ohlc/{ticker}?interval=1m|5m|15m|60m`
- [ ] **C.3** 前端：在 `ChartWorkspaceToolbar.vue` 加入分鐘週期按鈕（1m/5m/15m/60m/日K/週K/月K）
- [ ] **C.4** LWC 時間軸自動適應分鐘級別顯示

### Phase D：LWC 繪圖工具整合（預估工時：2-3 週）

**目標**：將自製繪圖工具系統遷移/橋接至 LWC Plugin 架構。

- [ ] **D.1** 評估 LWC Plugin API 成熟度，決定採用 Plugin 或 Canvas 疊加方案
- [ ] **D.2** 實作水平線（使用 LWC `createPriceLine()` API）
- [ ] **D.3** 實作買/賣訊號標記（使用 LWC Series Markers Plugin）
- [ ] **D.4** 實作趨勢線（使用 LWC `ISeriesPrimitive`）
- [ ] **D.5** 實作費波那契（使用 LWC `ISeriesPrimitive`）
- [ ] **D.6** 實作法人成本帶疊加（使用 LWC `ISeriesPrimitive`）
- [ ] **D.7** 決定是否完整廢棄現有 Canvas 繪圖層

### Phase E：命令面板與 OpenStock 功能整合（預估工時：1 週）

**目標**：引入 OpenStock 借鏡功能，提升日常使用流暢度。

- [ ] **E.1** 建立 `GlobalSearchCommand.vue`（Ctrl+K 命令面板）
  - 搜尋台股/美股代碼
  - 最近瀏覽紀錄（localStorage）
  - 快速跳轉到「專業看盤終端」
- [ ] **E.2** 在 `AppNavbar.vue` 加入市場熱力圖連結（使用 TradingView Market Heatmap Widget）
- [ ] **E.3** 在「市場總覽頁」整合 TradingView Market Overview Widget
- [ ] **E.4** 加入自選股分組/顏色標記功能

---

## 8. 風險與限制評估 {#risks}

### 8.1 技術風險

| 風險項目 | 影響程度 | 發生機率 | 緩解策略 |
|---------|--------|--------|---------|
| LWC Plugin API 不夠完整，無法實作所有繪圖工具 | 🔴 高 | 🟡 中 | 採用方案 C（Canvas 疊加），保留現有繪圖引擎 |
| LWC 與現有 `useDashboard.js` 狀態整合複雜 | 🟡 中 | 🔴 高 | 設計清晰的 chartBridge 介面層，解耦渲染與狀態 |
| 台股日期格式（YYYY-MM-DD）轉 Unix 時區錯誤 | 🔴 高 | 🟡 中 | 統一使用 UTC+8 轉換函數，加入單元測試 |
| `useChartEngine.js` 中現有功能迴歸 | 🟡 中 | 🟡 中 | 漸進式遷移 + Legend 引擎切換按鈕測試 |
| 後端分時資料 API 速度/穩定性問題 | 🔴 高 | 🟡 中 | 實作本地快取 + 限速保護 |

### 8.2 授權與合規

| 項目 | 評估結果 |
|------|---------|
| LWC 授權 | ✅ Apache 2.0，完全免費商用 |
| TradingView Widgets（嵌入式） | ⚠️ 免費但有品牌限制，商業用途需確認條款 |
| OpenStock 授權 | ⚠️ AGPL-3.0，**修改後衍生作品必須開源** - 本計畫僅借鏡概念，不複製程式碼 |

### 8.3 工程負債評估

遷移完成後的預期改善：

| 指標 | 現在 | 遷移後預期 |
|------|------|---------|
| 圖表引擎程式碼行數 | 3,417 行（單檔） | <500 行（LWC 封裝層） |
| 圖表維護難度 | 🔴 困難 | 🟢 容易 |
| 手機端支援 | 🔴 差 | 🟢 良好 |
| 分時圖 | 🔴 無 | 🟢 支援 |
| 效能（大量資料） | 🟡 普通 | 🟢 LWC 衝突合併 |

---

## 9. 決策建議 {#decision}

### 9.1 主要決策點

> [!IMPORTANT]
> **核心問題：是否現在立刻替換 K 線引擎？**

**建議分析：**

1. **Phase 0（UX 路由重構）仍應優先執行** — 頁面架構調整是基礎，圖表引擎遷移在新的 `ProChartTerminalView` 中更容易操作
2. **LWC 遷移採漸進式方案（方案 B）** — 風險最低，可邊驗證邊推進
3. **最高 ROI 的第一步是 Phase A** — 先讓 LWC 主 K 線跑起來，確認整合可行性

### 9.2 建議執行順序

```
當前優先執行路徑：
Phase 0（已規劃）→ Phase A（LWC 基礎）→ Phase B（指標遷移）
                                    ↓
                             Phase E（命令面板）
                                    ↓
                    Phase C（分時圖） + Phase D（繪圖工具）
```

### 9.3 建議暫不執行的項目

- 完整複製 OpenStock 的 TradingView Widget 嵌入（與 LWC 方向衝突）
- 引入 OpenStock 的 Tailwind CSS / shadcn/ui（會衝突現有 Vanilla CSS 架構）
- 帳號認證系統（OpenStock 的核心用途是多用戶 SaaS，QuantVision 是個人工具）

---

## 📎 相關文件

| 文件 | 路徑 |
|------|------|
| 前端 UX 重構規劃 | `docs/frontend-ux-redesign-plan.md` |
| 系統修改計畫 | `docs/system-modification-plan.md` |
| 產品規格書 | `docs/quantvision-product-spec.md` |
| 交付里程碑計畫 | `docs/quantvision-phase-delivery-plan.md` |

---

## 🔒 執行限制聲明

> [!CAUTION]
> **本文件為純規劃文件，不包含任何程式碼修改。**  
> 所有程式碼範例僅供示意用途，實際執行前請確認 LWC API 版本相容性。  
> 正式實作前請先在分支環境驗證，避免影響現有穩定功能。

---

*最後更新：2026-04-08 | 規劃版本：v1.0*
