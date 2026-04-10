# 富邦 Neo API 網頁設定介面規劃

**產出時間**：2026-04-10  
**前置依賴**：`docs/fubon-neo-realtime-integration-plan.md`  
**規劃性質**：本份文件為原規劃的「憑證管理方式升級」，以網頁 UI 取代 `.env` 設定

---

## 📑 目錄

1. [設計目標](#design-goals)
2. [資料庫 Schema 設計](#db-schema)
3. [加密方案](#encryption)
4. [後端 API 規格](#backend-api)
5. [前端 UI 規格](#frontend-ui)
6. [FubonSDKManager 多帳號設計](#sdk-manager)
7. [分階段實作清單](#implementation)
8. [環境變數調整](#env-changes)

---

## 1. 設計目標 {#design-goals}

| 需求 | 方案 |
|------|------|
| 網頁設定 API 憑證 | 新增 `/settings` 頁面，含富邦帳號管理面板 |
| 設定值存資料庫 | 新增 `fubon_api_accounts` 資料表 |
| 多組 API Key | 每筆記錄代表一組帳號，`is_active` 標記當前使用的帳號 |
| 憑證安全 | 密碼、API Key 字段以 AES-256（Fernet）加密後存儲 |
| 即時切換帳號 | 支援熱切換（不需重啟 Server）|
| 連線狀態可見 | 每組帳號顯示即時連線狀態（`connected/disconnected/error`）|

---

## 2. 資料庫 Schema 設計 {#db-schema}

### 2.1 新增資料表：`fubon_api_accounts`

新增至 `backend/models/schema.py` 的 `CREATE_TABLE_STATEMENTS`：

```python
"fubon_api_accounts": """
    CREATE TABLE `fubon_api_accounts` (
        `id`                  BIGINT NOT NULL AUTO_INCREMENT,
        `label`               VARCHAR(100) NOT NULL COMMENT '自訂名稱，如「主帳號」',
        `user_id`             VARCHAR(50)  NOT NULL COMMENT '身分證字號（明文，非敏感）',
        `password_enc`        TEXT         NOT NULL COMMENT 'AES-256 加密後的密碼',
        `cert_path`           VARCHAR(500) NULL      COMMENT '憑證檔絕對路徑（在伺服器本機）',
        `cert_password_enc`   TEXT         NULL      COMMENT 'AES-256 加密後的憑證密碼',
        `api_key_enc`         TEXT         NOT NULL  COMMENT 'AES-256 加密後的 API Key',
        `ws_mode`             VARCHAR(10)  NOT NULL DEFAULT 'Speed' COMMENT 'Speed|Normal',
        `is_active`           TINYINT      NOT NULL DEFAULT 0 COMMENT '1=當前使用此帳號',
        `is_enabled`          TINYINT      NOT NULL DEFAULT 1 COMMENT '0=停用',
        `connection_status`   VARCHAR(20)  NOT NULL DEFAULT 'disconnected'
                              COMMENT 'connected|disconnected|error|connecting',
        `connection_error`    TEXT         NULL      COMMENT '最後一次連線錯誤訊息',
        `last_connected_at`   DATETIME     NULL      COMMENT '最後成功連線時間',
        `created_at`          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at`          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        KEY `idx_fubon_api_accounts_active` (`is_active`, `is_enabled`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    COMMENT='富邦 Neo API 帳號設定（多組支援）'
""",
```

### 2.2 Schema 自動遷移

`build_schema_plan()` 已支援自動建表，新增上述 `CREATE TABLE` 後，系統啟動時會自動建立此資料表，**不需要手動執行 SQL**。

---

## 3. 加密方案 {#encryption}

### 3.1 使用 Fernet 對稱加密

`cryptography` 套件已在 `requirements.txt` 中，直接使用 `Fernet`（AES-128-CBC + HMAC-SHA256）：

```python
# backend/crypto_utils.py  ← 新增
"""
應用層字段加密工具
使用 Fernet 對稱加密，金鑰從環境變數 APP_ENCRYPT_KEY 讀取
"""
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _get_fernet() -> Fernet:
    """從環境變數取得或自動產生加密金鑰"""
    raw_key = os.environ.get("APP_ENCRYPT_KEY", "")
    if not raw_key:
        raise RuntimeError(
            "APP_ENCRYPT_KEY 未設定。請在 .env 加入一個隨機字串作為加密金鑰。\n"
            "產生指令：python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    # 以 PBKDF2 從任意長度的字串衍生出 32 byte key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"quantvision-fubon-salt-v1",  # 固定 salt（非 session salt，可寫死）
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(raw_key.encode()))
    return Fernet(key)


def encrypt_field(plaintext: str) -> str:
    """加密字串，回傳 base64 密文"""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: str) -> str:
    """解密字串，回傳明文。解密失敗時回傳空字串以避免崩潰"""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        return ""
```

### 3.2 金鑰管理（`.env`）

```env
# 應用層加密金鑰（用於加密 DB 中的密碼/API Key 字段）
# 產生指令：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
APP_ENCRYPT_KEY=（請自行產生並填入，勿洩漏）
```

> [!IMPORTANT]
> `APP_ENCRYPT_KEY` 是保管所有已存憑證的**主金鑰**。
> - 此 Key 遺失 = 資料庫內所有加密欄位無法解密（需重新輸入）
> - 此 Key 洩漏 = 所有帳號憑證資訊外洩
> - 請定期備份此 Key，並確保已在 `.gitignore`

### 3.3 加密字段對照

| DB 欄位 | 加密? | 說明 |
|---------|------|------|
| `user_id` | ❌ 明文 | 身分證字號（本地系統無需額外加密）|
| `password_enc` | ✅ Fernet | 電子平台密碼 |
| `cert_path` | ❌ 明文 | 路徑本身不敏感 |
| `cert_password_enc` | ✅ Fernet | 憑證密碼 |
| `api_key_enc` | ✅ Fernet | API Key |

---

## 4. 後端 API 規格 {#backend-api}

### 4.1 新增路由模組：`backend/routers/settings.py`

```python
# 掛載至 main.py：
# app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
```

#### API 端點清單

| Method | 路徑 | 功能 |
|--------|------|------|
| `GET` | `/api/settings/fubon-accounts` | 列出所有帳號（密碼欄位遮蔽）|
| `POST` | `/api/settings/fubon-accounts` | 新增帳號 |
| `PUT` | `/api/settings/fubon-accounts/{id}` | 修改帳號 |
| `DELETE` | `/api/settings/fubon-accounts/{id}` | 刪除帳號 |
| `POST` | `/api/settings/fubon-accounts/{id}/activate` | 切換為使用中帳號 |
| `POST` | `/api/settings/fubon-accounts/{id}/test` | 測試連線 |
| `GET` | `/api/settings/fubon-accounts/status` | 取得所有帳號連線狀態 |

#### 詳細規格

**`GET /api/settings/fubon-accounts`** — 列表

回應 Response（敏感欄位以 `"****"` 遮蔽）：
```json
{
  "accounts": [
    {
      "id": 1,
      "label": "主帳號",
      "user_id": "P124185549",
      "password": "****",
      "cert_path": "C:\\CAFubon\\P124185549\\P124185549.pfx",
      "cert_password": "****",
      "api_key": "****",
      "ws_mode": "Speed",
      "is_active": true,
      "is_enabled": true,
      "connection_status": "connected",
      "connection_error": null,
      "last_connected_at": "2026-04-10T13:00:00+08:00",
      "created_at": "2026-04-10T10:00:00+08:00"
    }
  ]
}
```

**`POST /api/settings/fubon-accounts`** — 新增

Request Body：
```json
{
  "label": "備用帳號",
  "user_id": "A123456789",
  "password": "明文密碼（後端加密後存庫）",
  "cert_path": "C:\\CAFubon\\A123456789\\A123456789.pfx",
  "cert_password": "明文憑證密碼",
  "api_key": "明文 API Key",
  "ws_mode": "Speed"
}
```

**`POST /api/settings/fubon-accounts/{id}/activate`** — 切換帳號

- 將指定 `id` 設為 `is_active=1`，其餘所有帳號設為 `is_active=0`
- 觸發後端 `fubon_manager.hot_switch(account_id)` 熱切換

**`POST /api/settings/fubon-accounts/{id}/test`** — 測試連線

- 用指定帳號的解密憑證嘗試登入富邦 SDK
- 回傳 `{ "success": true/false, "message": "..." }`
- 不影響當前連線中的 active 帳號

### 4.2 `backend/repositories/fubon_accounts.py` — 資料存取層

```python
"""
富邦 API 帳號的資料庫 CRUD 操作
"""
from typing import List, Optional, Dict, Any
from crypto_utils import encrypt_field, decrypt_field


class FubonAccountRepository:

    def __init__(self, db):
        self._db = db

    async def list_accounts(self) -> List[Dict]:
        """列出所有帳號（不解密，回傳加密內容）"""
        return await self._db._fetchall(
            "SELECT id, label, user_id, cert_path, ws_mode, is_active, "
            "is_enabled, connection_status, connection_error, last_connected_at, "
            "created_at, updated_at FROM fubon_api_accounts ORDER BY id"
        )

    async def get_account_with_secrets(self, account_id: int) -> Optional[Dict]:
        """取得指定帳號（含解密後的敏感欄位，僅內部使用）"""
        row = await self._db._fetchone(
            "SELECT * FROM fubon_api_accounts WHERE id=%s", (account_id,)
        )
        if not row:
            return None
        return {
            **row,
            "password": decrypt_field(row["password_enc"]),
            "cert_password": decrypt_field(row["cert_password_enc"] or ""),
            "api_key": decrypt_field(row["api_key_enc"]),
        }

    async def get_active_account(self) -> Optional[Dict]:
        """取得目前啟用中的帳號（含解密）"""
        row = await self._db._fetchone(
            "SELECT * FROM fubon_api_accounts WHERE is_active=1 AND is_enabled=1 LIMIT 1"
        )
        if not row:
            return None
        return {
            **row,
            "password": decrypt_field(row["password_enc"]),
            "cert_password": decrypt_field(row["cert_password_enc"] or ""),
            "api_key": decrypt_field(row["api_key_enc"]),
        }

    async def create_account(self, data: Dict) -> int:
        """新增帳號，密碼欄位加密後存入"""
        return await self._db._execute_insert(
            """INSERT INTO fubon_api_accounts
               (label, user_id, password_enc, cert_path, cert_password_enc,
                api_key_enc, ws_mode, is_active, is_enabled)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                data["label"],
                data["user_id"],
                encrypt_field(data["password"]),
                data.get("cert_path", ""),
                encrypt_field(data.get("cert_password", "")),
                encrypt_field(data["api_key"]),
                data.get("ws_mode", "Speed"),
                0,  # 新增時預設不啟用，需手動 activate
                1,
            ),
        )

    async def update_account(self, account_id: int, data: Dict) -> int:
        """更新帳號，只更新有值的欄位"""
        # 動態建構 SET 子句
        updates = []
        params = []
        for key in ["label", "cert_path", "ws_mode"]:
            if key in data:
                updates.append(f"`{key}`=%s")
                params.append(data[key])
        # 加密欄位
        if "password" in data and data["password"]:
            updates.append("`password_enc`=%s")
            params.append(encrypt_field(data["password"]))
        if "cert_password" in data and data["cert_password"]:
            updates.append("`cert_password_enc`=%s")
            params.append(encrypt_field(data["cert_password"]))
        if "api_key" in data and data["api_key"]:
            updates.append("`api_key_enc`=%s")
            params.append(encrypt_field(data["api_key"]))

        if not updates:
            return 0
        params.append(account_id)
        sql = f"UPDATE fubon_api_accounts SET {', '.join(updates)} WHERE id=%s"
        return await self._db._execute(sql, tuple(params))

    async def delete_account(self, account_id: int) -> int:
        return await self._db._execute(
            "DELETE FROM fubon_api_accounts WHERE id=%s", (account_id,)
        )

    async def activate_account(self, account_id: int) -> None:
        """設定指定帳號為 active，其餘全部 deactivate"""
        await self._db._execute(
            "UPDATE fubon_api_accounts SET is_active=0"
        )
        await self._db._execute(
            "UPDATE fubon_api_accounts SET is_active=1 WHERE id=%s", (account_id,)
        )

    async def update_connection_status(
        self, account_id: int, status: str, error: str = None
    ) -> None:
        if status == "connected":
            await self._db._execute(
                "UPDATE fubon_api_accounts SET connection_status=%s, connection_error=NULL, "
                "last_connected_at=NOW() WHERE id=%s",
                (status, account_id),
            )
        else:
            await self._db._execute(
                "UPDATE fubon_api_accounts SET connection_status=%s, connection_error=%s WHERE id=%s",
                (status, error, account_id),
            )
```

### 4.3 `backend/routers/settings.py` — 路由實作

```python
"""
系統設定 API 路由（富邦 API 帳號管理）
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from repositories.fubon_accounts import FubonAccountRepository
from database import db

router = APIRouter()


class FubonAccountCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    user_id: str = Field(..., min_length=5)
    password: str = Field(..., min_length=1)
    cert_path: Optional[str] = None
    cert_password: Optional[str] = None
    api_key: str = Field(..., min_length=10)
    ws_mode: str = Field("Speed", pattern="^(Speed|Normal)$")


class FubonAccountUpdate(BaseModel):
    label: Optional[str] = None
    password: Optional[str] = None
    cert_path: Optional[str] = None
    cert_password: Optional[str] = None
    api_key: Optional[str] = None
    ws_mode: Optional[str] = None


def _mask(account: dict) -> dict:
    """遮蔽 API 回應中的敏感欄位"""
    return {**account, "password": "****", "cert_password": "****", "api_key": "****"}


@router.get("/fubon-accounts")
async def list_fubon_accounts():
    repo = FubonAccountRepository(db)
    accounts = await repo.list_accounts()
    return {"accounts": accounts}


@router.post("/fubon-accounts", status_code=201)
async def create_fubon_account(body: FubonAccountCreate):
    repo = FubonAccountRepository(db)
    new_id = await repo.create_account(body.model_dump())
    return {"id": new_id, "message": "帳號已建立"}


@router.put("/fubon-accounts/{account_id}")
async def update_fubon_account(account_id: int, body: FubonAccountUpdate):
    repo = FubonAccountRepository(db)
    count = await repo.update_account(account_id, body.model_dump(exclude_none=True))
    if count == 0:
        raise HTTPException(404, "帳號不存在或無變更")
    return {"message": "帳號已更新"}


@router.delete("/fubon-accounts/{account_id}")
async def delete_fubon_account(account_id: int):
    repo = FubonAccountRepository(db)
    count = await repo.delete_account(account_id)
    if count == 0:
        raise HTTPException(404, "帳號不存在")
    return {"message": "帳號已刪除"}


@router.post("/fubon-accounts/{account_id}/activate")
async def activate_fubon_account(account_id: int):
    from providers import fubon_manager  # 避免循環 import
    repo = FubonAccountRepository(db)
    await repo.activate_account(account_id)
    account = await repo.get_account_with_secrets(account_id)
    if not account:
        raise HTTPException(404, "帳號不存在")
    # 熱切換 SDK 連線
    success = await fubon_manager.hot_switch(account)
    return {"message": "已切換", "connected": success}


@router.post("/fubon-accounts/{account_id}/test")
async def test_fubon_account(account_id: int):
    repo = FubonAccountRepository(db)
    account = await repo.get_account_with_secrets(account_id)
    if not account:
        raise HTTPException(404, "帳號不存在")
    # 用臨時 SDK 實例測試（不影響當前連線）
    from fubon_provider import test_fubon_login
    result = await test_fubon_login(account)
    return result


@router.get("/fubon-accounts/status")
async def get_fubon_accounts_status():
    repo = FubonAccountRepository(db)
    accounts = await repo.list_accounts()
    return {
        "accounts": [
            {
                "id": a["id"],
                "label": a["label"],
                "is_active": a["is_active"],
                "connection_status": a["connection_status"],
                "connection_error": a["connection_error"],
                "last_connected_at": a["last_connected_at"],
            }
            for a in accounts
        ]
    }
```

---

## 5. 前端 UI 規格 {#frontend-ui}

### 5.1 新增路由：`SettingsView`

在 `frontend/src/router/index.js` 新增：

```javascript
{
  path: '/settings',
  name: 'Settings',
  component: () => import('@/views/SettingsView.vue'),
  meta: { title: '系統設定', icon: 'settings' }
}
```

在 `AppNavbar.vue` 導覽列新增「設定」入口（齒輪圖示）。

### 5.2 新增 View：`SettingsView.vue`

分頁式設定頁面，包含：
- **富邦 API 帳號** — 本文核心
- **通知設定**（預留）
- **系統資訊**（預留）

### 5.3 核心組件：`FubonAccountsPanel.vue`

```
frontend/src/components/settings/
├── FubonAccountsPanel.vue    核心面板：帳號列表 + 管理
└── FubonAccountFormModal.vue 新增/編輯帳號的 Modal 表單
```

#### `FubonAccountsPanel.vue` 功能清單

**帳號列表卡片**（每組帳號顯示）：
```
┌─────────────────────────────────────────┐
│ 🟢 主帳號                  [當前使用中]  │
│ P124185549   Speed 模式                 │
│ 憑證: C:\CAFubon\...\P124185549.pfx     │
│ 最後連線: 2026-04-10 13:00:00           │
│                                         │
│ [測試連線]  [編輯]  [設為使用]  [刪除]  │
└─────────────────────────────────────────┘
```

連線狀態顏色：
- 🟢 `connected` — 綠色，已連線
- 🟡 `connecting` — 黃色，連線中
- 🔴 `error` — 紅色，連線失敗（顯示錯誤訊息）
- ⚫ `disconnected` — 灰色，未連線

#### `FubonAccountFormModal.vue` 表單欄位

```
┌──────────────────────────────────────────────────┐
│ 新增富邦 API 帳號                          [✕]   │
├──────────────────────────────────────────────────┤
│ 帳號名稱（自訂）*    [主帳號               ]     │
│ 身分證字號*          [P124185549           ]     │
│ 電子平台密碼*        [•••••••••           👁]    │
│ 憑證檔路徑           [C:\CAFubon\...\*.pfx ]     │
│ 憑證密碼             [•••••••••           👁]    │
│ API Key*             [•••••••••••••••    👁]    │
│ 行情模式             ● Speed  ○ Normal           │
│                                                  │
│ ⚠️ 密碼將以 AES-256 加密儲存於本地資料庫       │
│                                                  │
│              [取消]  [儲存並測試連線]            │
└──────────────────────────────────────────────────┘
```

#### `useFubonAccounts.js` — Composable

```javascript
// frontend/src/composables/useFubonAccounts.js
import { ref, computed } from 'vue';
import axios from 'axios';

export function useFubonAccounts() {
  const accounts = ref([]);
  const loading = ref(false);
  const statusPolling = ref(null);

  const activeAccount = computed(() =>
    accounts.value.find(a => a.is_active) || null
  );

  async function fetchAccounts() {
    loading.value = true;
    try {
      const { data } = await axios.get('/api/settings/fubon-accounts');
      accounts.value = data.accounts;
    } finally {
      loading.value = false;
    }
  }

  async function createAccount(formData) {
    await axios.post('/api/settings/fubon-accounts', formData);
    await fetchAccounts();
  }

  async function updateAccount(id, formData) {
    await axios.put(`/api/settings/fubon-accounts/${id}`, formData);
    await fetchAccounts();
  }

  async function deleteAccount(id) {
    await axios.delete(`/api/settings/fubon-accounts/${id}`);
    await fetchAccounts();
  }

  async function activateAccount(id) {
    const { data } = await axios.post(`/api/settings/fubon-accounts/${id}/activate`);
    await fetchAccounts();
    return data;
  }

  async function testConnection(id) {
    const { data } = await axios.post(`/api/settings/fubon-accounts/${id}/test`);
    return data;  // { success: true/false, message: '' }
  }

  // 輪詢連線狀態（每 10 秒）
  function startStatusPolling() {
    stopStatusPolling();
    statusPolling.value = setInterval(async () => {
      const { data } = await axios.get('/api/settings/fubon-accounts/status');
      // 更新各帳號的 connection_status（不觸發全量重載）
      data.accounts.forEach(s => {
        const acc = accounts.value.find(a => a.id === s.id);
        if (acc) {
          acc.connection_status = s.connection_status;
          acc.connection_error = s.connection_error;
          acc.last_connected_at = s.last_connected_at;
        }
      });
    }, 10_000);
  }

  function stopStatusPolling() {
    if (statusPolling.value) clearInterval(statusPolling.value);
  }

  return {
    accounts, activeAccount, loading,
    fetchAccounts, createAccount, updateAccount,
    deleteAccount, activateAccount, testConnection,
    startStatusPolling, stopStatusPolling,
  };
}
```

---

## 6. FubonSDKManager 多帳號設計 {#sdk-manager}

### 6.1 修改 `backend/fubon_provider.py`

```python
class FubonSDKManager:
    """
    支援多組帳號：從 DB 載入 active 帳號，支援熱切換。
    """

    def __init__(self):
        self._sdk = None
        self._active_account_id: Optional[int] = None
        self._ws_stock = None
        self._subscriptions: Dict[str, str] = {}
        self._message_handlers: list = []
        self.connected = False

    @property
    def enabled(self) -> bool:
        # 不再依賴 .env 的 FUBON_ENABLED，而是看 DB 是否有 active 帳號
        return True  # 由 init_from_db() 決定是否真的啟動

    async def init_from_db(self, db) -> bool:
        """
        從資料庫讀取 active 帳號並初始化 SDK。
        在 main.py lifespan 中呼叫（取代原有的 env 讀取）。
        """
        from repositories.fubon_accounts import FubonAccountRepository
        repo = FubonAccountRepository(db)
        account = await repo.get_active_account()
        if not account:
            import logging
            logging.getLogger(__name__).info("無 active 富邦帳號，跳過 SDK 初始化")
            return False
        return await self._init_with_account(account, repo)

    async def _init_with_account(self, account: dict, repo=None) -> bool:
        """用帳號資料初始化 SDK"""
        import logging
        log = logging.getLogger(__name__)
        try:
            # 先關閉舊連線
            self.shutdown()

            from fubon_neo.sdk import FubonSDK, Mode
            sdk = FubonSDK()
            sdk.apikey_login(
                account["user_id"],
                account["api_key"],
                account.get("cert_path", ""),
                account.get("cert_password", ""),
            )
            mode = Mode.Normal if account.get("ws_mode") == "Normal" else Mode.Speed
            sdk.init_realtime(mode)

            self._sdk = sdk
            self._active_account_id = account["id"]
            self._ws_stock = sdk.marketdata.websocket_client.stock
            self.connected = True

            if repo:
                await repo.update_connection_status(account["id"], "connected")
            log.info("富邦 SDK 初始化成功（帳號: %s）", account["label"])
            return True
        except Exception as exc:
            log.error("富邦 SDK 初始化失敗: %s", exc)
            if repo:
                await repo.update_connection_status(
                    account["id"], "error", str(exc)
                )
            self.connected = False
            return False

    async def hot_switch(self, account: dict) -> bool:
        """
        熱切換到另一組帳號。
        1. 優雅關閉舊 SDK 連線
        2. 重新訂閱當前監控的所有股票
        """
        import logging, asyncio
        log = logging.getLogger(__name__)
        log.info("熱切換富邦帳號 → %s", account.get("label"))

        old_subscriptions = dict(self._subscriptions)  # 備份當前訂閱狀態

        from repositories.fubon_accounts import FubonAccountRepository
        from database import db as _db
        repo = FubonAccountRepository(_db)
        success = await self._init_with_account(account, repo)

        if success:
            # 重新訂閱舊的標的
            for key in old_subscriptions:
                symbol, channel = key.split(":", 1)
                self.subscribe_stock(symbol, channel)
            log.info("熱切換完成，已重新訂閱 %d 檔", len(old_subscriptions))
        return success


async def test_fubon_login(account: dict) -> dict:
    """
    獨立函數：用指定帳號測試連線（不影響 global SDK）
    """
    try:
        import asyncio
        from fubon_neo.sdk import FubonSDK
        loop = asyncio.get_event_loop()

        def _try_login():
            sdk = FubonSDK()
            sdk.apikey_login(
                account["user_id"],
                account["api_key"],
                account.get("cert_path", ""),
                account.get("cert_password", ""),
            )
            return True

        await loop.run_in_executor(None, _try_login)
        return {"success": True, "message": "連線測試成功"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}
```

### 6.2 修改 `backend/main.py` lifespan

```python
# 在 lifespan 的 startup 區段，取代原有 FUBON_ENABLED 讀取：
from providers import fubon_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 啟動 ---
    await db.connect()
    await db.create_tables()

    # 從 DB 載入 active 富邦帳號（取代 .env 讀取）
    fubon_enabled = await fubon_manager.init_from_db(db)
    if fubon_enabled:
        fubon_manager.start_ws_stock()

    # ... 其他啟動邏輯

    yield

    # --- 關閉 ---
    fubon_manager.shutdown()
    await db.close()
```

---

## 7. 分階段實作清單 {#implementation}

### Phase W1：後端基礎（資料庫 + 加密）

- [ ] **W1.1** 新增 `backend/crypto_utils.py`
- [ ] **W1.2** 在 `.env` 新增 `APP_ENCRYPT_KEY`（執行產生指令）
- [ ] **W1.3** 在 `backend/models/schema.py` 的 `CREATE_TABLE_STATEMENTS` 新增 `fubon_api_accounts` 資料表定義
- [ ] **W1.4** 新增 `backend/repositories/fubon_accounts.py`
- [ ] **W1.5** 重啟後端，確認 `fubon_api_accounts` 自動建表成功

### Phase W2：後端 API 路由

- [ ] **W2.1** 新增 `backend/routers/settings.py`
- [ ] **W2.2** 在 `backend/routers/__init__.py` 匯出 settings router
- [ ] **W2.3** 在 `backend/main.py` 掛載 `/api/settings` 路由
- [ ] **W2.4** 修改 `FubonSDKManager` 新增 `init_from_db()` 和 `hot_switch()`
- [ ] **W2.5** 修改 `main.py` lifespan 改用 `init_from_db()`
- [ ] **W2.6** 移除 `.env` 中的 `FUBON_USER_ID/FUBON_PASSWORD/...` 等帳號欄位（保留 `APP_ENCRYPT_KEY`）

### Phase W3：前端 Settings 頁面

- [ ] **W3.1** 新增 `frontend/src/views/SettingsView.vue`
- [ ] **W3.2** 在 router 新增 `/settings` 路由
- [ ] **W3.3** 在 `AppNavbar.vue` 新增齒輪圖示入口
- [ ] **W3.4** 新增 `frontend/src/composables/useFubonAccounts.js`
- [ ] **W3.5** 新增 `frontend/src/components/settings/FubonAccountsPanel.vue`
- [ ] **W3.6** 新增 `frontend/src/components/settings/FubonAccountFormModal.vue`

### Phase W4：首批帳號遷移（從 .env 到 DB）

- [ ] **W4.1** 透過網頁 UI 新增第一組帳號（P124185549）
- [ ] **W4.2** 點擊「測試連線」驗證可正常連線
- [ ] **W4.3** 點擊「設為使用中」啟動即時行情
- [ ] **W4.4** 確認 `.env` 中帳號相關欄位已清除

---

## 8. 環境變數調整 {#env-changes}

### 保留

```env
# 保留系統相關設定
APP_ENCRYPT_KEY=（用於加密 DB 中的憑證欄位，必填）
```

### 移除（改存 DB）

```env
# 下列欄位改由網頁設定，從 .env 移除：
# FUBON_ENABLED      → 改由 DB 是否有 active 帳號決定
# FUBON_USER_ID      → 移至 fubon_api_accounts.user_id
# FUBON_PASSWORD     → 移至 fubon_api_accounts.password_enc（加密）
# FUBON_CERT_PATH    → 移至 fubon_api_accounts.cert_path
# FUBON_CERT_PASSWORD→ 移至 fubon_api_accounts.cert_password_enc（加密）
# FUBON_API_KEY      → 移至 fubon_api_accounts.api_key_enc（加密）
# FUBON_WS_MODE      → 移至 fubon_api_accounts.ws_mode
# FUBON_MARKET_SCOPE → 不再需要
```

### 最終 `.env`（整合後）

```env
# 資料庫設定
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=000000
MYSQL_DATABASE=quantvision
MYSQL_CHARSET=utf8mb4

# 應用設定
APP_PORT=8001
STARTUP_DOWNLOAD_ENABLED=false
FRONTEND_DEV_URL=http://localhost:5173

# 應用層加密金鑰（保護 DB 中的敏感欄位）
# 產生指令：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
APP_ENCRYPT_KEY=（填入你產生的金鑰）
```

---

## 📎 相關文件

| 文件 | 路徑 |
|------|------|
| 原始行情整合規劃 | `docs/fubon-neo-realtime-integration-plan.md` |
| LWC 圖表整合規劃 | `docs/openstock-lwc-integration-plan.md` |
| 產品規格書 | `docs/quantvision-product-spec.md` |

---

*最後更新：2026-04-10 | 規劃版本：v1.0*
