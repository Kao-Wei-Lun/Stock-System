# 🧑‍🎨 交易員與前端 UX 體驗重構計畫 (UI/UX Redesign Plan)

**產出時間**：2026-04-04  
**報告目的**：根據 `[/analyze-frontend]`, `[/analyze-trader]`, `[/analyze-ux]` 的綜合評鑑，解決目前「功能過度堆疊於單一畫面」導致認知負荷過高的問題，重新定義系統的資訊架構 (Information Architecture) 與頁面路由。

---

## 🔍 現況問題診斷 (Pain Points)

經過綜合掃描，目前系統主要面臨以下核心 UX 與架構痛點：
1. **認知負荷超載 (Information Overload)**：
   儀表板同時塞入自選股、大盤風險、K線圖、回測、交易日誌、法人籌碼與警報器。對交易員而言，盤前、盤中與盤後的所需資訊不同，同時顯示會干擾決策焦距。
2. **螢幕空間浪費 (Screen Estate)**：
   技術分析需要極大的畫布面積，但被過寬的左、右側邊欄 (`WatchlistPanel` 與 `RightSidebar` 內的 Journal/Backtest) 擠壓，導致 K 線圖區域不足。
3. **沒有明確的工作流 (Lack of Workflows)**：
   看盤系統應符合使用者的旅程：`尋找機會 (Screener/Macro) -> 深度分析 (Chart/Chips) -> 模擬與紀錄 (Backtest/Journal)`，目前全混在一起。

---

## 📐 前端路由與頁面拆解提案 (Routing & Layout Strategy)

建議利用已安裝的 `vue-router`，將全站拆分為 **四大獨立工作區 (Workspaces)**，讓功能按交易階段徹底分流：

### 1. 📊 首頁 / 市場總覽 (Market Overview View)
*定位：盤前準備、尋找交易機會*
* **主要內容**：
  - 頂部：`MacroDashboard` (大盤風險溫度計、VIX、匯率)。
  - 左側：`WatchlistPanel` (自選股與板塊動態)。
  - 右側：`EventCenter` (今日財報、經濟數據日曆)。
  - 底部/主區塊：整合 `ScreenerWorkspace` (選股掃描結果列表)。
* **UX 優化**：使用者能一眼評估「今天該不該進場」、「有哪些標的符合策略」，不需要看到複雜的 K 線。

### 2. 📈 專業看盤終端 (Pro Chart Terminal View)
*定位：盤中盯盤、技術分析、找尋進出場點*
* **主要內容**：
  - **極大化主區**：滿版的 `ChartWorkspace`。
  - **可收折左側欄**：極簡版自選股清單 (點擊立刻切換主圖標的)。
  - **可收折右側欄 (抽屜 Drawer)**：只保留 `AlertConfigPanel` (設警報) 與極簡版 `JournalEntryFrom` (快速紀錄當下情緒與截圖)。
* **UX 優化**：
  - 加大 K 線占比，預設隱藏左右側板。
  - 支援「Zen Mode (純淨全螢幕K線)」快捷鍵 (如 `Alt + Z`)。
  - 主圖上直接按 `Alt + A` 呼叫警報設定，不需常駐顯示面板。

### 3. 🏦 法人與籌碼深度分析 (Institutional Analysis View)
*定位：盤後深究、籌碼跟蹤*
* **主要內容**：
  - 放置完整的 `InstitutionalDashboard`。
  - 期貨/選擇權未平倉量、三大法人買賣超、散戶多空比圖表。
* **UX 優化**：這類資料通常是以「表格」與「長條圖」為主，與日 K 線的工作區分開，給予足夠的寬度呈現法人籌碼詳細排行榜。

### 4. 📓 績效與回測管理 (Journal & Backtest View)
*定位：盤後復盤、策略開發*
* **主要內容**：
  - 採用 **Tabs (頁籤)** 設計，切換 `[ 交易日誌 ]` 與 `[ 系統回測 ]`。
  - 左側清單：歷史交易紀錄 / 回測歷史報告。
  - 右側主區：`JournalStatsView` (勝率、盈虧比圓餅圖) 或 `BacktestPanel` 詳細權益曲線圖。
* **UX 優化**：復盤需要高度專注檢視過去的決策，不需要被即時跳動的報價干擾。

---

## 🛠️ 具體執行行動清單 (Action Plan: Phase 0)

我們將此改版定義為 **Phase 0: 前端動線與 UX 徹底重構**，這必須在先前的 Phase 7/8/9 之前優先執行。

- [ ] **任務 0.1：建立全新 Layout 框架與導航列**
  - 在 `src/components/` 建立全局通用的 `AppNavbar.vue` (或 `DashboardTopbar.vue` 升級版)，加入連結四大頁面的 Tabs 或圖示導航 (如：總覽 / 終端 / 籌碼 / 復盤)。
- [ ] **任務 0.2：配置 Router 檔案配置**
  - 更新 `src/router/index.js`，建立上述四個主要的 view components 對應路由。
- [ ] **任務 0.3：抽離與重組組件**
  - 將原本擠在 `App.vue` 或 `Dashboard.vue` 中的組件，分別依據上述規劃打散裝入對應的 4 個視圖中。
  - 實作側邊欄 (Sidebar) 的「收合/展開 (Toggle)」功能，預設進入「看盤終端」時收起非必要面板。
- [ ] **任務 0.4：升級 Toast 通知體驗**
  - 盤中不論在哪個頁面（即使在日誌頁面），當價格觸發警報，由右下角的 `ToastStack` 統一滑出提示，點擊 Toast 即可一鍵跳轉至該標的的「專業看盤終端」。

---

## 🧑‍🎨 UX/Trader 總結
這樣的拆分將原本「瑞士刀式（所有工具全塞出來）」的介面，轉變為**「工作流驅動 (Workflow-driven)」**的專業介面。交易員在不同時段 (盤前、盤中、盤後) 只需要打開專屬頁面，能有效降低大腦解析畫面的時間，大幅提升每天使用的黏著度與專業感！
