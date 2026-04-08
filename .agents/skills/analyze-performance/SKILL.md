---
name: analyze-performance
description: Read-only DevOps and performance review for this repository. Use when Codex needs to inspect startup scripts, build configuration, backend dependencies, database performance, frontend bundle risk, observability, or performance-target gaps without modifying application code.
---

# Analyze Performance

Use this skill for structured read-only DevOps and performance analysis.

## Operating Rules

- Stay in inspection, testing, and planning mode.
- Do not modify application source files unless the user explicitly changes scope.
- Read prior planning documents in `docs/` before judging completion, especially `docs/system-review-report.md` and `docs/system-modification-plan.md` when present.
- If a referenced file, section, or command is missing, report that gap explicitly instead of guessing.
- Cite concrete files and line numbers for important findings.
- Order findings by severity.
- Return the report inline by default. Only update a planning file under `docs/` when the user explicitly asks to persist the output.

## Workflow

1. Review startup scripts.
   Read `scripts/start.bat`, `scripts/start.sh`, and `scripts/run-phase-gate.ps1`.
   Check whether the startup flow covers frontend, backend, and database concerns and whether environment-variable failure modes are handled.
2. Review frontend build configuration.
   Read `frontend/vite.config.js` and `frontend/package.json`.
   Check proxy setup, build optimization, code splitting, tree shaking, and script ergonomics.
3. Review backend dependency hygiene.
   Read `backend/requirements.txt`.
   Check pinning strategy, bloat, and whether a `requirements-dev.txt` split is warranted.
4. Review database performance posture.
   Read `backend/database.py`.
   Check indexes, high-frequency query coverage, possible N+1 patterns, and connection management.
5. Review frontend performance risk.
   Inspect `frontend/dist/` if it exists.
   Flag oversized components, likely lazy-load candidates, and expensive third-party libraries.
6. Compare current state against performance goals in `§14.1`.
   Estimate risk against dashboard first paint, symbol switching, and screener response-time targets.
   Suggest optimization paths.
7. Review observability.
   Check logging coverage, sync-job visibility, and API error tracking.

## Output

Produce the following sections:

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

Sort by `🔴 / 🟡 / 🔵` severity.

### 健康度評分

- Give a score from `0-100`.

### 優先行動項

- List up to three actions with the highest leverage.

