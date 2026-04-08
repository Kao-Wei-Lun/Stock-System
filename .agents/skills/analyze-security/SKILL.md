---
name: analyze-security
description: Read-only security and data audit for this repository. Use when Codex needs to inspect secrets handling, frontend and backend security posture, local-data compliance, or dependency risk without modifying application code.
---

# Analyze Security

Use this skill for structured read-only security and data-compliance analysis.

## Operating Rules

- Stay in inspection, testing, and planning mode.
- Do not modify application source files unless the user explicitly changes scope.
- Read prior planning documents in `docs/` before judging completion, especially `docs/system-review-report.md` and `docs/system-modification-plan.md` when present.
- If a referenced file, section, or command is missing, report that gap explicitly instead of guessing.
- Cite concrete files and line numbers for important findings.
- Order findings by severity.
- Return the report inline by default. Only update a planning file under `docs/` when the user explicitly asks to persist the output.

## Workflow

1. Review secret management.
   Inspect `.env`, `.env.example`, and `.gitignore`.
   Search the repository for hardcoded credentials such as `password`, `secret`, `token`, `api_key`, and `API_KEY`.
2. Review frontend security.
   Check whether the frontend exposes backend URLs, API keys, or sensitive environment variables.
   Inspect `vite.config.js`.
   Review `v-html` usage and other likely XSS surfaces.
   Note dependency risk visible from `package.json`.
3. Review backend security.
   Inspect CORS configuration in `main.py`.
   Check query construction and input validation in backend modules, especially `database.py`.
   Flag places where user input may flow into database access without validation or parameterization.
4. Review data-security and compliance rules.
   Verify the `§6.5` requirement that formal data is stored in the local database.
   Check whether `localStorage` is used only as cache for non-formal data.
   Check whether the system can degrade to local data if an external API fails.
   Note cleartext storage risks for sensitive data.
5. Review dependency security.
   Inspect versions in `backend/requirements.txt` and `frontend/package.json`.
   Flag outdated or risky dependencies when the repository evidence suggests a problem.

## Output

Produce the following sections:

### 安全問題清單

Sort by severity:

- `🔴 Critical`: risk of data leakage or compromise
- `🟡 Warning`: violates good practice with material risk
- `🔵 Info`: worthwhile improvements

### 資料規範合規矩陣

| 規範要求 | 落實狀態 | 違規檔案 | 說明 |
|---|---|---|---|

### 健康度評分

- Give a score from `0-100`.

### 優先行動項

- List up to three actions with the highest leverage.

