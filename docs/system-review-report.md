# 🔍 QuantVision Pro 全面系統健檢報告

**產出時間**：2026-04-04  
**報告目的**：根據 `docs/quantvision-product-spec.md` 與 8 大專業角色維度，對 QuantVision Pro 系統進行全面審查與健檢，提供後續優化方向。

---

## 📊 系統總覽評分卡

| 維度 | 評分 | 最嚴重問題 | 優先行動 |
| --- | --- | --- | --- |
| 🏗️ 後端架構 | **85/100** | `main.py` 仍包含過多背景任務邏輯 | 將背景任務抽離至 `tasks.py` 或獨立的排程模組 |
| 🎨 前端架構 | **60/100** | 單一組件過大（如 `ChartWorkspace.vue` 近 48KB），缺乏前端路由分頁 | 導入 `vue-router`，將複雜 UI 拆分為獨立組件 |
| 🔒 安全與資料 | **78/100** | 尚未區分開發與正式環境的嚴格 CORS 策略 | 增強環境變數載入時的型別驗證與正式環境防護 |
| 🧪 測試品質 | **70/100** | 前端 `App.spec.js` 過大，可能依賴過多整合測試而非單元測試 | 拆分前端測試，並加強回測引擎「前視偏誤」的邊界測試 |
| 📋 產品完成度 | **80/100** | 券商抽象層 (`BrokerProvider`) 尚未完全定義與實作 | 補齊 Broker 介面，為未來串接真實券商保留通道 |
| ⚡ 效能與運維 | **75/100** | 前端為單頁面全加載，缺乏 Lazy Loading；資料庫可能缺乏複合索引 | 前端引入路由與組件懶加載，後端優化 `(ticker, date)` 組合索引 |
| 📈 交易員體驗 | **80/100** | 視覺資訊密度極高，缺乏全域快速鍵 (Hotkeys) | 增加全域快捷操作（如 `/` 搜尋、快速切換週期） |
| 🧑‍🎨 使用者體驗 | **75/100** | 載入中僅有基本 spinner，缺乏 Skeleton 及細膩的微動畫 | 升級 Loading 狀態為 Skeleton，並優化響應式排版 |
| **總分** | **75/100** |  |  |

---

## 🔴 Critical 問題匯總

1. **前端組件肥大 (Frontend Architecture)**
   - **發現**：`ChartWorkspace.vue` (47KB) 與 `JournalPanel.vue` (44KB) 體積過大。將過多業務邏輯（繪圖、技術指標、狀態管理）集中在單一檔案，違反可維護性原則。
   - **影響**：後續要增加新技術指標或工具時極易產生衝突，且渲染效能可能隨元件內狀態變更而大幅下降。

2. **路由缺失 (UX & Architecture)**
   - **發現**：系統依賴單一 Dashboard 塞入全部 Panel（從 `App.vue` 23KB 的體積可看出），切換功能僅仰賴 `v-if` 或元件顯示隱藏。
   - **影響**：使用者無法透過 URL 直接分享或跳轉至特定分析畫面（如特定股票的回測結果 URL），違反現代 Web App 常規使用體驗。

## 🟡 Warning 問題匯總

1. **背景任務高耦合 (Backend Architecture)**
   - **發現**：`backend/main.py` 雖然已將 Router 拆出，但依然囊括了 `startup_download`、`daily_latest_sync_loop` 等大量排程方法。
   - **影響**：當系統擴展時，`main.py` 會難以維護，不利於部署分布式的 Worker。

2. **資料庫讀寫效能盲區 (DevOps)**
   - **發現**：K 線歷史 (OHLCV) 若資料量龐大，對 `ticker` 與 `date` 頻繁進行區間範圍查詢時，若無良好的複合索引，將導致 API 回應變慢。
   - **影響**：不符合產品規格書要求的首屏 < 3 秒的響應體驗。

3. **快捷鍵與鍵盤導航不足 (Trader Experience)**
   - **發現**：依賴滑鼠進行標的切換與操作，對於需要高速瀏覽個股的盤面操作情境效率不彰。
   - **影響**：降低重度交易使用者的黏著度。

## 🔵 Info 問題與建議 (UX & Product)

1. **使用者介面回饋 (UX)**
   - 目前在資料獲取階段較常顯示純粹的 loading spinner，建議可以更換為 Chart Skeleton 與 Table Skeleton，不僅能降低使用者體感等待時間，也能符合「高級質感」的開發原則。
2. **警報與通知 (Product)**
   - 持續完善 Alert 通道的外部串接（例如預留 Telegram / Line Notify API 的環境變數空間），能大幅提升「無需隨時看盤」的產品定位價值。

---

## 🎯 Top 10 優先改善事項

依據投資報酬率與重要性排序：

1. **導入 Vue Router**：將現有 Dashboard, Journal, Backtest 重構為獨立頁面路由，提升 URL 可推廣性。
2. **拆解 ChartWorkspace.vue**：將 Toolbar、DrawingManager、IndPanel 抽離成子元件。
3. **優化 Database Indexes**：檢查並在 backend MySQL OHLCV 表格加上 `(ticker, date)` 複合索引。
4. **抽離 Backend Tasks**：將 `main.py` 內的迴圈任務移至 `tasks.py` 或 `scheduler/`。
5. **引入組件 Lazy Loading**：在 Vue 中採用非同步引入組件 `defineAsyncComponent`，優化首屏加載大小。
6. **實作全域快捷鍵**：新增 Keydown Listener，支援 `Space` (切換標的)、`/` (搜尋)、`Shift + T` (切換週期)。
7. **改善空狀態與載入狀態**：全面升級 Skeleton Screen 替換傳統 Loading Spinner。
8. **嚴格分離測試**：將 `App.spec.js` 拆解為對應各個模組的單元與整合測試。
9. **實作 Toast 通知系統**：取代原有的基礎提示，增強畫面的互動高級感。
10. **完成 Broker Provider 介面定義**：將券商 API 需要的 auth, stream, place_order 等介面規格化以符合第 9 節產品規範。

---

## 💡 建議下一步

此份文件已建立完成。建議您**先進行前端組件的架構整理（引入 Vue Router 與拆分 ChartWorkspace）**，接著**補齊後端排程任務的重構**，這兩項行動將最顯著地提升系統的長期可維護性。
如果您準備好接續修改，請給予指示！
