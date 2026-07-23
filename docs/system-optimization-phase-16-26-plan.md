# QuantVision 系統優化 Phase 16～26 詳細修改與驗收規畫

**版本**：v1.0

**建立日期**：2026-07-23

**適用專案**：QuantVision Pro／Stock-System

**適用分支基準**：`codex/realtime-reliability-phases`

**規畫基準 commit**：`a45fa3a`

**前置成果**：

- `docs/terminal-performance-architecture-plan.md`：Phase 0～6。
- `docs/advanced-system-performance-optimization-plan.md`：Phase 7～15。
- `docs/performance/final-acceptance-matrix.md`：Phase 0～15 最終 Gate。
- `docs/system-audit-2026-07-22.md`：全系統功能、安全與產品盤點。

**規畫性質**：後續實作、測試、資料庫操作、正式環境驗收、回滾與 Git 提交的執行依據。

**目前狀態**：本文件只建立修改規畫，Phase 16～26 尚未開始實作。

---

## 1. 規畫目的

Phase 0～15 已完成期貨 K 線 DB-first、即時行情廣播與持久化解耦、前端每幀合併、圖表增量更新、bounded 查詢、production SPA、IndexedDB 快取、工作區延遲載入、回測 ProcessPool、資產報價限流與效能 Gate。

目前不需要再次重寫 K 線或即時行情架構。後續應處理實際量測後仍存在的下列缺口：

1. `/api/db/stats` 仍會對大型資料表執行精確全表統計。
2. 應用程式啟動會等待五個富邦帳號依序初始化，延後前端可用時間。
3. 富邦重連雖已存在，仍缺少完整故障注入、單帳號狀態機與訂閱恢復驗收。
4. 模擬交易保證金估算會對不相容帳號反覆呼叫，錯誤又可能被前端隱藏。
5. `taiwan_chip_snapshots`、`sync_log`、新聞與大型 JSON 快照缺少正式資料生命週期。
6. critical backup 不包含最大的籌碼與 K 線資料，需要明確的可重建性與還原策略。
7. Yahoo／海外商品更新頻率未依市場時段、商品類型與 provider 狀態調整。
8. Y 軸可被滾輪意外切換成手動，前端也缺少全域非同步元件錯誤邊界。
9. 單元測試完整，但缺少 production SPA 的自動化瀏覽器端到端測試。
10. 效能指標多為即時記憶體值，缺少短期趨勢、服務監督與正式／測試日誌隔離。
11. 多個大型模組仍承擔過多責任，增加後續修改的回歸風險。
12. 系統以個人本機使用為主，但開啟 LAN 存取時仍必須 fail closed。

本規畫不接真實下單、不導入微服務、不以 Redis 或增加 Uvicorn worker 作為預設解法，也不重寫已通過 Phase 0～15 Gate 的功能。

---

## 2. 已確認的現況基準

以下為 2026-07-23 盤點時的實際服務與資料庫狀態。實作 Phase 16 前必須重新量測並保存新的 before baseline，不得直接把本節數值當成修改後結果。

### 2.1 即時與資料庫互動指標

| 指標 | 盤點值 | 判讀 |
|---|---:|---|
| DB query p50 | 約 3.19 ms | 正常 |
| DB query p95 | 約 4.34 ms | 正常 |
| DB query max | 約 16.18 ms | 正常 |
| DB pool acquire p95 | 約 3.05 ms | 正常 |
| 即時 ingress | 84,225 | 已有實際負載 |
| 即時 broadcast | 205,279 | 正常 |
| 即時 dropped | 0 | 正常 |
| ingress → broadcast p95 | 約 3.18 ms | 正常 |
| persistence queue age p95 | 約 531 ms | 略高於 Phase 15 理想值，但未造成掉資料 |
| persistence queue max depth | 5 | 正常 |
| persistence failures | 0 | 正常 |

結論：一般 DB 查詢與即時廣播不是目前主要瓶頸，不得因單一慢 API 而重寫整個 repository 或即時架構。

### 2.2 已確認的慢 API

`GET /api/db/stats` 在 10 秒 timeout 內未完成。

目前實作會執行：

- `COUNT(*) FROM ohlcv`。
- `COUNT(DISTINCT ticker)`。
- 依 ticker 聚合與排序。
- 多個其他資料表的精確筆數統計。

該資料原本提供 legacy 右側資料庫面板使用，但目前主畫面已不再匯入該 legacy 元件，`useDashboard()` 仍保留載入與全量同步後呼叫。

### 2.3 啟動時間

盤點時序：

1. 後端啟動與 MySQL 初始化約在 1 秒內完成。
2. 五個富邦帳號依序初始化。
3. 每個帳號再建立 stock 與 futopt WebSocket。
4. 所有帳號完成後應用程式才宣告 startup complete。

五個帳號約增加 10 秒啟動等待。這是 readiness 定義與 provider warmup 排程問題，不是 production SPA 需要另一個前端 service。

### 2.4 資料規模

`information_schema` 估算：

| 資料表 | 估算列數 | Data | Index | 主要風險 |
|---|---:|---:|---:|---|
| `taiwan_chip_snapshots` | 約 30,690,718 | 約 40.35 GiB | 約 3.05 GiB | 大型 JSON、無生命週期 |
| `ohlcv` | 約 8,585,428 | 約 1.25 GiB | 約 1.50 GiB | 長期成長、完整備份成本 |
| `sync_log` | 約 1,003,430 | 約 61 MiB | 約 53 MiB | 每次同步持續累積 |
| `news_articles` | 約 106,705 | 約 142 MiB | 約 33 MiB | 舊新聞與重複內容 |
| `fubon_market_snapshots` | 約 134 | 約 63 MiB | 小 | 單筆 JSON 很大 |

以上為估算值；任何封存或刪除前都必須以 dry-run 統計、資料日期範圍、可重建性與備份狀態再次確認。

### 2.5 備份現況

- full SQL backup 約 46 GiB。
- critical backup 約 291 MiB。
- critical scope 排除 `taiwan_chip_snapshots` 與 `ohlcv` 的資料列。
- 備份已有 manifest、保留政策與 test-restore 工具。
- 目前缺少依資料類別定義的 RPO／RTO，以及市場歷史資料的分層或增量備份。

### 2.6 資料品質

盤點時資料品質狀態：

