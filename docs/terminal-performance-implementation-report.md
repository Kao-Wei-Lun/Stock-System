# 終端效能架構修改驗收報告

日期：2026-07-23  
分支：`codex/realtime-reliability-phases`

## 階段交付

| 階段 | 主要成果 | Git commit |
|---|---|---|
| Phase 0 | request ID、Server-Timing、前端效能標記、固定 Gate 與 benchmark | `902e1d8` |
| Phase 1 | 期貨 DB-first、background/blocking/none、single-flight 與 shutdown cleanup | `d04d693` |
| Phase 2 | route-first bootstrap、lazy resource、AbortController 與 stale response token | `7466929` |
| Phase 3 | 400 根 bounded K 線、`since` 增量、GZip、snapshot summary、watchlist metadata/cache | `c0c38d8` |
| Phase 4 | Legacy/LWC 互斥 lazy chunk、增量 series update、resize/instance cleanup | `c70d454` |
| Phase 5 | FastAPI production SPA、deep-link fallback、immutable cache、啟動腳本拆分 | `bfa66a5` |
| Phase 6 | IndexedDB 快取先畫、DB 覆核、WebSocket 更新、來源狀態與最終韌性驗收 | 本階段提交 |

## 最終效能量測

真實本機 MySQL、`*TMFF`、1 分 K、`limit=400`、`warmup=250`：

| 指標 | Cold | Warm |
|---|---:|---:|
| TTFB median | 31.17 ms | 30.64 ms |
| TTFB p95 | 49.47 ms | 35.07 ms |
| Total median | 32.20 ms | 30.99 ms |
| Total p95 | 54.03 ms | 35.58 ms |
| 未壓縮 JSON | 76,296 bytes | 76,296 bytes |
| GZip response | 7,881 bytes | 7,881 bytes |
| 回傳 K 棒 | 400 | 400 |

詳細原始結果：`docs/performance/phase-6-final.json`。

production build 的終端主要 chunk 為 85.73 KB（gzip 24.48 KB）；Legacy 與 LWC 引擎分別為獨立 lazy chunk，gzip 約 56.00 KB 與 68.57 KB。初始頁不會同時下載兩套引擎。

## Browser smoke

- `/app/terminal/*TMFF` 可直接重新整理並正確解析動態期貨代號。
- `/app/overview/2330.TW` 與 `/app/assets/2330.TW` deep link 可直接載入。
- 即時五檔共 10 列買賣盤，資料恢復正常。
- 連續 reload 20 次後只存在一個 StatusBar，終端回到資料庫 K 線並恢復 WebSocket 即時狀態。
- 狀態列可區分快取資料、資料庫資料與即時更新。

## 快取安全邊界

IndexedDB 僅保存 bounded OHLCV 與精簡 watchlist metadata，設有 schema version、七日有效期、日期順序驗證、每筆最多 500 根與最多 8 組快照。資產、交易紀錄、API key、密碼與憑證不會寫入此快取；MySQL 仍是正式資料來源。

## 操作方式

- 首次安裝／更新依賴：`scripts\setup.bat`
- 日常 production：`scripts\start.bat`
- 前端 HMR 開發：`scripts\start-dev.bat`
- 單獨重建前端：`scripts\build-frontend.bat`

production 啟動不執行 npm/pip 安裝，也不啟動 Vite；瀏覽器統一使用 `http://localhost:8001/app/`。

## 進階效能 Phase 7–15

| 階段 | 修改內容 | Git commit |
|---|---|---|
| Phase 7 | 後端即時廣播、DB pool 與前端 Long Task / paint 遙測 | `49a1873` |
| Phase 8 | 圖表引擎互斥 chunk、本機字型、bundle manifest 驗收 | `7b04f96` |
| Phase 9 | 即時廣播與報價寫入解耦、bounded queue、批次持久化 | `8aecd06` |
| Phase 10 | 即時訊息合併、每動畫幀最多一次 Vue 畫面更新 | `9474951` |
| Phase 11 | Legacy 與 LWC 都改為增量更新，避免每 tick 全量重畫 | `3bb8145` |
| Phase 12 | 期貨查詢 bounded、索引 migration、互動查詢優先權 | `aa43851` |
| Phase 13 | 路由 controller 拆分並依工作區延遲載入 | `6060c42` |
| Phase 14 | 回測改用單一 ProcessPool、資產報價限流與 single-flight | `8d6164b` |
| Phase 15 | 工具抽屜與警報視窗延遲載入、硬性效能預算、EXPLAIN 與 60 分鐘 soak gate | 本次提交 |

### 最終前端載入結果

- 終端靜態 JS gzip：119,688 bytes。
- Legacy 引擎選用後：137,761 bytes。
- LWC 引擎選用後：188,300 bytes。
- 初始靜態 JS：4 個檔案。
- 兩套圖表引擎保持互斥，未選用引擎下載量為 0。

相較 Phase 13 的 LWC 選用後 195,400 bytes，本階段再下降 7,100 bytes
（3.63%），並低於 190,000 bytes 的交付上限。警報 modal 與終端工具抽屜只在
使用者實際開啟時下載，因此不增加首次終端渲染成本。

### 驗收與環境邊界

`scripts/run-final-performance-gate.ps1` 會串接後端測試、前端測試、production
build、bundle 預算與 100,000 根回測隔離測試；加入 `-IncludeLiveChecks` 後
才會連線同版後端、MySQL 與即時市場 API。`scripts/soak-realtime.ps1` 預設執行
60 分鐘，驗證 `*TMFF`、`*TXFF` 與一檔股票。

正式 60 分鐘富邦連線測試仍需在交易時段、使用同一提交版本的後端執行。
目前執行中的開發後端不是本次修改後的服務，因此不把其 404 或舊版遙測當成
本階段結果。詳細狀態、回滾方式與待驗項目見
`docs/performance/final-acceptance-matrix.md`。
