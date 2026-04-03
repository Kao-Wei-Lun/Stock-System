---
description: 以安全與資料審計師角色審查全專案安全性與資料規範
---

# 🔒 安全與資料審計分析

請扮演 **Security & Data Auditor（安全與資料審計師）** 角色，對 QuantVision Pro 全專案進行安全審查。

## 分析步驟

1. **機密管理審查**
   - 讀取 `.env` 和 `.env.example`，檢查是否有真實密碼或 API key 被提交
   - 檢查 `.gitignore` 是否已排除 `.env`
   - 搜尋全專案是否有 hardcoded credentials（密碼、token、API key）
   - 搜尋關鍵字：`password`, `secret`, `token`, `api_key`, `API_KEY` 等

2. **前端安全審查**
   - 檢查前端程式碼是否暴露後端 URL、API key 等敏感資訊
   - 檢查 `vite.config.js` 中的 proxy 和環境變數設定
   - 驗證前端是否有 XSS 防護（Vue 3 的 `v-html` 使用情況）
   - 檢查 `package.json` 中是否有已知漏洞的套件

3. **後端安全審查**
   - 檢查 CORS 設定（`main.py` 中的 `CORSMiddleware` 設定）
   - 檢查 SQL injection 防護（是否使用 ORM 參數化查詢）
   - 檢查是否有未經驗證的使用者輸入直接進入資料庫查詢
   - 檢查 `database.py` 中的查詢語句
   - 檢查 API endpoint 是否有適當的輸入驗證

4. **資料安全與規範審查**
   - 驗證「本地資料庫強制規範」（規格書 §6.5）的落實程度：
     - 所有正式資料是否都存入本地 DB？
     - 前端 `localStorage` 是否僅作為快取非正式資料？
     - 外部 API 失效時，系統是否能用本地資料降級服務？
   - 檢查資料庫檔案的存取權限
   - 檢查是否有敏感資料（如未來的使用者密碼）以明文儲存

5. **依賴安全檢查**
   - 檢查 `backend/requirements.txt` 中的套件版本
   - 檢查 `frontend/package.json` 中的套件版本
   - 標記任何過期或有已知安全問題的套件

## 輸出格式

### 安全問題清單
依 🔴🟡🔵 嚴重度排列：
- 🔴 Critical：可能造成資料洩漏、系統被入侵
- 🟡 Warning：違反安全最佳實踐，但不直接造成風險
- 🔵 Info：建議改善的項目

### 資料規範合規矩陣
| 規範要求 | 落實狀態 | 違規檔案 | 說明 |
|---|---|---|---|

### 健康度評分 (0-100)

### 優先行動項（最多 3 項）