- MySQL、migration、scheduler、backup、WebSocket、富邦帳號及期貨 recorder 健康。
- 五個 Yahoo 商品超過現有 30 分鐘 freshness 門檻：
  - `0700.HK`
  - `9988.HK`
  - `BTC-USD`
  - `ETH-USD`
  - `^HSI`

這些是海外／加密資產的 Yahoo quote snapshot 新鮮度問題，不代表台股或期貨 K 線持久化失敗。

### 2.7 測試與正式環境缺口

- Phase 15 已建立後端、前端、bundle、ProcessPool 與 DB `EXPLAIN` Gate。
- 尚未建立專案自己的 Playwright／Cypress production SPA E2E。
- 60 分鐘真實富邦 soak 工具已存在，但仍需在開盤與富邦連線環境正式執行。
- 測試期間部分 fixture 訊息會寫入 production 使用的 log 檔，造成錯誤統計失真。

### 2.8 大型模組

盤點時主要大型檔案：

| 模組 | 約略行數 | 風險 |
|---|---:|---|
| `scripts/ai_daily_report_tw.py` | 4,261 | 資料組裝、評分、報告與傳送耦合 |
| `frontend/src/composables/useDashboard.js` | 3,287 | 多工作區狀態與生命週期集中 |
| `frontend/src/composables/useChartEngine.js` | 3,279 | 比例尺、互動、繪圖與指標集中 |
| `backend/asset_tracking_service.py` | 1,659 | 查詢、估值、匯入與 orchestration 集中 |
| `frontend/src/components/PaperTradingDashboard.vue` | 1,592 | 帳戶、Bot、回放與保證金集中 |
| `backend/routers/assets.py` | 1,570 | HTTP contract 與多種資產 use case 集中 |

大型檔案本身不是效能錯誤，但會提高每次修改的回歸面。拆分必須在功能修正與 E2E Gate 完成後漸進進行。

---

## 3. 優先級與階段依賴

| Phase | 優先級 | 主題 | 依賴 |
|---|---|---|---|
| 16 | P0 | 移除 DB 統計熱點與 legacy 殘留路徑 | Phase 15 |
| 17 | P0 | 兩階段 readiness 與 provider 背景暖機 | Phase 16 |
| 18 | P0 | 富邦復原、訂閱一致性與模擬保證金 | Phase 17 |
| 19 | P0 | 備份分層與完整還原演練 | Phase 18 |
| 20 | P0 | 大型資料生命週期與封存 | Phase 19 |
| 21 | P1 | Yahoo／海外商品 freshness 排程 | Phase 20 |
| 22 | P1 | 前端錯誤韌性、Y 軸與模擬交易 UX | Phase 18、21 |
| 23 | P1 | Production SPA E2E 與 60 分鐘 soak | Phase 22 |
| 24 | P1 | 指標趨勢、服務監督與日誌隔離 | Phase 23 |
| 25 | P2 | 大型模組漸進拆分 | Phase 23 |
| 26 | 條件式 P0 | LAN 存取安全與 fail-closed | 可獨立；若開放 LAN 必須提前 |

不可在 Phase 19 的備份與還原 Gate 完成前執行 Phase 20 的資料封存或清理。

---

## 4. 全域執行與 Git 規則

### 4.1 每個 Phase 的固定流程

每個 Phase 必須依序執行：

1. 確認工作區狀態，保留使用者既有修改。
2. 保存修改前 baseline。
3. 先補 characterization／failure-path 測試。
4. 實作該 Phase，禁止混入下一個 Phase。
5. 執行該 Phase 專屬測試。
6. 執行完整後端回歸。
7. 執行完整前端回歸。
8. 執行 production build。
9. 視修改範圍執行 live check、DB `EXPLAIN`、restore drill、E2E 或 soak。
10. 執行 `git diff --check`。
11. 人工檢查 diff，不得包含帳密、資產明細、持倉、完整 API payload 或 private `.env`。
12. 所有 Gate 通過後才能建立該 Phase commit。
13. 保存 after 結果與 commit SHA，再進入下一階段。

### 4.2 全域回歸指令

後端：

```powershell
venv\Scripts\python.exe -m pytest backend/tests -q
```

前端：

```powershell
Set-Location frontend
npm test -- --run
npm run build
```

