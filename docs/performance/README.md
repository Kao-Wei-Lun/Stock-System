# 終端效能量測紀錄

本目錄只保存不含帳密、API key、部位、SQL 與個人資產內容的終端效能 JSON。

## 執行方式

後端啟動後，在專案根目錄執行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/benchmark-terminal.ps1
```

預設量測 `*TMFF` 的 1 分 K，包含 3 次 cold run、5 次 warm run，以及 TTFB、總時間、回應 bytes、median、p95 與最大值。API 不可用或回傳非成功狀態時，腳本會以非零狀態結束。

若要一併保存瀏覽器標記，可在開發者工具執行：

```js
copy(JSON.stringify(window.__QV_PERFORMANCE__, null, 2))
```

將內容另存為 JSON 後，以 `-FrontendMetricsPath` 傳入。腳本只會擷取四個允許的時間標記，不會複製其他瀏覽器資料：

- `qv:app-mounted`
- `qv:terminal-visible`
- `qv:chart-data-ready`
- `qv:chart-painted`

## 安全限制

- 不可將 `.env`、富邦帳號、憑證、持倉、個人資產或完整錯誤內容放入結果。
- `request_id` 只用於對照本機後端紀錄。
- Git 提交前必須人工檢查新增的 JSON 欄位。

## 最終自動化驗收

本機、不依賴執行中後端的完整 gate：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-final-performance-gate.ps1
```

同版後端、MySQL 與富邦連線均可用時，再加入即時 API 與資料庫
`EXPLAIN`：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-final-performance-gate.ps1 -IncludeLiveChecks
```

終端 bundle gate 的預設上限為：靜態 gzip 190,000 bytes、任一圖表引擎
選用後 gzip 190,000 bytes、初始 JS 檔案 9 個，而且兩套圖表引擎不可同時成為
靜態依賴。

## 60 分鐘即時壓力測試

```powershell
powershell -ExecutionPolicy Bypass -File scripts/soak-realtime.ps1 `
  -DurationMinutes 60 `
  -FuturesSymbols "*TMFF","*TXFF" `
  -StockSymbol "2330.TW"
```

腳本每 10 秒採樣健康狀態、1 分 K 最新時間、佇列深度、廣播延遲、資料庫
pool 等待、回測工作數與資產報價併發數。輸出只保留彙總值與市場資料的新鮮度，
不保存個人資產、帳密、完整 API 回應或 SQL。

資料庫索引可獨立驗收：

```powershell
venv\Scripts\python.exe scripts/check-db-performance-plan.py `
  --ticker "*TMFF" --interval 1m --limit 400
```

完整門檻與正式環境待驗項目請見
`docs/performance/final-acceptance-matrix.md`。
