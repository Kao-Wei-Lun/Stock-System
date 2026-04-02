# QuantVision Pro 分階段實作與交付清單

## 1. 文件目的

本文件是 [quantvision-product-spec.md](/c:/Users/Alan/Desktop/Stock-System/Stock-System/docs/quantvision-product-spec.md) 的執行版補充文件，用來定義：

- 每一個階段要做的實作任務
- 每一個階段必須新增或補齊的測試
- 每一個階段的出關條件
- 每一個階段完成後的 Git 提交規則
- 若測試失敗時，Codex 應如何自動修復並重跑
- 若階段完成並提交成功，下一個階段如何接續

建議搭配 [quantvision-phase-task-checklist.md](/c:/Users/Alan/Desktop/Stock-System/Stock-System/docs/quantvision-phase-task-checklist.md) 一起使用，作為逐階段的執行清單與驗收對照文件。

## 2. 執行總原則

### 2.1 一次只做一個階段

- 一次只允許一個階段處於 `in progress`
- 未完成當前階段前，不得跳到下一階段正式實作
- 若為解 blocker 所需的極小範圍前置調整，必須在當前階段 commit 訊息中註明

### 2.2 每一階段都必須包含測試

- 每一個階段不能只完成功能，必須同時補測試
- 不允許「功能先上，測試以後補」作為該階段完成狀態
- 若本階段引入新模組，必須同時建立對應的最小測試骨架

### 2.3 自動修復規則

每一個階段完成後，Codex 必須執行下列固定流程：

1. 完成功能實作
2. 執行該階段規定的測試與出關命令
3. 若測試失敗：
   - 讀取錯誤輸出
   - 直接修正程式碼
   - 重跑相同測試
   - 持續迭代直到綠燈
4. 若所有測試通過：
   - 執行 `git status`
   - `git add -A`
   - 依本文件規定格式建立 commit
5. commit 成功後：
   - 立即進入下一階段任務
   - 重複相同流程

### 2.5 本地資料庫落地規則

- 每一個階段新增的正式功能資料，都必須同時定義本地資料庫持久化方案
- 不允許新增只存在前端 state、`localStorage`、記憶體 cache 或外部 API 即時回傳中的正式業務資料
- 若某功能資料尚未有本地資料表、repository、同步寫入流程與讀取流程，該功能不得視為該階段完成
- 每個階段測試都必須驗證核心資料可從本地資料庫讀回，而不是只驗證 API 即時回應

### 2.4 允許停止的唯一情況

只有下列情況才允許中止自動往下一階段推進：

- 外部憑證、正式 API key 或券商權限缺失
- 真正需要人工決策的產品分歧
- 使用者明確要求暫停
- 發現會破壞既有資料的高風險遷移，且必須先確認策略

若中止，必須：

- 明確說明 blocker
- 指出卡住的階段
- 列出已完成內容
- 列出下一步需要的人工輸入

## 3. 標準 Git 規則

### 3.1 Commit 粒度

- 最少每一階段 1 個 commit
- 若階段內容很大，可拆成多個 commit
- 但該階段最後一定要有一個可獨立通過該階段 gate 的 commit 狀態

### 3.2 Commit 訊息格式

格式：

`phase-X: <short summary>`

範例：

- `phase-0: bootstrap test and delivery workflow`
- `phase-1: add persistence foundation and migrations`
- `phase-3: implement persistent alert engine`

### 3.3 Commit 前條件

- 所有本階段 gate 通過
- `git status` 內不應存在未理解的衝突
- 若有刻意保留的 TODO，必須是下階段明確項目，不得影響本階段驗收

## 4. 標準測試矩陣

## 4.1 Backend 標準檢查

- `python -m compileall backend`
- `python -m pytest`

若某階段尚未建立完整 `pytest` 結構，至少要有：

- app import smoke test
- API route smoke test
- 新增模組的單元測試

## 4.2 Frontend 標準檢查

- `npm run build`
- `npm run test`

若某階段尚未建立 `npm run test`，Phase 0 必須先補上

## 4.3 全域驗收類型

- Unit tests
- Integration tests
- API smoke tests
- Frontend smoke tests
- Regression tests

## 5. 階段總覽