Phase 15 效能 Gate：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-final-performance-gate.ps1
```

Git whitespace：

```powershell
git diff --check
```

若當階段只修改文件，可以不執行完整程式回歸；但正式開始 Phase 16 前仍必須建立新的全域 baseline。

### 4.3 測試數量規則

- 通過數不得無理由下降。
- skipped／xfail 必須記錄原因。
- 不得為了通過 Gate 移除既有測試。
- 新增 timeout 時要測 timeout 行為，不能只測正常路徑。
- 外部 provider 測試預設使用 stub／fixture，不直接消耗真實富邦或 Yahoo 額度。
- 真實富邦測試只能訂閱行情，不得送出真實委託。

### 4.4 資料庫安全規則

- 所有 schema 變更建立新的 versioned migration，不可修改已套用 migration checksum。
- migration 需支援 plan／dry-run。
- 大型表 ALTER 前必須量測鎖定風險、磁碟空間與估算時間。
- 封存流程一律採「複製 → 筆數／checksum 驗證 → 標記 → 下一個維護窗才可清理」。
- 不可在同一 transaction 直接刪除數百萬筆。
- 個人資產、交易紀錄、紙上交易與設定資料不適用自動 retention。
- `ohlcv` 預設不刪除；除非已確認來源可重建且使用者明確同意。

### 4.5 Git 規則

- 一個 Phase 至少一個獨立 commit。
- 若 Phase 內容過大，可依 schema、backend、frontend、tests 拆 commit，但最後狀態必須通過完整 Gate。
- 建議 commit 格式：`phase-N: <single purpose>`。
- 不自動 push；除非使用者另外要求。
- `.env`、API key、帳號、憑證、備份 SQL、個人資產 CSV、測試產生的真實資料與 `.codex/config.toml` 不得加入 Git。

### 4.6 每階段結果檔

每個 Phase 建議保存：

```text
docs/optimization/phase-N-before.json
docs/optimization/phase-N-after.json
docs/optimization/phase-N-acceptance.md
```

結果只能保存彙總數值，不保存：

- 富邦帳號。
- 姓名或身分證字號。
- 持倉、現金與交易明細。
- API key／token。
- 完整 SQL dump。
- 完整外部 provider 回應。

---

## 5. Phase 16：DB 統計熱點與 legacy 路徑清理

### 5.1 目標

確保管理統計不再掃描大型 `ohlcv` 表，也不會因已未使用的 legacy UI 阻塞全量同步或工作區載入。

### 5.2 主要修改範圍

- `backend/repositories/sync.py`
- `backend/routers/market_data.py`
- `frontend/src/composables/useDashboard.js`
- `frontend/src/components/legacy/RightSidebar.vue`
- 對應 backend／frontend tests
- 新增 DB stats benchmark／query plan 檢查

### 5.3 詳細修改

1. 先以 import graph 與 production manifest 再次確認 `RightSidebar.vue` 未被正式畫面使用。
2. 移除 `syncAll()`、workspace preset 與其他互動路徑對 `loadDbStats()` 的強制等待。
3. 若 DB 統計頁已完全無入口：
   - 移除前端 dead state、dead action 與只服務 legacy 元件的 props。
   - legacy 元件先標記 deprecated；確認無使用者工作區依賴後才刪除。
4. 保留 `/api/db/stats` 相容性，但預設改為快速摘要：
   - 以 `information_schema.TABLES.TABLE_ROWS` 回傳估算列數。
   - 回傳 `estimated: true`。
   - 回傳 `as_of`、`cache_age_seconds`。
   - 不在請求內執行全表 `COUNT(DISTINCT ...)` 或全表 `GROUP BY`。
5. 若仍需要精確統計：
   - 建立明確的 background refresh command。
   - 只允許單一 refresh 執行。
   - 設定 wall-clock timeout。
   - 結果保存於 bounded TTL cache。
   - 使用管理／背景資源，不占用互動式 DB connection semaphore。
6. API timeout 時回傳最後成功快取與 `stale: true`，不得讓畫面無限等待。
7. 統計 API 不回傳敏感資料表內容，只回筆數、日期與 ticker 彙總。

### 5.4 測試

- repository 單元測試確認 default path 不產生 `COUNT(*) FROM ohlcv`。
- API contract 測試 `estimated`、`as_of`、`stale`。
- timeout 後回傳舊 cache 的測試。
- concurrent refresh single-flight 測試。
- frontend 測試確認全量同步不等待 DB stats。
- production manifest 確認 legacy sidebar 不進入正式 chunk graph。
- live endpoint 連續至少 20 次量測 median／p95／max。

### 5.5 驗收 Gate

- [ ] `/api/db/stats` warm p95 ≤ 300 ms。
- [ ] 單次 max ≤ 1,000 ms。
- [ ] 預設路徑無 `ohlcv` 全表掃描。
- [ ] `syncAll()` 完成時間不再包含 DB stats 等待。
- [ ] endpoint timeout 不占住 DB pool。
- [ ] 既有 API 欄位保留或提供向後相容 mapping。
- [ ] 完整 backend、frontend、build、Phase 15 Gate 通過。

### 5.6 建議 commit

```text
phase-16: remove blocking database statistics path
```

### 5.7 回滾

- 可恢復舊 frontend 統計入口，但不得恢復全表統計到互動熱路徑。
- 新 endpoint 可透過 feature flag 切回 cached exact result。
- 回滾不得刪除已建立的效能量測與 timeout。

---

## 6. Phase 17：兩階段 readiness 與 provider 背景暖機

### 6.1 目標

讓 MySQL、API 與 production SPA 在 3 秒內可使用；富邦多帳號在背景初始化，不再阻擋整個應用 startup。

### 6.2 主要修改範圍

- `backend/main.py`
- `backend/fubon_realtime_pool.py`
- `backend/scheduler.py`
- `backend/data_quality_service.py`
- `scripts/start.bat`
- 前端連線／系統狀態元件
- 對應 lifecycle、startup 與 frontend tests

### 6.3 Ready 狀態定義

狀態分為：

- `starting`：DB 或 migration 尚未完成。
- `ready_degraded`：API／SPA 可用，但部分 provider 尚在連線或失敗。
- `ready`：必要本機元件正常，主要 provider 已就緒。
- `stopping`：正在 drain queue 與取消背景工作。

基本 readiness 只要求：

- MySQL 可查詢。
- migration 版本相容。
- production SPA artifact 存在。
- scheduler 能建立必要工作。

富邦、Yahoo 或市場同步失敗應使狀態 degraded，但不阻止使用已保存的 K 線、資產與分析資料。

### 6.4 詳細修改

1. 將 `fubon_realtime_pool.init_from_db()` 移出阻塞 lifespan 路徑。
2. 建立受管理的 provider warmup task：
   - 主要期貨帳號優先。
   - 其餘帳號背景依序連線。
   - SDK thread-safety 未證實前，不直接將五帳號完全平行化。
3. 每個帳號依用途決定是否建立 stock、futopt 或兩者 WebSocket。
4. warmup task 必須：
   - 有狀態。
   - 可取消。
   - shutdown 時等待合理 timeout。
   - 不因單一帳號失敗取消其他帳號。
5. `/api/ready` 增加 component 欄位，但保持 `status` 與既有 `start.bat` 相容。
6. 前端顯示：
   - 本機資料可用。
   - 富邦連線中 `n/total`。
   - 哪一個市場仍在 degraded。
7. `start.bat` 仍只啟動單一 production service；不得新增不必要的 Vite CMD。
8. browser 只在 SPA HTTP 可用後開啟一次。

### 6.5 測試

- lifespan 測試：富邦 provider 延遲 20 秒，ready 仍在門檻內完成。
- 單一帳號 warmup 失敗，其他帳號繼續。
- shutdown 取消未完成 warmup。
- provider task 不重複建立。
- SPA 缺檔時 readiness 正確失敗。
- `start.bat` smoke：空閒 port、已占用 port、backend 啟動失敗、browser open 失敗。

### 6.6 驗收 Gate

- [ ] cold start `/api/ready` p95 ≤ 3 秒。
- [ ] `/app/` p95 ≤ 3 秒可回應。
- [ ] 正常帳號在 15 秒內完成背景暖機。
- [ ] 單一富邦帳號失敗不阻擋前端。
- [ ] 不產生重複 provider task 或重複 WebSocket。
- [ ] graceful shutdown 可完成 recorder drain。
- [ ] 完整回歸與 production build 通過。

### 6.7 建議 commit

```text
phase-17: make provider warmup non-blocking
```

### 6.8 回滾

- 可將主要帳號恢復為阻塞暖機，但其他帳號仍保留背景載入。
- 保留新的 component health，不回滾可觀測性。

---

## 7. Phase 18：富邦復原、訂閱一致性與模擬保證金

### 7.1 目標

富邦股票或期權 WebSocket 斷線後能在不重啟整個系統的情況下自行恢復；模擬交易保證金不再因帳號類別錯誤反覆呼叫。

### 7.2 主要修改範圍

- `backend/fubon_provider.py`
- `backend/fubon_realtime_pool.py`
- 富邦設定／狀態 routers
- `backend/paper_trading/margin_sync.py`
- paper trading repository／schema migration
- `frontend/src/components/PaperTradingDashboard.vue`
- 富邦設定頁與系統狀態頁

### 7.3 富邦連線狀態機

每個「帳號 × 市場」維護獨立狀態：

```text
disabled
→ disconnected
→ connecting
→ connected
→ degraded
→ backoff
→ connecting
```

需保存：

- `last_connected_at`
- `last_message_at`
- `last_disconnect_at`
- `last_error_code`
- `last_error_category`
- `reconnect_attempt`
- `next_retry_at`
- `subscription_count`
- `desired_subscription_count`

### 7.4 詳細修改

1. 對 connect／login／reconnect 加入 per-account single-flight lock。
2. 對 session invalid、WebSocket close、heartbeat timeout 分類處理。
3. 暫時錯誤使用 exponential backoff + jitter。
4. 認證／帳號類別錯誤停止無限重試，標示 `configuration_error`。
5. 重連完成後由 desired subscription ledger 恢復訂閱。
6. alias 與實體合約引用計數不得因重連重複增加。
7. 手動重新連線 API 只重置指定帳號／市場，不重啟整個 backend。
8. recorder 與 quote broadcaster 在 provider degraded 時繼續服務 DB 快取資料。
9. 增加故障注入測試：
   - close event。
   - heartbeat timeout。
   - login expired。
   - subscribe 部分失敗。
   - reconnect 中再次收到 reconnect request。

### 7.5 模擬保證金修改

1. 建立可用 account capability：
   - `stock`
   - `futures`
   - `options`
   - `unknown`
2. 保證金估算只能選 futures 相容帳號。
3. 頁面載入先使用最後成功的持久值，不自動阻塞 UI。
4. 新增：
   - `margin_last_attempt_at`
   - `margin_last_success_at`
   - `margin_last_error`
   - `margin_error_category`
   - `margin_next_retry_at`
5. 暫時錯誤 negative cache 建議 15～60 分鐘。
6. 設定錯誤不自動重試，需使用者修正帳號或手動刷新。
7. 每日 scheduler 只執行一次正常同步。
8. 前端明確顯示：
   - 目前使用的持久保證金。
   - 最後成功時間。
   - 更新失敗原因。
   - 手動重新取得按鈕。
9. `loadAccounts()`、`loadBots()`、`loadReplayRuns()` 不可再以空 `catch` 隱藏錯誤。

### 7.6 測試

- 斷線後重連 single-flight。
- 重連成功後 desired subscriptions 完整且無重複。
- 永久設定錯誤不持續重試。
- 暫時錯誤依 backoff 重試。
- 五帳號中單一失敗不影響其他帳號。
- 保證金選擇 futures 帳號。
- 錯誤時保留 last-success 值與時間。
- Paper UI 的 loading／empty／error／stale／success 狀態。

### 7.7 驗收 Gate

- [ ] 故障注入後 95% reconnect ≤ 60 秒。
- [ ] reconnect 不需要重啟 backend。
- [ ] duplicate WebSocket、duplicate subscription、duplicate recorder 均為 0。
- [ ] configuration error 每小時自動嘗試次數為 0。
- [ ] paper 頁面載入不等待 margin provider。
- [ ] last-success 值不被失敗結果覆蓋。
- [ ] 完整回歸、build 與至少 30 分鐘 stub soak 通過。

### 7.8 建議 commit

可拆為：

```text
phase-18a: harden fubon reconnect state
phase-18b: make paper margin refresh resilient
```

Phase 18 最終 Gate 通過後再進入 Phase 19。

### 7.9 回滾

- reconnect 新策略可用 feature flag 切回既有 backoff。
- margin 新欄位只新增不刪除；回滾程式時保留 migration。
- 不回滾 subscription ledger 與故障遙測。

---

## 8. Phase 19：備份分層與完整還原演練

### 8.1 目標

在執行任何大型資料封存前，先確保個人資料與不可重建市場資料都有明確備份、RPO、RTO 與實際還原證據。

### 8.2 資料分級

| 等級 | 資料 | 原則 |
|---|---|---|
| A：不可遺失 | 個人資產、現金、交易、匯入批次、紙上交易、設定、工作區、警報、日誌 | 每日 critical backup，必須實際還原 |
| B：成本高或部分不可重建 | 籌碼彙總、分點 JSON、富邦市場快照、訊號驗證 | 週期性歷史備份或可驗證封存 |
| C：可重新下載 | Yahoo 歷史、部分 OHLCV、新聞 | 保存來源、範圍與重建腳本；仍需避免無限重新下載 |
| D：暫存 | quote cache、短期 performance metrics | 有明確 TTL，不列入永久備份 |

若某資料來源無法可靠重新取得，不得只因資料量大就列為 C。

### 8.3 詳細修改

1. 擴充 backup manifest：
   - schema version。
   - scope。
   - included／excluded table data。
   - min／max business date。
   - row-count estimate。
   - checksum。
   - compressed size。
2. 增加 `market-history` 或等價分層 scope：
   - 籌碼歷史。
   - OHLCV。
   - 市場快照。
3. 支援按日期範圍或 partition 備份，避免每次重做 46 GiB full dump。
4. retention 同時考慮：
   - 天數。
   - 最少份數。
   - 總磁碟上限。
   - 每種 scope 至少保留數。
5. restore drill 只能還原到明確的暫存 schema。
6. restore drill 完成後驗證：
   - migration version。
   - 核心表存在。
   - 筆數／日期範圍。
   - 隨機抽樣 checksum。
   - 個人資產 ledger 可重建 overview。
7. 定義建議目標：
   - A 類 RPO ≤ 24 小時。
   - A 類本機 restore RTO ≤ 60 分鐘。
   - B 類 RPO ≤ 7 天或有可驗證 archive。
8. 還原測試不得將真實私人資料輸出到測試 log 或 Git。

### 8.4 測試

- backup manifest contract。
- scope include／exclude。
- retention by age／count／bytes。
- corrupted dump／checksum mismatch。
- restore 到錯誤 schema name 必須拒絕。
- critical restore integration。
- market-history 小型 fixture 的分段 backup／restore。

### 8.5 驗收 Gate

- [ ] 最新 critical backup 通過實際 restore drill。
- [ ] A 類資料可重建且數值一致。
- [ ] B 類資料有完整備份或書面可重建證據。
- [ ] full／history backup 失敗不會刪除上一份健康備份。
- [ ] retention 不會清除每個 scope 的最後健康備份。
- [ ] manifest 不含秘密或個人明細。

### 8.6 建議 commit

```text
phase-19: add tiered backup and restore verification
```

### 8.7 回滾

- 新 scope 可停用，但不可刪除已建立的健康備份。
- migration 或 metadata 欄位只新增不破壞舊 manifest reader。

---

## 9. Phase 20：大型資料生命週期與封存

### 9.1 目標

控制籌碼、同步紀錄、新聞及大型 JSON 的長期成長，且不影響近期查詢、回測、報表或資料復原。

### 9.2 建議預設政策

所有天數必須可設定，並在首次啟用前顯示 dry-run。

| 資料 | 線上保存建議 | 長期策略 |
|---|---|---|
| `ohlcv` | 預設全部保留 | 先分割／優化索引，不自動刪除 |
| 籌碼數值彙總 | 預設全部保留 | 舊資料可移到 history partition |
| 籌碼分點大型 JSON | 近 1～2 年 | 壓縮 archive 或 detail history |
| `sync_log` 明細 | 90 天 | 每日彙總長期保留 |
| `news_articles` | 180～365 天 | 保存必要 metadata，清理重複全文 |
| 富邦大型市場快照 | 365 天 | 壓縮按日 archive |
| performance snapshot | 7～30 天 | 分鐘資料降採樣為小時／日彙總 |

### 9.3 詳細修改

1. 新增唯讀 storage audit command：
   - 表大小。
   - 日期範圍。
   - 每月新增列數。
   - NULL／重複比例。
   - archive 候選筆數與估算 bytes。
2. 籌碼資料：
   - 分離常用數值欄位與大型 `branch_payload_json`。
   - 主查詢預設不讀大型 JSON。
   - 詳細分點內容只有使用者展開時才載入。
   - 舊 JSON 先 archive，再將 online detail 標記為 archived。
3. `sync_log`：
   - 建立 daily summary。
   - 分批封存／清理 90 天前明細。
   - 保留失敗摘要、duration 與 row counts。
4. 新聞：
   - 依 canonical URL／provider id 去重。
   - 保留標題、來源、時間、ticker mapping。
   - 過期全文可清理，但不得破壞歷史報告引用。
5. 富邦市場快照：
   - 檢查大型欄位是否每列重複 schema／metadata。
   - 可壓縮的 payload 改以 compressed blob 或外部 archive manifest 保存。
6. maintenance job：
   - 僅在離峰執行。
   - batch size 可設定。
   - 每批 commit。
   - 有 max runtime。
   - 可中斷續跑。
   - 有 progress 與 last error。
7. MySQL partition 僅在 `EXPLAIN`、migration 時間與 rollback 評估通過後使用。
8. `OPTIMIZE TABLE` 不得自動在啟動時執行。

### 9.4 封存一致性

每批封存保存：

- source table。
- date range。
- source row count。
- archived row count。
- checksum。
- started／completed time。
- backup id。
- cleanup eligibility。

只有下列條件全數成立才可進入 cleanup：

1. Phase 19 健康備份存在。
2. archive row count 一致。
3. checksum 一致。
4. 查詢可從 archive 重建抽樣資料。
5. 至少跨一個維護窗。

### 9.5 測試

- storage audit 只讀測試。
- archive dry-run。
- batch resume。
- 中途中斷。
- checksum mismatch 阻止 cleanup。
- recent query 不讀 archived JSON。
- 歷史 detail fallback。
- sync summary 聚合一致。
- migration plan 不鎖死大型 fixture。

### 9.6 驗收 Gate

- [ ] 首次執行只允許 dry-run。
- [ ] 無備份時 cleanup 必須拒絕。
- [ ] 近期籌碼、K 線、日報與回測結果一致。
- [ ] 主籌碼查詢不載入大型 detail JSON。
- [ ] maintenance 不使 DB pool wait p95 超過 10 ms。
- [ ] maintenance 可安全中斷與續跑。
- [ ] 零個個人資產／紙上交易表受 retention 影響。

### 9.7 建議 commit

可拆為：

```text
phase-20a: add storage lifecycle audit and dry-run
phase-20b: archive oversized market history payloads
phase-20c: enforce bounded retention maintenance
```

### 9.8 回滾

- 先停 maintenance scheduler。
- 已 archive 的資料保留，不直接反向大量搬移。
- online query 可透過 feature flag 讀舊欄位。
- 不回滾 migration history，不自動 drop archive table。

---

## 10. Phase 21：Yahoo／海外商品 freshness 排程

### 10.1 目標

依商品市場、交易時段與 provider 限制更新海外／加密商品，消除無意義 stale 警告，同時避免對 Yahoo 造成過量請求。

### 10.2 商品分類

- 台股／台灣指數：富邦優先，不以 Yahoo 作為一般 fallback。
- 台灣期貨：富邦／TAIFEX。
- 美股／美國指數：Yahoo，依美股 session。
- 港股／恆生指數：Yahoo，依香港 session。
- 加密資產：Yahoo 或指定 provider，24/7。
- 休市商品：以最近交易時間判斷，不因 wall-clock 年齡直接報 stale。

### 10.3 詳細修改

1. 建立 market calendar／timezone 判斷。
2. 每個 ticker 保存：
   - provider。
   - market。
   - expected freshness。
   - last attempt。
   - last success。
   - last provider timestamp。
   - next refresh。
   - last error category。
3. active ticker、可視 watchlist 與背景 watchlist 使用不同更新頻率。
4. 對 24/7 商品設定獨立 interval。
5. provider rate limit、429、timeout 使用 circuit breaker／backoff。
6. 同一 ticker refresh 使用 single-flight。
7. scheduler 採 bounded concurrency，不一次同步全部 54 個 ticker。
8. data-quality stale 判斷使用：
   - 市場是否應開盤。
   - provider 回傳 timestamp。
   - 是否處於 backoff。
   - 最近成功同步。
9. UI 提供：
   - stale 原因。
   - 下次更新時間。
   - 手動刷新。
   - provider degraded 說明。
10. 手動刷新也需遵守最小間隔，避免連續點擊。

### 10.4 測試

- 台北、香港、紐約與 UTC 時區。
- 週末、休市、跨午夜。
- 美股 daylight saving time。
- crypto 24/7。
- 429／timeout backoff。
- concurrent single-flight。
- stale data-quality 判斷。
- 富邦台股不誤用 Yahoo。

### 10.5 驗收 Gate

- [ ] provider 正常時，開盤商品 stale 數量為 0。
- [ ] 休市商品不因超過 30 分鐘誤報。
- [ ] Yahoo request concurrency 不超過設定值。
- [ ] 429 後遵守 backoff，不形成 retry storm。
- [ ] 手動刷新有明確結果與節流。
- [ ] 連續 24 小時 scheduler 無 task failure。

### 10.6 建議 commit

```text
phase-21: schedule quotes by market freshness
```

### 10.7 回滾

- 可關閉自動海外 quote scheduler，保留手動刷新。
- 保留新的 freshness metadata 與 data-quality 說明。

---

## 11. Phase 22：前端錯誤韌性、Y 軸與模擬交易 UX

### 11.1 目標

避免誤操作導致 K 線被裁切；非同步 chunk、API 或 provider 失敗時顯示可恢復狀態，而不是空白畫面或空資料假象。

### 11.2 Y 軸修改

1. 將 Y 軸模式明確分為：
   - `auto`
   - `manual_locked`
2. 價格軸滾輪／拖曳只有在使用者明確開啟手動模式時生效。
3. `Y 軸手動` chip 可直接點擊恢復自動。
4. ticker、interval、workspace reset 的行為明確定義：
   - 預設回到 auto。
   - 使用者可選擇 workspace 是否保存 manual range。
5. auto 模式每次可視資料改變都納入：
   - K 線 high／low。
   - 啟用且屬價格尺度的指標。
   - 合理 padding。
6. 偵測主 K 線超出 viewport 時：
   - auto 模式立即修正。
   - manual 模式顯示「資料超出範圍」與一鍵自動。
7. box zoom、Y+／Y-、雙擊重設與 price-axis wheel 的狀態轉換必須一致。

### 11.3 全域錯誤韌性

1. root 層加入 Vue error boundary／`onErrorCaptured`。
2. dynamic import 失敗時顯示：
   - 重新載入模組。
   - 重新整理頁面。
   - 清除舊版 cache 的安全提示。
3. `unhandledrejection` 只記錄 sanitized error category，不記錄敏感 payload。
4. route-level skeleton 必須和實際工作區大小一致，減少 layout shift。
5. API request：
   - route 切換時 abort。
   - 只保留最後一次 ticker request。
   - timeout 顯示 retry。
6. IndexedDB schema／舊 cache 不相容時可自動清理該 cache，不影響 MySQL。

### 11.4 模擬交易 UX

1. Account、Bot、Replay、Margin 分別顯示 loading／empty／error。
2. API error 不得轉成空陣列後顯示「尚無資料」。
3. 每區塊有獨立重試。
4. provider degraded 時仍可查看歷史紙上交易。
5. 明確顯示這是模擬交易，不會送出真實委託。

### 11.5 測試

- auto Y 軸包含所有可視 K 線。
- wheel 不會意外切 manual。
- explicit manual lock 保持範圍。
- 新高／新低進入 auto range。
- dynamic import rejection。
- IndexedDB corrupted／old schema。
- route abort race。
- paper 四種狀態。
- accessibility：按鈕可由鍵盤操作、錯誤訊息可讀。

### 11.6 驗收 Gate

- [ ] auto 模式 100% 顯示可視區 K 線 high／low。
- [ ] 未開啟 manual 時，價格軸 wheel 不改變 Y range。
- [ ] chunk 載入失敗不出現無提示白屏。
- [ ] API error 與 empty state 可區分。
- [ ] route 快速切換不顯示上一個 ticker 的晚到資料。
- [ ] frontend tests、production build 與 bundle Gate 通過。

### 11.7 建議 commit

可拆為：

```text
phase-22a: make chart price scale explicit
phase-22b: add recoverable frontend error states
```

### 11.8 回滾

- Y 軸互動可切回舊 handler，但保留一鍵 auto 與 clipped warning。
- error boundary 不應回滾；若特定 retry 行為有問題，只停用 retry。

---

## 12. Phase 23：Production SPA E2E 與正式 soak

### 12.1 目標

建立能攔截導航消失、重新整理失敗、Y 軸退化、模擬交易空白與啟動失敗的瀏覽器自動化 Gate。

### 12.2 測試架構

採兩層：

1. Deterministic E2E：
   - production build。
   - 本機測試 DB 或 fixture API。
   - 不需真實富邦。
   - 每次 Phase／CI 可執行。
2. Live smoke／soak：
   - 本機正式 MySQL。
   - 真實富邦行情。
   - 只讀與行情訂閱。
   - 開盤時人工觸發。

建議使用 Playwright，並固定瀏覽器版本與 viewport。

### 12.3 Deterministic E2E 案例

1. `/app/` 首頁載入。
2. 所有主導航逐一開啟：
   - 總覽。
   - 終端。
   - 籌碼。
   - 復盤。
   - 資產。
   - 模擬。
   - 設定。
3. 每一深層 route 直接輸入 URL 與重新整理。
4. `*TMFF`／`*TXFF` 搜尋與 resolved contract 顯示。
5. K 線 cache-first → DB confirm → realtime update。
6. Y 軸 auto／manual。
7. WebSocket disconnect → reconnect banner → recovered。
8. Paper account normal／empty／error。
9. 個人資產頁只使用 synthetic fixture，不讀真實資產。
10. dynamic chunk failure recovery。
11. backend 未啟動、啟動中、ready_degraded、ready。
12. production SPA history fallback 不回傳 API 的 `index.html`。

### 12.4 Live soak

使用既有：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/soak-realtime.ps1 `
  -DurationMinutes 60 `
  -FuturesSymbols "*TMFF","*TXFF" `
  -StockSymbol "2330.TW"
