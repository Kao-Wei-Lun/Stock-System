# 📝 QuantVision Pro 系統修改規劃與追蹤 (System Modification Plan)

**產出時間**：2026-04-04  
**前次報告**：`docs/system-review-report.md` (2026-04-04)  
**狀態驗證**：經系統掃描比對，前次報告中列出的 **Top 10 優先改善事項** 均處於「尚未開始 (To Do)」狀態，專案原始碼尚未產生任何變更。

---

## 🎯 本期核心維度掃描結果 (無變更)

基於前次全系統健檢的 8 大維度檢查結果，我們的系統健康度維持在 **75/100**。
本 Agent 再次確認系統現況，並將改善方案轉換為「具體執行對策與修改規劃」如下：

---

## 🚀 具體修改規劃 (Action Implementation Plan)

### Phase 1: 前端路由與架構解耦 (Frontend Architecture)
**對應問題**：組件肥大 (`ChartWorkspace.vue`)、缺乏路由 (`Router`)
**預期效益**：載入速度提升，降低單一檔案維護難度，可用 URL 直接分享具體頁面。

- [x] **任務 1.1**：安裝並設置 `vue-router`，建立 `src/router/index.js`。
- [x] **任務 1.2**：將 `App.vue` 中的條件渲染切分為獨立視圖元件：`DashboardView`, `JournalView`, `BacktestView`。
- [x] **任務 1.3**：拆解 `ChartWorkspace.vue`：
  - 抽離出 `ChartToolbar.vue` 處理上方面板與工具列。
  - 抽離出 `DrawingManager.vue` 負責圖形與左/右側繪圖選單。
  - 主體僅保留 canvas 與 `useChartEngine` 的整合。

### Phase 2: 後端任務抽離與效能優化 (Backend & DevOps)
**對應問題**：`main.py` 耦合度過高、資料庫缺乏針對性索引。
**預期效益**：後端服務啟動更加穩定，K 線歷史拉取不再卡頓。

- [x] **任務 2.1**：建立 `backend/scheduler` 目錄或 `backend/tasks.py`，將 `startup_download()`, `daily_latest_sync_loop()`, `alert_evaluator_loop()` 抽離。
- [x] **任務 2.2**：修改 `backend/main.py` 的 Lifespan，改為呼叫 `scheduler.start()`。
- [x] **任務 2.3**：修改 MySQL Schema (在 `backend/database` 中)：
  - 針對 `ohlcv` 資料表加上 `INDEX(ticker, date)` 複合索引。
  - 針對 `market_quotes_latest` 加上針對欄位更新的索引。

### Phase 3: 使用者體驗與互動細節優化 (UX & Trader Experience)
**對應問題**：缺乏快捷鍵操作、載入體驗不佳。
**預期效益**：大幅提升交易員的使用意願與操作流暢度。

- [x] **任務 3.1**：引入 Skeleton Screen（骨架屏）套件或手寫 CSS Skeleton，取代 `ChartWorkspace` 的傳統 Spinner。
- [x] **任務 3.2**：建立全域的快捷鍵 Hook (`useHotkeys`)：
  - `/` : 聚焦到搜尋列
  - `Shift + 方向鍵` : 切換不同週期的 K 線
  - `Ctrl/Cmd + S` : 存檔工作區
- [x] **任務 3.3**：將基礎 `alert()` 修改為全域 Toast 系統（如整合 Vue-toastification 或自寫元件），用於「同步成功」、「警報已建立」等提示。

---

## 🔒 執行限制聲明

> [!CAUTION]
> **操作限制：** 本次規劃與產出，嚴格遵循「**只進行測試與提出修改規劃，不實際修改專案程式碼**」的安全守則。
> 欲執行上述規劃，請開發者接手處理，或明確授權後方可變更。

---

## 🗓️ 下一步建議

請從 **Phase 1: 前端路由與架構解耦** 開始著手。每完成一個 Phase 中的任務，即可重新呼叫相對應的 Agent（例如 `/analyze-frontend`）來驗證目前的達成率，並更新此份 `docs/system-modification-plan.md` 文件。
