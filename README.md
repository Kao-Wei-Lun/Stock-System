# QuantVision Pro

以 FastAPI + MySQL 提供市場資料 API，並以 Vue 3 + Vite 提供前端服務的股票監控系統。

## 架構

```text
Stock-System/
├── backend/                # FastAPI API + WebSocket + MySQL data layer
├── frontend/               # Vue 3 + Vite frontend service
│   ├── public/
│   │   └── legacy-dashboard.html
│   └── src/
├── scripts/
│   ├── start.bat
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
`ALLOW_LAN_ACCESS` 設為 `true`。Docker Compose 可在 `.env` 另以
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

## 前端說明

- 前端已改為 Vue 3 + Vite 專案，不再使用直接雙擊 `frontend/index.html` 的啟動方式
- 目前先以 Vue 應用包住既有 dashboard，確保原本功能能平順遷移
- 舊版單檔 dashboard 內容保留在 `frontend/public/legacy-dashboard.html`，方便持續拆分元件

## 後端說明

- FastAPI 提供 `/api/*` 路由與 `/ws` WebSocket
- `/api/health` 僅表示程序存活；`/api/ready` 會實際檢查資料庫是否可用
- 啟動時會初始化 MySQL database / tables
- 如果 `frontend/dist` 存在，後端可從 `/app/` 提供建置後的前端
- 若尚未 build，後端根路徑會導向開發中的前端服務 `FRONTEND_DEV_URL`

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
