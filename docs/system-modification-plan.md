# QuantVision Pro 系統修改規劃 v3.1（現況校正版）

**產出依據**：`docs/system-modification-plan.md` v3.0 + repo 現況複核（2026-04-18）  
**規劃性質**：可直接執行的剩餘實作清單，已移除「已完成」與「前提失效」項目  
**前置說明**：API Key 已改由網頁設定存入資料庫，`docs/API Key.txt` 已不存在，無需再列為待辦。

---

## 📑 目錄

1. [已完成或自待辦移除的項目](#retired)
2. [緊急修補（本次最高優先）](#urgent)
3. [測試補強（本週首要）](#testing)
4. [前端體驗優化](#frontend-ux)
5. [效能優化](#performance)
6. [安全加固](#security)
7. [執行順序總覽](#execution-order)
8. [預期改善結果](#expected-results)

---

## 1. 已完成或自待辦移除的項目 {#retired}

以下項目在 2026-04-18 複核時，已確認不應再列為待辦：

### R1.1 `docs/API Key.txt` 刪除工作已完成

- 原 v3.0 的 `M1.3` 可直接移除。
- 實際檢查結果：`docs/API Key.txt` 已不存在。

### R1.2 Settings 路由入口已完成

- 原 v3.0 的 `M3.2` 可直接移除。
- 現況：
  - `AppNavbar.vue` 已有 `settings` workspace 導航
  - `frontend/src/router/index.js` 已有 `/settings/:ticker?`
  - `frontend/src/router/appRouteState.js` 已支援 settings route state

### R1.3 富邦帳號狀態 Polling Lifecycle 已完成

- 原 v3.0 的 `M3.3` 可直接移除。
- 現況：
  - `frontend/src/composables/useFubonAccounts.js` 已有 `startStatusPolling()` / `stopStatusPolling()`
  - `frontend/src/components/settings/FubonAccountsPanel.vue` 已在 mount / unmount 生命週期中正確啟停

### R1.4 富邦市場快照 API 已完成

- 原 v3.0 的 `M4.1`、`M4.2` 可直接移除。
- 現況：
  - `backend/routers/market_data.py` 已有 `GET /api/fubon/snapshot/{market}`
  - `backend/routers/market_data.py` 已有 `GET /api/fubon/movers/{market}`
  - `backend/tests/test_fubon_market_snapshot_api.py` 已覆蓋主要行為
  - 前端 `dashboardApi.js` 與 `TaiwanHeatmap.vue` 已實際使用

### R1.5 `pytest-asyncio` 不是目前的阻塞點

- 原 v3.0 的 `M1.1`、`M2.3` 自待辦移除。
- 原因：
  - `backend/tests/test_taifex_fetcher.py` 使用的是 `@pytest.mark.anyio`，不是 `@pytest.mark.asyncio`
  - 2026-04-18 實測：`venv\Scripts\python.exe -m pytest backend/tests/test_taifex_fetcher.py -q` 為 `11 passed`
- 備註：
  - 若未來新增 `@pytest.mark.asyncio` 測試，再重新評估是否引入 `pytest-asyncio`
  - 目前不建議為了既有 TAIFEX 測試而新增此依賴

---

## 2. 緊急修補（本次最高優先） {#urgent}

> 預估工時：1 小時內可完成

### M1.1 `env_validation.py` 加入 `APP_ENCRYPT_KEY` 驗證，並同步更新 README（45 分鐘）

**問題**：

- `backend/env_validation.py` 目前尚未在啟動時驗證 `APP_ENCRYPT_KEY`
- 系統實際已依賴 `backend/crypto_utils.py` 使用此金鑰
- 若漏設，會在首次加解密時才出錯，失敗點太晚
- `.env.example` 已有 `APP_ENCRYPT_KEY`，但 `README.md` 的最低環境變數範例尚未列出

**修改檔案**：

- `backend/env_validation.py`
- `backend/tests/test_env_validation.py`
- `README.md`

**建議修改**：

在 `validate_runtime_environment()` 中加入 `APP_ENCRYPT_KEY` 必填驗證；同時補一個測試案例確認缺值時會明確失敗，並在 README 的 `.env` 範例補上：

```env
APP_ENCRYPT_KEY=your_generated_secret
```

**驗證**：

```bash
venv\Scripts\python.exe -m pytest backend/tests/test_env_validation.py -q
venv\Scripts\python.exe -c "from env_validation import validate_runtime_environment; validate_runtime_environment()"
```

> 備註：`.env.example` 已含 `APP_ENCRYPT_KEY`，此項不需額外修改。

---

## 3. 測試補強（本週首要） {#testing}

> 預估工時：4-5 小時  
> **最高優先**：富邦帳號加密與設定流程已是正式功能，需補上實際可執行的測試，而不是僅保留草稿範例

### M2.1 新建 `test_crypto_utils.py`（1.5 小時）

**測試範圍**：`backend/crypto_utils.py`

**重點**：

- 驗證 `encrypt_field()` / `decrypt_field()` round-trip
- 驗證同明文多次加密產生不同 ciphertext
- 驗證空字串行為
- 驗證缺少 `APP_ENCRYPT_KEY` 時丟出 `RuntimeError`
- 驗證錯誤金鑰時 `decrypt_field()` 回傳空字串

**實作注意**：

原 v3.0 範例需修正，因為 `crypto_utils._get_fernet()` 有 `@lru_cache(maxsize=1)`。  
測錯金鑰時，不能只改環境變數，還需要：

- `crypto_utils._get_fernet.cache_clear()`，或
- `importlib.reload(crypto_utils)`

否則會沿用舊快取，測試會變成假陽性。

**修改檔案**：

- `backend/tests/test_crypto_utils.py`

**驗證**：

```bash
venv\Scripts\python.exe -m pytest backend/tests/test_crypto_utils.py -q
```

---

### M2.2 新建 `test_settings_router.py`（2.5 小時）

**測試範圍**：

- `backend/routers/settings.py`
- `backend/repositories/fubon_accounts.py` 的路由整合行為

**重點**：

- `GET /api/settings/fubon-accounts`：空列表與一般列表
- `POST /api/settings/fubon-accounts`：Pydantic 驗證失敗情境（`api_key` 太短、`ws_mode` 非法）
- `PUT /api/settings/fubon-accounts/{id}`：部分更新 payload
- `POST /api/settings/fubon-accounts/{id}/activate`：停用帳號回傳 `400`
- `GET /api/settings/fubon-accounts/status`：確認 repo 狀態與 runtime 狀態有正確合併

**實作原則**：

- 使用既有 FastAPI test client
- 不保留 `assert mock_repo is not None` 這種 placeholder 測試
- 以 monkeypatch / mock 方式替代：
  - `FubonAccountRepository`
  - `providers.fubon_realtime_pool.reload_from_db`
  - `providers.fubon_manager.hot_switch`

**修改檔案**：

- `backend/tests/test_settings_router.py`

**驗證**：

```bash
venv\Scripts\python.exe -m pytest backend/tests/test_settings_router.py -q
```

---

## 4. 前端體驗優化 {#frontend-ux}

> 預估工時：2 小時

### M3.1 `AppNavbar.vue` 加入富邦連線狀態 Badge（1 小時）

**問題**：

- 雖然 Settings 頁面已能看到帳號狀態，但主導覽列仍看不到富邦即時連線概況
- 使用者在主工作區無法快速判斷目前是 `connected / connecting / error / disconnected`

**修改檔案**：

- `frontend/src/components/AppNavbar.vue`
- 視需要新增共用 composable，例如 `frontend/src/composables/useFubonConnectionStatus.js`

**建議實作方向**：

- 不建議直接在 `AppNavbar.vue` 內寫裸 `setInterval` + `fetch`
- 優先做法：
  - 抽成小型 composable，統一處理 polling 與 cleanup
  - 或在 `App.vue` / dashboard state 層集中輪詢，再將狀態作為 props 傳入 Navbar
- 視覺上與現有 `quote-badge`、`market-pills` 風格一致，避免新增另一套不相容樣式

**驗證**：

```bash
cd frontend
npm run test -- AppNavbar.spec.js
```

---

### M3.2 新增首次使用引導 Banner（1 小時）

**目標**：

- 新使用者第一次打開系統時，能立即知道需要先去 Settings 設定富邦帳號

**觸發條件**：

- `/api/settings/fubon-accounts` 回傳空陣列
- 使用者尚未手動 dismiss

**建議修改檔案**：

- `frontend/src/App.vue`
- 或 `frontend/src/views/AppShellRouteView.vue`
- 視需要新增一個簡單的 banner component

**建議實作方向**：

- 只在非 settings workspace 顯示
- dismiss 狀態存於 `localStorage`
- 文案避免說「系統異常」，而是明確引導「前往設定富邦 API 帳號」

**驗證**：

```bash
cd frontend
npm run test
```

---

## 5. 效能優化 {#performance}

> 預估工時：1-2 小時  
> **背景**：2026-04-18 實測 `npm run build` 時，`assets/App-*.js` 仍約 902.71 kB，Vite 已出現 chunk size warning

### M4.1 調整 `vite.config.js` chunk 策略，降低主 chunk 體積

**問題**：

- 目前 `frontend/vite.config.js` 只拆出：
  - `legacy-chart-engine`
  - `lightweight-charts`
- 但主 chunk 仍過大，代表僅補 `manualChunks` 不一定足夠

**修改檔案**：

- `frontend/vite.config.js`
- 視需要同步調整 `frontend/src/App.vue` 或相關 composable 的載入方式

**建議方向**：

1. 先擴充 `manualChunks`，拆分：
   - `useDashboard.js`
   - `useLWCChart.js`
   - `useLWCDrawings.js`
   - `useLWCIndicators.js`
2. 再評估 `useChartEngine.js` 是否能只在 legacy 模式下動態載入
3. 以 build 輸出結果決定是否需要第二輪拆分，而不是只套固定 chunk 名稱

**驗證目標**：

- `npm run build` 不再出現 Vite 大 chunk warning
- `assets/App-*.js` 盡量壓到 500 kB 以下

**驗證**：

```bash
cd frontend
npm run build
```

---

## 6. 安全加固 {#security}

> 預估工時：15 分鐘

### M5.1 `allow_headers` 限縮（15 分鐘）

**問題**：

- `backend/main.py` 目前 `allow_methods` 已是明確清單
- 但 `allow_headers` 仍為 `["*"]`

**修改檔案**：

- `backend/main.py`

**修改方向**：

```python
allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
```

**驗證**：

- 確認前端一般 `fetch` 請求正常
- 確認 Settings 頁面 CRUD、警報 CRUD、watchlist 操作不受影響

---

## 7. 執行順序總覽 {#execution-order}

```text
Day 1（最高優先）
├── M1.1  env_validation.py 加 APP_ENCRYPT_KEY 驗證 + README 同步   [45 分鐘]
└── M5.1  CORS allow_headers 限縮                                   [15 分鐘]

Day 2-3（本週首要）
├── M2.1  新建 test_crypto_utils.py                                 [1.5 小時]
└── M2.2  新建 test_settings_router.py                              [2.5 小時]

Day 4（效能）
└── M4.1  調整 vite chunk 策略，降低主 chunk 體積                   [1-2 小時]

Day 5（前端體驗）
├── M3.1  AppNavbar 富邦連線狀態 Badge                              [1 小時]
└── M3.2  首次使用引導 Banner                                       [1 小時]
```

---

## 8. 預期改善結果 {#expected-results}

完成本版規劃後，預期會得到以下可驗證結果：

- 啟動階段就能明確攔下缺少 `APP_ENCRYPT_KEY` 的部署錯誤
- 富邦帳號加解密與 Settings API 流程具備基本自動測試保護
- 主畫面可直接看到富邦即時連線狀態，新使用者也更容易找到設定入口
- 前端 build 的主 chunk 下降，減少後續持續膨脹的風險
- CORS header surface 收斂，降低不必要的開放範圍

---

## 📎 相關文件

| 文件 | 路徑 |
|------|------|
| 本次規劃文件 | `docs/system-modification-plan.md` |
| 前版規劃基礎 | 本文件 v3.0（已由 v3.1 校正） |
| Heatmap UI 強化規劃 | `docs/heatmap-ui-enhancement-plan.md` |
| 富邦 WebUI 設定規劃 | `docs/fubon-neo-webui-settings-plan.md` |
| 富邦即時行情規劃 | `docs/fubon-neo-realtime-integration-plan.md` |
| LWC 圖表整合規劃 | `docs/openstock-lwc-integration-plan.md` |

---

*修訂時間：2026-04-18 | 本版目的：把規劃文件修正為符合 repo 現況的可執行待辦清單*
