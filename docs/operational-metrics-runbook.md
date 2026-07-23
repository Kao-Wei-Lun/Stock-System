# QuantVision 營運指標操作手冊

## 目的

系統每分鐘收集一次低成本營運指標，協助區分 API、資料庫、即時行情佇列、富邦連線、排程與程序資源問題。這些資料不包含逐筆行情、商品代號、SQL、帳號、憑證或個人資產內容。

## 保留與儲存

- 1 分鐘資料：最多保留 24 小時。
- 15 分鐘降採樣：最多保留 30 天。
- 儲存位置：`log/metrics/operational-metrics.json`。
- 寫入方式：先寫暫存檔再原子取代，系統重啟後會延續既有趨勢。
- `log/` 已由 Git 忽略，不會把執行期資料提交到版本庫。

## 查看方式

- 前端：設定 → 系統與資料品質 → 最近 24 小時。
- 即時效能摘要：`GET /api/system/performance`。
- 24 小時自動解析度：`GET /api/system/metrics/history?hours=24&resolution=auto`。
- 30 天降採樣：`GET /api/system/metrics/history?hours=720&resolution=downsampled`。

可觀察的主要欄位：

- API 回應 p50／p95／最大值。
- DB pool、等待與查詢延遲。
- 即時廣播延遲、持久化佇列年齡、深度與遺失數。
- 富邦連線狀態、重連次數與非敏感錯誤分類。
- 過期觀察商品與期貨商品數。
- 排程失敗／非預期停止數。
- 程序 RSS、private bytes、handle 數與背景工作數。

## 設定

```dotenv
OPERATIONAL_METRICS_INTERVAL_SECONDS=60
OPERATIONAL_METRICS_QUALITY_INTERVAL_SECONDS=300
OPERATIONAL_METRICS_STARTUP_DELAY_SECONDS=15
```

資料品質檢查比輕量效能取樣昂貴，因此預設每 5 分鐘更新一次；其餘效能數值每分鐘更新。

## 異常判讀

- API p95 上升、DB p95 正常：優先檢查 provider、序列化或背景工作競爭。
- DB wait p95 上升：檢查 pool 是否接近上限、長查詢或同時同步工作。
- broadcast p95 或 queue age 上升：檢查 WebSocket 用戶端、持久化速度與事件迴圈阻塞。
- dropped count 增加：視為即時資料完整性異常，需先停止增加負載並查明佇列壓力。
- provider 進入 failed／disconnected：使用系統提供的安全重連功能，不需重啟整套系統。
- process memory 或 handle 持續單向增加：執行 Phase 23 的長時間 soak 驗收並比對成長斜率。

## 隱私與備份

營運指標屬可重建的短期診斷資料，不列入個人資產或關鍵資料庫備份。若檔案毀損，服務會從空歷史重新收集；既有健康 API 仍可使用。
