---
description: 一次執行全部 8 個角色維度的完整系統健檢
---

> [!CAUTION]
> **操作限制**：本 Agent 工作流僅限用於系統檢測、測試、功能驗證與提出修改規劃。絕對禁止實際修改任何專案原始碼與檔案。

# 🔍 QuantVision Pro 全面系統健檢

一次跑完全部 8 個分析角色，對系統進行全面審查。

## 執行順序

請依序執行以下 8 個分析維度，每個維度結束後給出該維度的評分，最後產出綜合報告。

### 第 1 步：🏗️ 後端架構師

按 `.agents/workflows/analyze-backend.md` 的步驟執行。

### 第 2 步：🎨 前端架構師

按 `.agents/workflows/analyze-frontend.md` 的步驟執行。

### 第 3 步：🔒 安全與資料審計師

按 `.agents/workflows/analyze-security.md` 的步驟執行。

### 第 4 步：🧪 測試工程師

按 `.agents/workflows/analyze-testing.md` 的步驟執行。

### 第 5 步：📋 產品審查員

按 `.agents/workflows/analyze-product.md` 的步驟執行。

### 第 6 步：⚡ DevOps 與效能分析師

按 `.agents/workflows/analyze-performance.md` 的步驟執行。

### 第 7 步：📈 資深股票交易員

按 `.agents/workflows/analyze-trader.md` 的步驟執行。

### 第 8 步：🧑‍🎨 UX 使用者體驗設計師

按 `.agents/workflows/analyze-ux.md` 的步驟執行。

## 最終綜合報告

完成全部 8 個維度分析後，請產出以下綜合報告：

### 系統總覽評分卡

| 維度 | 評分 | 最嚴重問題 | 優先行動 |
|---|---|---|---|
| 🏗️ 後端架構 | /100 | | |
| 🎨 前端架構 | /100 | | |
| 🔒 安全與資料 | /100 | | |
| 🧪 測試品質 | /100 | | |
| 📋 產品完成度 | /100 | | |
| ⚡ 效能與運維 | /100 | | |
| 📈 交易員體驗 | /100 | | |
| 🧑‍🎨 使用者體驗 | /100 | | |
| **總分** | **/100** | | |

### 🔴 Critical 問題匯總
列出全部維度中所有 Critical 等級的問題

### Top 10 優先改善事項
跨維度排序，選出最重要的 10 個改善行動

### 建議下一步
根據分析結果，建議接下來應該優先處理的工作方向

### 輸出文件存放與驗證規範
1. **讀取前次規劃**：在開始分析前，請先讀取 `docs/` 資料夾中對應的規劃文件（如 `docs/system-review-report.md` 或 `docs/system-modification-plan.md`），以驗證前一次的修改是否已確實完成。
2. **存放本次規劃**：完成本次分析後，必須將新的分析結果與修改規劃更新或寫入至 `docs/` 資料夾中的特定文件（例如 `docs/system-modification-plan.md`）。該文件將作為下一次修改的依據。
