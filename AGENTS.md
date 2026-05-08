# AGENTS.md

## Project Goal
This project is a Taiwan stock analysis system covering market data sync, screening, backtesting, AI reports, email delivery, and automation.

## General Coding Rules
- Do not rewrite the whole system unless explicitly requested.
- Prefer modifying existing functions and modules.
- Keep backward compatibility with existing APIs, reports, database schemas, and automation scripts.
- Do not remove existing user-facing report sections unless requested.
- Add clear comments around scoring, signal classification, validation, and risk-sensitive logic.
- Never commit real secrets, API keys, SMTP passwords, account credentials, or private `.env` values.

## Safety Rules
- Do not place real trading orders.
- This system only generates analysis, observation lists, reports, and backtest results.
- Always include risk reminders in trading reports.
- Treat generated candidates as watchlists, not guaranteed buy or sell instructions.

## Daily Report Rules
- Single-day signals are not enough for recommendations.
- Compare with the previous 3 to 5 trading days when historical signal data is available.
- Save every generated signal to `signals_YYYY-MM-DD.json`.
- Support later validation of 1-day, 3-day, 5-day, and 10-day performance.
- Keep stocks, ETFs, funds, and REITs clearly separated when report clarity depends on instrument type.
- Use Traditional Chinese for report text and user-facing trading explanations.

## Signal Status Rules
Classify candidates into:
- `confirmed_uptrend`
- `new_breakout`
- `watch_only`
- `failed_breakout`
- `invalidated`

## Scoring Rules
The final score should not easily produce many 100-point results.

Break down `total_score` into:
- `price_score`
- `breakout_score`
- `volume_score`
- `institutional_score`
- `kline_score`

## Validation Rules
- Every generated signal should be saved to a daily JSON file.
- The system should support later validation of 1-day, 3-day, 5-day, and 10-day performance.
- Prefer structured signal JSON over parsing Markdown reports when both are available.
- Preserve Markdown report parsing as a backward-compatible fallback for older reports.