- Phase 0：測試基線與交付流程基礎
- Phase 1：資料模型、資料表與 API 基礎層
- Phase 2：儀表板持久化、報價抽象層與工作區後端化
- Phase 3：警報引擎與通知中心基礎
- Phase 4：完整回測平台
- Phase 5：交易日誌與個人化分析
- Phase 6：事件資訊中心與宏觀風險儀表板
- Phase 7：台股進階籌碼與基本面模組
- Phase 8：選股器、法人整合訊號化與最終硬化

## 6. Phase 0：測試基線與交付流程基礎

### 6.1 目標

- 先建立後續所有階段都能重複使用的測試與交付骨架

### 6.2 後端任務

- 建立 `pytest` 基礎結構
- 建立測試設定檔
- 建立 app import smoke test
- 建立健康檢查 API smoke test
- 將 provider 抽象層初步拆出介面檔
- 將環境設定集中化，避免測試時直接依賴正式 `.env`
- 建立本地資料庫持久化原則的測試基線與驗收模板

### 6.3 前端任務

- 建立前端測試基礎結構
- 為 App / 主要 layout 建立最小 smoke test
- 整理可測試的 API client 包裝層

### 6.4 文件任務

- 確認規格文件與分階段文件存在
- 新增測試與提交流程說明

### 6.5 必補測試

- Backend：`health` endpoint smoke test
- Backend：app startup import test
- Frontend：App mount smoke test
- Frontend：主要畫面 build smoke test

### 6.6 Gate

- `python -m compileall backend`
- `python -m pytest`
- `npm run build`
- `npm run test`

### 6.7 完成定義

- 專案具備正式測試入口
- 後續階段可直接沿用同一套 gate

### 6.8 建議 commit

- `phase-0: bootstrap test and delivery workflow`

## 7. Phase 1：資料模型、資料表與 API 基礎層

### 7.1 目標

- 建立未來所有功能的持久化骨架與 API 基礎

### 7.2 後端任務

- 新增或重構以下資料表：
  - `user_profiles`
  - `user_preferences`
  - `workspace_presets`
  - `market_quotes_latest`
  - `alerts`
  - `alert_trigger_logs`
  - `notifications`
  - `sync_jobs`
  - `sync_job_logs`
- 為既有表新增必要欄位：
  - `watchlist_groups.owner_id`
  - `watchlist_items.tags_json`
  - `ohlcv.source`
  - `ohlcv.updated_at`
- 補齊資料庫初始化與 migration 策略
- 建立以下 API skeleton：
  - workspaces CRUD
  - alerts CRUD
  - notifications list/read
  - quote metadata response model

### 7.3 前端任務

- 建立 workspace / alerts / notifications 對應 API client
- 將目前只存在前端 state 的功能逐步改成可讀寫後端

### 7.4 必補測試

- 資料表初始化測試
- repository CRUD 測試
- alerts / workspaces / notifications API smoke tests
- migration 前後相容測試

### 7.5 Gate

- `python -m compileall backend`
- `python -m pytest`
- `npm run build`
- `npm run test`

### 7.6 完成定義

- 所有核心業務資料皆已有正式資料表
- 新增 API 可通過最小 smoke test
- 本階段新增的核心資料皆可由本地資料庫讀回

### 7.7 建議 commit

- `phase-1: add persistence foundation and api skeletons`

## 8. Phase 2：儀表板持久化、報價抽象層與工作區後端化

### 8.1 目標

- 讓 Dashboard、工作區、自選與報價顯示進入可長期擴充的架構

### 8.2 後端任務

- 建立 `QuoteProvider` 抽象層
- 將現有報價查詢改成 provider 實作
- 定義 quote 回傳模型：
  - `price`
  - `source`
  - `quote_timestamp`
  - `quote_type`
  - `is_delayed`
- 建立 workspace CRUD 正式邏輯
- 自選欄位加上資料時間與來源欄位

### 8.3 前端任務

- 將 workspace 從 `localStorage` 改為後端持久化
- 將工作區載入、更新、刪除全面改走 API
- 畫面上所有報價相關區域顯示資料時間與延遲標記
- 自選股加入排序、標籤與欄位擴充骨架
- 移除會誤導使用者的「即時」語意

### 8.4 必補測試

- QuoteProvider contract test
- workspace CRUD integration test
- 自選股 hydrated response test
- 前端 workspace save/load smoke test
- 前端 quote timestamp rendering test

### 8.5 Gate

- `python -m compileall backend`
- `python -m pytest`
- `npm run build`
- `npm run test`

### 8.6 完成定義

