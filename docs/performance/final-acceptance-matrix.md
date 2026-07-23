# 進階效能最終驗收矩陣

日期：2026-07-23
分支：`codex/realtime-reliability-phases`

## 自動化驗收

| 項目 | 驗收門檻 | 驗收方式 | 狀態 |
|---|---:|---|---|
| 後端回歸 | 全數通過 | `python -m pytest backend/tests -q` | 通過 |
| 前端回歸 | 全數通過 | `npm test -- --run` | 通過 |
| Production build | 建置成功 | `npm run build` | 通過 |
| 終端靜態 JS gzip | ≤ 190,000 bytes | bundle manifest gate | 119,688 bytes，通過 |
| Legacy 選用後 JS gzip | ≤ 190,000 bytes | bundle manifest gate | 137,761 bytes，通過 |
| LWC 選用後 JS gzip | ≤ 190,000 bytes | bundle manifest gate | 188,300 bytes，通過 |
| 終端初始 JS 檔案 | ≤ 9 | bundle manifest gate | 4，通過 |
| 圖表引擎 | 初始不得同時載入 | bundle manifest gate | 通過 |
| 100,000 根回測隔離 | event-loop heartbeat p95 ≤ 30 ms、max ≤ 100 ms | process workload benchmark | 通過 |
| 1 分 K 查詢 | 使用索引，不得全表掃描，且存在 `ticker, interval, date` 複合索引 | `EXPLAIN` gate | range access，通過 |
| 即時長時間測試 | 60 分鐘、兩個期貨與一檔股票 | soak gate | 工具完成；須在開盤且富邦連線時執行 |

## 需要正式環境執行的驗收

下列項目依賴同一版後端、MySQL 實際資料、富邦登入與交易時段，不能由舊的開發服務結果代替：

1. `*TMFF`、`*TXFF` 與 `2330.TW` 連續 60 分鐘採樣。
2. WebSocket 人工斷線後自動恢復，並確認五檔、報價與 K 線持續更新。
3. 60 分鐘期間執行一次 100,000 根回測，確認即時廣播 p95、資料庫等待與前端 Long Task 未超標。
4. 部署到不同 MySQL 執行個體時，再使用 `scripts/check-db-performance-plan.py` 複驗 OHLCV 查詢索引。
5. 匯出 `window.__QV_PERFORMANCE__`，確認 realtime paint p95 與 Long Task 數量。

建議指令：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-final-performance-gate.ps1 -IncludeLiveChecks
powershell -ExecutionPolicy Bypass -File scripts/soak-realtime.ps1 -DurationMinutes 60
```

## 回滾界線

- Phase 15 的前端延遲載入可單獨回滾，不影響 API 或資料庫 schema。
- 效能 gate 與 soak 腳本均為唯讀驗收工具，不會下單，也不會修改個人資產。
- 若正式環境無法達標，先保留遙測與測試工具，再依 Phase 14 → Phase 7 的反向順序逐項回滾；不可刪除資料庫 migration 歷史。
- 壓力測試產物只允許保存計時、筆數、佇列與連線統計，不保存帳密、持股、交易明細、SQL 或完整錯誤內容。
