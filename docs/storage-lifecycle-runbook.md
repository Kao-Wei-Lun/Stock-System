# QuantVision 大型資料生命週期 Runbook

## 安全原則

- 預設命令全部是 dry-run；只有明確加上 `-Execute` 才可能寫入。
- `ohlcv` 只做 audit，不提供自動刪除動作。
- `asset_*` 與 `paper_trading_*` 不在 policy allow-list，維護工具無法選取或清理。
- archive 與 cleanup 是兩個不同維護窗。archive 成功後至少等待 1 天，cleanup 才會成為候選。
- cleanup 前會重新驗證備份、archive gzip、SHA-256、列數與可讀回樣；任一不一致即拒絕。
- 不自動執行 `OPTIMIZE TABLE`，也不在啟動流程執行 partition migration。

## 2026-07-23 唯讀基準

| 資料表 | 估計列數 | Data | Index | 線上範圍／候選 |
|---|---:|---:|---:|---|
| `ohlcv` | 8,585,523 | 1.34 GB | 1.61 GB | 全部保留，不清理 |
| `taiwan_chip_snapshots` | 30,690,718 | 43.32 GB | 3.27 GB | 2024-07-23 前約 26,890,456 列 branch JSON；估計 payload 約 17.58 GB |
| `sync_log` | 1,003,430 | 61.44 MB | 53.10 MB | 2026-04-24 前約 15,850 列 |
| `news_articles` | 106,764 | 142.26 MB | 33.23 MB | 目前沒有超過 365 天的 payload |
| `fubon_market_snapshots` | 134 | 63.46 MB | 32 KB | 目前沒有超過 365 天的 payload |

本次 audit 耗時約 51.86 秒，使用獨立 MySQL client；完成後線上 DB pool wait p95 為 0.059 ms，低於 10 ms Gate。audit 應只在離峰執行。

## 資料結構

- `taiwan_chip_branch_archives`：每個交易日／來源一個 deterministic gzip JSONL，保留 SHA-256、來源列數、原始／壓縮大小、來源 ID 範圍、backup ID 與 cleanup 時間。
- `sync_log_daily_summary`：按日期、ticker、status 保存筆數、同步列數、起訖時間與最後錯誤摘要。
- `market_payload_archives`：為新聞全文與富邦每日大型 payload 預留的通用壓縮 archive。
- `storage_maintenance_runs`：保存 dry-run、進度、cursor、錯誤與恢復狀態。

## 操作順序

### 1. 唯讀 audit

```powershell
.\scripts\storage-lifecycle.ps1 -Command audit
```

### 2. 全域 dry-run

```powershell
.\scripts\storage-lifecycle.ps1 -Command dry-run
```

### 3. 籌碼 branch archive

先記錄 dry-run：

```powershell
.\scripts\storage-maintenance.ps1 `
  -Action archive-chip `
  -CutoffDate 2024-07-23 `
  -MaxGroups 1
```

確認對應日期已經有涵蓋該日的 `market-history` 或 `full` 健康備份，再明確執行：

```powershell
.\scripts\storage-maintenance.ps1 `
  -Action archive-chip `
  -CutoffDate 2024-07-23 `
  -MaxGroups 1 `
  -Execute
```

工具每個日期／來源獨立 transaction，因此中斷後可由下一個未封存 group 繼續。

### 4. 籌碼 cleanup

先執行不帶 `-Execute` 的 `cleanup-chip`。只有 archive 已跨過 grace window、原 backup 仍可驗證、archive checksum 與列數一致時，才可加 `-Execute`。cleanup 只將線上 `branch_payload_json` 設為 NULL，數值籌碼列不會刪除；歷史詳細內容會在使用者展開時從 archive 回讀。

### 5. sync log summary 與批次 cleanup

```powershell
.\scripts\storage-maintenance.ps1 `
  -Action summarize-sync `
  -CutoffDate 2026-04-24
```

明確執行 summary 後，來源 `COUNT/SUM(rows_added)` 必須與 daily summary 完全一致。至少等待一個維護窗，再對 `cleanup-sync` 先 dry-run。清理每批預設最多 5,000 列、硬上限 50,000 列，進度可續跑。

## 目前的備份覆蓋與整合證據

2026-07-23 建立的 `market-history` 演練備份只涵蓋 2026-07-22，本身不能涵蓋 2024-07-23 以前的候選資料；但 2026-07-22 的完整備份 `20260722T065807Z` 已通過 checksum 驗證，可作為舊資料 archive Gate。

整合驗證已封存 2012-05-02／`twse_t86` 一個 group：

- 來源 4,925 列。
- 原始 deterministic JSONL 3,342,548 bytes。
- gzip archive 154,807 bytes。
- archive 讀回 SHA-256 與列數一致。
- 線上 `branch_payload_json` 尚未清除。
- resume dry-run 已指向 2012-05-03 的下一個 group。
- cleanup dry-run 為零候選，因 1 天 grace window 尚未到期。

不得拿單日或不涵蓋來源日期的 backup ID 通過 Gate；完整備份與分段歷史備份都必須先實際驗證。
