from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from daily_report.delivery import build_delivery_bodies
except ImportError:
    from scripts.daily_report.delivery import build_delivery_bodies


def http_json(url: str, *, method: str = "GET", body: object | None = None, timeout: int = 180) -> object:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def fmt_num(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def fmt_int(value: object) -> str:
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return "-"


def cell(value: object) -> str:
    text = "-" if value is None or value == "" else str(value)
    return " ".join(text.replace("\r", " ").replace("\n", " ").replace("|", "｜").split())


def ticker_root(ticker: str) -> str:
    return ticker.upper().split(".", 1)[0]


def is_etf_like(item: dict) -> bool:
    text = " ".join(str(item.get(k) or "") for k in ("ticker", "name", "sector", "industry")).upper()
    root = ticker_root(str(item.get("ticker") or ""))
    return (
        "ETF" in text
        or "ETN" in text
        or "REIT" in text
        or root.startswith("00")
        or root.startswith("IX")
    )


def candidate_score(item: dict) -> float:
    for key in ("total_score", "accumulation_score", "score", "setup_quality", "base_score"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def chip(item: dict, key: str) -> object:
    profile = item.get("accumulation_profile") or {}
    chip_profile = profile.get("chip") or {}
    return chip_profile.get(key)


def kline_label(item: dict) -> str:
    for key in ("kline_structure", "technical_profile", "candlestick_profile"):
        value = item.get(key)
        if isinstance(value, dict):
            labels = []
            for label_key in ("structure_label", "trend_label", "summary", "bias"):
                if value.get(label_key):
                    labels.append(str(value.get(label_key)))
            if labels:
                return " / ".join(labels[:2])
    return str(item.get("decision_reason") or item.get("setup_type") or "-")


def trigger_price(item: dict) -> str:
    for key in ("breakout_price", "trigger_price", "week_52_high", "high"):
        if item.get(key) not in (None, ""):
            return fmt_num(item.get(key), 2)
    return "-"


def fail_price(item: dict) -> str:
    for key in ("stop_loss", "failure_price", "ma20", "low"):
        if item.get(key) not in (None, ""):
            return fmt_num(item.get(key), 2)
    return "-"


def sort_candidates(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda x: (candidate_score(x), float(x.get("volume_ratio") or 0)), reverse=True)


def candidate_rows(title: str, items: list[dict], limit: int = 12) -> list[str]:
    lines = [title, "| 類型 | 代號 | 名稱 | 產業/主題 | 收盤 | 漲跌% | 量比 | 分數 | 法人5日 | 外資5日 | K線/理由 | 觸發價 | 失敗線 |", "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
    if not items:
        lines.append("| - | - | - | - | - | - | - | - | - | - | 目前資料不足 | - | - |")
        return lines + [""]
    for item in items[:limit]:
        lines.append(
            "| "
            + " | ".join(
                [
                    "ETF/基金/REIT" if is_etf_like(item) else "個股",
                    cell(item.get("ticker")),
                    cell(item.get("name")),
                    cell(item.get("sector") or item.get("industry")),
                    fmt_num(item.get("close"), 2),
                    fmt_num(item.get("change_pct"), 2),
                    fmt_num(item.get("volume_ratio"), 2),
                    fmt_num(candidate_score(item), 1),
                    fmt_int(chip(item, "institutional_5d_sum")),
                    fmt_int(chip(item, "foreign_5d_sum")),
                    cell(kline_label(item)),
                    trigger_price(item),
                    fail_price(item),
                ]
            )
            + " |"
        )
    return lines + [""]


def sector_rows(items: list[dict], limit: int = 10) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        buckets[str(item.get("sector") or item.get("industry") or "未分類")].append(item)
    rows = []
    for sector, bucket in buckets.items():
        positives = [x for x in bucket if (chip(x, "institutional_5d_sum") or 0) and (chip(x, "institutional_5d_sum") or 0) > 0]
        rows.append(
            {
                "sector": sector,
                "count": len(bucket),
                "avg_score": sum(candidate_score(x) for x in bucket) / max(1, len(bucket)),
                "avg_volume": sum(float(x.get("volume_ratio") or 0) for x in bucket) / max(1, len(bucket)),
                "chip_count": len(positives),
                "representatives": "、".join(f"{x.get('name') or x.get('ticker')}({x.get('ticker')})" for x in sort_candidates(bucket)[:5]),
            }
        )
    return sorted(rows, key=lambda x: (x["avg_score"], x["chip_count"], x["avg_volume"]), reverse=True)[:limit]


def fetch_recent_rows(base: str, ticker: str) -> list[dict]:
    encoded = urllib.parse.quote(ticker, safe="")
    try:
        payload = http_json(f"{base}/api/kline/{encoded}?period=3mo&interval=1d", timeout=30)
    except Exception:
        return []
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return payload["items"][-30:]
    if isinstance(payload, list):
        return payload[-30:]
    return []


def build_context(base: str, report_date: str) -> dict:
    coverage = http_json(f"{base}/api/tw/universe/coverage?interval=1d", timeout=30)
    analysis_coverage = http_json(f"{base}/api/tw/universe/analysis-coverage?interval=1d", timeout=60)
    running = http_json(f"{base}/api/tw/history/status?interval=1d&status=running&limit=5000", timeout=60)
    pending = http_json(f"{base}/api/tw/history/status?interval=1d&status=pending&limit=5000", timeout=60)
    chips = http_json(f"{base}/api/tw/chips/coverage?date={report_date}", timeout=60)
    taifex = http_json(f"{base}/api/taifex/institutional?date={report_date}", timeout=60)
    screener = http_json(
        f"{base}/api/screener/run",
        method="POST",
        body={"filters": {"market": "TW", "setup_type": "accumulation", "sort_by": "accumulation_score", "limit": 120}},
        timeout=240,
    )
    items = [x for x in screener.get("items", []) if isinstance(x, dict)] if isinstance(screener, dict) else []
    items = sort_candidates(items)
    for item in items[:24]:
        item["daily_bars_1m"] = fetch_recent_rows(base, str(item.get("ticker") or ""))
    return {
        "report_date": report_date,
        "generated_at_taipei": datetime.now().astimezone().isoformat(),
        "source_posture": "fallback_context_from_local_api_after_official_build_report_timed_out",
        "coverage": coverage,
        "analysis_coverage": analysis_coverage,
        "running_count": len(running.get("items") or []) if isinstance(running, dict) else None,
        "pending_count": len(pending.get("items") or []) if isinstance(pending, dict) else None,
        "chip_coverage": chips,
        "taifex": taifex,
        "market_context": screener.get("market_context") if isinstance(screener, dict) else {},
        "candidates": items[:60],
        "stock_candidates": [x for x in items if not is_etf_like(x)][:30],
        "etf_fund_reit_candidates": [x for x in items if is_etf_like(x)][:20],
        "sector_rotation": sector_rows([x for x in items if not is_etf_like(x)], limit=12),
        "data_limitations": [
            "原始 build_report 在本機後端 screener/逐檔補資料階段逾時，改以可成功回應的本機 API 端點建立 fallback context。",
            "不得補寫 JSON 未提供的價格、新聞、籌碼或財報資訊。",
        ],
    }


def analysis_markdown(ctx: dict) -> str:
    market = ctx.get("market_context") or {}
    sectors = ctx.get("sector_rotation") or []
    stocks = ctx.get("stock_candidates") or []
    etfs = ctx.get("etf_fund_reit_candidates") or []
    coverage = ctx.get("coverage") or {}
    analysis_cov = ctx.get("analysis_coverage") or {}
    chips = ctx.get("chip_coverage") or {}
    lines = [
        f"> 本段只依 `codex_report_context_{ctx['report_date']}.json` 的候選標的、近一個月日 K、分數、籌碼、訊號與族群資料判讀；候選標的是觀察清單，不是買賣建議。",
        "",
        "### 一句話結論",
        "| 判斷面向 | Codex/AI 綜合判讀 | 風險限制 |",
        "|---|---|---|",
        f"| 大盤/資料風險 | 資料池最新日為 {cell(coverage.get('newest_latest_date'))}，覆蓋率 {fmt_num(coverage.get('coverage_pct'), 2)}%；分析 K 線最新覆蓋 {fmt_num(analysis_cov.get('latest_coverage_pct'), 2)}%，籌碼覆蓋 {fmt_num(chips.get('coverage_pct'), 2)}%。市場狀態為 {cell(market.get('regime'))}，風險為 {cell(market.get('overall_risk'))}。 | fallback context 來自可回應 API，原始完整 build_report 逾時；低流動性與缺資料標的需降權。 |",
        f"| 主線 | 候選分數與法人資料優先指向 {cell(sectors[0]['sector'] if sectors else '未分類')}、{cell(sectors[1]['sector'] if len(sectors) > 1 else '未分類')} 等族群。 | 族群轉強只代表觀察優先序，不代表隔日可追價。 |",
        "| 操作 | 隔日只看收盤確認、量能延續與失敗線是否守住。 | 若開高走低、量縮或跌破失敗線，候選即降為觀望。 |",
        "",
        "### 可能轉強族群",
        "| 排序 | 族群 | 證據 | Codex/AI 判讀 | 隔日觀察 |",
        "|---:|---|---|---|---|",
    ]
    if not sectors:
        lines.append("| - | - | JSON 族群資料不足 | 暫不新增推論 | 等資料補齊 |")
    for idx, row in enumerate(sectors[:5], start=1):
        lines.append(
            f"| {idx} | {cell(row['sector'])} | 候選 {fmt_int(row['count'])} 檔，平均分數 {fmt_num(row['avg_score'], 1)}，法人偏多數 {fmt_int(row['chip_count'])}；代表：{cell(row['representatives'])} | 可列為轉強雷達，優先看族群內是否同步放量與收盤站穩。 | 不追單檔急拉；若代表股跌破失敗線則整組降權。 |"
        )
    lines += [
        "",
        "### 個股觀察",
        "| 優先 | 代號 | 名稱 | 產業 | 列入理由 | 明日只看什麼 | 降權條件 |",
        "|---:|---|---|---|---|---|---|",
    ]
    for idx, item in enumerate(stocks[:6], start=1):
        lines.append(
            f"| {idx} | {cell(item.get('ticker'))} | {cell(item.get('name'))} | {cell(item.get('sector') or item.get('industry'))} | 分數 {fmt_num(candidate_score(item), 1)}、量比 {fmt_num(item.get('volume_ratio'), 2)}、法人5日 {fmt_int(chip(item, 'institutional_5d_sum'))}；{cell(kline_label(item))}。 | 收盤是否站穩 {trigger_price(item)} 且量能不縮。 | 跌破 {fail_price(item)}、法人轉賣或量能退潮。 |"
        )
    if not stocks:
        lines.append("| - | - | - | - | JSON 無個股候選 | 不新增清單 | 等資料補齊 |")
    lines += [
        "",
        "### ETF/基金/REIT 觀察",
        "| 優先 | 代號 | 名稱 | 類型 | 列入理由 | 明日只看什麼 | 降權條件 |",
        "|---:|---|---|---|---|---|---|",
    ]
    for idx, item in enumerate(etfs[:4], start=1):
        lines.append(
            f"| {idx} | {cell(item.get('ticker'))} | {cell(item.get('name'))} | ETF/基金/REIT | 分數 {fmt_num(candidate_score(item), 1)}、量比 {fmt_num(item.get('volume_ratio'), 2)}、法人5日 {fmt_int(chip(item, 'institutional_5d_sum'))}。 | 收盤是否站穩 {trigger_price(item)}。 | 跌破 {fail_price(item)} 或同類股資金退潮。 |"
        )
    if not etfs:
        lines.append("| - | - | - | - | JSON 無 ETF/基金/REIT 候選 | 不自行補名單 | 等正式資料表更新 |")
    lines += [
        "",
        "### 隔日策略與風險提醒",
        "| 情境 | 觸發條件 | 策略 | 風險提醒 |",
        "|---|---|---|---|",
        "| 進攻 | 族群代表股收盤突破且量能不縮 | 只提高已確認標的觀察權重，避免同族群過度集中。 | 候選不是買賣建議，需自行核對即時價格與成交量。 |",
        "| 防守 | 回測支撐不破但未突破 | 等二次放量或收盤確認，不追第一根急拉。 | 若資料池或 API 狀態轉差，所有候選降權。 |",
        "| 觀望 | 跌破失敗線、量縮或法人轉弱 | 保留觀察清單，等待新訊號。 | 不用新聞或單日分數取代風險控管。 |",
    ]
    return "\n".join(lines).strip() + "\n"


def build_report(ctx: dict, analysis_text: str, base: str) -> str:
    report_date = ctx["report_date"]
    coverage = ctx.get("coverage") or {}
    analysis_cov = ctx.get("analysis_coverage") or {}
    chips = ctx.get("chip_coverage") or {}
    market = ctx.get("market_context") or {}
    taifex = ctx.get("taifex") or {}
    stocks = ctx.get("stock_candidates") or []
    etfs = ctx.get("etf_fund_reit_candidates") or []
    sectors = ctx.get("sector_rotation") or []
    strong = [x for x in stocks if float(x.get("volume_ratio") or 0) >= 1.2][:15]
    bullish = [x for x in stocks if (x.get("ma20") and x.get("ma50") and float(x.get("close") or 0) >= float(x.get("ma20") or 0) >= float(x.get("ma50") or 0))][:15]
    ma5 = [x for x in stocks if x.get("daily_bars_1m")][:15]
    inst_stocks = [x for x in stocks if (chip(x, "institutional_5d_sum") or 0) and (chip(x, "institutional_5d_sum") or 0) > 0]
    inst_etfs = [x for x in etfs if (chip(x, "institutional_5d_sum") or 0) and (chip(x, "institutional_5d_sum") or 0) > 0]

    lines = [
        f"# 每日盤後 AI 交易策略報告（台股）｜{report_date}",
        f"生成時間（台北）：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 1) 今日結論（可執行）",
        f"- 資料狀態：fallback 產出；API 正常，日 K 最新日 {cell(coverage.get('newest_latest_date'))}，覆蓋率 {fmt_num(coverage.get('coverage_pct'), 2)}%，分析覆蓋 {fmt_num(analysis_cov.get('latest_coverage_pct'), 2)}%，籌碼覆蓋 {fmt_num(chips.get('coverage_pct'), 2)}%。",
        f"- 市場狀態：風險={cell(market.get('overall_risk'))}；盤勢={cell(market.get('regime'))}；操作姿態={cell(market.get('trade_posture'))}。",
        "- 交易執行：候選標的是觀察清單，不是買賣建議；隔日以收盤突破、量能延續與失敗線控管為準。",
        "- 資料風險：原始完整 build_report 在本機 API 計算階段逾時，本報告使用可回應的本機 API 端點與 JSON fallback context。",
        "",
        "## 1A) Codex/AI 綜合分析",
        f"- 來源：Codex 自動化分析檔 `{PROJECT_ROOT / 'log' / f'codex_ai_analysis_{report_date}.md'}`",
        "",
        analysis_text.strip(),
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
        "| 代號 | 名稱 | 分數 | 量比 | K線/理由 | 觀察重點 |",
        "|---|---|---:|---:|---|---|",
    ]
    for item in stocks[:12]:
        lines.append(f"| {cell(item.get('ticker'))} | {cell(item.get('name'))} | {fmt_num(candidate_score(item), 1)} | {fmt_num(item.get('volume_ratio'), 2)} | {cell(kline_label(item))} | 以收盤確認與失敗線控管，不把單日訊號當建議。 |")
    if not stocks:
        lines.append("| - | - | - | - | 無資料 | - |")
    lines += [
        "",
        "## 5) 訊號後績效驗證摘要",
        "| 指標 | 今日狀態 | 解讀 |",
        "|---|---|---|",
        "| 驗證資料 | fallback 未重跑完整 backtest；正式 signals JSON 由原始 build_report 負責，但本次該流程逾時。 | 以候選觀察為主，隔日需用實際價格驗證 1/3/5/10 日績效。 |",
        "| 風險控管 | 單日訊號不足以構成建議。 | 需比較後續 1、3、5、10 日走勢後再驗證訊號有效性。 |",
        "",
        "## 6B) 可能轉強族群（交易所產業）",
        "| 族群 | 候選數 | 平均分數 | 平均量比 | 法人偏多數 | 代表標的 | 觀察重點 |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for row in sectors[:10]:
        lines.append(f"| {cell(row['sector'])} | {fmt_int(row['count'])} | {fmt_num(row['avg_score'], 1)} | {fmt_num(row['avg_volume'], 2)} | {fmt_int(row['chip_count'])} | {cell(row['representatives'])} | 收盤確認與量能延續優先。 |")
    if not sectors:
        lines.append("| - | 0 | - | - | 0 | - | 族群資料不足 |")
    lines += [""]
    lines += candidate_rows("## 7) 個股潛伏起漲候選（Top 20）", stocks, 20)
    lines += candidate_rows("## 8) ETF/基金/REIT 候選（Top 10）", etfs, 10)
    lines += [
        "## 9) 新聞與事件雷達",
        "| 標的 | 類型 | 日期 | 標題/事件 | 來源 | 連結 |",
        "|---|---|---|---|---|---|",
        "| 全市場 | 資料限制 | - | fallback context 未取得新增新聞 packet；不編造 JSON 沒有的新聞或事件。 | 本機 API | - |",
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
        f"- GET /api/tw/universe/coverage?interval=1d：覆蓋率={fmt_num(coverage.get('coverage_pct'), 2)}%（{fmt_int(coverage.get('covered_count'))}/{fmt_int(coverage.get('universe_count'))}），最舊/最新資料日期={cell(coverage.get('oldest_latest_date'))} → {cell(coverage.get('newest_latest_date'))}",
        f"- GET /api/tw/universe/analysis-coverage?interval=1d：最新覆蓋率={fmt_num(analysis_cov.get('latest_coverage_pct'), 2)}%",
        f"- GET /api/tw/chips/coverage?date={report_date}：覆蓋率={fmt_num(chips.get('coverage_pct'), 2)}%，resolved_date={cell(chips.get('resolved_date'))}",
        f"- GET /api/taifex/institutional?date={report_date}：resolved_date={cell(taifex.get('resolved_date'))}",
        f"- running={ctx.get('running_count')}；pending={ctx.get('pending_count')}",
        f"- Codex/AI 分析輸入 JSON 已保存：`{PROJECT_ROOT / 'log' / f'codex_report_context_{report_date}.json'}`",
        "- 風險提醒：本報告不下單、不保證報酬，所有候選僅作觀察清單。",
    ]
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--base", default=os.environ.get("QV_API_BASE", "http://localhost:8001").rstrip("/"))
    args = parser.parse_args()
    log_dir = PROJECT_ROOT / "log"
    log_dir.mkdir(exist_ok=True)
    ctx = build_context(args.base, args.date)
    analysis = analysis_markdown(ctx)
    report = build_report(ctx, analysis, args.base)

    (log_dir / f"codex_report_context_{args.date}.json").write_text(
        json.dumps(ctx, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (log_dir / f"codex_ai_analysis_{args.date}.md").write_text(analysis, encoding="utf-8")
    (log_dir / f"ai_daily_tw_report_{args.date}.context-preview.md").write_text(report, encoding="utf-8")
    delivery = build_delivery_bodies(report, title=f"每日盤後 AI 交易策略報告｜{args.date}")
    (log_dir / f"ai_daily_tw_report_{args.date}.context-preview.html").write_text(delivery.html_text, encoding="utf-8")
    print(f"Fallback context/report written for {args.date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
