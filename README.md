# QuantVision Pro

以 FastAPI + MySQL 提供市場資料 API，並以 Vue 3 + Vite 提供前端服務的股票監控系統。

## 架構

```text
Stock-System/
├── backend/                # FastAPI API + WebSocket + MySQL data layer
├── frontend/               # Vue 3 + Vite（production 由 FastAPI 提供 dist）
│   ├── public/
│   │   └── legacy-dashboard.html
│   └── src/
├── scripts/
│   ├── start.bat           # 日常 production 啟動（不安裝套件、不啟動 Node）
│   ├── start-dev.bat       # 開發模式（FastAPI + Vite HMR）
│   ├── setup.bat           # 明確安裝依賴
│   ├── build-frontend.bat  # 建置 production 前端
│   └── start.sh
├── docker-compose.yml
├── start.bat              # Windows wrapper; use "start.bat docker" for Docker
├── .env
└── README.md
```

## 系統需求

- Python 3.10+
- Node.js 18+
- MySQL 8+
- Docker Desktop（選用，用於容器化啟動）

## 環境設定

專案根目錄的 `.env` 至少要有：

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=quantvision
MYSQL_CHARSET=utf8mb4
APP_PORT=8001
APP_BIND_HOST=127.0.0.1
FRONTEND_BIND_HOST=127.0.0.1
ALLOW_LAN_ACCESS=false
APP_ENCRYPT_KEY=your_generated_secret
STARTUP_DOWNLOAD_ENABLED=false
FRONTEND_DEV_URL=http://localhost:5173
```

`APP_ENCRYPT_KEY` 用來加密儲存在資料庫中的富邦帳號敏感欄位。可使用以下指令產生：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

系統預設只接受本機連線。若確定要讓區域網路中的其他裝置使用，才在啟動前的環境變數中將
`APP_BIND_HOST`、`FRONTEND_BIND_HOST` 設為 `0.0.0.0`，並將
`ALLOW_LAN_ACCESS` 設為 `true`。建議同時用 `LAN_ALLOWED_NETWORKS`
限制為自己的網段（例如 `192.168.1.0/24`）；若從另一個開發伺服器來源
連線，再將完整來源加入 `LAN_ALLOWED_ORIGINS`。系統會拒絕公開 IP、非 IP
Host 與未授權網段。Docker Compose 可在 `.env` 另以
`DOCKER_BIND_HOST` 控制主機端綁定。

## 啟動方式

### Windows

```bat
scripts\start.bat
```

或從根目錄：

```bat
start.bat
```

### Mac / Linux

```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

啟動後會同時跑：

- 前端服務: `http://localhost:5173`
- 後端 API: `http://localhost:8001`
- Swagger 文件: `http://localhost:8001/docs`

### Docker

```bash
docker compose up --build
```

Windows 也可以使用：

```bat
start.bat docker
```

Docker Compose 會啟動：

- MySQL: `localhost:3306`
- 後端 API: `http://localhost:8001`
- 前端服務: `http://localhost:5173`

若本機已經有 MySQL 佔用 `3306`，可在 `.env` 調整 `MYSQL_PORT` 後再啟動。

## 外部通知

警報觸發時會先寫入站內通知；若 `.env` 設定以下任一組外部通道，後端會同步推送：

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
```

Telegram 需要同時提供 bot token 與 chat id；Discord 使用完整 webhook URL。

## Windows 啟動方式

首次安裝或套件更新時執行：

```bat
scripts\setup.bat
```

日常使用只需執行下列指令；它只啟動 FastAPI 並開啟 `http://localhost:8001/app/`，不會執行 npm/pip 安裝，也不會啟動 Vite：

```bat
scripts\start.bat
```

只有修改前端程式並需要 HMR 時才使用：

```bat
scripts\start-dev.bat
```

前端修改後可單獨執行 `scripts\build-frontend.bat` 重建 production 檔案。

## 前端說明

- 前端已改為 Vue 3 + Vite 專案，不再使用直接雙擊 `frontend/index.html` 的啟動方式
- 目前先以 Vue 應用包住既有 dashboard，確保原本功能能平順遷移
- 舊版單檔 dashboard 內容保留在 `frontend/public/legacy-dashboard.html`，方便持續拆分元件

## 後端說明

- FastAPI 提供 `/api/*` 路由與 `/ws` WebSocket
- `/api/health` 僅表示程序存活；`/api/ready` 會實際檢查資料庫是否可用
- 啟動時會初始化 MySQL database / tables
- 後端從 `/app/` 提供 `frontend/dist`，並支援 Vue Router deep link 重新整理
- 若 `frontend/dist/index.html` 不存在，後端會回傳 503 與明確建置提示
- hashed JS/CSS/font 使用一年 immutable cache；HTML 使用 `no-cache`

## 常用指令

### MySQL 備份與安全還原

備份會寫入 `backups/mysql`，並產生 SHA-256 manifest。備份密碼只會放在短暫的
MySQL client option file，不會出現在命令列或 manifest：

```powershell
scripts\backup-mysql.ps1
```

檢查備份完整性：

```powershell
python backend\mysql_backup.py verify backups\mysql\quantvision_YYYYMMDDTHHMMSSZ.manifest.json
```

還原預設只能寫入新的測試資料庫。建議先執行 dry-run，再正式還原：

```powershell
scripts\restore-mysql.ps1 `
  -Manifest backups\mysql\quantvision_YYYYMMDDTHHMMSSZ.manifest.json `
  -TargetDatabase quantvision_restore_test `
  -DryRun
```

若 `mysqldump` 或 `mysql` 不在 PATH，可設定 `MYSQLDUMP_PATH` 與
`MYSQL_CLIENT_PATH`。不要在尚未驗證備份前使用 `AllowSourceOverwrite`。

### 資料庫 migration

系統使用 `schema_migrations` 記錄 migration 版本、checksum、執行時間與 SQL
數量。先查看唯讀計畫，再於完成備份後套用：

```powershell
python backend\database_migrate.py plan
scripts\backup-mysql.ps1
python backend\database_migrate.py apply
python backend\database_migrate.py status
```

`DB_AUTO_MIGRATE=true` 保留既有啟動相容性；正式維護時可設為 `false`，讓有
pending migration 的服務拒絕啟動，改由上述流程明確套用。已套用 migration
若 checksum 改變，系統會拒絕繼續執行，必須建立新的 migration 版本。

### 單獨啟動前端

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### 單獨啟動後端

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 建置前端

```bash
cd frontend
npm install
npm run build
```

建置完成後，輸出會在 `frontend/dist`，後端可透過 `http://localhost:8001/app/` 提供靜態頁面。

## 效能驗收

每次修改終端、圖表、即時資料、資料庫查詢或回測後，執行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-final-performance-gate.ps1
```

正式環境驗收需啟動同一提交版本的後端，再執行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-final-performance-gate.ps1 -IncludeLiveChecks
powershell -ExecutionPolicy Bypass -File scripts/soak-realtime.ps1 -DurationMinutes 60
```

第一個指令驗證測試、production build、前端載入預算、100,000 根回測隔離、
即時 API 與資料庫索引；第二個指令連續觀察 `*TMFF`、`*TXFF` 與一檔股票。
詳細門檻與結果位於 `docs/performance/final-acceptance-matrix.md`。
