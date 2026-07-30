# 富邦 WebSocket 重連風暴修復規劃

日期：2026-07-30  
分支：`codex/fubon-reconnect-storm`

## 1. 問題摘要

本次事件不是單一 WebSocket 斷線，而是以下三層問題疊加：

1. Windows WLAN 先中斷網路：
   - 2026-07-30 03:04:49 WLAN 被驅動程式中斷。
   - 隨後出現 Wi-Fi Driver Miniport Halt。
   - 03:05:59 再次暫時斷線，03:07:05 才恢復。
2. 富邦 stock／futopt TLS 連線因此出現：
   - `WinError 10053`
   - `SSL UNEXPECTED_EOF_WHILE_READING`
   - TLS handshake timeout
3. 系統使用同一個已關閉的 SDK WebSocket 物件反覆重連，並允許錯誤回呼在前一次
   重連尚未完成時再建立下一次重連，造成：
   - `socket is already closed`
   - `Connection is already closed`
   - `NoneType object has no attribute sock`
   - 執行緒、handle 與 HTTP `CLOSE_WAIT` 持續增加。

事件檢查時，後端程序已達 897 個執行緒、約 2,790 個 handles、203 條本機
HTTP `CLOSE_WAIT`；8001 埠仍在監聽，但 `/api/ready` 無法回應。

## 2. 根因

### 2.1 外部觸發

- Wi-Fi 驅動重設或暫時中斷會直接破壞既有 TCP／TLS 連線。
- 富邦上游也可能以 `Server maintenance - going down for restart` 主動回收連線。
- 上述事件本身屬可預期的長連線故障，系統必須能在不重新啟動整台電腦的情況下恢復。

### 2.2 系統放大器

- 每個已啟用富邦帳號都同時啟動 stock 與 futopt 通道；五個帳號最多有十條連線。
- `FubonSDKManager` 的計時器在實際重連完成前即移除 pending 標記。
- error／disconnect 回呼可在前一個 `connect()` 尚未完成時再次建立計時器。
- `fugle-marketdata` 的同步 `connect()` 會建立執行緒並無期限等待驗證狀態。
- 通道重連重用已關閉的 WebSocket client，而不是建立新的 SDK session。
- Supervisor 只檢查程序是否退出與埠是否存在，無法辨識「埠還在、API 已假死」。
- 08:00 維護排程位於後端程序內；當 event loop 被拖垮時，排程本身也可能失效。

## 3. 修改目標

1. 同一帳號在任何時間最多只能有一個 recovery 工作。
2. stock 與 futopt 同時故障時只重建一次完整帳號 session。
3. 不再對已關閉的 SDK WebSocket client 進行原地重連。
4. 舊 session 的延遲 callback 不得修改新 session 的狀態。
5. 自動恢復必須有退避、最大連續失敗保護與可觀測狀態。
6. Supervisor 必須能從程序外偵測 `/api/ready` 無回應並回收假死程序。
7. 外部健康檢查不得在正常啟動暖機期間誤殺後端。
8. 所有變更維持既有 API、資料庫 schema、報價與 K 線資料相容。
9. 不執行真實交易，不改變交易下單安全邊界。

## 4. 目標架構

```text
SDK callback thread
        │ error / disconnect
        ▼
FubonSDKManager
  - 記錄 channel degraded
  - 驗證 session generation
  - 不直接呼叫已關閉 client.connect()
        │ thread-safe recovery notification
        ▼
FubonRealtimeSubscriptionPool
  - account-level single-flight
  - automatic backoff / circuit breaker
  - 從 DB 讀取該帳號設定
        │
        ▼
完整建立新 FubonSDK
  - login
  - init_realtime
  - 建立新的 stock / futopt clients
  - 只啟動有能力且有需求的通道
  - 重新平衡並恢復 desired subscriptions

Supervisor（獨立程序）
  - child process poll
  - /api/ready HTTP probe
  - startup grace
  - consecutive failure threshold
  - unhealthy recycle + restart breaker
```

## 5. 階段規劃

### Phase 0：規劃基線

內容：