```

soak 期間至少執行一次 100,000 根回測，並觀察：

- 行情 freshness。
- ingress → broadcast。
- persistence queue age／depth。
- DB pool wait。
- reconnect。
- dropped quote。
- 前端 Long Task。
- process memory。
- browser console error。

### 12.5 驗收 Gate

- [ ] deterministic E2E 全數通過。
- [ ] 每一主導航與 direct reload 通過。
- [ ] E2E 無需真實帳號或個人資料。
- [ ] 60 分鐘 live soak 完成。
- [ ] 正常負載 dropped quote = 0。
- [ ] ingress → broadcast p95 ≤ 75 ms。
- [ ] DB pool wait p95 ≤ 10 ms。
- [ ] queue age p95 ≤ 750 ms；理想 ≤ 500 ms。
- [ ] 100,000 根回測期間 event-loop Gate 仍通過。
- [ ] 無真實下單。

### 12.6 建議 commit

```text
phase-23: add production browser acceptance gates
```

### 12.7 回滾

- E2E 工具本身不影響 production runtime，不因 flaky test 直接刪除。
- flaky case 必須修正等待條件或隔離外部依賴，不得長期 skip 核心導航。

---

## 13. Phase 24：指標趨勢、服務監督與日誌隔離

### 13.1 目標

不用翻閱混合 log 就能判斷 DB、provider、queue、scheduler、資料 freshness 或 process 是否異常；backend 意外退出時可選擇由本機 supervisor 安全恢復。

### 13.2 指標趨勢

保存 bounded、無敏感資料的短期 snapshot：

- API latency p50／p95／max。
- DB query／pool wait。
- realtime ingress／broadcast／drop。
- persistence queue depth／age／failure。
- provider connected／reconnect／last error category。
- stale ticker count。
- scheduler failure。
- process RSS／private bytes／handles。
- active background task count。

建議：

- 1 分鐘粒度保存 24 小時。
- 5～15 分鐘降採樣保存 7～30 天。
- 不保存 ticker 的完整 quote 或個人資料。

### 13.3 系統狀態 UI

顯示：

- 當前狀態與 24 小時趨勢。
- 各 component 最後成功時間。
- degraded 原因。
- 可執行的安全動作：
  - 單 provider 重連。
  - 手動 quote refresh。
  - scheduler retry。
- 不提供真實委託或任意 shell 執行。

### 13.4 本機 supervisor

提供 optional Windows supervisor／watchdog：

1. 啟動前檢查 PID 與 port。
2. 不殺死無法確認屬於 QuantVision 的 process。
3. backend 非預期退出後 exponential backoff。
4. 短時間連續失敗達門檻後停止重啟並顯示錯誤。
5. planned shutdown 不自動拉起。
6. 同一時間只允許一個 backend instance。
7. supervisor 本身不持有或輸出 secrets。

### 13.5 日誌隔離

1. production、test、backup、scheduler 分開 logger／檔案。
2. pytest 預設不寫 production log。
3. log rotation 同時限制 days 與 total bytes。
4. provider error 只保存分類與 sanitized message。
5. request payload、帳號、資產與 token 不進 log。
6. health alert 計算只讀 production runtime log／metrics。

### 13.6 測試

- metric retention／downsample。
- app restart 後 bounded history。
- supervisor crash／planned exit／port collision。
- restart storm breaker。
- test log 不污染 production log。
- sensitive field redaction。
- status UI component degraded states。

### 13.7 驗收 Gate

- [ ] 可由狀態頁定位 DB／provider／queue／scheduler 四類故障。
- [ ] 指標資料量受 retention 限制。
- [ ] backend crash 後 optional supervisor ≤ 60 秒恢復。
- [ ] 不產生雙 backend。
- [ ] planned stop 不自動重啟。
- [ ] backend 全測後 production log 新增測試 fixture error = 0。
- [ ] log 與 metrics 不含秘密或個人明細。

### 13.8 建議 commit

可拆為：

```text
phase-24a: persist bounded operational metrics
phase-24b: isolate logs and add local service supervision
```

### 13.9 回滾

- supervisor 為 opt-in，可立即停用。
- 指標寫入可停用，但 health endpoint 與既有即時 metrics 保留。
- 不刪除尚在 retention 期限內的診斷資料。

---

## 14. Phase 25：大型模組漸進拆分

### 14.1 目標

降低後續修改回歸面，不改變 API contract、畫面行為、評分邏輯或資料庫結果。

### 14.2 拆分順序

#### 25A：PaperTradingDashboard

拆成：

- `usePaperAccounts`
- `usePaperBots`
- `usePaperReplays`
- `usePaperMargin`
- Account／Bot／Replay 子元件

先使用 Phase 23 E2E 鎖定行為。

#### 25B：useDashboard

保留薄 facade，逐步抽出：

- terminal ticker state。
- workspace persistence。
- market sync actions。
- comparison state。
- notification orchestration。
- route lifecycle。

不得一次重寫所有 reactive state。

#### 25C：useChartEngine

拆成：

- price scale。
- coordinate transform。
- interaction controller。
- drawing renderer。
- indicator renderer。
- crosshair。

抽出純函式時先補數值測試，避免浮點與座標退化。

#### 25D：資產後端

依 use case 拆分：

- account／ledger command。
- valuation query。
- quote／FX hydration。
- CSV import。
- reconciliation。

router 只處理 HTTP contract；repository 不承擔 presentation。

#### 25E：AI 日報

拆成：

- data assembly。
- signal classification。
- scoring。
- validation。
- report rendering。
- delivery。

必須保留：

- `confirmed_uptrend`
- `new_breakout`
- `watch_only`
- `failed_breakout`
- `invalidated`
- `price_score`
- `breakout_score`
- `volume_score`
- `institutional_score`
- `kline_score`
- `signals_YYYY-MM-DD.json`
- 1／3／5／10 日驗證
- Traditional Chinese 風險提醒

### 14.3 拆分原則

- 每次只移動一個 bounded responsibility。
- refactor commit 不混入功能修正。
- public function／API 先由 facade 代理，逐步遷移 caller。
- 使用 characterization、snapshot 與 contract tests。
- 不以行數下降作為唯一完成條件。
- 新模組避免形成循環依賴。
- 不增加初始 bundle 或常駐 watcher。

### 14.4 測試

- facade contract。
- before／after snapshot。
- chart coordinate golden cases。
- asset ledger／valuation parity。
- daily report Markdown 與 signal JSON schema parity。
- Phase 23 全套 E2E。
- Phase 15 bundle／performance Gate。

### 14.5 驗收 Gate

- [ ] API schema 無非預期差異。
- [ ] 同 fixture 的資產估值、回測、評分與報告結果一致。
- [ ] 初始 bundle gzip 不增加超過 5%。
- [ ] realtime message → paint 不退化超過 10%。
- [ ] 沒有新增循環依賴。
- [ ] 每個子階段均有獨立 commit 與完整回歸。

### 14.6 建議 commit

```text
phase-25a: split paper trading dashboard responsibilities
phase-25b: slim dashboard orchestration facade
phase-25c: split chart interaction and rendering
phase-25d: separate asset commands and queries
phase-25e: modularize daily report pipeline
```

### 14.7 回滾

- 每個 facade 保留到所有 caller 遷移完成。
- 可逐子模組回滾，不需整個 Phase 25 一次退回。
- 不在 refactor 階段移除 legacy API。

---

## 15. Phase 26：LAN 存取安全與 fail-closed

### 15.1 適用條件

系統預設只綁定 `127.0.0.1`。若永遠只在本機使用，Phase 26 的必要工作是驗證本機 fail-closed；若允許手機、平板或其他電腦透過 LAN 存取，完整 Phase 26 必須提前到所有外部使用之前完成。

### 15.2 詳細修改

1. 預設 bind host 維持 `127.0.0.1`。
2. `ALLOW_LAN_ACCESS=true` 時要求：
   - 明確允許來源清單。
   - 強度足夠的管理 session／token。
   - WebSocket authentication。
   - mutating API 的 CSRF 防護。
3. 不接受 `*` CORS 與 credentials 同時啟用。
4. 富邦設定、通知、備份、資產與紙上交易 API 需額外保護。
5. login／reconnect／sync／import 加入本機適度 rate limit。
6. 啟動檢查：
   - LAN 已開但沒有安全金鑰時拒絕啟動。
   - 使用預設或弱金鑰時拒絕。
7. 單人系統維持單一 owner context，不假裝支援多人隔離。
8. 不將 auth token 保存於 log、URL 或 Git。

### 15.3 測試

- localhost allow。
- LAN disabled deny。
- LAN enabled without secret fail startup。
- CORS allowed／denied origin。
- WebSocket unauthorized。
- CSRF。
- rate limit。
- private endpoint authorization。
- static SPA 可載入但私人 API 不可匿名讀取。

### 15.4 驗收 Gate

- [ ] 預設只能從本機存取。
- [ ] LAN 未完整設定安全參數時 fail closed。
- [ ] 未授權者無法讀取個人資產、設定、帳號與紙上交易。
- [ ] WebSocket 不接受未授權 LAN client。
- [ ] secrets 不進 log／URL／Git。

### 15.5 建議 commit

```text
phase-26: enforce secure local network access
```

### 15.6 回滾

- 可關閉 LAN access 回到 localhost-only。
- 不允許以回滾名義恢復未驗證的 LAN 匿名存取。

---

## 16. 全域最終驗收矩陣

Phase 16～26 全部完成後，至少必須符合：

| 類別 | 最終門檻 |
|---|---|
| DB stats | warm p95 ≤ 300 ms，無大型表全掃描 |
| Startup | API／SPA p95 ≤ 3 秒可用 |
| Provider | 單帳號失敗不阻塞啟動，95% reconnect ≤ 60 秒 |
| Subscription | 重連後無遺失、無重複訂閱 |
| Paper margin | 設定錯誤不重試風暴，保留最後成功值 |
| Backup | critical restore drill 通過，歷史資料有明確復原策略 |
| Retention | archive-first，無個人資料被自動清理 |
| Freshness | provider 正常時開盤商品 stale = 0 |
| Chart | auto Y 軸顯示所有可視 K 線 |
| Frontend failure | 無無提示白屏，error 與 empty 可區分 |
| E2E | 主導航、direct reload、reconnect、paper、assets、Y 軸全數通過 |
| Soak | 60 分鐘 live soak 通過，dropped quote = 0 |
| DB pool | 正常與 maintenance 負載 p95 ≤ 10 ms |
| Logs | pytest 不污染 production log，無秘密與個人資料 |
| Supervisor | opt-in crash recovery ≤ 60 秒且不產生雙 process |
| Bundle | 持續通過 Phase 15 最終預算 |
| Safety | 無真實下單；LAN 存取 fail closed |

---

## 17. 正式實作的 Git 提交順序

建議順序：

```text
phase-16: remove blocking database statistics path
phase-17: make provider warmup non-blocking
phase-18a: harden fubon reconnect state
phase-18b: make paper margin refresh resilient
phase-19: add tiered backup and restore verification
phase-20a: add storage lifecycle audit and dry-run
phase-20b: archive oversized market history payloads
phase-20c: enforce bounded retention maintenance
phase-21: schedule quotes by market freshness
phase-22a: make chart price scale explicit
phase-22b: add recoverable frontend error states
phase-23: add production browser acceptance gates
phase-24a: persist bounded operational metrics
phase-24b: isolate logs and add local service supervision
phase-25a: split paper trading dashboard responsibilities
phase-25b: slim dashboard orchestration facade
phase-25c: split chart interaction and rendering
phase-25d: separate asset commands and queries
phase-25e: modularize daily report pipeline
phase-26: enforce secure local network access
```

每個 commit 前必須有對應 Gate。不得將多個尚未分別通過測試的 Phase 合併成單一大型 commit。

---

## 18. 建議第一輪執行範圍

第一輪只執行 Phase 16：

1. 重新保存全域 baseline。
2. 確認 DB stats 與 legacy sidebar 的實際使用關係。
3. 移除 frontend 阻塞呼叫。
4. 將 endpoint 改為快取／估算統計。
5. 新增 timeout、single-flight 與效能測試。
6. 全部 Gate 通過。
7. 建立 Phase 16 commit。
8. 提交驗收結果後再開始 Phase 17。

這個順序能先消除已實測超過 10 秒的明確熱點，又不會立即碰觸 40 GiB 籌碼資料或富邦多帳號生命週期，風險最低。

---

## 19. 不在本規畫內的工作

- 真實自動下單。
- 未經驗證的 AI 買賣指令。
- 微服務拆分。
- Kubernetes。
- 以 Redis 取代 MySQL。
- 為了效能移除歷史訊號驗證。
- 未經備份與 dry-run 的大量資料刪除。
- 將本機個人系統直接公開到 Internet。

所有選股、訊號、AI 報告與紙上交易結果均為研究與觀察用途，不保證獲利；報告必須保留資料時間、分數拆解、驗證狀態與風險提醒。