- 工作區不再只依賴瀏覽器儲存
- 所有報價畫面都有資料時間與來源
- 架構上已可替換成券商報價供應器
- 本階段涉及的工作區、自選與報價快照資料皆已本地落地

### 8.7 建議 commit

- `phase-2: backendize workspaces and abstract quote provider`

## 9. Phase 3：警報引擎與通知中心基礎

### 9.1 目標

- 將警報從前端暫存功能升級成正式後端引擎

### 9.2 後端任務

- 完整 alerts CRUD
- 建立 alert evaluator service
- 建立 trigger log persistence
- 建立 notification creation flow
- 支援以下條件：
  - price > / <
  - price cross up / down
  - pct > / <
  - RSI > / < / cross
  - MACD golden / death cross
  - volume spike
  - basis divergence
  - institutional anomaly
  - event reminder
- 建立背景檢查排程

### 9.3 前端任務

- 警報列表頁
- 警報編輯 / 暫停 / 恢復 / 刪除
- 觸發紀錄檢視
- 通知中心基礎畫面
- 在標的詳情頁快速建立警報

### 9.4 必補測試

- 警報條件判斷 parameterized tests
- evaluator scheduler integration tests
- alert trigger log tests
- alerts API tests
- frontend alerts CRUD smoke tests

### 9.5 Gate

- `python -m compileall backend`
- `python -m pytest`
- `npm run build`
- `npm run test`

### 9.6 完成定義

- 警報重啟後不遺失
- 觸發後能看到時間、數值、來源
- Notification 可追到對應 alert
- 警報與通知資料可完全由本地資料庫重建

### 9.7 建議 commit

- `phase-3: implement persistent alert engine`

## 10. Phase 4：完整回測平台

### 10.1 目標

- 將回測從簡化前端函式升級為正式策略平台

### 10.2 後端任務

- 建立 strategy registry
- 實作策略：
  - MA
  - RSI
  - MACD
  - Bollinger breakout
  - KD cross
- 建立 backtest run persistence
- 建立 trade detail persistence
- 回測結果 summary API
- 權益曲線與績效指標 API
- 加入 fee / slippage / stop loss / take profit / position sizing

### 10.3 前端任務

- 回測頁重構
- 支援所有正式策略
- 顯示 summary、equity curve、trade list
- 支援回測紀錄保存與再載入

### 10.4 必補測試

- 每個策略的 deterministic unit test
- no-lookahead regression tests
- metrics calculation tests
- backtest API integration tests
- frontend backtest result rendering tests

### 10.5 Gate

- `python -m compileall backend`
- `python -m pytest`
- `npm run build`
- `npm run test`

### 10.6 完成定義

- UI 上所有回測策略皆有實作
- 可查看逐筆交易與權益曲線
- 結果可保存並重載
- 回測 summary、逐筆交易與參數皆已本地落地

### 10.7 建議 commit

- `phase-4: ship persistent backtest platform`

## 11. Phase 5：交易日誌與個人化分析

### 11.1 目標

- 建立交易執行與事後檢討閉環

### 11.2 後端任務

- 建立 trade journal CRUD
- 建立 attachment metadata
- 建立 stats aggregation service
- 建立 journal filters / search API
- 將通知中心完善成可讀 / 未讀模型

### 11.3 前端任務

- 交易日誌頁
- 新增 / 編輯交易紀錄表單
- 從圖表工作區直接建立交易紀錄
- 交易統計頁
- 通知中心正式頁

### 11.4 必補測試

- journal CRUD tests
- statistics aggregation tests
- notification read/unread tests
- attachment metadata tests
- frontend journal flow smoke tests

### 11.5 Gate

- `python -m compileall backend`
- `python -m pytest`
- `npm run build`
- `npm run test`

### 11.6 完成定義

- 交易紀錄、統計與通知形成閉環
- 可依策略、標籤、市場篩選歷史交易
- 交易日誌、附件 metadata 與統計來源皆可由本地資料庫重建

### 11.7 建議 commit

- `phase-5: add trade journal and personal analytics`

## 12. Phase 6：事件資訊中心與宏觀風險儀表板

### 12.1 目標

- 把事件風險與宏觀風險納入交易前判斷流程

### 12.2 後端任務

- 建立 event provider 與 normalization
- 建立 news provider 與 normalization
- 建立 macro provider
- 建立事件與宏觀資料同步任務
- 建立 API：
  - events calendar
  - ticker events
  - news list
  - macro dashboard

### 12.3 前端任務