- 建立本文件。
- 記錄事件證據、修改邊界、驗收條件與回滾方式。
- 保留使用者未提交的 `scripts/daily_report/validation.py`，不納入本功能 commit。

驗收：

- `git diff --check` 通過。
- 規劃文件包含根因、階段、測試、實機驗收及回滾。

Git：

- `docs: plan Fubon reconnect storm remediation`

### Phase 1：Manager callback 隔離與重連競態修復

內容：

- 為每次 SDK 初始化建立遞增的 session generation。
- message／connect／disconnect／error callback 捕捉建立當下的 generation。
- 舊 generation callback 僅記錄 debug，不得改變目前狀態或觸發 recovery。
- 新增 manager recovery notifier；SDK callback 只發出非阻塞通知。
- notifier 存在時禁止 manager 對原 WebSocket client 直接執行 reconnect。
- `pending` 狀態涵蓋已通知但尚未完成的 recovery。
- shutdown、重新初始化與成功連線時正確清除 pending 狀態。
- 保留無 notifier 情境的安全降級：標記 degraded，等待上層 watchdog；
  不再產生無上限的 `threading.Timer`／`connect()`。

測試：

- error 與 disconnect 連續發生時只通知一次。
- recovery pending 時不重複通知。
- 舊 generation callback 不影響新 session。
- shutdown callback 不通知 recovery。
- manager 自動錯誤處理不得呼叫 `connect()`。
- reconnect status 正確呈現 generation、pending 與錯誤分類。

Git：

- `phase-29a: isolate Fubon websocket recovery callbacks`

### Phase 2：帳號級完整 session 重建與熔斷

內容：

- Pool 在主 event loop 註冊 manager recovery notifier。
- 從 SDK thread 使用 `loop.call_soon_threadsafe()` 排入 recovery。
- `_reconnect_tasks` 改為 account-level single-flight，不再以 market 分裂工作。
- stock／futopt 任一通道失敗都重建完整帳號 session，不重用關閉的 client。
- 完整 session 重建流程：
  1. 保存 desired assignments。
  2. 移除 bridge／recovery handler。
  3. shutdown 舊 SDK。
  4. 從 DB 取得帳號設定並重新登入。
  5. 建立新 stock／futopt clients。
  6. 重新掛載 handlers。
  7. 啟動必要通道。
  8. 重新平衡與恢復訂閱。
- 同帳號同時收到 stock／futopt 故障時只重建一次。
- 保留既有 2～60 秒 exponential backoff 與 configuration error 停止規則。
- 新增連續 transient failure 上限與 cooldown，避免上游長時間故障造成登入風暴。
- 手動 reconnect 可清除 cooldown；自動 reconnect 必須遵守 cooldown。
- 狀態 API 增加 recovery reason、最後 request／success 與 circuit 狀態。

測試：

- 同帳號跨 market recovery 為 single-flight。
- 完整 recovery 建立新 SDK，不呼叫 `force_reconnect_ws()`。
- 恢復後 desired subscriptions 無遺失、無重複。
- 舊 callback 在新 SDK 上線後被忽略。
- transient failure 遵守退避與 cooldown。
- configuration error 不自動重試。
- 手動 recovery 可解除 cooldown。
- 多帳號故障彼此隔離。

Git：

- `phase-29b: rebuild Fubon sessions with account circuit breaker`

### Phase 3：Supervisor 外部健康檢查

內容：

- Supervisor 使用標準函式庫從外部探測 `/api/ready`。
- 新增設定：
  - startup grace
  - check interval
  - request timeout
  - consecutive failure threshold
- 只有在 startup grace 結束後，連續失敗達門檻才回收 child。
- HTTP 200 且 payload `ready=true` 才算健康。
- 假死回收沿用既有 crash backoff 與 restart breaker，避免無限重啟。
- runtime state 記錄安全的健康欄位：
  - last health check
  - consecutive failures
  - last unhealthy reason code
- 不記錄 URL query、帳號、ticker、憑證或回應內容。
- `start.bat status` 可顯示最近 health 狀態。
- 既有 planned stop／planned restart 優先權維持不變。

