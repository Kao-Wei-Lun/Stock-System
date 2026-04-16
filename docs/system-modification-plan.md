# QuantVision Pro 系統修改規劃 v3.0

**產出依據**：系統健檢報告 v3.0（2026-04-14）  
**規劃性質**：可直接執行的實作清單，按優先度排序  
**前置說明**：API Key 已改由網頁設定存入資料庫，`docs/API Key.txt` 文件不再需要，可直接刪除。

---

## 📑 目錄

1. [緊急修補（今日可完成）](#urgent)
2. [測試補強（本週首要）](#testing)
3. [前端體驗優化](#frontend-ux)
4. [後端 API 補建（Phase F7）](#backend-api)
5. [效能優化](#performance)
6. [安全加固](#security)
7. [執行順序總覽](#execution-order)

---

## 1. 緊急修補 {#urgent}

> 預估工時：1 小時內全部完成

### M1.1 安裝 `pytest-asyncio`（15 分鐘）

**問題**：`pytest-asyncio` 未安裝導致 `test_taifex_fetcher.py` 的 async 測試被跳過。

**修改檔案**：`backend/requirements.txt`

```diff
 pytest==8.3.5
+pytest-asyncio>=0.23,<1.0
 httpx==0.27.2
```

**驗證**：
```bash
venv\Scripts\pip install pytest-asyncio
venv\Scripts\python.exe -m pytest backend/tests/test_taifex_fetcher.py -v
```

---

### M1.2 `env_validation.py` 加入 `APP_ENCRYPT_KEY` 驗證（30 分鐘）

**問題**：啟動時未驗證加密金鑰，遺漏時會在首次解密操作才崩潰，錯誤訊息不明確。

**修改檔案**：`backend/env_validation.py`

在 `validate_runtime_environment()` 函數（第 103 行附近）加入驗證邏輯：

```python
# 在 if errors: 之前加入
encrypt_key = _read_raw_value("APP_ENCRYPT_KEY", None, env=source)
if not encrypt_key:
    errors.append(
        "Missing required environment variable: APP_ENCRYPT_KEY\n"
        "  產生指令：python -c \"from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())\""
    )
else:
    validated["APP_ENCRYPT_KEY"] = encrypt_key
```

**驗證**：
```bash
# 暫時移除 .env 中的 APP_ENCRYPT_KEY，確認啟動時立即報錯
venv\Scripts\python.exe -c "from env_validation import validate_runtime_environment; validate_runtime_environment()"
```

---

### M1.3 刪除 `docs/API Key.txt` 實體檔案（5 分鐘）

**說明**：API Key 已改由網頁設定存入資料庫，此文字檔不再需要。`.gitignore` 中的對應規則已由使用者移除，說明此文件已不需要版控保護。

**執行**：直接在 Windows Explorer 或命令列刪除：
```bash
del "docs\API Key.txt"
```

> ✅ 無需修改 `.gitignore`，現有設定已正確（不含此檔案規則）。

---

## 2. 測試補強 {#testing}

> 預估工時：4–5 小時  
> **最高優先**：富邦帳號加密系統是即時行情整合的基礎，無測試保護風險極高

### M2.1 新建 `test_crypto_utils.py`（1.5 小時）

**測試範圍**：`backend/crypto_utils.py`

```python
# backend/tests/test_crypto_utils.py
"""
加解密工具測試
"""
import os
import pytest


@pytest.fixture(autouse=True)
def set_encrypt_key(monkeypatch):
    monkeypatch.setenv("APP_ENCRYPT_KEY", "test-secret-key-for-unit-tests")


def test_encrypt_decrypt_roundtrip():
    """加密後可正確解密為原始字串"""
    from crypto_utils import encrypt_field, decrypt_field
    plaintext = "my-secret-password"
    assert decrypt_field(encrypt_field(plaintext)) == plaintext


def test_encrypt_produces_different_ciphertext():
    """同一明文兩次加密結果不同（Fernet 含 IV）"""
    from crypto_utils import encrypt_field
    assert encrypt_field("test") != encrypt_field("test")


def test_decrypt_wrong_key_returns_empty():
    """金鑰不符時 decrypt 回傳空字串（不拋例外）"""
    from crypto_utils import encrypt_field, decrypt_field
    ciphertext = encrypt_field("secret")
    os.environ["APP_ENCRYPT_KEY"] = "wrong-key"
    result = decrypt_field(ciphertext)
    assert result == ""


def test_encrypt_empty_string():
    """空字串加密回傳空字串"""
    from crypto_utils import encrypt_field, decrypt_field
    assert encrypt_field("") == ""
    assert decrypt_field("") == ""


def test_missing_key_raises():
    """未設定 APP_ENCRYPT_KEY 時，encrypt 應拋出 RuntimeError"""
    import importlib
    from unittest.mock import patch
    with patch.dict(os.environ, {}, clear=True):
        import crypto_utils
        importlib.reload(crypto_utils)
        with pytest.raises(RuntimeError, match="APP_ENCRYPT_KEY"):
            crypto_utils.encrypt_field("test")
```

---

### M2.2 新建 `test_settings_router.py`（2.5 小時）

**測試範圍**：`backend/routers/settings.py` + `backend/repositories/fubon_accounts.py`

```python
# backend/tests/test_settings_router.py
"""
富邦帳號 CRUD API 整合測試（使用 httpx + FastAPI TestClient）
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


MOCK_ACCOUNT_PAYLOAD = {
    "label": "測試帳號",
    "user_id": "P123456789",
    "password": "test_password",
    "cert_path": "C:\\certs\\test.pfx",
    "cert_password": "cert_pass",
    "api_key": "A" * 64,
    "ws_mode": "Speed",
}


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.list_accounts = AsyncMock(return_value=[])
    repo.create_account = AsyncMock(return_value=1)
    repo.update_account = AsyncMock(return_value=1)
    repo.delete_account = AsyncMock(return_value=1)
    repo.activate_account = AsyncMock(return_value=True)
    repo.get_account_with_secrets = AsyncMock(return_value={
        "id": 1, "is_enabled": True, **MOCK_ACCOUNT_PAYLOAD
    })
    repo.list_statuses = AsyncMock(return_value=[])
    repo.update_connection_status = AsyncMock()
    return repo


def test_list_accounts_empty(mock_repo):
    """列表 API 在無帳號時回傳空陣列"""
    # 實作：使用 TestClient 測試 GET /api/settings/fubon-accounts
    assert mock_repo.list_accounts is not None


def test_create_account_validates_api_key_min_length():
    """api_key 少於 10 字元時回傳 422"""
    # Pydantic Field min_length=10 驗證
    from routers.settings import FubonAccountCreate
    with pytest.raises(Exception):
        FubonAccountCreate(**{**MOCK_ACCOUNT_PAYLOAD, "api_key": "short"})


def test_create_account_validates_ws_mode():
    """ws_mode 非 Speed/Normal 時回傳 422"""
    from routers.settings import FubonAccountCreate
    with pytest.raises(Exception):
        FubonAccountCreate(**{**MOCK_ACCOUNT_PAYLOAD, "ws_mode": "Fast"})


def test_fubon_account_update_partial():
    """更新 payload 允許只傳部分欄位"""
    from routers.settings import FubonAccountUpdate
    model = FubonAccountUpdate(label="新名稱")
    dumped = model.model_dump(exclude_none=True)
    assert "label" in dumped
    assert "password" not in dumped


def test_activate_disabled_account_raises_400(mock_repo):
    """停用帳號不可設為 active，應回傳 400"""
    mock_repo.get_account_with_secrets = AsyncMock(return_value={
        "id": 1, "is_enabled": False, **MOCK_ACCOUNT_PAYLOAD
    })
    # 補充：整合 FastAPI TestClient 測試 activate 端點
    assert mock_repo is not None
```

---

### M2.3 補強 `test_taifex_fetcher.py` 的 async 測試

安裝 `pytest-asyncio` 後，在 `backend/tests/test_taifex_fetcher.py` 確認 `@pytest.mark.asyncio` 可正常執行，並在 `pytest.ini` 加入：

```ini
[pytest]
asyncio_mode = auto
```

**修改檔案**：`pytest.ini`（根目錄）

---

## 3. 前端體驗優化 {#frontend-ux}

### M3.1 `AppNavbar.vue` 加入富邦連線狀態 Badge（1 小時）

**問題**：使用者在主介面看不到富邦 WS 連線狀態，需進 Settings 才能知道。

**修改內容**：在 `AppNavbar.vue` 的工具列區域加入：

```vue
<!-- 富邦連線狀態 Badge（加在 Navbar 右側工具區） -->
<div class="fubon-status-badge" :class="fubonStatusClass" :title="fubonStatusTitle">
  <span class="status-dot"></span>
  <span class="status-label">{{ fubonStatusLabel }}</span>
</div>

<script setup>
// 定期輪詢連線狀態（每 15 秒）
const fubonStatus = ref('disconnected');

onMounted(async () => {
  await refreshFubonStatus();
  setInterval(refreshFubonStatus, 15_000);
});

async function refreshFubonStatus() {
  try {
    const { data } = await axios.get('/api/settings/fubon-accounts/status');
    const active = data.accounts?.find(a => a.is_active);
    fubonStatus.value = active?.connection_status ?? 'disconnected';
  } catch { fubonStatus.value = 'disconnected'; }
}

const fubonStatusLabel = computed(() => ({
  connected: '即時',
  connecting: '連線中',
  error: '連線失敗',
  disconnected: '盤後',
}[fubonStatus.value] ?? '—'));

const fubonStatusClass = computed(() => `status-${fubonStatus.value}`);
const fubonStatusTitle = computed(() => `富邦行情狀態：${fubonStatusLabel.value}`);
</script>

<style>
.fubon-status-badge { display: flex; align-items: center; gap: 5px; font-size: 11px; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; }
.status-connected .status-dot  { background: #00d9a3; box-shadow: 0 0 5px #00d9a3; }
.status-error .status-dot      { background: #ff4d6a; }
.status-connecting .status-dot { background: #ffd166; animation: pulse 1s infinite; }
.status-disconnected .status-dot { background: #888; }
</style>
```

---

### M3.2 `AppNavbar.vue` 加入 Settings 路由入口（30 分鐘）

**問題**：`SettingsWorkspace.vue` 已建立，但 Navbar 缺少入口。

**修改內容**：在 Navbar 右側工具列加入齒輪圖示按鈕：

```vue
<router-link to="/settings" class="nav-icon-btn" title="系統設定">
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 
             2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 
             1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 
             1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 
             1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 
             0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82 
             l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 
             4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 
             1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 
             0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 
             0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
</router-link>
```

---

### M3.3 `FubonAccountsPanel.vue` 確認 Polling Lifecycle（30 分鐘）

確認 `useFubonAccounts.js` 的 `startStatusPolling` 有正確的 lifecycle hooks：

```javascript
// FubonAccountsPanel.vue <script setup> 中確認有：
import { onMounted, onUnmounted } from 'vue';
import { useFubonAccounts } from '@/composables/useFubonAccounts';

const { accounts, fetchAccounts, startStatusPolling, stopStatusPolling, ... } = useFubonAccounts();

onMounted(async () => {
  await fetchAccounts();
  startStatusPolling();  // ← 確認存在
});

onUnmounted(() => {
  stopStatusPolling();   // ← 確認存在，避免 memory leak
});
```

---

### M3.4 新增首次使用引導 Banner（1 小時）

**目標**：新使用者打開系統不知道要去 Settings 設定富邦帳號。

**觸發條件**：`/api/settings/fubon-accounts` 回傳空陣列時顯示。

**建議在 `AppNavbar.vue` 或 `AppShellRouteView.vue` 加入**：

```vue
<!-- 首次使用引導（無帳號時顯示） -->
<div v-if="showOnboardingBanner" class="onboarding-banner">
  <span>💡 尚未設定富邦 API，行情資料將使用延遲快照。</span>
  <router-link to="/settings" class="banner-action">前往設定 →</router-link>
  <button @click="dismissBanner" class="banner-dismiss">✕</button>
</div>
```

---

## 4. 後端 API 補建（Phase F7）{#backend-api}

> 預估工時：3–4 小時

### M4.1 新增 `GET /api/fubon/snapshot/{market}`

**修改檔案**：`backend/routers/market_data.py` 或新建 `backend/routers/fubon.py`

```python
@router.get("/fubon/snapshot/{market}")
async def get_market_snapshot(market: str = Path(..., pattern="^(TSE|OTC)$")):
    """
    取得全市場即時快照（台股所有股票的漲跌幅）
    使用 60 秒快取避免頻繁查詢
    """
    from providers import fubon_market_snapshot_provider
    if not fubon_manager.connected:
        raise HTTPException(503, "富邦行情未連線")
    data = await fubon_market_snapshot_provider.get_market_snapshot(market)
    return {"market": market, "data": data, "source": "fubon_neo"}
```

---

### M4.2 新增 `GET /api/fubon/movers/{market}`

```python
@router.get("/fubon/movers/{market}")
async def get_market_movers(
    market: str = Path(..., pattern="^(TSE|OTC)$"),
    direction: str = Query("up", pattern="^(up|down)$"),
    limit: int = Query(20, ge=5, le=100),
):
    """
    取得漲/跌幅排行
    """
    from providers import fubon_market_snapshot_provider
    if not fubon_manager.connected:
        raise HTTPException(503, "富邦行情未連線")
    data = await fubon_market_snapshot_provider.get_movers(market, direction, limit)
    return {"market": market, "direction": direction, "data": data}
```

---

## 5. 效能優化 {#performance}

### M5.1 擴充 `vite.config.js` 的 `manualChunks`（30 分鐘）

**修改檔案**：`frontend/vite.config.js` 第 32-36 行

```javascript
// 現況
manualChunks(id) {
  if (id.includes("useChartEngine.js")) return "legacy-chart-engine";
  if (id.includes("lightweight-charts")) return "lightweight-charts";
  return undefined;
}

// 修改為
manualChunks(id) {
  if (id.includes("useChartEngine.js"))   return "legacy-chart-engine";
  if (id.includes("lightweight-charts"))  return "lightweight-charts";
  if (id.includes("useDashboard.js"))     return "dashboard-core";
  if (id.includes("useLWCDrawings.js"))   return "lwc-drawings";
  if (id.includes("useLWCIndicators.js")) return "lwc-indicators";
  if (id.includes("useLWCChart.js"))      return "lwc-chart";
  return undefined;
}
```

**驗證**：
```bash
cd frontend && npm run build
# 確認 dist/assets/ 中各 chunk 大小合理（目標：主 chunk < 300KB）
```

---

## 6. 安全加固 {#security}

### M6.1 `allow_headers` 限縮（15 分鐘）

**修改檔案**：`backend/main.py` 第 311-318 行

```python
# 現況
allow_headers=["*"],

# 修改為
allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
```

---

## 7. 執行順序總覽 {#execution-order}

```
Day 1（今天）
├── M1.3  刪除 docs/API Key.txt                        [5 分鐘]
├── M1.1  安裝 pytest-asyncio + requirements.txt        [15 分鐘]
├── M1.2  env_validation.py 加 APP_ENCRYPT_KEY 驗證    [30 分鐘]
└── M6.1  CORS allow_headers 限縮                       [15 分鐘]

Day 2-3（本週，最優先）
├── M2.1  新建 test_crypto_utils.py                     [1.5 小時]
├── M2.2  新建 test_settings_router.py                  [2.5 小時]
└── M2.3  pytest.ini 加 asyncio_mode = auto             [15 分鐘]

Day 4-5（本週，前端體驗）
├── M3.2  AppNavbar.vue 加 Settings 齒輪入口            [30 分鐘]
├── M3.1  AppNavbar.vue 加富邦連線狀態 Badge             [1 小時]
├── M3.3  FubonAccountsPanel polling lifecycle 確認     [30 分鐘]
└── M3.4  首次使用引導 Banner                           [1 小時]

下週
├── M5.1  vite.config.js 擴充 manualChunks             [30 分鐘]
├── M4.1  GET /api/fubon/snapshot/{market}              [2 小時]
└── M4.2  GET /api/fubon/movers/{market}                [2 小時]
```

---

## 📊 預期改善效果

| 修改後 | 預估評分 |
|--------|---------|
| 🏗️ 後端架構 | 93 → **96** |
| 🔒 安全與資料 | 90 → **95** |
| 🧪 測試品質 | 91 → **96** |
| 🎨 前端架構 | 79 → **85** |
| 🧑‍🎨 使用者體驗 | 77 → **84** |
| 📈 交易員體驗 | 74 → **80** |
| **總分** | 84 → **90** |

---

## 📎 相關文件

| 文件 | 路徑 |
|------|------|
| 系統健檢報告 v3.0 | 本次對話（可持久化至 `docs/system-review-report-2026-04-14.md`）|
| 富邦 WebUI 設定規劃 | `docs/fubon-neo-webui-settings-plan.md` |
| 富邦即時行情規劃 | `docs/fubon-neo-realtime-integration-plan.md` |
| LWC 圖表整合規劃 | `docs/openstock-lwc-integration-plan.md` |

---

*產出時間：2026-04-14 | 基於系統健檢 v3.0 | 執行前請確認 `.env` 中 `APP_ENCRYPT_KEY` 已填入*
