# 富邦 WebSocket 條件式維護重啟修改規畫

## 1. 目標

當富邦股票或期貨 WebSocket 發生 `WinError 10053`、斷線回呼遺失，或自動重連
停止後，不再依賴使用者手動重開整套系統。

系統應依下列順序處理：

1. 立即進行單一行情通道重連。
2. watchdog 發現重連流程停止時，重新啟動該通道並恢復訂閱。
3. 只有承載實際訂閱的通道持續異常超過寬限時間，才登記維護重啟。
4. 到下一個台北時間工作日 08:00，由 Supervisor 受控重啟後端。
5. 每個維護時段最多重啟一次，避免無限重啟。

08:00 距離臺灣期貨日盤 08:45 與台股 09:00 尚有暖機時間。此功能只重啟
QuantVision backend，不重啟 Windows、MySQL 或瀏覽器。

## 2. 非目標與安全邊界

- 不因任一未使用帳號顯示 disconnected 就重啟。
- 不因沒有盤中訊息就判定斷線；休市時沒有 tick 是正常狀態。
- 不終止占用 8001 的不明程序。
- 不使用 `taskkill` 強制終止未確認程序。
- 不把帳號、憑證、API key、訂閱 ticker 或錯誤原文寫入 restart marker。
- 不在交易時段立即重啟整個 backend；先使用隔離式通道恢復。
- 電腦關機、Supervisor 未啟動時，應用程式內排程無法自行開機；這種需求另由
  Windows 工作排程器處理。

## 3. 異常判定

### 3.1 需要監控的通道

每個富邦帳號分別監控：

- `stock`
- `futopt`

只有同時符合下列條件才算需要升級處理：

1. 帳號已啟用。
2. 該通道 `desired_subscription_count > 0`。
3. 通道狀態不是 `connected`。

使用中帳號若沒有承載任何即時訂閱，即使 socket 顯示 disconnected，也不能觸發整套
服務重啟。

### 3.2 錯誤分類

下列訊息應分類為可恢復的 `transient`：

- `ConnectionAbortedError`
- `WinError 10053`
- `connection aborted`
- `連線已被您主機上的軟體中止`

登入失效仍使用 `session_invalid`；憑證、帳密或帳號類別錯誤仍使用
`configuration_error`，不得進入無限重試。

## 4. 恢復狀態機

```text
connected
   │ on_error / on_disconnect
   ▼
channel_backoff ── timer retry ──► connecting
   ▲                                  │
   │                                  ├─ success ─► connected + restore subscriptions
   │                                  │
   └──────────── failure ─────────────┘

watchdog 發現 desired subscriptions > 0 且沒有 pending retry
   │
   ▼
isolated channel reconnect
   │
   ├─ success ─► connected
   │
   └─ 持續異常超過 grace period ─► maintenance_pending
                                         │
                                         ▼
                              下一個工作日 08:00
                                         │
                                         ▼
                               supervised planned restart
```

### 4.1 Watchdog

- 每 30 秒檢查一次通道。
- 已有 pending reconnect 時不建立第二個任務。
- 沒有 pending reconnect、仍有訂閱且未 connected 時，呼叫既有
  `reconnect_account(account_id, market_type, manual=False)`。
- 健康恢復後清除該異常 episode。
- 異常持續時間預設 300 秒後，才具備維護重啟資格。

### 4.2 維護時段

- 異常在 08:00 前發生：最早於當日 08:00 執行。
- 異常在 08:00 後發生：排到下一個工作日 08:00。
- 異常在週五 08:00 後發生且啟用 weekdays-only：排到週一 08:00。
- 到達時段時若通道已恢復，不重啟。
- 若 07:59 才異常，必須等滿 grace period，可在 08:04 左右執行，而不是忽略寬限期。

## 5. Supervisor planned restart

### 5.1 Marker

新增 `.runtime/backend-service.restart`，使用原子寫入的版本化 JSON：

```json
{
  "schema_version": 1,
  "requested_at": "2026-07-27T00:00:00+00:00",
  "reason_code": "fubon_ws_maintenance",
  "source": "scheduler"
}
```

Marker 不含帳號 ID、ticker、錯誤原文或秘密。

### 5.2 Supervisor 行為

Supervisor 管理中的 child process 執行期間，每 0.5 秒檢查：

1. planned stop marker 優先於 restart marker。
2. 收到 restart marker 後，對已確認的 child process 執行正常終止。
3. 等待 child 清理 FastAPI lifespan、WebSocket、K 線 recorder 與資料庫連線。
4. 清除 restart marker。
5. 重新啟動 child process。
6. planned restart 不計入 crash count，不觸發 restart breaker。
7. 寫入不含秘密的最後重啟結果，供狀態頁與日誌查詢。

若 Supervisor 不在運作，排程只能留下 marker；不得自行尋找或終止其他程序。

## 6. 設定

新增：

