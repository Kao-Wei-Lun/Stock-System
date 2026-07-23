# QuantVision 本機服務監督與日誌手冊

## Production 架構

Production 只需要一個後端程序。FastAPI 同時提供 API、WebSocket 與已編譯的 Vue `frontend/dist`，因此不會另外開啟 Vite service CMD；Vite 僅供 `start-dev.bat` 開發使用。

## 啟動、狀態與停止

```bat
start.bat
start.bat status
start.bat stop
```

啟動器會先檢查 8001 埠：

- 空閒：啟動 supervisor 與 uvicorn。
- 已由同一 supervisor 管理，或符合相同專案 venv 完整 uvicorn 簽章：沿用既有後端，不建立第二份。
- 不明程序占用：停止啟動並回報 PID；不執行 `taskkill`。

`start.bat stop` 會先比對 `.runtime/backend-service.json`，或同專案 venv 路徑、PID、port 與 `uvicorn main:app` 完整命令簽章；只有確認相符才送出 planned shutdown。這也讓導入 supervisor 後第一次啟動能安全沿用舊版 launcher 的現存程序。`.runtime/` 不包含憑證或啟動參數，且不提交 Git。

## 崩潰復原

- 非零結束碼視為非預期崩潰。
- 重啟退避依序為 1、2、4、8、16 秒，上限 30 秒。
- 5 分鐘內發生 5 次崩潰會開啟 restart breaker，不再無限重啟。
- 正常結束碼、Ctrl+C 或 `start.bat stop` 都屬 planned shutdown，不會重啟。
- breaker 狀態位於 `.runtime/backend-service-breaker.json`，不含命令列或秘密。

排除問題後重新執行 `start.bat`，新一輪監督會清除舊 breaker；若 8001 仍被不明程序占用，需由使用者確認該程序用途後自行處理。

## 日誌隔離

| 檔案 | 用途 |
|---|---|
| `log/backend.log` | production API、provider 與一般執行期事件 |
| `log/scheduler.log` | 背景同步、排程與定時備份事件 |
| `log/backup.log` | CLI 備份、還原與儲存維護 |
| `log/test.log` | pytest 執行期事件 |
| `log/test-scheduler.log` | pytest 中的排程事件 |

所有檔案都會先經敏感文字遮罩。富邦失敗訊息包含 `category` 與已遮罩的 `message`，不記錄完整報價 payload、憑證、token 或帳號秘密。

## 輪替與保留

```dotenv
LOG_FILE_ENABLED=true
LOG_FILE_PATH=log/backend.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=14
LOG_RETENTION_DAYS=14
```

日誌在跨日或達到大小上限時輪替；歷史檔同時受數量與天數限制。`LOG_FILE_PATH` 只覆寫 production 主日誌，test、scheduler 與 backup 仍使用隔離檔名。

## 常見狀況

- `unconfirmed process`：8001 被非 supervisor 管理的程序占用；系統刻意不自動終止。
- `restart breaker is open`：先查看 `backend.log` 最早的失敗原因，不要反覆重開。
- 後端 healthy 但頁面未開：確認 `frontend/dist/index.html` 存在，再看啟動器的 `/app/` 檢查結果。
- 排程異常但 API 正常：優先查看 `scheduler.log` 與設定頁「系統與資料品質」。
