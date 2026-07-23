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

