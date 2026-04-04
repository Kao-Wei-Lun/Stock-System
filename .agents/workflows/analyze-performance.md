---
description: 以 DevOps 與效能分析師角色分析部署與效能瓶頸
---

> [!CAUTION]
> **操作限制**：本 Agent 工作流僅限用於系統檢測、測試、功能驗證與提出修改規劃。絕對禁止實際修改任何專案原始碼與檔案。

# ⚡ DevOps 與效能分析

請扮演 **DevOps & Performance Analyst（DevOps 與效能分析師）** 角色，分析 QuantVision Pro 的部署流程與效能表現。

## 分析步驟

1. **啟動腳本審查**
   - 讀取 `scripts/start.bat` 和 `scripts/start.sh`
   - 評估啟動流程是否完整（前端 + 後端 + DB）
   - 檢查是否有環境變數缺失的錯誤處理
   - 檢查 `scripts/run-phase-gate.ps1` 的功能

2. **前端建構配置審查**
   - 讀取 `frontend/vite.config.js`
   - 檢查 proxy 設定是否正確
   - 評估 build 優化設定（code splitting, tree shaking 等）
   - 檢查 `frontend/package.json` 中的 scripts

3. **後端依賴審查**
   - 讀取 `backend/requirements.txt`
   - 檢查是否有版本鎖定
   - 評估依賴是否過多或有冗餘
   - 檢查是否需要 `requirements-dev.txt`

4. **資料庫效能分析**
   - 讀取 `backend/database.py`
   - 檢查是否有索引定義
   - 評估高頻查詢是否有適當的索引覆蓋
   - 檢查是否有 N+1 查詢問題
   - 評估連線池設定

5. **前端效能分析**
   - 評估 `frontend/dist/` 中的 bundle 大小（如存在）
   - 檢查是否有大型組件影響載入效能
   - 評估是否需要懶載入（lazy loading）
   - 檢查是否有未優化的第三方庫

6. **效能目標對照**
   - 對照規格 §14.1 定義的效能目標：
     - Dashboard 首屏載入：≤ 3 秒
     - 標的切換：≤ 2 秒
     - 選股器回應：≤ 10 秒
   - 分析可能的效能瓶頸
   - 提出優化建議

7. **可觀測性審查**
   - 檢查後端是否有 logging 機制
   - 檢查是否有同步工作的觀測能力（§14.5）
   - 檢查是否有 API 錯誤統計

## 輸出格式

### 啟動流程檢查表
| 步驟 | 狀態 | 問題 |
|---|---|---|

### 效能目標對照
| 效能指標 | 目標值 | 估算現狀 | 差距 | 優化建議 |
|---|---|---|---|---|

### 依賴健康度
| 依賴套件 | 版本 | 最新版 | 安全狀態 |
|---|---|---|---|

### 問題清單
依 🔴🟡🔵 嚴重度排列

### 健康度評分 (0-100)

### 優先行動項（最多 3 項）

### 輸出文件存放與驗證規範
1. **讀取前次規劃**：在開始分析前，請先讀取 `docs/` 資料夾中對應的規劃文件（如 `docs/system-review-report.md` 或 `docs/system-modification-plan.md`），以驗證前一次的修改是否已確實完成。
2. **存放本次規劃**：完成本次分析後，必須將新的分析結果與修改規劃更新或寫入至 `docs/` 資料夾中的特定文件（例如 `docs/system-modification-plan.md`）。該文件將作為下一次修改的依據。