- 事件中心頁
- 標的事件卡
- 宏觀風險儀表板
- 圖表垂直事件線與事件列表連動

### 12.4 必補測試

- provider normalization tests
- event ordering tests
- macro snapshot tests
- API integration tests
- frontend event rendering smoke tests

### 12.5 Gate

- `python -m compileall backend`
- `python -m pytest`
- `npm run build`
- `npm run test`

### 12.6 完成定義

- 使用者可看到市場級與標的級事件
- 圖表可看到事件標記
- 宏觀頁可呈現至少一套風險摘要
- 事件、新聞與宏觀快照皆有本地資料庫保存

### 12.7 建議 commit

- `phase-6: add event center and macro dashboard`

## 13. Phase 7：台股進階籌碼與基本面模組

### 13.1 目標

- 補齊台股交易者最常用的個股籌碼與基本面資訊

### 13.2 後端任務

- 建立 Taiwan chip provider
- 同步以下資料：
  - margin
  - short balance
  - securities lending
  - institutional net buy/sell by ticker
  - branch payload if source available
- 基本面 provider 補齊：
  - sector
  - industry
  - pe
  - dividend yield
  - 52w high/low
  - avg volume
  - profile
- API：
  - fundamentals detail
  - fundamentals events
  - taiwan chips detail

### 13.3 前端任務

- 標的基本面卡
- 台股籌碼卡
- 基本面與籌碼摘要
- 與警報 / 選股條件整合入口

### 13.4 必補測試

- fundamentals normalization tests
- taiwan chip normalization tests
- API integration tests
- frontend detail card rendering tests

### 13.5 Gate

- `python -m compileall backend`
- `python -m pytest`
- `npm run build`
- `npm run test`

### 13.6 完成定義

- 搜尋與標的頁能看到完整基本面
- 台股個股能看到進階籌碼摘要
- 基本面與台股籌碼資料皆已本地落地

### 13.7 建議 commit

- `phase-7: add taiwan chips and fundamentals modules`

## 14. Phase 8：選股器、法人整合訊號化與最終硬化

### 14.1 目標

- 將零散模組整合成真正可用的市場決策工作台

### 14.2 後端任務

- 建立 screener engine
- 建立 screener presets persistence
- 將法人異常值、basis、事件與基本面條件整合進篩選器
- 建立全域 regression fixtures
- 補 sync observability
- 補 performance profiling 與必要 cache

### 14.3 前端任務

- 選股器頁
- 篩選條件保存
- 結果排序、加入自選、一鍵跳圖
- 法人頁與圖表的訊號整合
- 整體 UX polish

### 14.4 必補測試

- screener filter correctness tests
- saved preset tests
- institutional summary regression tests
- end-to-end smoke tests covering:
  - 自選 -> 圖表 -> 警報
  - 圖表 -> 回測 -> journal
  - 事件 -> 圖表事件線
  - 篩選器 -> 加入自選 -> 標的分析

### 14.5 Gate

- `python -m compileall backend`
- `python -m pytest`
- `npm run build`
- `npm run test`

### 14.6 完成定義

- 核心模組已整合
- 可以用一套工作流完成發現標的、分析、警報、回測、記錄與檢討
- 選股器、法人訊號與整合後的正式資料皆可由本地資料庫重建

### 14.7 建議 commit

- `phase-8: add screener and complete market workstation integration`

## 15. 每一階段的自動流程模板

每次實作某一階段時，Codex 必須遵循下列模板：

1. 讀取本文件對應階段
2. 實作該階段所有任務
3. 補齊本階段要求的測試
4. 執行 gate
5. 若 gate 失敗：
   - 修正
   - 重跑
   - 直到綠燈
6. 執行：
   - `git status --short`
   - `git add -A`
   - `git commit -m "phase-X: ..."`
7. commit 成功後：
   - 讀取下一階段
   - 直接開始下一階段

## 16. 與 Codex 的執行約束

未來若以 Codex 直接連續執行多階段開發，必須遵守：

- 不可在測試失敗時停止於半成品狀態
- 不可跳過 Git 提交直接跨階段
- 不可在未達到該階段完成定義前宣稱完成
- 若遇到 blocker，需明確指出是外部依賴或產品決策問題

## 17. 建議搭配腳本

建議搭配：

- `scripts/run-phase-gate.ps1`
- `scripts/run-phase-gate.bat`

用於標準化每一個階段的測試與 Git 提交流程
