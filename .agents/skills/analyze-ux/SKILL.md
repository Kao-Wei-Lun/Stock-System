---
name: analyze-ux
description: Read-only UX review for this repository. Use when Codex needs to audit information architecture, interaction design, visual consistency, state coverage, Nielsen usability heuristics, or key user journeys without modifying application code.
---

# Analyze UX

Use this skill for structured read-only UX and interaction review.

## Operating Rules

- Stay in inspection, testing, and planning mode.
- Do not modify application source files unless the user explicitly changes scope.
- Read prior planning documents in `docs/` before judging completion, especially `docs/system-review-report.md` and `docs/system-modification-plan.md` when present.
- If a referenced file, section, or command is missing, report that gap explicitly instead of guessing.
- Cite concrete files and line numbers for important findings.
- Order findings by severity.
- Return the report inline by default. Only update a planning file under `docs/` when the user explicitly asks to persist the output.

## Perspective

Review the system as a UX designer with strong experience in data-dense SaaS products and with familiarity across Nielsen usability heuristics, Fitts' Law, and Hick's Law.

## Workflow

1. Read UX requirements in the spec.
   Review `docs/quantvision-product-spec.md` sections `§13`, `§4.3`, and `§14.2`.
2. Review information architecture.
   Inspect `frontend/src/App.vue`, `frontend/src/components/DashboardTopbar.vue`, `frontend/src/components/WatchlistPanel.vue`, and `frontend/src/components/RightSidebar.vue`.
   Evaluate hierarchy, navigation consistency, discoverability, context retention, and shortcuts.
3. Review interaction design.
   Inspect `frontend/src/styles/` and major components under `frontend/src/components/`.
   Check feedback states, loading states, long-running progress, error messages, empty states, validation feedback, search, filtering, and keyboard efficiency.
4. Review visual consistency.
   Assess color system, typography, spacing, component styling, icon usage, and animation consistency.
5. Review state coverage.
   Check whether major feature areas account for initial, loading, normal, empty, partial, error, and stale-data states.
6. Evaluate Nielsen's 10 heuristics.
   Score each principle and explain the biggest gaps.
7. Walk through the five key journeys from the legacy workflow.
   Evaluate the path for symbol analysis, alert setup, trade journaling, stock screening, and strategy backtesting.
8. Review responsive design.
   Assess desktop and tablet usability, collapsible sidebars, and table behavior on narrow viewports.

## Output

Produce the following sections:

### Nielsen 可用性原則評分

| 原則 | 評分 (1-5) | 問題摘要 | 改善建議 |
|------|-----------|---------|---------|

### 使用者旅程分析

| 旅程 | 步驟數 | 主要摩擦點 | 建議優化 |
|------|--------|-----------|---------|

### 狀態覆蓋度矩陣

| 功能區域 | 初始 | 載入中 | 正常 | 空狀態 | 錯誤 | 過期 |
|---------|------|--------|------|--------|------|------|

### 問題清單

Sort by `🔴 / 🟡 / 🔵` severity. Include impacted user journey, concrete files and line numbers, and a practical improvement.

### UX 健康度評分

- Give a score from `0-100`.
- Break it down across information architecture, interaction design, visual consistency, error handling, and efficiency.

### 優先行動項

- List up to three actions with the highest UX impact.

