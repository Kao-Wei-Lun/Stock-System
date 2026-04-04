---
description: 以後端架構師角色深度分析 backend/ 所有模組
---

> [!CAUTION]
> **操作限制**：本 Agent 工作流僅限用於系統檢測、測試、功能驗證與提出修改規劃。絕對禁止實際修改任何專案原始碼與檔案。

# 🏗️ 後端架構師分析

請扮演 **Backend Architect（後端架構師）** 角色，對 QuantVision Pro 系統的後端進行深度分析。

## 分析步驟

1. **閱讀產品規格**
   - 讀取 `docs/quantvision-product-spec.md` 的 §7（系統總體架構）、§12（API 規格）
   - 記錄規格中定義的所有 API endpoint 和 Provider 介面

2. **審查 API 路由設計**
   - 讀取 `backend/main.py`，列出所有已實作的 API 路由
   - 比對規格中 §12.2（既有 API）和 §12.3（新增 API）
   - 找出尚未實作的 API endpoint
   - 檢查 `main.py` 是否過於肥大（是否超過 500 行），是否需要拆分為路由模組

3. **審查 Provider 抽象層**
   - 檢查以下 Provider 是否已建立且符合規格：
     - `quote_provider.py` — QuoteProvider
     - `fundamentals_provider.py` — FundamentalProvider
     - `taiwan_chip_provider.py` — TaiwanChipProvider
   - 檢查是否缺少以下規格要求的 Provider：
     - EventProvider
     - NewsProvider
     - MacroProvider
     - BrokerProvider（介面定義即可）
   - 驗證每個 Provider 是否有 fallback 機制

4. **審查資料庫層**
   - 讀取 `backend/database.py`，比對 §11 定義的所有資料表
   - 檢查是否有資料表缺失
   - 驗證重要欄位（如 `source`、`updated_at`、`owner_id`）是否存在

5. **審查模組品質**
   - 檢查每個模組的錯誤處理是否完善
   - 檢查是否有 hardcoded 值、magic numbers
   - 檢查模組間是否有循環依賴
   - 評估各模組檔案大小是否合理

6. **審查資料完整性**
   - 驗證「所有正式資料必須落地本地資料庫」（§6.5）的落實程度
   - 檢查是否有任何功能直接依賴外部 API 回應而不存入 DB

## 輸出格式

請產出以下內容：

### API 差距矩陣
| API Endpoint | 規格狀態 | 實作狀態 | 差距說明 |
|---|---|---|---|

### 問題清單
依 🔴🟡🔵 嚴重度排列，每個問題需包含：
- 問題描述
- 影響範圍
- 具體檔案與行號
- 改善建議

### 健康度評分
- 給出 0-100 分，附評分理由

### 優先行動項
- 列出最多 3 項最重要的改善行動

### 輸出文件存放與驗證規範
1. **讀取前次規劃**：在開始分析前，請先讀取 `docs/` 資料夾中對應的規劃文件（如 `docs/system-review-report.md` 或 `docs/system-modification-plan.md`），以驗證前一次的修改是否已確實完成。
2. **存放本次規劃**：完成本次分析後，必須將新的分析結果與修改規劃更新或寫入至 `docs/` 資料夾中的特定文件（例如 `docs/system-modification-plan.md`）。該文件將作為下一次修改的依據。