```dotenv
FUBON_MAINTENANCE_RESTART_ENABLED=false
FUBON_MAINTENANCE_RESTART_TIME=08:00
FUBON_WS_UNHEALTHY_GRACE_SECONDS=300
FUBON_WS_HEALTH_CHECK_INTERVAL_SECONDS=30
FUBON_MAINTENANCE_RESTART_WEEKDAYS_ONLY=true
```

程式預設關閉，避免升級後對其他環境產生非預期重啟。本機使用者明確啟用後才生效。

## 7. 分階段修改

### Phase 0：規畫與基線

- 建立本文件。
- 保留現有 API、資料庫 schema 與啟動方式。
- 確認使用者尚未提交的 daily report 檔案不納入任何 commit。

驗收：

- `git diff --check` 通過。
- 規畫涵蓋異常判定、時段、防迴圈、回滾與測試。

### Phase 1：通道分類與 watchdog

修改：

- `fubon_provider.py`：10053 分類為 transient。
- `fubon_realtime_pool.py`：找出有實際訂閱但 stalled 的通道。
- `refresh_session_assignments()`：補做 isolated channel reconnect。
- 加入狀態與日誌，不輸出帳號秘密。

測試：

- 10053、中文訊息及 `ConnectionAbortedError` 分類。
- 沒有 desired subscriptions 的 disconnected 通道不處理。
- connected 或已有 pending timer 的通道不重複處理。
- stalled stock/futopt 只重連對應通道。
- configuration error 維持 backoff／停止自動循環規則。

### Phase 2：Supervisor 受控重啟

修改：

- 新增 restart marker 讀寫。
- Supervisor wait loop 支援 planned restart。
- stop 優先、planned restart 不計 crash。
- `status` 顯示 pending restart 與最後結果。

測試：

- marker schema 與敏感資訊限制。
- child 正常終止後重新建立。
- restart 不增加 crash count。
- stop 與 restart 同時存在時只停止。
- 不明 8001 程序仍不會被終止。

### Phase 3：08:00 條件式維護排程

修改：

- Scheduler settings/dependencies 加入健康狀態與 restart callback。
- 新增可注入 clock 的 maintenance loop。
- 主程式讀取環境設定並連接 Supervisor marker callback。
- `.env.example`、本機 `.env` 與操作文件更新。
- 系統健康資訊加入最近 maintenance 狀態。

測試：

- 08:00 前、08:00 後與週末目標時間。
- 異常不足 grace period 不重啟。
- 時段到達前恢復不重啟。
- 無訂閱通道不重啟。
- 同一 episode 只提出一次 request。
- 功能關閉時不建立排程。

### Phase 4：Windows venv 程序樹可靠性

實機啟動可能形成 `supervisor → venv python launcher → Python/uvicorn`
三層程序。Supervisor 必須把實際監聽 PID 辨識為受管理的子孫程序，
planned stop/restart 也必須終止整棵已確認的程序樹，避免留下仍占用
8001 埠的孤兒程序。

測試：

- 監聽 PID 是 launcher 的多層子程序時仍顯示 `managed=true`。
- 優雅停止後埠仍被已確認的子程序占用時，才使用 Windows tree kill。
- CLI stop 先等待 supervisor 處理 marker，避免雙方競爭停止同一程序。
- 不明命令列或非本專案 Python 程序仍不會被終止。

### Phase 5：整體驗收

- 富邦、Supervisor、Scheduler 相關測試。
- 後端完整 pytest。
- runtime environment validation。
- production `start.bat status`。
- `git diff --check`。
- 確認 `.env`、`.codex/config.toml` 與使用者 daily report 修改均未進入 commit。

## 8. 驗收情境

### 情境 A：短暫 10053

1. socket 發生 10053。
2. 30 秒內成功重連。
3. 訂閱恢復。
4. 08:00 不重啟。

### 情境 B：持續斷線

1. 有訂閱的 futopt 通道持續 disconnected。
2. watchdog 重試但超過 300 秒未恢復。
3. 記錄下一維護時間。
4. 08:00 Supervisor 重啟一次。
5. child 重啟後暖機與訂閱恢復。

### 情境 C：未使用通道

1. active account socket disconnected。
2. `desired_subscription_count == 0`。
3. 不登記維護、不重啟。

### 情境 D：重啟後仍異常

1. Supervisor 完成 planned restart。
2. 新程序仍無法連線。
3. 當日不再次重啟。
4. 保留 degraded 狀態與日誌，等待下一維護時段或人工處理設定問題。

## 9. 回滾

- 將 `FUBON_MAINTENANCE_RESTART_ENABLED=false` 可立即停用排程。
- watchdog 與現有單通道重連可獨立保留。
- 刪除 restart marker 不影響資料庫。
- 功能不需要 database migration。
- 若 planned restart 機制異常，可回到 Supervisor 原有的 crash-only restart 行為。
