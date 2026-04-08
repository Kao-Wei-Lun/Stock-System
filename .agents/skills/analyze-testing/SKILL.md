---
name: analyze-testing
description: Read-only test and QA review for this repository. Use when Codex needs to map test coverage, identify untested modules, inspect backtest look-ahead bias risk, compare tests against acceptance criteria, or run the smallest relevant test commands without modifying application code.
---

# Analyze Testing

Use this skill for structured read-only test-quality and QA analysis.

## Operating Rules

- Stay in inspection, testing, and planning mode.
- Do not modify application source files unless the user explicitly changes scope.
- Read prior planning documents in `docs/` before judging completion, especially `docs/system-review-report.md` and `docs/system-modification-plan.md` when present.
- If a referenced file, section, or command is missing, report that gap explicitly instead of guessing.
- Cite concrete files and line numbers for important findings.
- Order findings by severity.
- You may run non-destructive test commands when they are available and useful.
- Return the report inline by default. Only update a planning file under `docs/` when the user explicitly asks to persist the output.

## Workflow

1. Inventory backend tests under `backend/tests/`.
   List test files, estimate case counts, map them to backend modules, and identify backend modules with no corresponding tests.
2. Inventory frontend tests under `frontend/src/`.
   List `.spec.js` or equivalent test files and identify important components without tests.
3. Build a module-to-test coverage matrix.
   Flag modules with no tests as `🔴`.
   Flag partially covered modules as `🟡`.
4. Inspect look-ahead bias risk in the backtest engine.
   Read `backend/backtest_engine.py`.
   Check for future-data access, risky `shift` usage, or other look-ahead patterns.
   Read `backend/tests/test_backtest_engine.py` and confirm whether this risk is explicitly tested.
5. Compare tests with acceptance requirements.
   Read `docs/quantvision-product-spec.md` section `§15`.
   Map spec-defined test requirements to actual tests.
6. Review test quality.
   Check setup and teardown discipline, mocking strategy for external APIs, edge-case coverage, and integration-test coverage.
7. Run the smallest relevant test commands when feasible.
   Prefer `python -m pytest --tb=short -q` for backend and `npx vitest run --reporter=verbose` for frontend when the environment supports them.
   Record passes, failures, and blockers.

## Output

Produce the following sections:

### 測試覆蓋矩陣

| 模組 | 測試檔 | 案例數 | 跑通狀態 | 覆蓋程度 |
|---|---|---|---|---|

### 驗收要求覆蓋度

| 驗收要求 (§15) | 對應測試 | 覆蓋狀態 |
|---|---|---|

### 前視偏誤檢查結果

- List each check result clearly.

### 問題清單

Sort by `🔴 / 🟡 / 🔵` severity.

### 健康度評分

- Give a score from `0-100`.

### 優先行動項

- List up to three actions with the highest leverage.

