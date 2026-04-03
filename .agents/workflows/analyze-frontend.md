---
description: 以前端架構師角色深度分析 frontend/src/ 所有組件
---

# 🎨 前端架構師分析

請扮演 **Frontend Architect（前端架構師）** 角色，對 QuantVision Pro 系統的前端進行深度分析。

## 分析步驟

1. **閱讀產品規格**
   - 讀取 `docs/quantvision-product-spec.md` 的 §13（前端頁面與資訊架構）
   - 記錄所有必做主頁與 UI 要求

2. **審查組件結構**
   - 列出 `frontend/src/components/` 下所有組件，標注每個的檔案大小
   - 特別標記超過 20KB 的「巨型組件」
   - 分析每個組件的職責是否單一
   - 評估是否需要進一步拆分（例如 `RightSidebar.vue` 約 78KB、`ChartWorkspace.vue` 約 50KB）

3. **審查狀態管理**
   - 檢查 `frontend/src/composables/` 目錄
   - 分析狀態共享模式是否合理
   - 檢查是否過度依賴 `localStorage` 作為正式資料存儲
   - 驗證工作區資料是否已改用後端 API 持久化

4. **審查 API 整合**
   - 檢查 `frontend/src/api/` 目錄
   - 列出所有 API 呼叫，比對後端已實作的 endpoint
   - 檢查錯誤處理是否一致
   - 驗證是否有適當的 loading state 和 error state

5. **驗證資料時間標示**
   - 🔴 重大：所有價格資料是否都顯示「資料時間」？
   - 🔴 重大：是否有地方使用「即時」字樣？（規格明確禁止）
   - 檢查是否所有報價都標示「延遲/盤後/快照」

6. **審查 Legacy 遷移狀況**
   - 檢查 `frontend/public/legacy-dashboard.html` 是否還存在
   - 檢查 `frontend/src/legacyDashboard.js` 的使用情況
   - 評估 Legacy 程式碼的遷移完成度

7. **審查響應式設計**
   - 檢查 `frontend/src/styles/` 中的 CSS
   - 評估是否支援桌機與平板（規格 §14.2 要求）
   - 檢查重要表格是否有固定表頭和虛擬捲動

## 輸出格式

### 組件清單與健康度
| 組件名稱 | 檔案大小 | 職責 | 拆分建議 | 健康度 |
|---|---|---|---|---|

### 問題清單
依 🔴🟡🔵 嚴重度排列

### 資料時間標示檢查表
| 頁面/組件 | 是否顯示資料時間 | 是否標示延遲標記 | 狀態 |
|---|---|---|---|

### 健康度評分 (0-100)

### 優先行動項（最多 3 項）
