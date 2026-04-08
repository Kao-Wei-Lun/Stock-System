# 📝 QuantVision Pro 系統修改規劃與追蹤 (System Modification Plan)

**產出時間**：2026-04-04  
**前次報告**：`docs/system-modification-plan.md` (上一版)  
**狀態驗證**：
經系統掃描比對，您成功完成了 **Phase 4 (前端剩餘巨型組件拆分)** 與 **Phase 6 (測試覆蓋率與前視偏誤防護)**。目前我們觀測到 `institutional/` 與 `journal/` 子模組的拆出，前端整體架構更具備擴展性。後端測試的補強與啟動檢查也到位了。
根據您的特別批示，**Phase 5 (券商抽象層)** 將暫停處理，待相關 API 申請完成後再行施作。

---

## 🎯 本期核心維度掃描與健康度評估

隨着技術債的清理與防禦性測試的補強，整體系統健康度正式邁進 **84/100** 的高穩定位階：
- 🏗️ 後端架構：**92/100** (環境變數啟動校驗補強了架構穩定度)
- 🎨 前端架構：**88/100** (大型元件事實上被拆解完成，大幅提升可讀性)
- 🔒 安全資料：**85/100** (啟動前檢查可防止敏感設置遺漏)
- 🧪 測試品質：**80/100** (回測引擎的 Look-ahead 偏誤測試為系統可信度核心！)
- 📋 產品完成度：**80/100** (維持，等待 Phase 5 解鎖)
- ⚡ 效能運維：**80/100** (維持)
- 📈 交易員體驗：**88/100** (系統出錯機率降低，交易員信心提升)
- 🧑‍🎨 體驗設計：**80/100** (維持)

既然核心業務模組已臻於成熟 (Production Ready 邊緣)，本 Agent 將下一階段的焦點轉向 **「上線前準備 (Pre-flight) 與自動化」**：

---

## 🚀 具體修改規劃 (Action Implementation Plan) - 系統上線前擴充

### Phase 0: 交易員與前端 UX 體驗重構 (Workflow & UI Redesign) [🌟 當前最高優先級]
**對應問題**：目前所有功能全數擠在單一畫面，造成強烈「認知負荷」，嚴重損害看盤效率與體驗。
**預期效益**：將系統切分為四大專屬工作區 (總覽 / 終端 / 籌碼 / 復盤)，根據交易員的「盤前、盤中、盤後」工作流徹底分流，提供彭博/TradingView等級的專業純淨感。（詳細分析見 `docs/frontend-ux-redesign-plan.md`）

- [ ] **任務 0.1**：實作全域頂部導航列 (`AppNavbar.vue` 或 `DashboardTopbar.vue`)，將功能切分並綁定至獨立的 Router 連結。
- [ ] **任務 0.2**：建立 **大盤總覽頁面 (Market Overview)**，專門容納大盤風險、事件日曆、選股掃描結果與自選股總表。
- [ ] **任務 0.3**：打造極端大畫面的 **專業圖表終端 (Pro Chart Terminal)**，在此頁面將側邊欄改為可完全收合，盡可能放大 K 線空間。
- [ ] **任務 0.4**：將原有的日誌、回測等龐大資訊，統整移動至獨立的 **績效與回測 (Journal & Backtest)** 與 **法人籌碼 (Institutional)** 專屬頁面中。

---


### Phase 5: 券商抽象層與正式報價準備 (Broker & Provider Abstraction) [⏸️ 暫停中：等待 API 申請]
**對應問題**：規格書要求的 `BrokerProvider` 尚未完全定義，缺少真實券商串接介面。
**預期效益**：為未來對接正式券商 API 預留擴充標準。
- [ ] **任務 5.1**：於 `backend/providers/` 建立 `broker_provider.py`，定義 `BrokerProvider` 抽象基底類別。
- [ ] **任務 5.2**：建立 `MockBrokerProvider` 用於開發階段的延遲狀態模擬與斷線情境測試。
- [ ] **任務 5.3**：將前端有報價欄位的地方與 Broker 狀態連接。

---


### Phase 7: 容器化與安裝檔封裝 (Docker & Local Execution Packaging)
**對應問題**：既為個人使用，不需部署至雲端作 CI/CD，但常需在不同本機電腦間無痛轉移設定。
**預期效益**：只要有 Docker 的相對環境或是透過一鍵執行腳本，即可快速重現專屬的看盤分析系統。

- [ ] **任務 7.1**：建立 `Dockerfile` 與 `docker-compose.yml`，將 前端靜態檔案、後端 FastAPI 服務與 MySQL 資料庫打包設定為一個可攜式服務群。
- [ ] **任務 7.2**：撰寫一個輕量化的一鍵啟動腳本 (如 `start.bat` / `start.sh`)，供不想使用 Docker 的環境直接雙擊啟動。
- [ ] **任務 7.3**：(選擇性) 評估使用 Tauri, Electron 或是 PyInstaller 將系統完全封裝成可點擊的桌面應用程式 (.exe / .app)，徹底在地化。

### Phase 8: 效能與 Bundle 尺寸極致優化 (Performance & Build)
**對應問題**：在前端逐漸擴充後，Vite 的打包檔案可能會變得過大，影響首次載入速度。
**預期效益**：首屏渲染控制在 1.5 秒以內，提升整體操作滑順感。

- [ ] **任務 8.1**：在 `src/router/index.js` 將所有路由級視圖 (如 `BacktestView`, `InstitutionalView`) 全面改為異步加載 `() => import('...')`。
- [ ] **任務 8.2**：在 `vite.config.js` 配置 `rollupOptions.output.manualChunks`，將 `vue`, `echarts` 或圖表模組強制分離打包 (Vendor Splitting)。
- [ ] **任務 8.3**：建立統一的 Axios 或 Fetch 請求池機制，優化同頻率的 API 請求並取消快速切換頁面時的僵屍請求 (AbortController)。

### Phase 9: 外部推播與自動化告警 (External Notification Bridges)
**對應問題**：目前 Alert 邏輯侷限於站內通知，無法真正解放盯盤時間。
**預期效益**：交易員盤中無需開著網頁，即可精準接收突破警報。

- [ ] **任務 9.1**：實作 Telegram Bot API 或 Discord Webhook 的通訊介面 (`backend/providers/notification_provider.py`)。
- [ ] **任務 9.2**：在前端「通知設定」面板中加入輸入 Webhook URL 或 Bot Token/Chat ID 的欄位，並將之保存於 `user_preferences`。

*(Phase 5 將持續處於 [Paused] 狀態，直到您通知 API 申請完成)*

---

## 🔒 執行限制聲明

> [!CAUTION]
> **操作限制：** 本次規劃與產出，嚴格遵循「**只進行系統掃描、驗證與提出修改規劃，不對專案進行任何實際程式碼編修**」的安全守則。
> 您的程式碼成果令人驚艷！請依據新階段手動進行開發，祝 Coding 愉快！

---

## 🗓️ 下一步建議

在您準備推上線前，強烈建議可以優先佈署 **Phase 8 (效能與 Bundle 尺寸優化)** 與 **Phase 7 (CI/CD)**。當您完成任一階段後，請隨時呼叫 `/full-system-review` 來讓本 Agent 為您驗證新血脈的注入！
