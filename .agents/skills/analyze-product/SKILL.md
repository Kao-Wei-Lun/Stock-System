---
name: analyze-product
description: Read-only product implementation gap review for this repository. Use when Codex needs to compare the current system against the product specification, phase plans, delivery checklist, or definition-of-done requirements without modifying application code.
---

# Analyze Product

Use this skill for structured read-only product-completion analysis.

## Operating Rules

- Stay in inspection, testing, and planning mode.
- Do not modify application source files unless the user explicitly changes scope.
- Read prior planning documents in `docs/` before judging completion, especially `docs/system-review-report.md` and `docs/system-modification-plan.md` when present.
- If a referenced file, section, or command is missing, report that gap explicitly instead of guessing.
- Cite concrete files and line numbers for important findings.
- Order findings by severity.
- Return the report inline by default. Only update a planning file under `docs/` when the user explicitly asks to persist the output.

## Workflow

1. Read the full product specification and planning documents.
   Review `docs/quantvision-product-spec.md`, `docs/quantvision-phase-delivery-plan.md`, and `docs/quantvision-phase-task-checklist.md`.
   Build a checklist of required features.
2. Scan actual implementation.
   List backend modules and API endpoints.
   List frontend components and pages.
   List database tables.
3. Build the feature-gap matrix.
   Compare implementation against spec sections `§8.1` through `§8.14`.
4. Assess phase progress.
   Estimate completion of Phase 1 through Phase 4 and note blockers.
5. Check definition of done.
   Review section `§18` and verify each completion condition.
6. Evaluate UX-related product outcomes.
   Check whether users can reach a symbol summary in three clicks, whether data-time labeling is broad enough, and whether page transitions preserve flow.

## Output

Produce the following sections:

### 功能差距矩陣

| 功能模組 | 規格要求 | 後端狀態 | 前端狀態 | 整體完成度 | 缺失項 |
|---|---|---|---|---|---|

### Phase 里程碑進度

| Phase | 目標功能 | 完成度 | 阻塞項 |
|---|---|---|---|

### 完成定義檢核表

| 完成條件 (§18) | 是否達成 | 說明 |
|---|---|---|

### 問題清單

Sort by `🔴 / 🟡 / 🔵` severity.

### 健康度評分

- Give a score from `0-100`.

### 優先行動項

- List up to three actions with the highest leverage.