測試：

- startup grace 期間不健康不重啟。
- 單次 timeout 後恢復不重啟。
- 連續失敗達門檻後只回收一次。
- 假死重啟計入 crash breaker。
- planned stop／restart 優先於 health recycle。
- HTTP 200 但 `ready=false` 視為失敗。
- health response malformed 時安全失敗。
- state file 不包含敏感資料。

Git：

- `phase-29c: restart unresponsive backend from supervisor`

### Phase 4：完整與實機驗收

自動化：

- `backend/tests/test_fubon_provider.py`
- `backend/tests/test_fubon_realtime_pool.py`
- `backend/tests/test_providers_fubon_ws_channels.py`
- `backend/tests/test_fubon_maintenance_restart.py`
- `backend/tests/test_service_supervisor.py`
- `backend/tests/test_app_smoke.py`
- 完整 backend pytest
- runtime environment validation
- `git diff --check`

實機：

1. 重新啟動服務，記錄基線 PID、thread count、handle count。
2. `/api/ready` 必須在設定時間內回覆。
3. 確認五個帳號不會在無需求時建立不必要通道。
4. 使用安全的 fake／測試注入模擬同時 stock＋futopt error：
   - 同帳號只建立一個 recovery。
   - 不對真實帳號送出交易指令。
5. 驗證 recovery 後：
   - 新 session generation。
   - 訂閱恢復。
   - thread count 不隨錯誤次數線性成長。
6. 使用獨立測試 child 驗證 Supervisor：
   - 埠仍監聽但 `/api/ready` timeout。
   - 達門檻後 child 被回收。
   - 新 child 恢復 ready。
7. 觀察至少兩個 health interval，確認沒有誤重啟。
8. 記錄結果到本文件後提交。

Git：

- `docs: record Fubon reconnect storm acceptance`

## 6. 驗收規格

### A. 短暫網路中斷

- 單帳號同一時間 recovery task 數量最多 1。
- 不出現重複 `connect()` thread。
- 60 秒內恢復或進入可觀測 backoff。
- API 仍可回應；若 API 假死，Supervisor 能回收。

### B. 長時間斷網

- recovery 次數受 backoff 與 circuit breaker 限制。
- thread count 不因 retry 次數線性增加。
- 不重用已關閉 WebSocket client。
- 系統保留 DB 歷史資料與非即時頁面功能。

### C. stock 與 futopt 同時故障

- 同帳號只重建一次 SDK session。
- recovery 後兩個必要通道與所有 desired subscriptions 恢復。
- 不同帳號可獨立恢復。

### D. 舊 callback 延遲抵達

- 舊 generation 的 connect／disconnect／error／message 全部忽略。
- 新 session 狀態不得被改回 degraded。

### E. 後端假死

- 8001 仍 LISTENING 但 `/api/ready` 連續失敗達門檻。
- Supervisor 回收受管理的程序樹並啟動新 child。
- restart breaker 在短期反覆假死時停止無限循環。

### F. 相容性

- API path 與既有 response 欄位不刪除。
- 資料庫無 migration。
- K 線、個人資產、模擬交易資料不修改。
- 不執行任何真實交易。

## 7. 效能與資源門檻

- 穩定啟動後 thread count 應維持在基線附近。
- 同帳號重複 100 次 error callback，不得建立 100 個 recovery threads。
- recovery 任務與 timer 數量必須有固定上限。
- `/api/ready` 正常狀態應在 Supervisor timeout 內回覆。
- 日誌對同帳號／通道的重複錯誤應節流，保留首筆、狀態變化及彙總。

## 8. 回滾

- Phase 1 可回滾 notifier／generation，恢復原 manager 行為。
- Phase 2 可回滾 account-level recovery，資料庫不需回復。
- Phase 3 可透過 Supervisor health check 設定停用外部探測。
- 若外部健康檢查誤判，可保留 crash supervisor 並關閉 health recycle。
- 所有階段都不修改行情、個人資產或交易資料，因此不需要資料還原。

## 9. Git 與工作樹規則

