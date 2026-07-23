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
