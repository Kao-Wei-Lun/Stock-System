# QuantVision Pro 逐階段實作任務清單與自動執行規範

## 1. 文件目的

本文件是 [quantvision-phase-delivery-plan.md](/c:/Users/Alan/Desktop/Stock-System/Stock-System/docs/quantvision-phase-delivery-plan.md) 的執行型補充文件，目的為：

- 將每一個 Phase 拆成可直接執行的任務清單
- 明確規定每一個 Phase 結束後必須執行的測試與 Gate
- 明確規定測試失敗時的自動修復迭代流程
- 明確規定 Gate 通過後的 Git 提交與自動推進到下一個 Phase 的流程
- 再次強化所有正式資料都必須落地到本地資料庫的硬性規範

本文件不取代產品規格與交付計畫，而是提供後續逐階段落地時的執行清單。

## 2. 全域硬規範

### 2.1 一次只允許一個 Phase in progress

- 未完成目前 Phase 之前，不可正式開始下一個 Phase 的功能實作
- 為了解 blocker 而做的極小範圍前置調整，仍須算入當前 Phase

### 2.2 所有正式資料必須存到本地資料庫

- 凡是會影響畫面顯示、分析結果、警報判斷、回測結果、選股結果、通知、交易日誌、工作區還原、同步狀態、驗收結果的資料，都必須能由本地資料庫重建
- 外部 API、公開網站、第三方資料源只可作為資料輸入來源，不可成為正式功能的唯一依賴
- `localStorage`、前端記憶體 state、暫存 cache 只可作為非關鍵快取，不可作為正式業務資料唯一保存位置
- 每一個 Phase 新增的正式資料都必須同時具備：
  - 資料表或可追溯持久化結構
  - 寫入流程
  - 讀取流程
  - 同步或更新流程
  - 測試驗證可從本地資料庫讀回

### 2.3 每一個 Phase 都必須包含測試

- 不允許只做功能不補測試
- 每一個 Phase 都必須新增或補齊：
  - Backend unit tests
  - Backend integration/API smoke tests
  - Frontend smoke tests
  - Phase regression tests

### 2.4 每一個 Phase 完成後的固定自動流程

1. 完成本 Phase 任務
2. 執行本 Phase 指定測試
3. 執行全域 Gate
4. 若失敗：
   - 讀取錯誤輸出
   - 修正程式碼或設定
   - 重跑相同測試
   - 持續迭代直到綠燈
5. 若成功：
   - 執行 `git status --short`
   - 確認無未理解衝突
   - 執行 `git add -A`
   - 依規範建立 commit
6. commit 成功後：
   - 立刻讀取下一個 Phase 的任務清單
   - 自動開始下一個 Phase

### 2.5 全域 Gate

所有 Phase 完成後至少執行：

- `python -m compileall backend`
- `python -m pytest`
- `npm run build`
- `npm run test`

若某個 Phase 有額外 gate，須在全域 Gate 之前或之後補跑。

### 2.6 允許停止自動推進的唯一情況

- 缺少外部正式憑證、正式 API key 或帳號授權
- 遇到需要人工決策的產品分歧
- 使用者明確要求暫停
- 發現高風險資料遷移且必須先確認策略

若停止，必須明確輸出：

- 卡住的 Phase
- blocker 原因
- 已完成內容
- 下一步所需的人工作業

## 3. Git 規範

### 3.1 Commit 粒度

- 每一個 Phase 至少 1 個 commit
- 若 Phase 太大可拆多個 commit
- 但最後必須有一個可獨立通過該 Phase gate 的 commit 狀態

### 3.2 Commit 格式

格式：

`phase-X: <short summary>`

範例：

- `phase-0: bootstrap test and delivery workflow`
- `phase-1: add persistence foundation and api skeletons`
- `phase-3: implement persistent alert engine`

## 4. 每一個 Phase 的標準驗收模板

每一個 Phase 結束時，都必須逐項確認：

- 資料模型是否已定義
- 本地資料庫是否可保存正式資料
- API 是否可讀寫正式資料
- 前端是否使用正式 API 而非暫存資料
- 同步流程是否會寫回本地資料庫
- 測試是否覆蓋該 Phase 核心流程
- 全域 Gate 是否綠燈
- Git commit 是否成功

## 5. Phase 0：測試基線與交付流程基礎

