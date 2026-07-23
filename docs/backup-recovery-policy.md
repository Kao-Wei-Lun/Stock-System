# QuantVision 資料備份與復原政策

## 目的與安全邊界

本文件定義資料分級、備份範圍、RPO／RTO、保留規則與還原驗收方式。任何大型資料封存或清理前，必須先確認對應 scope 至少有一份 checksum 正確的健康備份。

還原工具只接受名稱包含 `_restore_test` 或 `_restore_drill` 的暫存 schema。正式 `quantvision` schema 不允許作為還原目標；還原演練不會輸出持股、現金、交易明細或憑證。

## 資料分級

| 等級 | 主要資料 | 復原策略 | 目標 |
|---|---|---|---|
| A：不可遺失 | 個人資產、現金與交易 ledger、匯入批次、模擬交易、使用者設定、工作區、警報、交易日誌、富邦帳號設定（不含明文密碼） | `critical` 每日壓縮備份及實際 restore drill | RPO ≤ 24 小時；本機 RTO ≤ 60 分鐘 |
| B：取得成本高或無法完整重建 | 台股籌碼、法人／期交所結構化歷史、富邦市場快照 | `market-history` 每週分段備份 | RPO ≤ 7 天 |
| C：可重新下載 | Yahoo／部分 OHLCV、股票清單、新聞、總經資料 | 記錄來源與日期範圍；OHLCV 可併入 `market-history` 分段備份 | 避免一次重做全歷史下載 |
| D：暫存 | 最新報價 cache、短期 performance metrics | TTL／重啟重建，不列入永久備份 | 不適用 |

訊號 JSON 位於報告輸出目錄，屬於 B 類驗證證據；必須由檔案層備份保留 `signals_YYYY-MM-DD.json`。它不在 MySQL dump 內。

## Scope 契約

### `critical`

- 備份所有資料表 schema，確保還原後結構完整。
- 只備份 A 類資料列；不把 OHLCV、籌碼、新聞、最新報價等大型或可重建資料列混入。
- manifest 記錄實際 included／excluded tables、每張 A 類表的精確列數、migration version、壓縮大小與 SHA-256。

### `market-history`

- 包含 `ohlcv`、籌碼、期交所結構化資料與富邦市場快照。
- 支援 `--start-date`／`--end-date`，結束日採包含式輸入。
- 每張資料表使用自己的 allow-list 日期欄位產生 `mysqldump --where`，不能由外部輸入任意 SQL 或欄名。

### `full`

- 僅作低頻完整災難復原用途。
- 目前資料量大時不應由每日排程執行。

## 操作方式

建立每日 A 類備份：

```powershell
.\scripts\backup-mysql.ps1 -Scope critical -Compression gzip
```

建立一週市場歷史分段備份：

```powershell
.\scripts\backup-mysql.ps1 `
  -Scope market-history `
  -StartDate 2026-07-13 `
  -EndDate 2026-07-19 `
  -Compression gzip
```

只驗證 dump、大小與 checksum：

```powershell
python .\backend\mysql_backup.py verify <manifest-path>
```

執行完整演練（建立暫存 schema、還原、驗證、成功後刪除暫存 schema）：

```powershell
.\scripts\restore-drill-mysql.ps1 -Manifest <manifest-path>
```

若需人工檢查演練 schema，可加上 `-KeepTarget`。使用者必須在確認後，以同一套嚴格命名規則清理暫存 schema。

## 還原 Gate

演練成功必須同時符合：

1. manifest 版本、檔案大小、SHA-256 與 gzip 串流正確。
2. scope 所需核心資料表存在。
3. `schema_migrations` 最新版本與 manifest 一致。
4. manifest 標示為 exact 的列數完全一致。
5. 歷史資料的最早／最晚業務日期一致。
6. 資產核心 ledger 的來源與還原表 checksum 一致，因此可重新建立個人資產 overview。
7. 驗證完成且未使用 `-KeepTarget` 時，暫存 schema 已安全刪除。

## Retention

- 預設依天數與最少份數保留。
- 可用 `-MaxTotalBytes` 限制備份總磁碟用量。
- 無論天數或容量設定，每個 scope 至少保留一份結構健康的備份。
- 建立新備份失敗時只刪除 `.part`，不會執行 retention，也不會動到上一份健康備份。
- manifest 格式 v1 仍可驗證與還原；新備份使用格式 v2。

## Phase 20 前置檢查

任何 archive／cleanup 必須取得：

- 最新健康 critical backup ID。
- 最近一次 critical restore drill 通過時間與耗時。
- 涉及 B 類資料時，對應日期區間的健康 `market-history` backup ID。
- dry-run 的表名、日期範圍、估計列數與預估釋放空間。

缺少上述證據時，清理程序必須拒絕執行。
