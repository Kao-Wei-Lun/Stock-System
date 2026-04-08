---
name: analyze-frontend
description: Read-only frontend architecture review for this repository. Use when Codex needs to audit frontend components, state management, API integration, data timestamp labeling, legacy migration, or responsive design without modifying application code.
---

# Analyze Frontend

Use this skill for structured read-only frontend analysis of QuantVision Pro.

## Operating Rules

- Stay in inspection, testing, and planning mode.
- Do not modify application source files unless the user explicitly changes scope.
- Read prior planning documents in `docs/` before judging completion, especially `docs/system-review-report.md` and `docs/system-modification-plan.md` when present.
- If a referenced file, section, or command is missing, report that gap explicitly instead of guessing.
- Cite concrete files and line numbers for important findings.
- Order findings by severity.
- Return the report inline by default. Only update a planning file under `docs/` when the user explicitly asks to persist the output.

## Workflow

1. Read `docs/quantvision-product-spec.md` section `§13`.
   Record required pages, navigation, and UI requirements.
2. Review `frontend/src/components/`.
   List all components with file size.
   Flag components over `20KB` as large components.
   Check whether each component has a single responsibility and call out likely split targets such as `RightSidebar.vue` or `ChartWorkspace.vue` if they still exist.
3. Review `frontend/src/composables/`.
   Assess the state-sharing model.
   Check whether `localStorage` is being used as formal storage instead of cache.
   Verify whether workspace data is persisted through backend APIs.
4. Review `frontend/src/api/`.
   List API calls, compare them with implemented backend endpoints, and assess loading and error handling consistency.
5. Verify market-data timestamp labeling.
   Check whether price views show a clear `資料時間`.
   Flag any use of the word `即時` if the spec forbids it.
   Check whether quotes are labeled as delayed, after-hours, or snapshot data where appropriate.
6. Review legacy migration status.
   Check for `frontend/public/legacy-dashboard.html`.
   Check the usage of `frontend/src/legacyDashboard.js`.
   Estimate how complete the migration is.
7. Review responsive design.
   Inspect `frontend/src/styles/`.
   Assess desktop and tablet support against spec `§14.2`.
   Check whether important tables have sticky headers and virtual scrolling where needed.

## Output

Produce the following sections:

### 組件清單與健康度

| 組件名稱 | 檔案大小 | 職責 | 拆分建議 | 健康度 |
|---|---|---|---|---|

### 問題清單

Sort by `🔴 / 🟡 / 🔵` severity.

### 資料時間標示檢查表

| 頁面/組件 | 是否顯示資料時間 | 是否標示延遲標記 | 狀態 |
|---|---|---|---|

### 健康度評分

- Give a score from `0-100`.

### 優先行動項

- List up to three actions with the highest leverage.