### 5.1 目標

先建立後續所有 Phase 可重複使用的測試、交付、資料庫驗收基線。

### 5.2 實作任務清單

#### 後端

- 建立 `pytest` 測試骨架
- 建立 app import smoke test
- 建立 health endpoint smoke test
- 建立 provider interface 的最小測試入口
- 建立可在測試時使用的獨立環境設定
- 建立本地資料庫初始化與重建測試基線

#### 前端

- 建立 `vitest` 測試入口
- 建立 App mount smoke test
- 建立主要 layout / dashboard smoke test
- 整理 API client 讓後續功能可測試

#### 文件與流程

- 確認產品規格、交付計畫、任務清單文件存在
- 定義標準 Gate 指令
- 定義自動修復、Git、下一階段推進規則

### 5.3 本階段必補測試

- Backend：app import smoke test
- Backend：`/api/health` smoke test
- Backend：本地資料庫初始化 smoke test
- Frontend：App mount smoke test
- Frontend：主要畫面 build smoke test

### 5.4 完成定義

- 專案具備正式測試入口
- 具備可重複使用的 Gate 流程
- 本地資料庫持久化驗收模板已建立

## 6. Phase 1：資料模型、資料表與 API 基礎層

### 6.1 目標

建立後續所有正式功能共用的持久化骨架與 API 基礎。

### 6.2 實作任務清單

#### 資料庫

- 建立或補齊：
  - `user_profiles`
  - `user_preferences`
  - `workspace_presets`
  - `market_quotes_latest`
  - `alerts`
  - `alert_trigger_logs`
  - `notifications`
  - `sync_jobs`
  - `sync_job_logs`
- 為既有資料表補齊必要欄位與索引
- 建立 schema migration / create table 向後相容策略

#### 後端

- 完成 workspaces CRUD API skeleton
- 完成 alerts CRUD API skeleton
- 完成 notifications list/read API skeleton
- 建立 quote metadata response model
- 建立 repository / database access 層 CRUD

#### 前端

- 建立 workspaces / alerts / notifications API client
- 將只存在前端 state 的核心資料逐步接上後端 API
- 補出最小可用的讀寫流程

### 6.3 本階段必補測試

- 資料表初始化測試
- migration 相容性測試
- repository CRUD tests
- workspaces API smoke tests
- alerts API smoke tests
- notifications API smoke tests
- 前端 API client smoke tests

### 6.4 完成定義

- 所有核心業務資料已有正式資料表
- 新增核心資料可由本地資料庫讀回
- 前端不再只依賴暫存 state 作為唯一資料來源

## 7. Phase 2：儀表板持久化、報價抽象層與工作區後端化

### 7.1 目標

讓 dashboard、workspace、報價顯示進入可長期擴充且可被信任的架構。

### 7.2 實作任務清單

#### 資料庫

- 正式使用 `workspace_presets`
- 正式使用 `market_quotes_latest`
- 建立 watchlist hydrated response 所需查詢資料結構

#### 後端

- 建立 `QuoteProvider` 抽象層
- 將現有報價查詢改走 provider
- 定義正式 quote response：
  - `price`
  - `source`
  - `quote_timestamp`
  - `quote_type`
  - `is_delayed`
- 完成 workspace CRUD 正式邏輯
- watchlist response 補上時間與來源欄位

#### 前端

- 將 workspace 從 `localStorage` 改為後端持久化
- 補畫面上的資料來源、資料時間、延遲標記
- 移除誤導性的即時語意
- watchlist 顯示每列的資料時間或快照狀態

### 7.3 本階段必補測試

- QuoteProvider contract tests
- workspace CRUD integration tests
- watchlist hydrated response tests
- 前端 workspace save/load smoke tests
- 前端 quote timestamp/source rendering tests

### 7.4 完成定義

- 工作區不再只依賴瀏覽器儲存
- 報價畫面都能明確顯示來源與資料時間
- 本階段涉及的工作區、自選股、報價快照資料都已本地落地

## 8. Phase 3：警報引擎與通知中心基礎

### 8.1 目標

把警報從前端暫存功能升級成後端正式引擎，並建立通知閉環。

### 8.2 實作任務清單

#### 資料庫

- 正式使用 `alerts`
- 正式使用 `alert_trigger_logs`
- 正式使用 `notifications`
- 建立 alert 與 notification 關聯查詢

