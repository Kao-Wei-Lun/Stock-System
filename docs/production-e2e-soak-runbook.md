# Production SPA E2E 與即時行情 Soak 操作手冊

## 目的

Phase 23 將瀏覽器驗收拆成兩層：

1. deterministic production E2E：使用 production build、合成 API 與合成 WebSocket，不連線 MySQL、富邦帳號或個人資產。
2. live soak：連線本機正式後端與真實行情，只讀取行情與效能指標，不會送出真實委託。

## Deterministic E2E

在專案根目錄執行：

```powershell
Set-Location frontend
npm run test:e2e
```

測試固定使用本機 Chrome，可用 `QV_E2E_BROWSER_CHANNEL` 改成 Playwright 支援的其他已安裝 channel。
fixture server 只回傳 `synthetic_e2e` 資料，涵蓋：

- production SPA 與深層 route reload。
- 所有主導航。
- `*TMFF`、`*TXFF` 動態近月解析。
- IndexedDB cache-first → DB confirm → WebSocket 即時更新。
- Y 軸 auto／manual。
- WebSocket 中斷與自動重連。
- 模擬交易、合成資產與 dynamic chunk 復原。
- `/api` 與遺失靜態檔不被 SPA fallback 攔截。
- starting、ready_degraded、ready 與 unavailable readiness 狀態。

## 60 分鐘 Live Soak

開盤期間、正式後端已 ready 後執行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/soak-realtime.ps1 `
  -DurationMinutes 60 `
  -FuturesSymbols "*TMFF","*TXFF" `
  -StockSymbol "2330.TW" `
  -RequireMarketActivity
```

輸出會寫入 `docs/performance/soak-YYYYMMDD-HHMMSS.json`，內容不保存憑證、帳號或完整行情 payload。

硬性 Gate：

- 每次採樣均成功。
- dropped quote delta = 0。
- ingress → broadcast p95 ≤ 75 ms。
- DB pool wait p95 ≤ 10 ms。
- persistence queue age max ≤ 750 ms。
- 使用 `-RequireMarketActivity` 時 ingress 與 broadcast delta 均需大於 0。

在 soak 執行期間，另開一個終端執行 100,000 根隔離回測：

```powershell
venv\Scripts\python.exe scripts/benchmark-backtest-isolation.py `
  --bars 100000 `
  --executor-kind process `
  --max-heartbeat-p95-ms 30 `
  --max-heartbeat-max-ms 100
```

若非開盤時段，不可移除 `-RequireMarketActivity` 後把結果當成正式 live 驗收；只能標記為腳本 smoke test。

所有模擬交易、E2E 資產與回測結果僅供研究、觀察與驗證，不保證獲利，也不會送出真實委託。
