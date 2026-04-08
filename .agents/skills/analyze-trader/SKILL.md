---
name: analyze-trader
description: Read-only trader-workflow review for this repository. Use when Codex needs to evaluate the system from a senior Taiwan and US stock trader perspective, assess premarket, intraday, and postmarket workflows, or compare the product against TradingView, XQ, 三竹, and CMoney without modifying application code.
---

# Analyze Trader

Use this skill for structured read-only review from a senior stock trader perspective.

## Operating Rules

- Stay in inspection, testing, and planning mode.
- Do not modify application source files unless the user explicitly changes scope.
- Read prior planning documents in `docs/` before judging completion, especially `docs/system-review-report.md` and `docs/system-modification-plan.md` when present.
- If a referenced file, section, or command is missing, report that gap explicitly instead of guessing.
- Cite concrete files and line numbers for important findings.
- Order findings by severity.
- Return the report inline by default. Only update a planning file under `docs/` when the user explicitly asks to persist the output.

## Perspective

Review the system as a trader with:

- 10+ years of Taiwan and US equity trading experience
- a swing-trading focus with occasional intraday trading
- a workflow centered on technical analysis, institutional flow, and event-driven setups
- familiarity with TradingView, XQ, 三竹股市, and CMoney

## Workflow

1. Read the current system surface area.
   Review `docs/quantvision-product-spec.md`, `frontend/src/components/`, and `backend/main.py`.
   Distinguish implemented capabilities from spec-only capabilities.
2. Review premarket workflow support.
   Check support for overnight market summary, macro risk snapshot, event calendar, watchlist alerts, premarket screening, and overnight watchlist change summaries.
3. Review intraday workflow support.
   Check symbol switching speed, breakout alerts, institutional-flow awareness, technical summary visibility, pre-trade checklist support, and multi-chart or split-view support.
4. Review postmarket workflow support.
   Check trade journaling, performance tracking, strategy review, chip-flow recap, daily sync coverage, batch watchlist refresh, and mistake-pattern analysis.
5. Compare the product against mainstream tools.
   Evaluate gaps versus TradingView, XQ, 三竹, and CMoney in charting, screening, Taiwan-chip depth, mobile and order flow integration, and modular strategy support.
6. Summarize mandatory gaps, bonus opportunities, and current strengths from a trader's point of view.

## Output

Produce the following sections:

### 交易工作流覆蓋度

| 交易階段 | 場景 | 系統支援度 | 缺口說明 |
|---------|------|-----------|---------|

### 競爭力差距矩陣

| 功能類別 | TradingView | XQ | 三竹 | QuantVision Pro | 差距等級 |
|---------|------------|-----|------|----------------|---------|

### 必備功能缺口

- Focus on `🔴 Critical` items that block daily use.

### 加分功能建議

- Focus on `🟡 Nice-to-have` improvements.

### 系統亮點

- List meaningful strengths already present.

### 交易員體驗評分

- Give a score from `0-100`.
- Explain the score and daily-use willingness.

### 優先行動項

- List up to three actions that most increase the chance a trader would open the product every day.