#### 後端

- 完成 alerts CRUD
- 建立 alert evaluator service
- 建立背景檢查排程
- 建立 trigger log persistence
- 建立 notification creation flow
- 支援正式警報型別：
  - `price`
  - `pct`
  - `rsi`
  - `macd`
  - `volume`
  - `basis`
  - `institutional`
  - `event`
- 若前端有顯示但後端未實作的型別，必須補上或隱藏，禁止不一致

#### 前端

- 完成警報列表畫面
- 完成警報建立、編輯、暫停、恢復、刪除
- 顯示 trigger logs
- 完成通知中心基礎畫面
- 支援從標的詳情與圖表快速建立警報

### 8.3 本階段必補測試

- alert rule parameterized tests
- evaluator scheduler integration tests
- trigger log persistence tests
- notifications creation tests
- alerts API tests
- frontend alerts CRUD smoke tests
- frontend notification center smoke tests

### 8.4 完成定義

- 警報與通知重啟後不遺失
- 每次觸發都可回看時間、數值、來源
- 警報與通知資料可完全由本地資料庫重建

## 9. Phase 4：完整回測平台

### 9.1 目標

將回測從簡化功能升級成正式策略驗證模組。

### 9.2 實作任務清單

#### 資料庫

- 正式使用：
  - `backtest_runs`
  - `backtest_trades`
  - `backtest_equity_points`
- 建立 summary / trade detail / equity curve 的讀寫流程

#### 後端

- 建立 strategy registry
- 完成正式策略：
  - `ma_cross`
  - `rsi_reversion`
  - `macd_cross`
  - `bollinger_breakout`
  - `kd_cross`
- 補強：
  - fee
  - slippage
  - stop loss
  - take profit
  - position sizing
- 建立 summary API
- 建立 trade detail API
- 建立 equity curve API

#### 前端

- 重構回測頁
- 支援所有正式策略
- 顯示 summary、equity curve、trade list
- 支援回測紀錄重載與比較

### 9.3 本階段必補測試

- 每個策略 deterministic unit tests
- no-lookahead regression tests
- metrics calculation tests
- backtest API integration tests
- frontend backtest rendering tests

### 9.4 完成定義

- UI 顯示的每個正式策略都有後端實作
- 可回看逐筆交易與權益曲線
- 回測 summary、交易明細、權益資料皆可由本地資料庫重建

## 10. Phase 5：交易日誌與個人化分析

### 10.1 目標

建立交易執行與事後檢討閉環。

### 10.2 實作任務清單

#### 資料庫

- 正式使用：
  - `trade_journal_entries`
  - `trade_journal_tags`
  - `trade_journal_attachments`
- 補強 notification read/unread 狀態資料模型

#### 後端

- 完成 trade journal CRUD
- 完成 attachment metadata 存取
- 建立 stats aggregation service
- 建立 journal filters / search API
- 完善 notification read/unread API

#### 前端

- 完成交易日誌頁
- 完成新增 / 編輯 / 刪除交易紀錄
- 從圖表工作區直接建立交易紀錄
- 顯示 journal stats
- 完成正式通知中心頁

### 10.3 本階段必補測試

- journal CRUD tests
- attachment metadata tests
- statistics aggregation tests
- notification read/unread tests
- frontend journal flow smoke tests

### 10.4 完成定義

- 交易紀錄、附件 metadata、統計、通知都可由本地資料庫重建
- 使用者能依條件篩選與檢視歷史交易

## 11. Phase 6：事件資訊中心與宏觀風險儀表板

### 11.1 目標

把事件風險與宏觀風險正式納入交易前判斷流程。

### 11.2 實作任務清單

#### 資料庫

- 正式使用：
  - `market_events`
  - `news_articles`
  - `macro_snapshots`
- 建立 provider normalization 後的持久化流程

#### 後端

- 建立 event provider 與 normalization
- 建立 news provider 與 normalization
- 建立 macro provider
- 建立事件、新聞、宏觀同步任務
- 完成 API：
  - events calendar
  - ticker events
  - news list
  - macro dashboard
- 宏觀風險摘要必須可由本地快照重建，不可只在記憶體內生成

#### 前端

- 完成事件中心頁
- 完成標的事件卡
- 完成宏觀風險儀表板
- 完成圖表垂直事件線與事件列表聯動

