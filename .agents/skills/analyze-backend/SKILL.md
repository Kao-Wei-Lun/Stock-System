---
name: analyze-backend
description: Read-only backend architecture review for this repository. Use when Codex needs to audit backend modules, API route coverage versus the product spec, provider abstractions, database schema coverage, module quality, or local-data persistence compliance without modifying application code.
---

# Analyze Backend

Use this skill for structured read-only backend analysis of QuantVision Pro.

## Operating Rules

- Stay in inspection, testing, and planning mode.
- Do not modify application source files unless the user explicitly changes scope.
- Read prior planning documents in `docs/` before judging completion, especially `docs/system-review-report.md` and `docs/system-modification-plan.md` when present.
- If a referenced file, section, or command is missing, report that gap explicitly instead of guessing.
- Cite concrete files and line numbers for important findings.
- Order findings by severity.
- Return the report inline by default. Only update a planning file under `docs/` when the user explicitly asks to persist the output.

## Workflow

1. Read `docs/quantvision-product-spec.md` sections `§7` and `§12`.
   Record all required API endpoints and provider interfaces.
2. Read `backend/main.py`.
   List implemented routes, compare them against spec `§12.2` and `§12.3`, identify missing endpoints, and note whether `main.py` is large enough to justify route extraction.
3. Review provider abstractions.
   Verify `quote_provider.py`, `fundamentals_provider.py`, and `taiwan_chip_provider.py`.
   Check whether `EventProvider`, `NewsProvider`, `MacroProvider`, and a `BrokerProvider` interface are missing.
   Confirm fallback behavior for each provider.
4. Read `backend/database.py`.
   Compare tables and critical fields against spec `§11`.
   Check for required fields such as `source`, `updated_at`, and `owner_id`.
5. Review backend module quality.
   Look for inconsistent error handling, hardcoded values, magic numbers, cyclic dependencies, and oversized files.
6. Verify data integrity requirements.
   Check whether formal data lands in the local database as required by `§6.5`.
   Flag any feature that depends on external API responses without persistence.

## Output

Produce the following sections:

### API Gap Matrix

| API Endpoint | 規格狀態 | 實作狀態 | 差距說明 |
|---|---|---|---|

### 問題清單

Sort by `🔴 / 🟡 / 🔵` severity. For each issue include:

- 問題描述
- 影響範圍
- 具體檔案與行號
- 改善建議

### 健康度評分

- Give a score from `0-100`.
- Explain the score briefly.

### 優先行動項

- List up to three actions with the highest leverage.

