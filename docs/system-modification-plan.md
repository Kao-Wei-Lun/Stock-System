# 📝 QuantVision Pro 系統修改規劃與追蹤 (System Modification Plan)

**產出時間**：2026-04-04  
**前次報告**：`docs/system-modification-plan.md` (上一版)  
**狀態驗證**：經系統掃描比對，前次報告中列出的 **Phase 1 ~ Phase 3 所有任務已順利完成 ([x])**。我們成功觀測到了 `vue-router` 的建置、`ChartWorkspace.vue` 的拆分 (47KB -> 24KB)、`backend/scheduler.py` 的建置、以及 `ToastStack` 的建立。系統架構已獲得顯著提升！

---

## 🎯 本期核心維度掃描與健康度提升

受惠於前階段的重構，我們的系統健康度已從 **75/100 攀升至 80/100**。各維度最新評分如下：
- 🏗️ 後端架構：**90/100** (排程器已解耦)
- 🎨 前端架構：**78/100** (路由已引進，但仍有遺留的肥大元件)
- 🔒 安全資料：**78/100** (維持)
- 🧪 測試品質：**70/100** (前端規格測試檔尚未隨元件拆解)
- 📋 產品完成度：**80/100** (維持)
- ⚡ 效能運維：**80/100** (優化索引效益顯現)
- 📈 交易員體驗：**85/100** (快捷鍵實作大幅加分)
- 🧑‍🎨 體驗設計：**80/100** (Toast 與載入優化)

基於此現況，本 Agent 提出下一輪「推進系統至 Production Ready」的修改規劃：

---

## 🚀 具體修改規劃 (Action Implementation Plan) - 針對本次及下階段

### Phase 4: 前端剩餘巨型組件拆分 (Frontend Technical Debt)
**對應問題**：`JournalPanel.vue` (44KB) 與 `InstitutionalDashboard.vue` (40KB) 尚未重構，且測試檔案 `App.spec.js` (13KB) 過度集中。
**預期效益**：全面落實組件單一職責，提升前端測試可測性。

- [ ] **任務 4.1**：拆分 `JournalPanel.vue`：將日誌紀錄表單與歷史績效圖表切分為兩個主要的子組件 (`JournalEntryForm.vue`, `JournalStatsView.vue`)。
- [ ] **任務 4.2**：拆解 `InstitutionalDashboard.vue`：分離三大法人買賣超、期權未平倉圖表至獨立子元件。
- [ ] **任務 4.3**：重構測試檔，將 `App.spec.js` 打散，對應至新建立的 `DashboardView.spec.js` 或 Router 級別的整合測試。

### Phase 5: 券商抽象層與正式報價準備 (Broker & Provider Abstraction)
**對應問題**：規格書 §9 及 §3.4 要求的 `BrokerProvider` 尚未完全定義，阻礙未來下單與真實券商串流的實作。
**預期效益**：為未來對接券商 API (如 Shioaji、Fubon 等) 奠定標準。

- [ ] **任務 5.1**：於 `backend/providers/` 或相應的模組中建立 `broker_provider.py`，定義 `BrokerProvider` 抽象基底類別 (包含 `authenticate`, `stream_quotes`, `place_order`, `get_positions` 等抽象方法)。
- [ ] **任務 5.2**：建立一個 `MockBrokerProvider` 用於開發階段的延遲狀態模擬與斷線情境測試。
- [ ] **任務 5.3**：將 Frontend 凡有報價欄位的地方全部與 Broker 狀態連接（顯示來源是模擬券商還是真實券商）。

### Phase 6: 測試覆蓋率與前視偏誤防護 (Testing & Security)
**對應問題**：回測模組的靈魂在於絕不可看見未來，目前需加強對抗「前視偏誤」的邊界測試。
**預期效益**：提高系統回測結算的信賴度，讓交易員能安心依賴訊號。

- [ ] **任務 6.1**：在 `backend/tests/` 建立針對 `backtest_engine.py` 的防禦性測試，傳入特定的 Mock OHLCV，斷言「今日的訊號絕對不包含明天的資訊」。
- [ ] **任務 6.2**：為 `.env` 變數加入嚴格啟動校驗，確保在啟動 `main.py` 之前必定攔截缺失的 Token 配置。

---

## 🔒 執行限制聲明

> [!CAUTION]
> **操作限制：** 本次規劃與產出，嚴格遵循「**只進行測試與提出修改規劃，不實際修改專案程式碼**」的安全守則。
> 本 Agent 經過驗證，已明確知悉前次任務成功執行；目前已將下一步指示擬定完畢，交由您後續手動實作。

---

## 🗓️ 下一步建議

恭喜完成第一輪大重構！接下來建議先從 **Phase 4: 前端剩餘巨型組件拆分** 切入，延續之前的經驗來收斂前端架構。完成後，再次呼叫 `/analyze-frontend` 或 `/full-system-review` 來進行新一輪的掃描。