### 11.3 本階段必補測試

- provider normalization tests
- event ordering tests
- news persistence tests
- macro snapshot tests
- API integration tests
- frontend event rendering smoke tests

### 11.4 完成定義

- 使用者可看見市場級與標的級事件
- 圖表可顯示事件標記
- 事件、新聞、宏觀快照都已寫入本地資料庫

## 12. Phase 7：台股進階籌碼與基本面模組

### 12.1 目標

補齊台股使用者最常用的個股籌碼與基本面資訊，並將其正式化。

### 12.2 實作任務清單

#### 資料庫

- 正式使用 `taiwan_chip_snapshots`
- 正式使用 `stock_info`
- 若新增更多籌碼明細或事件欄位，需同步擴表與 migration

#### 後端

- 建立正式 Taiwan chip provider
- 同步：
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
- 完成 API：
  - fundamentals detail
  - fundamentals events
  - taiwan chips detail
- 若現有籌碼資料為推導模型，只可作為過渡方案；正式驗收以前需明確標示資料來源與可信度

#### 前端

- 完成標的基本面卡
- 完成台股籌碼卡
- 完成基本面與籌碼摘要
- 補與警報 / 選股條件的整合入口

### 12.3 本階段必補測試

- fundamentals normalization tests
- taiwan chip normalization tests
- persistence tests
- API integration tests
- frontend detail card rendering tests

### 12.4 完成定義

- 搜尋與標的頁可看到完整基本面
- 台股標的可看到正式籌碼摘要
- 基本面與台股籌碼資料皆已本地落地

## 13. Phase 8：選股器、法人整合訊號化與最終硬化

### 13.1 目標

將零散模組整合成真正可用的市場決策工作台。

### 13.2 實作任務清單

#### 資料庫

- 正式使用 `screener_presets`
- 補齊整合型訊號所需的本地持久化資料結構
- 補齊 sync observability 與效能所需資料表或欄位

#### 後端

- 完成 screener engine
- 完成 screener preset persistence
- 將法人、basis、事件、基本面、籌碼條件整合進篩選器
- 補齊全域 regression fixtures
- 補齊 sync observability
- 補齊 performance profiling 與必要 cache

#### 前端

- 完成選股器頁
- 支援條件保存、排序、加入自選、一鍵跳圖
- 完成法人頁與圖表的訊號整合
- 補整體 UX polish

### 13.3 本階段必補測試

- screener filter correctness tests
- saved preset tests
- institutional summary regression tests
- end-to-end smoke tests covering:
  - 自選 -> 圖表 -> 警報
  - 圖表 -> 回測 -> journal
  - 事件 -> 圖表事件線
  - 篩選器 -> 加入自選 -> 標的分析

### 13.4 完成定義

- 核心模組完成整合
- 可以用單一工作流完成發現標的、分析、警報、回測、紀錄、檢討
- 選股器、法人整合訊號與相關正式資料都能由本地資料庫重建

## 14. Phase 執行用標準操作模板

每次進入某個 Phase 時，必須照以下模板執行：

1. 讀取本文件對應 Phase
2. 讀取 [quantvision-phase-delivery-plan.md](/c:/Users/Alan/Desktop/Stock-System/Stock-System/docs/quantvision-phase-delivery-plan.md) 對應 Gate 與完成定義
3. 完成本 Phase 任務清單
4. 補齊本 Phase 測試
5. 執行本 Phase 指定測試
6. 執行全域 Gate
7. 若失敗：
   - 直接修正
   - 重跑
   - 持續到綠燈
8. 若成功：
   - `git status --short`
   - `git add -A`
   - `git commit -m "phase-X: ..."`
9. commit 成功後：
   - 立即讀下一個 Phase
   - 自動開始下一個 Phase

## 15. 最終完成定義

只有當以下條件全部滿足時，整套分階段任務才算完成：

- 所有正式功能資料都已存到本地資料庫
- 不存在只能依賴前端 state / `localStorage` / 外部 API 即時回應的正式資料
- 每一個 Phase 都有對應測試與 Gate
- 每一個 Phase 都經過自動修復迭代直到綠燈
- 每一個 Phase 都有正式 Git commit
- 每一個 Phase commit 完成後都可繼續進入下一個 Phase