- 每個 Phase 測試通過後才 commit。
- 每次只 stage 本階段明確檔案。
- 不使用 `git add -A`。
- 不納入 `.env`、帳密、憑證、runtime marker、log 或使用者既有修改。
- 最後確認工作樹只保留使用者原有的
  `scripts/daily_report/validation.py` 修改。

## 10. 實際驗收結果（2026-07-30）

### 10.1 原因確認

- Windows WLAN 事件顯示無線網卡曾發生驅動中止、斷線與重新連線，這是第一個外部觸發點。
- 富邦上游亦曾回傳 server maintenance，代表 WebSocket 被上游定期關閉是必須處理的正常故障情境。
- 舊版在錯誤 callback 內重用已關閉的 client 並反覆呼叫 `connect()`；第三方 SDK 的連線等待沒有 timeout，
  因而可累積大量 thread、handle 與 `CLOSE_WAIT`。
- 故障程序實測曾達約 897 threads、2,790 handles、203 個 `CLOSE_WAIT`，且 8001 仍在 LISTENING，
  但 `/api/ready` 無法回應。

### 10.2 各階段交付

- `c931fa9`：完成詳細修復、測試、驗收及回滾規劃。
- `a15f5cd`：加入 WebSocket generation 隔離與 owner recovery callback。
- `5fcb450`：改為帳號層級 single-flight session rebuild、timeout、backoff 與 circuit breaker。
- `9b29b35`：Supervisor 加入外部 `/api/ready` 探測與假死程序樹回收。
- `5ee75be`：序列化 startup warmup、settings reload 與 recovery，排除啟動競態。

### 10.3 自動測試

- 富邦 provider／realtime pool 相關測試：`125 passed`。
- Supervisor 專項測試：`17 passed`。
- 完整後端測試：`657 passed`。
- 執行環境檢查：通過；LAN access 維持停用。
- `git diff --check`：本次修改無 whitespace error。

自動測試涵蓋：

- 同帳號重複 100 次 error callback 只產生一個 recovery，不建立無界 reconnect timer。
- stock 與 futopt 同時失敗時只重建一個帳號 session。
- 舊 generation callback 不得污染新 session。
- connect timeout 能中止第三方 SDK 的無界等待。
- recovery 連續失敗會進入 bounded backoff／circuit breaker。
- 8001 仍監聽但 `/api/ready` 連續失敗時，Supervisor 會回收 child；單次失敗不會誤重啟。
- planned stop／restart 的優先順序不受 health recycle 影響。
- warmup 尚未完成時，session refresh 不會重建正在初始化的帳號。
- recovery 必須等待 configuration reload 完成，避免同一 manager 被並行替換。

### 10.4 實機服務驗收

最新程式重新啟動後：

- `/api/ready` 回傳 `ready=true`、`degraded=false`，資料庫及 production SPA 均可用。
- provider warmup 為 `ready`，帳號連線 `5/5`。
- 只啟動有訂閱需求的 5 條通道：3 條 stock、2 條 futopt；未再為 5 個帳號固定建立 10 條連線。
- 5 條有效通道均為 `connected`、`pending=false`、`generation=1`。
- 啟動後沒有重複帳號初始化、isolated recovery、WebSocket error 或 disconnect warning。
- 程序基線由 71 threads／481 handles 收斂至 66 threads／482 handles，沒有隨時間線性成長。
- `CLOSE_WAIT` 在兩次取樣為 0 與 7，沒有重現舊版累積至 203 的情況。
- `/api/ready` 實測約 150.1 ms。
- Supervisor 跨過 120 秒 startup grace 後，至少兩次探測均為 `healthy`，
  `consecutive_failures=0`、`last_reason_code=ready`、`restart_count=0`。

### 10.5 資料與安全確認

- 未新增資料庫 migration，未修改 K 線、個人資產或模擬交易資料。
- 未送出任何真實交易指令。
- 未納入 `.env`、帳密、憑證、runtime marker 或 log。
- 使用者原有的 `scripts/daily_report/validation.py` 修改未被 stage、commit 或回滾。
