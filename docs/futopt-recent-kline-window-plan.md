# 期貨近期 K 線顯示視窗修正規劃

日期：2026-07-27
目標分支：`codex/futopt-recent-kline-window`

## 1. 問題與實際證據

終端選擇 `*TMFF` 的 1 分 K 時，前端目前送出：

```text
period=1d&interval=1m&limit=400&warmup=250
```

後端資料庫查詢把 `period=1d` 轉成「從昨天的日曆日期開始」。
在週一查詢時，昨天是週日，因此週五日盤與大部分週五夜盤不在查詢
下限內，即使資料庫已有足夠資料，畫面仍只會顯示週一開盤後的 K 棒。

2026-07-27 實際檢查：

- `*TMFF` 1 分 K：3,181 根。
- `TMF` 連續別名 1 分 K：70,316 根。
- `TMFG6`：20,500 根。
- `TMFH6`：8,959 根。
- `period=1d` API 只回傳 133 根，起點為 08:45。
- 同一資料改用較大日曆期間可回傳最近 400 根。

結論：資料未遺失，缺陷位於「顯示用 DB 視窗」與「上游補資料期間」
共用同一個 `period`。

## 2. 修改目標

1. 初次載入有 `limit`、沒有 `since` 的期貨 K 線時，從資料庫取得真正
   的最近 N 根，不受週末、連假或休市日影響。
2. 富邦 API 的 refresh 仍使用前端要求的原始 period，例如 1 分 K 仍只
   補 `1d`，避免為了顯示歷史而重複下載一個月資料。
3. 增量更新有 `since` 時維持既有語意，只讀取該時間之後的資料。
4. 沒有 `limit` 的舊 API 呼叫維持 period 範圍，保留向後相容。
5. `*TMFF`、`TMF` 與實體合約如 `TMFH6` 使用相同規則。
6. 不搬移、不刪除、不複製既有 OHLCV 資料，不需要資料庫 migration。

## 3. 設計

### 3.1 分離兩種期間

`load_futopt_ohlc_db_first()` 內部拆分：

- `requested_period`：API 請求 period，回傳 metadata 與富邦 refresh 使用。
- `database_period`：資料庫初次顯示查詢使用。

規則：

| 情境 | database period | refresh period |
|---|---:|---:|
| `limit=400` 且沒有 `since` | `max`，但 SQL 仍 `LIMIT 400` | 原始 period |
| 有 `since` | 原始 period；repository 以 since 為下限 | 原始 period |
| 沒有 `limit` | 原始 period | 原始 period |

使用 `max + LIMIT` 並不是載入全部資料；repository 會使用倒序索引取得
最近 N 根後再正序回傳，記憶體與 API payload 仍受 5,000 根上限保護。

### 3.2 API 相容性與觀測資訊

保留既有欄位：

- `period` 仍回傳使用者要求的 period。
- `data`、`row_count`、`refresh_mode`、`refresh_status` 語意不變。

新增非破壞性 metadata：

- `database_period`
- `history_window_expanded`

用來從日誌或 API 判斷本次是否為取得足夠近期 K 棒而擴展 DB 視窗。

### 3.3 前端

前端仍可維持 `1m → period=1d`，因為它代表富邦尾端補資料範圍。
不把前端固定改成 `5d` 或 `1mo`，避免每次 stale refresh 擴大上游請求。

終端仍以：

```text
limit=400&warmup=250
```

控制初次渲染與指標暖機的資料量。

## 4. 邊界與風險

### 週末與連假

最近 N 根直接跨越非交易日，週一與連假後可顯示上一交易時段。

### 增量輪詢

帶 `since` 的 REST fallback 不可回送 since 以前的 400 根，否則會增加
合併成本；因此增量查詢不啟用 DB 視窗擴展。

### 現行與舊合約

`*TMFF` 會合併 `*TMFF` 與 canonical `TMF` 的資料；`TMF` 已保存跨月
連續資料。實體合約則只讀取該合約自身最近資料，不混入其他月份。

### 效能

- 查詢仍有 `ticker + interval + date` 索引與 LIMIT。
- 不允許超過既有 5,000 根上限。
- background refresh 不等待慢速富邦 API。
- 必須保留既有 API latency gate。

### 資料安全

- 不刪除 `ohlcv`。
- 不修改 unique key。
- 不重寫既有期貨價格。
- 不影響真實交易；系統仍只執行分析與模擬交易。

## 5. 分階段修改

### Phase 0：規劃與基線

- 建立本文件。
- 記錄資料庫與 API 實際範圍。
- 確認工作樹乾淨。

驗收：

- 規劃涵蓋相容性、週末／連假、增量、效能及回滾。
- `git diff --check` 通過。

### Phase 1：DB 顯示視窗分離

- 新增純函式決定 database period。
- `load_futopt_ohlc_db_first()` 的初次與 refresh 後 DB 查詢使用
  database period。
- 富邦 sync 繼續使用 requested period。
- 新增 metadata。

測試：

- 有 limit、無 since 時 DB 使用 `max`。
- 無 limit 時仍使用原 period。
- 有 since 時不擴展。
- refresh provider 仍收到原始 `1d`。
- alias 合併、排序、去重及 limit 維持正確。

### Phase 2：API 與週末回歸

- API 測試模擬週一只有 133 根在 1d 範圍、DB 實際有 400 根。
- 驗證 `/api/futopt/ohlc/*TMFF` 回傳最近 400 根。
- 驗證 `period` 不變、metadata 正確。
- 保留 background latency gate。
- 前端契約測試確認仍送出 `limit=400`、`warmup=250`。

### Phase 3：完整與實機驗收

- 期貨 history/service/API 測試。
- 完整 backend pytest。
- 相關 frontend Vitest。
- Runtime environment validation。
- 實際呼叫 `*TMFF` 1 分 K API。
- 確認第一根跨到上一交易時段、最後一根為最新資料。
- 確認服務狀態正常、Git working tree 只含預期變更。

## 6. 驗收情境

### A. 週一初次載入

1. 使用 `period=1d&interval=1m&limit=400`。
2. 1d 日曆範圍內只有週一 133 根。
3. API 仍回傳最近 400 根。
4. 前 267 根來自上一交易時段。

### B. 一般交易日

1. 當日已有超過 400 根。
2. API 回傳最近 400 根。
3. 不增加 payload 大小。

### C. 增量更新

1. 帶 `since=最後一根時間`。
2. 只回傳 since 後資料。
3. 不重新回傳歷史 400 根。

### D. 資料不足

1. DB 總資料少於 400 根。
2. 回傳實際可用根數。
3. background refresh 依原 period 補最新尾端。

### E. 上游失敗

1. 富邦 refresh 失敗。
2. DB 已有資料仍正常回傳。
3. `sync_error` 保留，但圖表不因上游錯誤失去歷史。

## 7. 回滾

- 回滾 database-period 選擇函式與 metadata 即可恢復原行為。
- 不需要回復資料庫，因本修改不寫入或搬移資料。
- 前端 API 參數不變，不需要同步回滾前端。
