---
name: full-system-review
description: Read-only cross-functional system review for this repository. Use when Codex needs to coordinate backend, frontend, security, testing, product, performance, trader-workflow, and UX analysis into one consolidated report without modifying application code.
---

# Full System Review

Use this skill to coordinate a full read-only system review across all analysis tracks.

## Operating Rules

- Stay in inspection, testing, and planning mode.
- Do not modify application source files unless the user explicitly changes scope.
- Read prior planning documents in `docs/` before judging completion, especially `docs/system-review-report.md` and `docs/system-modification-plan.md` when present.
- If a referenced file, section, or command is missing, report that gap explicitly instead of guessing.
- Cite concrete files and line numbers for important findings.
- Order findings by severity.
- Default to sequential analysis to keep the review controlled and easy to verify.
- Only delegate or parallelize when the user explicitly asks for subagents or parallel work.
- Return the report inline by default. Only update a planning file under `docs/` when the user explicitly asks to persist the output.

## Workflow

Run the following eight review tracks in order and capture a score for each one:

1. Run `$analyze-backend`.
2. Run `$analyze-frontend`.
3. Run `$analyze-security`.
4. Run `$analyze-testing`.
5. Run `$analyze-product`.
6. Run `$analyze-performance`.
7. Run `$analyze-trader`.
8. Run `$analyze-ux`.

If the user explicitly asks for delegation or parallel review, you may assign one track per subagent and then consolidate the results.

## Output

Produce the following consolidated sections:

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

- List all critical issues across tracks.

### Top 10 優先改善事項

- Merge and sort the most important actions across all tracks.

### 建議下一步

- Recommend the next workstream to tackle first and explain why.

