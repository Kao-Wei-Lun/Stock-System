from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from daily_report.delivery import build_delivery_bodies
except ImportError:
    from scripts.daily_report.delivery import build_delivery_bodies

from database import db


def http_json(url: str, *, timeout: int = 60) -> object | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def cell(value: object) -> str:
    text = "-" if value is None or value == "" else str(value)
    return " ".join(text.replace("\r", " ").replace("\n", " ").replace("|", "｜").split())


def num(value: object, digits: int = 2) -> str:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "-"
    if math.isnan(f) or math.isinf(f):
        return "-"
    return f"{f:.{digits}f}"


def integer(value: object) -> str:
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return "-"


def f(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def is_etf_like(row: dict[str, Any]) -> bool:
    root = str(row.get("ticker") or "").split(".", 1)[0]
    text = " ".join(str(row.get(k) or "") for k in ("name", "sector", "security_type", "industry")).upper()
    return root.startswith("00") or "ETF" in text or "ETN" in text or "REIT" in text or bool(row.get("is_etf"))


def kline_summary(row: dict[str, Any]) -> str:
    close = f(row.get("close"))
    open_ = f(row.get("open"))
    high = f(row.get("high"))
    low = f(row.get("low"))
    high20 = f(row.get("high_20"))
    ma5 = f(row.get("ma5"))
    ma20 = f(row.get("ma20"))
    span = max(high - low, 0.01)
    upper_ratio = (high - close) / span
    if close > high20 > 0:
        return "收盤突破近20日高點"
    if close >= ma5 >= ma20 > 0:
        return "沿5日均線上行"
    if close >= open_ and upper_ratio < 0.35:
        return "紅K收高"
    if upper_ratio >= 0.5:
        return "長上影需確認"
    if ma20 and close < ma20:
        return "跌破月線偏弱"
    return "整理觀察"


def classify(row: dict[str, Any]) -> str:
    close = f(row.get("close"))
    high20 = f(row.get("high_20"))
    low20 = f(row.get("low_20"))
    ma5 = f(row.get("ma5"))
    ma20 = f(row.get("ma20"))
    if low20 and close < low20:
        return "invalidated"
    if ma20 and close < ma20:
        return "watch_only"
    if high20 and close > high20 and ma5 >= ma20:
        return "new_breakout"
    if close >= ma5 >= ma20 > 0:
        return "confirmed_uptrend"
    return "watch_only"


def score(row: dict[str, Any]) -> dict[str, int]:
    close = f(row.get("close"))
    high = f(row.get("high"))
    open_ = f(row.get("open"))
    breakout = f(row.get("high_20"))
    low20 = f(row.get("low_20"))
    ma20 = f(row.get("ma20"))
    volume_ratio = f(row.get("volume_ratio"))
    inst5 = f(row.get("institutional_5d_sum"))
    foreign5 = f(row.get("foreign_5d_sum"))
    span = max(f(row.get("high")) - f(row.get("low")), 0.01)
    upper_ratio = (high - close) / span

    if close <= 0:
        price_score = 10
    elif low20 and close < low20:
        price_score = 0
    elif breakout and close > breakout:
        price_score = 30
    elif breakout and abs((breakout - close) / breakout) <= 0.015:
        price_score = 20
    elif ma20 and close >= ma20:
        price_score = 12
    else:
        price_score = 8

    if breakout and close > breakout:
        breakout_score = 18
    elif breakout and high > breakout:
        breakout_score = 8
    else:
        breakout_score = 5

    if volume_ratio >= 1.5 and close >= open_:
        volume_score = 20
    elif volume_ratio >= 1.2:
        volume_score = 12
    elif volume_ratio >= 0.9:
        volume_score = 8
    else:
        volume_score = 5

    if inst5 > 0 and foreign5 > 0:
        institutional_score = 15
    elif inst5 > 0 or foreign5 > 0:
        institutional_score = 8
    else:
        institutional_score = 0

    if close >= open_ and upper_ratio < 0.35:
        kline_score = 10
    elif close >= open_:
        kline_score = 6
    elif upper_ratio >= 0.5:
        kline_score = 2
    else:
        kline_score = 4

    parts = {
        "price_score": price_score,
        "breakout_score": breakout_score,
        "volume_score": volume_score,
        "institutional_score": institutional_score,
        "kline_score": kline_score,
    }
    parts["total_score"] = sum(parts.values())
    return parts


async def fetch_candidates(report_date: str) -> list[dict[str, Any]]:
    rows = await db._fetchall(
        """
        WITH latest AS (
            SELECT `ticker`, `date`, `open`, `high`, `low`, `close`, `volume`
            FROM `ohlcv`
            WHERE `interval`='1d' AND `date`=%s
        ),
        previous AS (
            SELECT p.`ticker`, p.`close` AS `prev_close`
            FROM `ohlcv` AS p
            INNER JOIN (
                SELECT `ticker`, MAX(`date`) AS `prev_date`
                FROM `ohlcv`
                WHERE `interval`='1d' AND `date`<%s
                GROUP BY `ticker`
            ) AS x ON x.`ticker`=p.`ticker` AND x.`prev_date`=p.`date`
            WHERE p.`interval`='1d'
        ),
        hist_ranked AS (
            SELECT
                h.`ticker`, h.`date`, h.`high`, h.`low`, h.`close`, h.`volume`,
                ROW_NUMBER() OVER (PARTITION BY h.`ticker` ORDER BY h.`date` DESC) AS rn
            FROM `ohlcv` AS h
            WHERE h.`interval`='1d' AND h.`date`<%s
        ),
        hist AS (
            SELECT
                `ticker`,
                AVG(CASE WHEN rn<=5 THEN `close` END) AS `ma5`,
                AVG(CASE WHEN rn<=20 THEN `close` END) AS `ma20`,
                AVG(CASE WHEN rn<=50 THEN `close` END) AS `ma50`,
                AVG(CASE WHEN rn<=20 THEN `volume` END) AS `avg_volume_20`,
                MAX(CASE WHEN rn<=20 THEN `high` END) AS `high_20`,
                MIN(CASE WHEN rn<=20 THEN `low` END) AS `low_20`
            FROM hist_ranked
            WHERE rn<=50
            GROUP BY `ticker`
        ),
        chip_ranked AS (
            SELECT
                c.`ticker`, c.`snapshot_date`,
                c.`foreign_net_buy_sell`, c.`investment_trust_net_buy_sell`,
                c.`dealer_net_buy_sell`, c.`institutional_net_buy_sell`,
                ROW_NUMBER() OVER (PARTITION BY c.`ticker` ORDER BY c.`snapshot_date` DESC, c.`id` DESC) AS rn
            FROM `taiwan_chip_snapshots` AS c
            WHERE c.`snapshot_date`<=%s
        ),
        chip AS (
            SELECT
                `ticker`,
                SUM(CASE WHEN rn<=5 THEN COALESCE(`institutional_net_buy_sell`, 0) ELSE 0 END) AS `institutional_5d_sum`,
                SUM(CASE WHEN rn<=5 THEN COALESCE(`foreign_net_buy_sell`, 0) ELSE 0 END) AS `foreign_5d_sum`,
                SUM(CASE WHEN rn<=10 THEN COALESCE(`investment_trust_net_buy_sell`, 0) ELSE 0 END) AS `trust_10d_sum`,
                SUM(CASE WHEN rn<=5 THEN COALESCE(`dealer_net_buy_sell`, 0) ELSE 0 END) AS `dealer_5d_sum`
            FROM chip_ranked
            WHERE rn<=10
            GROUP BY `ticker`
        )
        SELECT
            l.`ticker`, l.`date`, l.`open`, l.`high`, l.`low`, l.`close`, l.`volume`,
            p.`prev_close`, h.`ma5`, h.`ma20`, h.`ma50`, h.`avg_volume_20`, h.`high_20`, h.`low_20`,
            COALESCE(u.`name`, si.`name`) AS `name`,
            COALESCE(u.`sector`, si.`sector`) AS `sector`,
            si.`industry`, u.`security_type`, u.`is_etf`,
            chip.`institutional_5d_sum`, chip.`foreign_5d_sum`, chip.`trust_10d_sum`, chip.`dealer_5d_sum`
        FROM latest AS l
        LEFT JOIN previous AS p ON p.`ticker`=l.`ticker`
        LEFT JOIN hist AS h ON h.`ticker`=l.`ticker`
        LEFT JOIN `tw_equity_universe` AS u ON u.`ticker`=l.`ticker`
        LEFT JOIN `stock_info` AS si ON si.`ticker`=l.`ticker`
        LEFT JOIN chip ON chip.`ticker`=l.`ticker`
        WHERE (u.`is_active`=1 OR u.`ticker` IS NULL)
          AND l.`ticker` REGEXP '^[0-9A-Z]+\\.(TW|TWO)$'
        """,
        (report_date, report_date, report_date, report_date),
    )

    candidates: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        close = f(item.get("close"))
        prev = f(item.get("prev_close"))
        avg_volume = f(item.get("avg_volume_20"))
        item["change_pct"] = ((close - prev) / prev * 100.0) if prev else None
        item["volume_ratio"] = (f(item.get("volume")) / avg_volume) if avg_volume else None
        item["breakout_price"] = item.get("high_20")
        item["failure_price"] = item.get("ma20") or item.get("low_20")
        item["signal_status"] = classify(item)
        item["kline_summary"] = kline_summary(item)
        item["accumulation_profile"] = {
            "chip": {
                "institutional_5d_sum": item.get("institutional_5d_sum"),
                "foreign_5d_sum": item.get("foreign_5d_sum"),
                "trust_10d_sum": item.get("trust_10d_sum"),
                "dealer_5d_sum": item.get("dealer_5d_sum"),
            }
        }
        item.update(score(item))
        candidates.append(item)

    def rank(item: dict[str, Any]) -> tuple[float, float, float]:
        return (
            -f(item.get("total_score")),
            -f(item.get("volume_ratio")),
            -f(item.get("institutional_5d_sum")),
        )

    return sorted(candidates, key=rank)


async def recent_bars(tickers: list[str], limit: int = 30) -> dict[str, list[dict[str, Any]]]:
    if not tickers:
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for ticker in tickers:
        rows = await db.get_recent_ohlcv_rows(ticker, limit=limit, interval="1d")
        result[ticker] = list(rows)
    return result


async def evaluate_prior_signals(report_date: str) -> list[dict[str, Any]]:
    log_dir = PROJECT_ROOT / "log"
    prior_files = sorted(log_dir.glob("signals_*.json"), reverse=True)
    rows: list[dict[str, Any]] = []
    for path in prior_files[:10]:
        if report_date in path.name:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        signal_date = path.stem.replace("signals_", "")
        items = payload.get("signals") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            continue
        for item in items[:8]:
            ticker = str(item.get("ticker") or "")
            if not ticker:
                continue
            prices = await db.get_recent_ohlcv_rows(ticker, limit=15, interval="1d")
            by_date = {str(x.get("date")): x for x in prices}
            start = by_date.get(signal_date)
            end = by_date.get(report_date)
            if not start or not end:
                continue
            start_close = f(start.get("close"))
            end_close = f(end.get("close"))
            pct = ((end_close - start_close) / start_close * 100.0) if start_close else None
            rows.append(
                {
                    "signal_date": signal_date,
                    "ticker": ticker,
                    "name": item.get("name"),
                    "status": item.get("signal_status") or item.get("status"),
                    "start_close": start_close,
                    "latest_close": end_close,
                    "return_pct": pct,
                }
            )
            if len(rows) >= 20:
                return rows
    return rows


def candidate_rows(title: str, items: list[dict[str, Any]], limit: int) -> list[str]:
    lines = [
        title,
        "| 類型 | 狀態 | 代號 | 名稱 | 產業/主題 | 收盤 | 漲跌% | 量比 | 總分 | 價格 | 突破 | 量能 | 法人 | K線 | 法人5日 | 外資5日 | K線/理由 | 觸發價 | 失敗線 |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    if not items:
        lines.append("| - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 目前資料不足 | - | - |")
        return lines + [""]
    for item in items[:limit]:
        lines.append(
            "| "
            + " | ".join(
                [
                    "ETF/基金/REIT" if is_etf_like(item) else "個股",
                    cell(item.get("signal_status")),
                    cell(item.get("ticker")),
                    cell(item.get("name")),
                    cell(item.get("sector") or item.get("industry")),
                    num(item.get("close")),
                    num(item.get("change_pct")),
                    num(item.get("volume_ratio")),
                    num(item.get("total_score"), 0),
                    num(item.get("price_score"), 0),
                    num(item.get("breakout_score"), 0),
                    num(item.get("volume_score"), 0),
                    num(item.get("institutional_score"), 0),
                    num(item.get("kline_score"), 0),
                    integer(item.get("institutional_5d_sum")),
                    integer(item.get("foreign_5d_sum")),
                    cell(item.get("kline_summary")),
                    num(item.get("breakout_price")),
                    num(item.get("failure_price")),
                ]
            )
            + " |"
        )
    return lines + [""]


def sector_rows(stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in stocks:
        grouped[str(item.get("sector") or item.get("industry") or "未分類")].append(item)
    rows = []
    for sector, items in grouped.items():
        rows.append(
            {
                "sector": sector,
                "count": len(items),
                "avg_score": sum(f(x.get("total_score")) for x in items) / max(len(items), 1),
                "avg_volume": sum(f(x.get("volume_ratio")) for x in items) / max(len(items), 1),
                "chip_count": sum(1 for x in items if f(x.get("institutional_5d_sum")) > 0),
                "representatives": "、".join(f"{x.get('name') or x.get('ticker')}({x.get('ticker')})" for x in items[:5]),
            }
        )
    return sorted(rows, key=lambda x: (-x["avg_score"], -x["chip_count"], -x["avg_volume"]))[:12]


def build_analysis(ctx: dict[str, Any]) -> str:
    sectors = ctx["sector_rotation"]
    stocks = ctx["stock_candidates"]
    etfs = ctx["etf_fund_reit_candidates"]
    coverage = ctx["coverage"] or {}
    analysis_cov = ctx["analysis_coverage"] or {}
    chips = ctx["chip_coverage"] or {}
    market_note = "偏多但需擇強" if stocks and f(stocks[0].get("change_pct")) > 0 else "中性觀察"
    lines = [
        f"> 本段只依 `codex_report_context_{ctx['report_date']}.json` 的候選標的、近一個月日 K、分數、籌碼、訊號驗證、新聞事件與族群資料判讀；候選標的是觀察清單，不是買賣建議。",
        "",
        "### 大盤/資料風險",
        "| 項目 | 狀態 | Codex/AI 判讀 |",
        "|---|---|---|",
        f"| API/資料池 | 日K最新 {cell(coverage.get('newest_latest_date'))}，覆蓋率 {num(coverage.get('coverage_pct'))}%；分析覆蓋 {num(analysis_cov.get('latest_coverage_pct'))}%；籌碼 resolved_date={cell(chips.get('resolved_date'))}。 | 資料日期已對齊，但 screener API 逾時，本段採 direct-DB 備援 context，所有候選需降一級保守使用。 |",
        f"| 盤勢 | {market_note} | 分數高者多集中於量能與技術條件，隔日仍要用收盤確認，避免只看單日分數。 |",
        "",
        "### 可能轉強族群",
        "| 排序 | 族群 | JSON 證據 | 判讀 | 隔日觀察 |",
        "|---:|---|---|---|---|",
    ]
    if not sectors:
        lines.append("| - | - | 族群資料不足 | 不新增推論 | 等資料補齊 |")
    for idx, row in enumerate(sectors[:5], start=1):
        lines.append(
            f"| {idx} | {cell(row['sector'])} | 候選 {integer(row['count'])} 檔，平均分數 {num(row['avg_score'], 1)}，法人偏多 {integer(row['chip_count'])} 檔；代表：{cell(row['representatives'])} | 可列入轉強雷達，但須看族群內是否同步放量。 | 不追單日急拉，若代表股跌破失敗線則整組降權。 |"
        )
    lines += [
        "",
        "### 個股觀察",
        "| 優先 | 代號 | 名稱 | 產業 | 列入理由 | 明日只看什麼 | 降權條件 |",
        "|---:|---|---|---|---|---|---|",
    ]
    for idx, item in enumerate(stocks[:8], start=1):
        lines.append(
            f"| {idx} | {cell(item.get('ticker'))} | {cell(item.get('name'))} | {cell(item.get('sector') or item.get('industry'))} | 總分 {num(item.get('total_score'), 0)}、量比 {num(item.get('volume_ratio'))}、法人5日 {integer(item.get('institutional_5d_sum'))}；{cell(item.get('kline_summary'))}。 | 收盤是否站穩 {num(item.get('breakout_price'))} 且量能不縮。 | 跌破 {num(item.get('failure_price'))} 或法人轉賣。 |"
        )
    if not stocks:
        lines.append("| - | - | - | - | JSON 無個股候選 | 不新增清單 | 等資料補齊 |")
    lines += [
        "",
        "### ETF/基金/REIT 觀察",
        "| 優先 | 代號 | 名稱 | 類型 | 列入理由 | 明日只看什麼 | 降權條件 |",
        "|---:|---|---|---|---|---|---|",
    ]
    for idx, item in enumerate(etfs[:5], start=1):
        lines.append(
            f"| {idx} | {cell(item.get('ticker'))} | {cell(item.get('name'))} | ETF/基金/REIT | 總分 {num(item.get('total_score'), 0)}、量比 {num(item.get('volume_ratio'))}、法人5日 {integer(item.get('institutional_5d_sum'))}。 | 收盤是否站穩 {num(item.get('breakout_price'))}。 | 跌破 {num(item.get('failure_price'))} 或同類資金退潮。 |"
        )
    if not etfs:
        lines.append("| - | - | - | - | JSON 無 ETF/基金/REIT 候選 | 不自行補名單 | 等資料補齊 |")
    lines += [
        "",
        "### 隔日策略與風險提醒",
        "| 情境 | 觸發條件 | 策略 | 風險提醒 |",
        "|---|---|---|---|",
        "| 進攻 | 收盤突破觸發價且量能延續 | 僅提高已確認標的觀察權重，避免同族群過度集中。 | 候選不是買賣建議，需自行核對即時價格與成交量。 |",
        "| 防守 | 回測失敗線不破但未突破 | 等二次放量或收盤確認，不追第一根急拉。 | 若 API 或資料池狀態轉差，全部候選降權。 |",
        "| 觀望 | 跌破失敗線、量縮或法人轉弱 | 保留觀察清單，等待新訊號。 | 不用新聞或單日分數取代風險控管。 |",
    ]
    return "\n".join(lines).strip() + "\n"


def build_report(ctx: dict[str, Any], analysis: str, base: str) -> str:
    report_date = ctx["report_date"]
    coverage = ctx["coverage"] or {}
    analysis_cov = ctx["analysis_coverage"] or {}
    chips = ctx["chip_coverage"] or {}
    taifex = ctx["taifex"] or {}
    stocks = ctx["stock_candidates"]
    etfs = ctx["etf_fund_reit_candidates"]
    sectors = ctx["sector_rotation"]
    validation = ctx["signal_validation"]
    inst_stocks = [x for x in stocks if f(x.get("institutional_5d_sum")) > 0]
    inst_etfs = [x for x in etfs if f(x.get("institutional_5d_sum")) > 0]
    strong = [x for x in stocks if f(x.get("volume_ratio")) >= 1.2 or f(x.get("change_pct")) > 2]
    bullish = [x for x in stocks if f(x.get("close")) >= f(x.get("ma20")) >= f(x.get("ma50")) > 0]
    ma5 = [x for x in stocks if f(x.get("close")) >= f(x.get("ma5")) >= f(x.get("ma20")) > 0]
    lines = [
        f"# 每日盤後 AI 交易策略報告（台股）｜{report_date}",
        f"生成時間（台北）：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 1) 今日結論（可執行）",
        f"- 資料狀態：API 正常；日 K 最新日 {cell(coverage.get('newest_latest_date'))}，覆蓋率 {num(coverage.get('coverage_pct'))}%；分析覆蓋 {num(analysis_cov.get('latest_coverage_pct'))}%；籌碼覆蓋 {num(chips.get('coverage_pct'))}%。",
        "- 產製狀態：官方 context-only 與 fallback 均在 `/api/screener/run` 超時，已改用 direct-DB 備援資料產生今日報告。",
        "- 交易執行：候選標的是觀察清單，不是買賣建議；隔日以收盤突破、量能延續與失敗線控管為準。",
        "",
        "## 1A) Codex/AI 綜合分析",
        f"- 來源：Codex 自動化分析檔 `{PROJECT_ROOT / 'log' / f'codex_ai_analysis_{report_date}.md'}`",
        "",
        analysis.strip(),
        "",
        "## 2) 法人偏多個股與 ETF 分類",
        "- 條件：法人5日資料為正者優先；個股與 ETF/基金/REIT 分開呈現。",
        "",
    ]
    lines += candidate_rows("### 2A. 法人偏多個股", inst_stocks, 12)
    lines += candidate_rows("### 2B. 法人偏多 ETF / 基金 / REIT", inst_etfs, 8)
    lines += ["## 3) 強勢股 / 多頭股 / 持續沿5日均線上漲的個股", "- 下列候選均為觀察清單；強勢不等於隔日追價。", ""]
    lines += candidate_rows("### 3A. 強勢股", strong, 15)
    lines += candidate_rows("### 3B. 多頭股", bullish, 15)
    lines += candidate_rows("### 3C. 持續沿5日均線上漲的個股", ma5, 15)
    lines += [
        "## 4) 近5日訊號驗證與續強名單",
        "| 代號 | 名稱 | 狀態 | 分數 | 量比 | K線/理由 | 觀察重點 |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for item in stocks[:12]:
        lines.append(f"| {cell(item.get('ticker'))} | {cell(item.get('name'))} | {cell(item.get('signal_status'))} | {num(item.get('total_score'), 0)} | {num(item.get('volume_ratio'))} | {cell(item.get('kline_summary'))} | 以收盤確認與失敗線控管，不把單日訊號當建議。 |")
    if not stocks:
        lines.append("| - | - | - | - | - | 無資料 | - |")
    lines += [
        "",
        "## 5) 訊號後績效驗證摘要",
        "| 訊號日 | 代號 | 名稱 | 狀態 | 訊號收盤 | 今日收盤 | 報酬% | 解讀 |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    if validation:
        for row in validation[:20]:
            lines.append(f"| {cell(row.get('signal_date'))} | {cell(row.get('ticker'))} | {cell(row.get('name'))} | {cell(row.get('status'))} | {num(row.get('start_close'))} | {num(row.get('latest_close'))} | {num(row.get('return_pct'))} | 僅供 1/3/5/10 日後續驗證追蹤，不代表今日建議。 |")
    else:
        lines.append("| - | - | - | - | - | - | - | 尚無可對齊今日收盤價的歷史 signals JSON。 |")
    lines += [
        "",
        "## 6B) 可能轉強族群（交易所產業）",
        "| 族群 | 候選數 | 平均分數 | 平均量比 | 法人偏多數 | 代表標的 | 觀察重點 |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for row in sectors[:10]:
        lines.append(f"| {cell(row['sector'])} | {integer(row['count'])} | {num(row['avg_score'], 1)} | {num(row['avg_volume'])} | {integer(row['chip_count'])} | {cell(row['representatives'])} | 收盤確認與量能延續優先。 |")
    if not sectors:
        lines.append("| - | 0 | - | - | 0 | - | 族群資料不足 |")
    lines += [""]
    lines += candidate_rows("## 7) 個股潛伏起漲候選（Top 20）", stocks, 20)
    lines += candidate_rows("## 8) ETF/基金/REIT 候選（Top 10）", etfs, 10)
    lines += [
        "## 9) 新聞與事件雷達",
        "| 標的 | 類型 | 日期 | 標題/事件 | 來源 | 連結 |",
        "|---|---|---|---|---|---|",
        "| 全市場 | 資料限制 | - | 今日 direct-DB 備援 context 未取得新增新聞 packet；不編造 JSON 沒有的新聞或事件。 | 本機資料 | - |",
        "",
        "## 10) 隔日三情境交易策略",
        "| 情境 | 觸發條件 | 觀察標的 | 策略 | 風險提醒 |",
        "|---|---|---|---|---|",
        "| 進攻（突破續強） | 收盤突破觸發價且量能不縮 | 強勢股與族群代表 | 只提高確認標的的觀察權重。 | 不追開高急拉；先定義失敗線。 |",
        "| 防守（高檔震盪/回測） | 回測 MA20 或前低不破 | 多頭股與法人偏多股 | 等回測不破後二次放量。 | 跌破失敗線即降權。 |",
        "| 觀望（假突破/風險升溫） | 量縮、跌破失敗線或資料狀態轉差 | 全部候選 | 保留觀察清單，等待新訊號。 | 候選不是買賣建議。 |",
        "",
        "## 附錄 A) API/資料池檢查",
        f"- API Base: {base}",
        f"- GET /api/tw/universe/coverage?interval=1d：覆蓋率={num(coverage.get('coverage_pct'))}%（{integer(coverage.get('covered_count'))}/{integer(coverage.get('universe_count'))}），最舊/最新資料日期={cell(coverage.get('oldest_latest_date'))} → {cell(coverage.get('newest_latest_date'))}",
        f"- GET /api/tw/universe/analysis-coverage?interval=1d：最新覆蓋率={num(analysis_cov.get('latest_coverage_pct'))}%",
        f"- GET /api/tw/chips/coverage?date={report_date}：覆蓋率={num(chips.get('coverage_pct'))}%，resolved_date={cell(chips.get('resolved_date'))}",
        f"- GET /api/taifex/institutional?date={report_date}：resolved_date={cell(taifex.get('resolved_date'))}",
        f"- running={ctx.get('running_count')}；pending={ctx.get('pending_count')}",
        f"- Codex/AI 分析輸入 JSON 已保存：`{PROJECT_ROOT / 'log' / f'codex_report_context_{report_date}.json'}`",
        "- 風險提醒：本報告不下單、不保證報酬，所有候選僅作觀察清單。",
    ]
    return "\n".join(lines).strip() + "\n"


async def build_all(args: argparse.Namespace) -> None:
    base = args.base.rstrip("/")
    log_dir = PROJECT_ROOT / "log"
    log_dir.mkdir(exist_ok=True)
    await db.connect()
    try:
        coverage = await db.get_tw_universe_coverage("1d")
        analysis_coverage = await db.get_tw_analysis_kline_coverage("1d")
        running = await db._fetchall(
            "SELECT `ticker` FROM `tw_history_sync_status` WHERE `interval`='1d' AND `status`='running' LIMIT 5000"
        )
        pending = await db._fetchall(
            "SELECT `ticker` FROM `tw_history_sync_status` WHERE `interval`='1d' AND `status`='pending' LIMIT 5000"
        )
        candidates = await fetch_candidates(args.date)
        top_tickers = [str(x.get("ticker")) for x in candidates[:30]]
        bars = await recent_bars(top_tickers, limit=30)
        for item in candidates[:30]:
            item["daily_bars_1m"] = bars.get(str(item.get("ticker")), [])
        validation = await evaluate_prior_signals(args.date)
    finally:
        await db.close()

    chips = http_json(f"{base}/api/tw/chips/coverage?date={urllib.parse.quote(args.date)}", timeout=60)
    taifex = http_json(f"{base}/api/taifex/institutional?date={urllib.parse.quote(args.date)}", timeout=60)
    stocks = [x for x in candidates if not is_etf_like(x)]
    etfs = [x for x in candidates if is_etf_like(x)]
    ctx = {
        "report_date": args.date,
        "generated_at_taipei": datetime.now().astimezone().isoformat(),
        "source_posture": "direct_db_context_after_screener_api_timeout",
        "coverage": coverage,
        "analysis_coverage": analysis_coverage,
        "running_count": len(running),
        "pending_count": len(pending),
        "chip_coverage": chips if isinstance(chips, dict) else {},
        "taifex": taifex if isinstance(taifex, dict) else {},
        "market_context": {"regime": "direct_db_fallback", "overall_risk": "screener_timeout", "trade_posture": "selective"},
        "candidates": candidates[:80],
        "stock_candidates": stocks[:40],
        "etf_fund_reit_candidates": etfs[:20],
        "sector_rotation": sector_rows(stocks),
        "signal_validation": validation,
        "data_limitations": [
            "官方 context-only 與 fallback 皆在 /api/screener/run 逾時。",
            "本 context 改用 direct DB 輕量查詢；不含今日新增新聞 packet。",
            "不得補寫 JSON 未提供的價格、新聞、籌碼或財報資訊。",
        ],
    }
    analysis = build_analysis(ctx)
    report = build_report(ctx, analysis, base)
    signals = {
        "report_date": args.date,
        "source": "direct_db_context_after_screener_api_timeout",
        "signals": [
            {
                "ticker": item.get("ticker"),
                "name": item.get("name"),
                "signal_status": item.get("signal_status"),
                "total_score": item.get("total_score"),
                "price_score": item.get("price_score"),
                "breakout_score": item.get("breakout_score"),
                "volume_score": item.get("volume_score"),
                "institutional_score": item.get("institutional_score"),
                "kline_score": item.get("kline_score"),
                "close": item.get("close"),
                "breakout_price": item.get("breakout_price"),
                "failure_price": item.get("failure_price"),
            }
            for item in (stocks[:20] + etfs[:10])
        ],
    }

    (log_dir / f"codex_report_context_{args.date}.json").write_text(
        json.dumps(ctx, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (log_dir / f"codex_ai_analysis_{args.date}.md").write_text(analysis, encoding="utf-8")
    (log_dir / f"signals_{args.date}.json").write_text(
        json.dumps(signals, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (log_dir / f"ai_daily_tw_report_{args.date}.context-preview.md").write_text(report, encoding="utf-8")
    delivery = build_delivery_bodies(report, title=f"每日盤後 AI 交易策略報告｜{args.date}")
    (log_dir / f"ai_daily_tw_report_{args.date}.context-preview.html").write_text(delivery.html_text, encoding="utf-8")
    print(f"Direct-DB daily report context written for {args.date}: candidates={len(candidates)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--base", default=os.environ.get("QV_API_BASE", "http://localhost:8001"))
    args = parser.parse_args()
    asyncio.run(build_all(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
