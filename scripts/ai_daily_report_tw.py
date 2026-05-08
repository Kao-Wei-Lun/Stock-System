from __future__ import annotations

import argparse
import html
import json
import os
import re
import textwrap
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import signal_validation
except ImportError:  # pragma: no cover - supports importing as scripts.ai_daily_report_tw
    from scripts import signal_validation


def _now_tw() -> datetime:
    return datetime.now(ZoneInfo("Asia/Taipei"))


def _http_json(
    url: str,
    *,
    method: str = "GET",
    json_body: object | None = None,
    timeout: int = 60,
) -> object:
    data = None
    headers: dict[str, str] = {}
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        text = raw.decode("utf-8", errors="replace")
        return json.loads(text)


@dataclass(frozen=True)
class ApiCheck:
    ok: bool
    base_url: str
    error: str | None = None


REPORT_FILE_RE = re.compile(r"^ai_daily_tw_report_(\d{4}-\d{2}-\d{2})\.md$")


def check_api(base_url: str) -> ApiCheck:
    try:
        _http_json(f"{base_url}/api/tw/universe/coverage?interval=1d", timeout=15)
        _http_json(f"{base_url}/api/tw/history/status", timeout=15)
        return ApiCheck(ok=True, base_url=base_url)
    except Exception as exc:  # noqa: BLE001
        return ApiCheck(ok=False, base_url=base_url, error=str(exc))


def _fmt_int(n: int | float | None) -> str:
    if n is None:
        return "—"
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def _fmt_num(n: float | int | None, digits: int = 2) -> str:
    if n is None:
        return "—"
    try:
        return f"{float(n):.{digits}f}"
    except Exception:
        return str(n)


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _table_cell(value: object, *, width: int | None = None) -> str:
    text = "—" if value is None or value == "" else str(value)
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    text = text.replace("|", "｜")
    if width and len(text) > width:
        text = textwrap.shorten(text, width=width, placeholder="…")
    return text


def _ticker_root(ticker: object) -> str:
    raw = str(ticker or "").upper().strip()
    return raw.split(".", 1)[0]


def _instrument_type(item: dict) -> str:
    ticker = str(item.get("ticker") or "")
    root = _ticker_root(ticker)
    name = str(item.get("name") or "")
    sector = str(item.get("sector") or "")
    upper_name = name.upper()
    if root.startswith("IX") or root.startswith("A"):
        return "特殊/指數"
    if root.startswith("00") or "ETF" in upper_name or "ETN" in upper_name:
        return "ETF/ETN"
    if root.startswith("01") or "REIT" in upper_name or "受益證券" in sector:
        return "REIT/受益證券"
    if re.match(r"^[1-9][0-9]{3}[A-Z]?$", root):
        return "個股"
    return "其他"


def _is_common_stock(item: dict) -> bool:
    return _instrument_type(item) == "個股"


def _is_etf_like(item: dict) -> bool:
    return _instrument_type(item) in {"ETF/ETN", "REIT/受益證券"}


def _classify_k(candlestick_score: float | int | None, bias: str | None) -> str:
    score = float(candlestick_score or 0)
    b = (bias or "").lower()
    if b == "bullish" or score >= 45:
        return "偏多"
    if score >= 15:
        return "建設性"
    if score <= -10 or b == "bearish":
        return "偏空"
    return "中性"


def _k_text(item: dict) -> str:
    cp = item.get("candlestick_profile") or {}
    latest = cp.get("latest") or {}
    o = latest.get("open")
    h = latest.get("high")
    l = latest.get("low")
    c = latest.get("close")
    body_pct = latest.get("body_pct")
    close_pos = latest.get("close_position")
    vol_expanded = bool(latest.get("volume_expanded"))
    near_ma20 = bool(latest.get("near_ma20"))
    summary = cp.get("summary") or "未見明確型態"

    def f(x: object) -> str:
        return _fmt_num(x, 2) if isinstance(x, (int, float)) else str(x)

    upper = None
    lower = None
    body = None
    if all(isinstance(v, (int, float)) for v in (o, h, l, c)):
        o_f = float(o)
        h_f = float(h)
        l_f = float(l)
        c_f = float(c)
        body = abs(c_f - o_f)
        upper = h_f - max(o_f, c_f)
        lower = min(o_f, c_f) - l_f

    parts = [
        f"O/H/L/C {f(o)}/{f(h)}/{f(l)}/{f(c)}",
        f"實體={_fmt_num(body, 2)} 上影={_fmt_num(upper, 2)} 下影={_fmt_num(lower, 2)}",
        f"收盤位置={_fmt_num(close_pos, 2)} 實體%={_fmt_num(body_pct, 2)}",
        f"量能={'放大' if vol_expanded else '未放大'}",
        f"均線位置={'貼近/站上MA20' if near_ma20 else '未貼近MA20'}",
        f"型態={summary}",
    ]
    return "；".join(parts)


def _k_trade_plan(item: dict) -> str:
    cp = item.get("candlestick_profile") or {}
    latest = cp.get("latest") or {}
    h = latest.get("high")
    l = latest.get("low")
    ma20 = item.get("ma20")

    trigger = float(h) if isinstance(h, (int, float)) else None
    stop = float(l) if isinstance(l, (int, float)) else None
    if stop is not None and isinstance(ma20, (int, float)):
        stop = max(stop, float(ma20))

    trigger_text = _fmt_num(trigger, 2) if trigger is not None else "—"
    stop_text = _fmt_num(stop, 2) if stop is not None else "—"
    return f"確認：突破{trigger_text}且量不縮；失敗：跌破{stop_text}"


def _chip_text(item: dict) -> str:
    ap = item.get("accumulation_profile") or {}
    chip = ap.get("chip") or {}
    inst5 = chip.get("institutional_5d_sum")
    fore5 = chip.get("foreign_5d_sum")
    it10 = chip.get("investment_trust_10d_sum")
    inst_streak = chip.get("institutional_streak") or {}
    fore_streak = chip.get("foreign_streak") or {}
    inst_dir = inst_streak.get("direction") or "—"
    inst_days = inst_streak.get("days")
    fore_dir = fore_streak.get("direction") or "—"
    fore_days = fore_streak.get("days")
    return (
        f"法人5日{_fmt_int(inst5)} / 外資5日{_fmt_int(fore5)} / 投信10日{_fmt_int(it10)}；"
        f"法人連續{inst_dir}{_fmt_int(inst_days)}日、外資連續{fore_dir}{_fmt_int(fore_days)}日"
    )


def _candidate_reason(item: dict) -> str:
    cp = item.get("candlestick_profile") or {}
    ap = item.get("accumulation_profile") or {}
    latest = cp.get("latest") or {}
    chip = ap.get("chip") or {}
    reasons: list[str] = []
    if item.get("total_score") is not None:
        reasons.append(f"潛伏總分{_fmt_int(item.get('total_score'))}")
    elif item.get("accumulation_score") is not None:
        reasons.append(f"原始潛伏分數{_fmt_int(item.get('accumulation_score'))}")
    if cp.get("summary"):
        reasons.append(f"K線：{cp.get('summary')}")
    if latest.get("volume_expanded"):
        reasons.append("量能放大")
    if latest.get("near_ma20"):
        reasons.append("貼近/站上MA20")
    inst5 = chip.get("institutional_5d_sum")
    fore5 = chip.get("foreign_5d_sum")
    if isinstance(inst5, (int, float)) and inst5 > 0 and isinstance(fore5, (int, float)) and fore5 > 0:
        reasons.append("法人與外資5日同步偏多")
    elif isinstance(inst5, (int, float)) and inst5 > 0:
        reasons.append("法人5日偏多")
    return "；".join(reasons[:5]) or "條件符合但需等待隔日確認"


def _positive_chip(item: dict) -> bool:
    chip = ((item.get("accumulation_profile") or {}).get("chip") or {})
    inst5 = chip.get("institutional_5d_sum") or 0
    fore5 = chip.get("foreign_5d_sum") or 0
    return isinstance(inst5, (int, float)) and isinstance(fore5, (int, float)) and inst5 + fore5 > 0


def _has_breakout_signal(item: dict) -> bool:
    cp = item.get("candlestick_profile") or {}
    labels = []
    for pattern in cp.get("patterns") or []:
        if isinstance(pattern, dict) and pattern.get("label"):
            labels.append(str(pattern.get("label")))
    summary = str(cp.get("summary") or "")
    return any("突破" in label or "轉強" in label or "墊高" in label for label in labels) or any(
        word in summary for word in ("突破", "轉強", "墊高")
    )


def _volume_expanded(item: dict) -> bool:
    return bool(((item.get("candlestick_profile") or {}).get("latest") or {}).get("volume_expanded"))


def _candidates_with_names(base_url: str, candidates_raw: list[object]) -> list[dict]:
    candidates: list[dict] = []
    for raw in candidates_raw:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        ticker = item.get("ticker")
        name = item.get("name") or ""
        if not ticker:
            continue
        if not name or name == ticker:
            try:
                results = _http_json(f"{base_url}/api/search?q={urllib.parse.quote(str(ticker))}", timeout=20)
                if isinstance(results, list):
                    hit = next(
                        (r for r in results if isinstance(r, dict) and r.get("ticker") == ticker and r.get("name")),
                        None,
                    )
                    if hit and hit.get("name") != ticker:
                        name = str(hit.get("name"))
            except Exception:
                pass
        item["name"] = name if name and name != ticker else "名稱待補"
        candidates.append(item)
    return candidates


def _dedupe_candidates(candidates: list[dict]) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for item in candidates:
        ticker = str(item.get("ticker") or "").strip()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        rows.append(item)
    return rows


def _fetch_optional_json(url: str, *, timeout: int = 20) -> dict:
    try:
        obj = _http_json(url, timeout=timeout)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _is_relevant_news_title(ticker: str, name: str, title: object) -> bool:
    title_text = str(title or "").lower()
    root = _ticker_root(ticker).lower()
    clean_name = str(name or "").strip().lower()
    if not title_text:
        return False
    if root and root in title_text:
        return True
    if ticker.lower() in title_text:
        return True
    if clean_name and clean_name != "名稱待補" and clean_name in title_text:
        return True
    return False


def _news_event_digest(base_url: str, ticker: str, *, name: str = "", refresh: bool = False) -> tuple[str, list[dict]]:
    encoded = urllib.parse.quote(ticker)
    refresh_text = "true" if refresh else "false"
    news_payload = _fetch_optional_json(
        f"{base_url}/api/news/{encoded}?limit=3&refresh={refresh_text}",
        timeout=25,
    )
    event_payload = _fetch_optional_json(
        f"{base_url}/api/events/{encoded}?refresh={refresh_text}",
        timeout=25,
    )
    news_items = [item for item in (news_payload.get("items") or []) if isinstance(item, dict)]
    event_items = [item for item in (event_payload.get("items") or []) if isinstance(item, dict)]

    fragments: list[str] = []
    records: list[dict] = []
    for item in news_items[:2]:
        title = item.get("title")
        if not title or not _is_relevant_news_title(ticker, name, title):
            continue
        source = item.get("source") or item.get("summary") or "news"
        published = str(item.get("published_at") or "")[:10]
        fragments.append(f"新聞：{title}（{source} {published}）")
        records.append(
            {
                "ticker": ticker,
                "type": "新聞",
                "date": published or "—",
                "title": title,
                "source": source,
                "url": item.get("url") or "",
            }
        )
    for item in event_items[:2]:
        title = item.get("title") or item.get("event_type")
        if not title:
            continue
        event_date = item.get("event_date") or str(item.get("event_time") or "")[:10]
        fragments.append(f"事件：{title}（{event_date or '未定'}）")
        records.append(
            {
                "ticker": ticker,
                "type": "事件",
                "date": event_date or "—",
                "title": title,
                "source": item.get("source") or "calendar",
                "url": item.get("url") or "",
            }
        )

    return ("；".join(fragments) if fragments else "暫無重大新聞/事件", records)


def _enrich_news_for_candidates(base_url: str, candidates: list[dict], *, refresh_limit: int = 12) -> list[dict]:
    all_records: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(candidates):
        ticker = str(item.get("ticker") or "")
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        digest, records = _news_event_digest(
            base_url,
            ticker,
            name=str(item.get("name") or ""),
            refresh=index < refresh_limit,
        )
        item["news_event_digest"] = digest
        all_records.extend(records)
    return all_records


def _parse_rss_date(value: str) -> datetime | None:
    try:
        return parsedate_to_datetime(value)
    except Exception:
        return None


def _fetch_google_news_records(query: str, *, report_date: str, limit: int = 4) -> list[dict]:
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        req = urllib.request.Request(url=url, headers={"User-Agent": "Mozilla/5.0 QuantVision/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_text = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    records: list[dict] = []
    try:
        target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
    except ValueError:
        target_date = _now_tw().date()
    min_date = target_date - timedelta(days=3)
    max_date = target_date + timedelta(days=1)

    for item in root.findall("./channel/item")[:limit]:
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        published = item.findtext("pubDate") or ""
        published_dt = _parse_rss_date(published)
        published_date = published_dt.date() if published_dt else None
        if published_date and not (min_date <= published_date <= max_date):
            continue
        source_node = item.find("source")
        source = source_node.text if source_node is not None and source_node.text else "Google News"
        if not title:
            continue
        records.append(
            {
                "ticker": "市場/族群",
                "type": "新聞",
                "date": published_date.isoformat() if published_date else "—",
                "title": title,
                "source": source,
                "url": link,
                "query": query,
            }
        )
    return records


def _market_news_records(sector_rows: list[dict], *, report_date: str, limit: int = 12) -> list[dict]:
    queries = [
        f"台股 盤後 法人 期貨 選擇權 {report_date}",
        f"台股 族群 轉強 {report_date}",
        f"台股 半導體 AI 伺服器 {report_date}",
    ]
    for row in sector_rows[:4]:
        sector = str(row.get("sector") or "").strip()
        if sector and sector not in {"其他", "未分類"}:
            queries.append(f"台股 {sector} 轉強 {report_date}")

    records: list[dict] = []
    seen_titles: set[str] = set()
    for query in queries:
        for record in _fetch_google_news_records(query, report_date=report_date, limit=5):
            title = str(record.get("title") or "")
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            records.append(record)
            if len(records) >= limit:
                return records
    return records


def _sector_rotation_rows(candidates: list[dict], *, limit: int = 8) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for item in candidates:
        if not _is_common_stock(item):
            continue
        sector = str(item.get("sector") or item.get("industry") or "未分類")
        buckets.setdefault(sector, []).append(item)

    rows: list[dict] = []
    for sector, items in buckets.items():
        if len(items) < 2:
            continue
        acc_values = [
            float(item.get("total_score") if item.get("total_score") is not None else item.get("accumulation_score") or 0)
            for item in items
        ]
        k_values = [float(item.get("candlestick_score") or 0) for item in items]
        chip_count = sum(1 for item in items if _positive_chip(item))
        breakout_count = sum(1 for item in items if _has_breakout_signal(item))
        volume_count = sum(1 for item in items if _volume_expanded(item))
        avg_acc = sum(acc_values) / len(acc_values)
        avg_k = sum(k_values) / len(k_values)
        rotation_score = avg_acc * 0.45 + avg_k * 0.25 + chip_count / len(items) * 20 + breakout_count / len(items) * 10
        reps = sorted(
            items,
            key=lambda item: (
                item.get("total_score") if item.get("total_score") is not None else item.get("accumulation_score") or 0,
                item.get("candlestick_score") or 0,
                item.get("score") or 0,
            ),
            reverse=True,
        )[:4]
        rows.append(
            {
                "sector": sector,
                "rotation_score": round(rotation_score, 1),
                "count": len(items),
                "avg_acc": round(avg_acc, 1),
                "avg_k": round(avg_k, 1),
                "chip_count": chip_count,
                "breakout_count": breakout_count,
                "volume_count": volume_count,
                "representatives": "、".join(f"{r.get('ticker')} {r.get('name')}" for r in reps),
                "watch": f"觀察族群內強勢股是否續過高；若{sector}代表股跌破當日低點，轉為等待回測",
            }
        )
    return sorted(rows, key=lambda row: row["rotation_score"], reverse=True)[:limit]


def _fetch_recent_daily_rows(base_url: str, ticker: str, *, period: str = "3mo") -> list[dict]:
    encoded = urllib.parse.quote(ticker, safe="")
    payload = _fetch_optional_json(f"{base_url}/api/kline/{encoded}?period={period}&interval=1d", timeout=30)
    rows = payload.get("data") or []
    valid_rows: list[dict] = []
    if not isinstance(rows, list):
        return valid_rows
    for row in rows:
        if not isinstance(row, dict):
            continue
        close = _to_float(row.get("close"))
        if close is None or close <= 0:
            continue
        valid_rows.append(row)
    valid_rows.sort(key=lambda row: str(row.get("date") or ""))
    return valid_rows[-60:]


def _simple_ma(values: list[float], window: int, *, end_index: int | None = None) -> float | None:
    end = len(values) if end_index is None else end_index
    start = end - window
    if window <= 0 or start < 0 or end > len(values):
        return None
    sample = values[start:end]
    if len(sample) != window:
        return None
    return sum(sample) / window


def _ma5_walk_profile(rows: list[dict]) -> dict | None:
    closes = [_to_float(row.get("close")) for row in rows]
    closes = [value for value in closes if value is not None and value > 0]
    if len(closes) < 8:
        return None

    latest_close = closes[-1]
    latest_ma5 = _simple_ma(closes, 5)
    prev_ma5 = _simple_ma(closes, 5, end_index=len(closes) - 3)
    if latest_ma5 is None or prev_ma5 is None or prev_ma5 <= 0:
        return None

    near_days = 0
    above_days = 0
    for index in range(max(4, len(closes) - 5), len(closes)):
        ma5 = _simple_ma(closes, 5, end_index=index + 1)
        if ma5 is None:
            continue
        if closes[index] >= ma5:
            above_days += 1
        if closes[index] >= ma5 * 0.985:
            near_days += 1

    ret5_pct = ((latest_close / closes[-6]) - 1) * 100 if len(closes) >= 6 and closes[-6] else 0.0
    ma5_slope_pct = ((latest_ma5 / prev_ma5) - 1) * 100
    distance_to_ma5_pct = ((latest_close / latest_ma5) - 1) * 100
    latest_row = rows[-1] if rows else {}
    latest_high = _to_float(latest_row.get("high"))
    latest_low = _to_float(latest_row.get("low"))
    qualified = (
        latest_close >= latest_ma5 * 0.995
        and near_days >= 4
        and above_days >= 3
        and ma5_slope_pct > 0
        and ret5_pct > 0
        and distance_to_ma5_pct <= 10
    )
    summary = (
        f"近5日{near_days}日貼/站MA5、{above_days}日收在MA5上；"
        f"MA5斜率{_fmt_num(ma5_slope_pct, 2)}%、5日漲幅{_fmt_num(ret5_pct, 2)}%"
    )
    return {
        "qualified": qualified,
        "latest_close": latest_close,
        "latest_high": latest_high,
        "latest_low": latest_low,
        "ma5": latest_ma5,
        "ma5_slope_pct": ma5_slope_pct,
        "distance_to_ma5_pct": distance_to_ma5_pct,
        "ret5_pct": ret5_pct,
        "near_days": near_days,
        "above_days": above_days,
        "summary": summary,
    }


def _recent_price_profile(rows: list[dict]) -> dict | None:
    if len(rows) < 8:
        return None
    closes = [_to_float(row.get("close")) for row in rows]
    volumes = [_to_float(row.get("volume")) for row in rows]
    if any(value is None or value <= 0 for value in closes[-8:]):
        return None
    close_values = [float(value) for value in closes if value is not None and value > 0]
    if len(close_values) < 8:
        return None

    latest_row = rows[-1]
    latest_close = close_values[-1]
    prev_close = close_values[-2]
    change_pct = ((latest_close / prev_close) - 1) * 100 if prev_close else 0.0
    ret5_pct = ((latest_close / close_values[-6]) - 1) * 100 if len(close_values) >= 6 and close_values[-6] else 0.0
    ma5 = _simple_ma(close_values, 5)
    ma20 = _simple_ma(close_values, 20)
    ma50 = _simple_ma(close_values, 50)
    recent_high = max(close_values[-60:])
    distance_high = ((recent_high / latest_close) - 1) * 100 if latest_close else None

    latest_volume = _to_float(latest_row.get("volume")) or 0.0
    previous_volumes = [float(value) for value in volumes[-21:-1] if value is not None and value > 0]
    if not previous_volumes:
        previous_volumes = [float(value) for value in volumes[:-1] if value is not None and value > 0]
    avg_volume = sum(previous_volumes) / len(previous_volumes) if previous_volumes else None
    volume_ratio = latest_volume / avg_volume if avg_volume and avg_volume > 0 else None

    return {
        "latest_close": latest_close,
        "latest_high": _to_float(latest_row.get("high")),
        "latest_low": _to_float(latest_row.get("low")),
        "change_pct": change_pct,
        "ret5_pct": ret5_pct,
        "volume_ratio": volume_ratio,
        "ma5": ma5,
        "ma20": ma20,
        "ma50": ma50,
        "distance_to_recent_high_pct": distance_high,
    }


def _attach_recent_profiles(base_url: str, candidates: list[dict], *, scan_limit: int = 60) -> list[dict]:
    ranked = sorted(candidates, key=_strong_stock_score, reverse=True)
    scan_tickers = {str(item.get("ticker") or "") for item in ranked[:scan_limit] if item.get("ticker")}
    rows: list[dict] = []
    for item in candidates:
        row = dict(item)
        ticker = str(row.get("ticker") or "")
        if ticker in scan_tickers:
            daily_rows = _fetch_recent_daily_rows(base_url, ticker)
            recent_profile = _recent_price_profile(daily_rows)
            ma5_profile = _ma5_walk_profile(daily_rows)
            if recent_profile:
                row["recent_profile"] = recent_profile
            if ma5_profile:
                row["ma5_profile"] = ma5_profile
        rows.append(row)
    return rows


def _recent_metric(item: dict, profile_key: str, fallback_key: str | None = None) -> float | None:
    profile = item.get("recent_profile") or {}
    value = profile.get(profile_key) if isinstance(profile, dict) else None
    if value is not None:
        return _to_float(value)
    return _to_float(item.get(fallback_key or profile_key))


def _strong_stock_score(item: dict) -> float:
    score = _to_float(item.get("score")) or 0
    change = _recent_metric(item, "change_pct") or 0
    volume_ratio = _recent_metric(item, "volume_ratio") or 0
    distance_high = _recent_metric(item, "distance_to_recent_high_pct", "distance_to_52w_high_pct")
    k_score = _to_float(item.get("candlestick_score")) or 0
    setup = _to_float(item.get("setup_quality")) or 0
    close = _recent_metric(item, "latest_close", "close")
    ma20 = _recent_metric(item, "ma20")
    ma50 = _recent_metric(item, "ma50")
    dist_bonus = max(0.0, 12.0 - max(0.0, distance_high)) if distance_high is not None else 0.0
    trend_bonus = 0.0
    if close is not None and ma20 is not None and close >= ma20:
        trend_bonus += 12
    if ma20 is not None and ma50 is not None and ma20 >= ma50:
        trend_bonus += 12
    chip_bonus = 8 if _positive_chip(item) else 0
    breakout_bonus = 10 if _has_breakout_signal(item) else 0
    return (
        score
        + setup * 0.25
        + max(0.0, change) * 4
        + min(max(volume_ratio, 0.0), 3.5) * 7
        + dist_bonus * 2
        + k_score * 0.2
        + trend_bonus
        + chip_bonus
        + breakout_bonus
    )


def _strong_stock_rows(candidates: list[dict], *, limit: int = 15) -> list[dict]:
    rows: list[dict] = []
    for item in candidates:
        if not _is_common_stock(item):
            continue
        close = _recent_metric(item, "latest_close", "close")
        ma20 = _recent_metric(item, "ma20")
        change = _recent_metric(item, "change_pct") or 0
        distance_high = _recent_metric(item, "distance_to_recent_high_pct", "distance_to_52w_high_pct")
        if close is not None and ma20 is not None and close < ma20:
            continue
        if change < 0 and not _has_breakout_signal(item):
            continue
        if distance_high is not None and distance_high > 25:
            continue
        row = dict(item)
        row["momentum_rank_score"] = round(_strong_stock_score(item), 1)
        rows.append(row)
    return sorted(rows, key=lambda row: row.get("momentum_rank_score") or 0, reverse=True)[:limit]


def _bullish_stock_rows(candidates: list[dict], *, limit: int = 15) -> list[dict]:
    rows: list[dict] = []
    for item in candidates:
        if not _is_common_stock(item):
            continue
        close = _recent_metric(item, "latest_close", "close")
        ma20 = _recent_metric(item, "ma20")
        ma50 = _recent_metric(item, "ma50")
        if close is None or ma20 is None or ma50 is None:
            continue
        if close < ma20 or ma20 < ma50:
            continue
        row = dict(item)
        row["bullish_rank_score"] = round(
            (_to_float(item.get("score")) or 0)
            + (_to_float(item.get("setup_quality")) or 0) * 0.35
            + (_to_float(item.get("accumulation_score")) or 0) * 0.25
            + (_to_float(item.get("candlestick_score")) or 0) * 0.2
            + (8 if _positive_chip(item) else 0),
            1,
        )
        rows.append(row)
    return sorted(rows, key=lambda row: row.get("bullish_rank_score") or 0, reverse=True)[:limit]


def _ma5_walk_stock_rows(base_url: str, candidates: list[dict], *, limit: int = 15, scan_limit: int = 60) -> list[dict]:
    scan_pool = sorted(candidates, key=_strong_stock_score, reverse=True)[:scan_limit]
    rows: list[dict] = []
    for item in scan_pool:
        ticker = str(item.get("ticker") or "")
        if not ticker:
            continue
        profile = item.get("ma5_profile") if isinstance(item.get("ma5_profile"), dict) else None
        if not profile:
            profile = _ma5_walk_profile(_fetch_recent_daily_rows(base_url, ticker))
        if not profile or not profile.get("qualified"):
            continue
        row = dict(item)
        row["ma5_profile"] = profile
        row["ma5_rank_score"] = round(
            profile["ret5_pct"] * 3
            + profile["ma5_slope_pct"] * 5
            + profile["near_days"] * 4
            + profile["above_days"] * 3
            + (_strong_stock_score(item) * 0.15),
            1,
        )
        rows.append(row)
    return sorted(rows, key=lambda row: row.get("ma5_rank_score") or 0, reverse=True)[:limit]


def _trend_reason(item: dict, *, mode: str) -> str:
    close = _recent_metric(item, "latest_close", "close")
    ma20 = _recent_metric(item, "ma20")
    ma50 = _recent_metric(item, "ma50")
    change = _recent_metric(item, "change_pct")
    volume_ratio = _recent_metric(item, "volume_ratio")
    distance_high = _recent_metric(item, "distance_to_recent_high_pct", "distance_to_52w_high_pct")
    parts: list[str] = []
    if close is not None and ma20 is not None:
        parts.append("收盤站上MA20" if close >= ma20 else "收盤低於MA20")
    if ma20 is not None and ma50 is not None:
        parts.append("MA20高於MA50" if ma20 >= ma50 else "MA20低於MA50")
    if mode == "strong" and change is not None and change > 0:
        parts.append(f"日漲幅{_fmt_num(change, 2)}%")
    if mode == "strong" and volume_ratio is not None and volume_ratio >= 1:
        parts.append(f"量比{_fmt_num(volume_ratio, 2)}")
    if distance_high is not None:
        parts.append(f"距近60日/52週高點{_fmt_num(distance_high, 2)}%")
    if _positive_chip(item):
        parts.append("法人/外資合計偏多")
    return "；".join(parts[:5]) or "趨勢條件成立，等待價量確認"


def _momentum_table_lines(title: str, candidates: list[dict], *, mode: str) -> list[str]:
    lines = [title]
    if not candidates:
        lines.append("- （本次沒有符合條件的標的）")
        lines.append("")
        return lines
    score_label = "強勢分數" if mode == "strong" else "多頭分數"
    score_key = "momentum_rank_score" if mode == "strong" else "bullish_rank_score"
    lines.append(
        f"| 代號 | 名稱 | 族群/產業 | 收盤 | 漲跌% | 量比 | 距高點% | {score_label} | 趨勢/篩選說明 | K線/籌碼 | 操作重點 |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---|---|---|")
    for it in candidates:
        lines.append(
            "| "
            + " | ".join(
                [
                    _table_cell(it.get("ticker")),
                    _table_cell(it.get("name")),
                    _table_cell(it.get("sector") or it.get("industry") or "—", width=18),
                    _table_cell(_fmt_num(_recent_metric(it, "latest_close", "close"), 2)),
                    _table_cell(_fmt_num(_recent_metric(it, "change_pct"), 2)),
                    _table_cell(_fmt_num(_recent_metric(it, "volume_ratio"), 2)),
                    _table_cell(_fmt_num(_recent_metric(it, "distance_to_recent_high_pct", "distance_to_52w_high_pct"), 2)),
                    _table_cell(_fmt_num(it.get(score_key), 1)),
                    _table_cell(_trend_reason(it, mode=mode), width=72),
                    _table_cell(f"{_candidate_reason(it)}；{_chip_text(it)}", width=88),
                    _table_cell(_k_trade_plan(it), width=54),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _ma5_walk_table_lines(title: str, candidates: list[dict]) -> list[str]:
    lines = [title]
    if not candidates:
        lines.append("- （本次沒有符合條件的標的）")
        lines.append("")
        return lines
    lines.append("| 代號 | 名稱 | 族群/產業 | 收盤 | MA5 | 5日漲幅% | 距MA5% | 站/貼MA5天數 | MA5斜率% | 型態說明 | 操作重點 |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---|---|")
    for it in candidates:
        profile = it.get("ma5_profile") or {}
        latest_high = profile.get("latest_high")
        latest_low = profile.get("latest_low")
        action = (
            f"續強確認：突破{_fmt_num(latest_high, 2)}且收盤守MA5；"
            f"失敗：跌破MA5 {_fmt_num(profile.get('ma5'), 2)} 或前低 {_fmt_num(latest_low, 2)}"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    _table_cell(it.get("ticker")),
                    _table_cell(it.get("name")),
                    _table_cell(it.get("sector") or it.get("industry") or "—", width=18),
                    _table_cell(_fmt_num(profile.get("latest_close"), 2)),
                    _table_cell(_fmt_num(profile.get("ma5"), 2)),
                    _table_cell(_fmt_num(profile.get("ret5_pct"), 2)),
                    _table_cell(_fmt_num(profile.get("distance_to_ma5_pct"), 2)),
                    _table_cell(f"{_fmt_int(profile.get('above_days'))}/{_fmt_int(profile.get('near_days'))}"),
                    _table_cell(_fmt_num(profile.get("ma5_slope_pct"), 2)),
                    _table_cell(profile.get("summary"), width=78),
                    _table_cell(action, width=64),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _candidate_table_lines(title: str, candidates: list[dict]) -> list[str]:
    lines = [title]
    if not candidates:
        lines.append("- （本次沒有符合條件的標的）")
        lines.append("")
        return lines
    lines.append(
        "| 類型 | 代號 | 名稱 | 族群/產業 | total_score | price_score | breakout_score | volume_score | institutional_score | kline_score | 近1日績效 | 近3日績效 | 近5日績效 | 歷史同類型命中率 | API原始潛伏分 | K線分數 | AI篩選說明 | K線判讀 | 籌碼重點 | 新聞/事件 | 隔日策略 |"
    )
    lines.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|")
    for it in candidates:
        cp = it.get("candlestick_profile") or {}
        k_level = _classify_k(it.get("candlestick_score"), cp.get("bias"))
        sector = it.get("sector") or it.get("industry") or "—"
        k_summary = f"{cp.get('summary') or '未見明確型態'}（{k_level}）"
        lines.append(
            "| "
            + " | ".join(
                [
                    _table_cell(_instrument_type(it)),
                    _table_cell(it.get("ticker")),
                    _table_cell(it.get("name")),
                    _table_cell(sector, width=18),
                    _table_cell(_fmt_int(it.get("total_score"))),
                    _table_cell(_fmt_int(it.get("price_score"))),
                    _table_cell(_fmt_int(it.get("breakout_score"))),
                    _table_cell(_fmt_int(it.get("volume_score"))),
                    _table_cell(_fmt_int(it.get("institutional_score"))),
                    _table_cell(_fmt_int(it.get("kline_score"))),
                    _table_cell(_pct_text(it.get("return_1d"))),
                    _table_cell(_pct_text(it.get("return_3d"))),
                    _table_cell(_pct_text(it.get("return_5d"))),
                    _table_cell(
                        f"{_pct_text(it.get('historical_type_hit_rate'))}"
                        + (
                            f" / n={_fmt_int(it.get('historical_type_sample_size'))}"
                            if it.get("historical_type_sample_size")
                            else ""
                        )
                    ),
                    _table_cell(_fmt_int(it.get("accumulation_score"))),
                    _table_cell(_fmt_int(it.get("candlestick_score"))),
                    _table_cell(_candidate_reason(it), width=76),
                    _table_cell(k_summary + "；" + _k_text(it), width=92),
                    _table_cell(_chip_text(it), width=70),
                    _table_cell(it.get("news_event_digest") or "暫無重大新聞/事件", width=80),
                    _table_cell(_k_trade_plan(it), width=54),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _institutional_table_lines(title: str, candidates: list[dict]) -> list[str]:
    lines = [title]
    if not candidates:
        lines.append("- （本次沒有符合條件的標的）")
        lines.append("")
        return lines

    lines.append("| 類型 | 代號 | 名稱 | 族群/產業 | 法人5日 | 外資5日 | 投信10日 | K線 | 觀察重點 |")
    lines.append("|---|---|---|---|---:|---:|---:|---|---|")
    for it in candidates:
        ap = it.get("accumulation_profile") or {}
        chip = ap.get("chip") or {}
        cp = it.get("candlestick_profile") or {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _table_cell(_instrument_type(it)),
                    _table_cell(it.get("ticker")),
                    _table_cell(it.get("name")),
                    _table_cell(it.get("sector") or it.get("industry") or "—", width=18),
                    _table_cell(_fmt_int(chip.get("institutional_5d_sum"))),
                    _table_cell(_fmt_int(chip.get("foreign_5d_sum"))),
                    _table_cell(_fmt_int(chip.get("investment_trust_10d_sum"))),
                    _table_cell(cp.get("summary") or "—", width=36),
                    _table_cell(_candidate_reason(it), width=72),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_markdown_table_separator(line: str) -> bool:
    cells = _split_markdown_table_row(line)
    if not cells:
        return False
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) is not None for cell in cells)


EMAIL_STYLES = {
    "body": (
        "margin:0;padding:0;background:#f6f8fb;color:#1f2937;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans TC','Microsoft JhengHei',Arial,sans-serif;"
        "line-height:1.55;"
    ),
    "content": "max-width:1180px;margin:0 auto;padding:24px;",
    "h1": "font-size:26px;line-height:1.25;margin:0 0 18px;color:#111827;font-weight:700;",
    "h2": "font-size:20px;margin:28px 0 12px;color:#111827;border-bottom:2px solid #d8dee9;padding-bottom:6px;font-weight:700;",
    "h3": "font-size:16px;margin:20px 0 10px;color:#111827;font-weight:700;",
    "h4": "font-size:15px;margin:16px 0 8px;color:#111827;font-weight:700;",
    "p": "margin:8px 0 12px;",
    "ul": "margin:8px 0 14px;padding-left:22px;",
    "li": "margin:4px 0;",
    "table_wrap": "margin:12px 0 22px;background:#ffffff;",
    "table": "border-collapse:collapse;width:100%;font-size:13px;border:1px solid #9ca3af;",
    "th": "border:1px solid #9ca3af;padding:8px 10px;text-align:left;vertical-align:top;background:#eef2f7;color:#111827;font-weight:700;",
    "td": "border:1px solid #9ca3af;padding:8px 10px;text-align:left;vertical-align:top;background:#ffffff;color:#1f2937;",
    "code": "background:#eef2f7;border-radius:4px;padding:1px 4px;font-family:Consolas,'Courier New',monospace;",
    "a": "color:#2563eb;text-decoration:none;",
}


def _inline_markdown_to_html(text: str) -> str:
    placeholders: list[str] = []

    def hold(value: str) -> str:
        placeholders.append(value)
        return f"\u0000{len(placeholders) - 1}\u0000"

    def replace_link(match: re.Match[str]) -> str:
        label = html.escape(match.group(1), quote=False)
        url = html.escape(match.group(2), quote=True)
        return hold(
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="{EMAIL_STYLES["a"]}">{label}</a>'
        )

    def replace_code(match: re.Match[str]) -> str:
        return hold(f'<code style="{EMAIL_STYLES["code"]}">{html.escape(match.group(1), quote=False)}</code>')

    working = re.sub(r"`([^`]+)`", replace_code, text)
    working = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, working)
    working = html.escape(working, quote=False)
    working = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", working)

    for index, value in enumerate(placeholders):
        working = working.replace(f"\u0000{index}\u0000", value)
    return working


def markdown_to_email_html(markdown_text: str, *, title: str = "每日盤後 AI 交易策略報告") -> str:
    lines = markdown_text.splitlines()
    body: list[str] = []
    paragraph: list[str] = []
    in_list = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(part.strip() for part in paragraph if part.strip())
            body.append(f'<p style="{EMAIL_STYLES["p"]}">{_inline_markdown_to_html(text)}</p>')
            paragraph = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            body.append("</ul>")
            in_list = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            close_list()
            i += 1
            continue

        if stripped.startswith("|"):
            flush_paragraph()
            close_list()
            table_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            if len(table_lines) >= 2 and _is_markdown_table_separator(table_lines[1]):
                headers = _split_markdown_table_row(table_lines[0])
                rows = [_split_markdown_table_row(row) for row in table_lines[2:]]
                body.append(f'<div style="{EMAIL_STYLES["table_wrap"]}"><table style="{EMAIL_STYLES["table"]}">')
                body.append(
                    "<thead><tr>"
                    + "".join(
                        f'<th style="{EMAIL_STYLES["th"]}">{_inline_markdown_to_html(header)}</th>'
                        for header in headers
                    )
                    + "</tr></thead>"
                )
                body.append("<tbody>")
                for row in rows:
                    padded = row + [""] * max(0, len(headers) - len(row))
                    body.append(
                        "<tr>"
                        + "".join(
                            f'<td style="{EMAIL_STYLES["td"]}">{_inline_markdown_to_html(cell)}</td>'
                            for cell in padded[: len(headers)]
                        )
                        + "</tr>"
                    )
                body.append("</tbody></table></div>")
            else:
                for table_line in table_lines:
                    body.append(f'<p style="{EMAIL_STYLES["p"]}">{_inline_markdown_to_html(table_line)}</p>')
            continue

        heading_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading_match:
            flush_paragraph()
            close_list()
            level = min(len(heading_match.group(1)), 4)
            heading_style = EMAIL_STYLES[f"h{level}"]
            body.append(
                f'<h{level} style="{heading_style}">{_inline_markdown_to_html(heading_match.group(2))}</h{level}>'
            )
            i += 1
            continue

        if stripped.startswith("- "):
            flush_paragraph()
            if not in_list:
                body.append(f'<ul style="{EMAIL_STYLES["ul"]}">')
                in_list = True
            body.append(f'<li style="{EMAIL_STYLES["li"]}">{_inline_markdown_to_html(stripped[2:])}</li>')
            i += 1
            continue

        close_list()
        paragraph.append(stripped)
        i += 1

    flush_paragraph()
    close_list()

    escaped_title = html.escape(title, quote=False)
    return (
        "<!doctype html>\n"
        '<html lang="zh-Hant">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{escaped_title}</title>\n"
        "</head>\n"
        f'<body style="{EMAIL_STYLES["body"]}">\n'
        f'<div style="{EMAIL_STYLES["content"]}">\n'
        + "\n".join(body)
        + "\n</div>\n"
        "</body>\n"
        "</html>\n"
    )


def markdown_to_plain_text(markdown_text: str) -> str:
    lines: list[str] = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if _is_markdown_table_separator(line):
            continue
        if line.startswith("|"):
            cells = _split_markdown_table_row(line)
            lines.append("  " + " | ".join(cells))
            continue
        heading_match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading_match:
            lines.append(heading_match.group(2))
            lines.append("-" * min(40, len(heading_match.group(2))))
            continue
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1: \2", line)
        line = line.replace("**", "").replace("`", "")
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def _report_log_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "log"


def _parse_report_date(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()[:10]
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None
    return text


def _recent_report_paths(report_date: str, *, limit: int = 4) -> list[Path]:
    current_date = _parse_report_date(report_date)
    if not current_date:
        return []
    paths: list[tuple[str, Path]] = []
    log_dir = _report_log_dir()
    if not log_dir.exists():
        return []
    for path in log_dir.glob("ai_daily_tw_report_*.md"):
        match = REPORT_FILE_RE.match(path.name)
        if not match:
            continue
        file_date = match.group(1)
        if file_date >= current_date:
            continue
        paths.append((file_date, path))
    paths.sort(key=lambda item: item[0])
    return [path for _, path in paths[-limit:]]


def _clean_price_text(value: object) -> float | None:
    text = str(value or "").strip()
    if not text or text == "—":
        return None
    text = text.replace(",", "")
    match = re.search(r"-?[0-9]+(?:\.[0-9]+)?", text)
    return _to_float(match.group(0)) if match else None


def _price_after_patterns(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = _clean_price_text(match.group(1))
            if value is not None and value > 0:
                return value
    return None


def _looks_like_tw_symbol(ticker: str) -> bool:
    return re.fullmatch(r"[0-9A-Z]{4,8}\.(?:TW|TWO)|IX[0-9A-Z]+\.(?:TW|TWO)|A[0-9A-Z]+\.(?:TW|TWO)", ticker) is not None


def _historical_signal_records_from_report(path: Path) -> list[dict]:
    match = REPORT_FILE_RE.match(path.name)
    if not match:
        return []
    signal_date = match.group(1)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8-sig", errors="replace")

    records: list[dict] = []
    lines = text.splitlines()
    section = ""
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            section = heading.group(2)
            i += 1
            continue
        if (
            not stripped.startswith("|")
            or i + 1 >= len(lines)
            or not _is_markdown_table_separator(lines[i + 1])
        ):
            i += 1
            continue

        headers = _split_markdown_table_row(lines[i])
        header_index = {header: index for index, header in enumerate(headers)}
        if "代號" not in header_index or "訊號驗證" in section or "新聞" in section:
            i += 1
            continue

        j = i + 2
        while j < len(lines) and lines[j].strip().startswith("|"):
            cells = _split_markdown_table_row(lines[j])
            padded = cells + [""] * max(0, len(headers) - len(cells))

            def pick(*names: str) -> str:
                for name in names:
                    index = header_index.get(name)
                    if index is not None and index < len(padded):
                        return padded[index]
                return ""

            ticker = pick("代號").upper().strip()
            if not _looks_like_tw_symbol(ticker):
                j += 1
                continue
            action_text = "；".join(padded)
            close = _clean_price_text(pick("收盤", "最新收盤價"))
            breakout_price = _clean_price_text(pick("突破確認價")) or _price_after_patterns(
                action_text,
                [r"突破\s*([0-9][0-9,]*(?:\.[0-9]+)?)"],
            )
            signal_low = _price_after_patterns(
                action_text,
                [
                    r"前低\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
                    r"跌破(?:MA5\s*)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
                ],
            )
            records.append(
                {
                    "ticker": ticker,
                    "name": pick("名稱"),
                    "sector": pick("族群/產業", "產業"),
                    "signal_date": signal_date,
                    "close": close,
                    "breakout_price": breakout_price,
                    "signal_low": signal_low,
                    "source": "report",
                }
            )
            j += 1
        i = j
    return records


def _load_recent_historical_signals(report_date: str) -> tuple[list[str], list[dict]]:
    paths = _recent_report_paths(report_date, limit=4)
    dates: list[str] = []
    records: list[dict] = []
    for path in paths:
        match = REPORT_FILE_RE.match(path.name)
        if not match:
            continue
        dates.append(match.group(1))
        records.extend(_historical_signal_records_from_report(path))
    return dates, records


def _candlestick_latest_value(item: dict, key: str) -> float | None:
    latest = (item.get("candlestick_profile") or {}).get("latest") or {}
    if isinstance(latest, dict):
        return _to_float(latest.get(key))
    return None


def _candidate_latest_close(item: dict) -> float | None:
    return (
        _recent_metric(item, "latest_close", "close")
        or _to_float((item.get("ma5_profile") or {}).get("latest_close"))
        or _candlestick_latest_value(item, "close")
    )


def _candidate_breakout_price(item: dict) -> float | None:
    return (
        _to_float((item.get("ma5_profile") or {}).get("latest_high"))
        or _recent_metric(item, "latest_high")
        or _candlestick_latest_value(item, "high")
    )


def _candidate_signal_low(item: dict) -> float | None:
    return (
        _to_float((item.get("ma5_profile") or {}).get("latest_low"))
        or _recent_metric(item, "latest_low")
        or _candlestick_latest_value(item, "low")
    )


def _current_signal_record(item: dict, report_date: str) -> dict | None:
    ticker = str(item.get("ticker") or "").upper().strip()
    if not _looks_like_tw_symbol(ticker):
        return None
    return {
        "ticker": ticker,
        "name": item.get("name") or "",
        "sector": item.get("sector") or item.get("industry") or "",
        "signal_date": report_date,
        "close": _candidate_latest_close(item),
        "breakout_price": _candidate_breakout_price(item),
        "signal_low": _candidate_signal_low(item),
        "source": "current",
    }


def _latest_candle(item: dict) -> dict:
    latest = (item.get("candlestick_profile") or {}).get("latest") or {}
    return latest if isinstance(latest, dict) else {}


def _candle_shape(item: dict) -> dict[str, float | None | bool]:
    latest = _latest_candle(item)
    open_price = _to_float(latest.get("open"))
    high = _to_float(latest.get("high"))
    low = _to_float(latest.get("low"))
    close = _to_float(latest.get("close")) or _candidate_latest_close(item)
    body = upper = lower = None
    is_red = is_black = long_upper = False
    if all(value is not None for value in (open_price, high, low, close)):
        open_f = float(open_price)
        high_f = float(high)
        low_f = float(low)
        close_f = float(close)
        body = abs(close_f - open_f)
        upper = high_f - max(open_f, close_f)
        lower = min(open_f, close_f) - low_f
        is_red = close_f >= open_f
        is_black = close_f < open_f
        long_upper = upper > max(body or 0.0, high_f * 0.003) * 1.2
    return {
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "body": body,
        "upper": upper,
        "lower": lower,
        "is_red": is_red,
        "is_black": is_black,
        "long_upper": long_upper,
    }


def _candidate_score_breakdown(item: dict, validation: dict | None = None) -> dict[str, int]:
    # price_score: measures whether price is already above, near, or invalidating the breakout line.
    close = _candidate_latest_close(item)
    breakout_price = _candidate_breakout_price(item)
    signal_low = _candidate_signal_low(item)
    if validation:
        close = _to_float(validation.get("latest_close")) or close
        breakout_price = _to_float(validation.get("breakout_price")) or breakout_price

    if close is None or close <= 0:
        price_score = 10
    elif signal_low is not None and close < signal_low:
        price_score = 0
    elif breakout_price is not None and breakout_price > 0 and close > breakout_price:
        price_score = 30
    elif breakout_price is not None and breakout_price > 0 and abs((breakout_price - close) / breakout_price) <= 0.015:
        price_score = 20
    else:
        price_score = 10

    # breakout_score: rewards confirmed breakouts more than one-day or intraday-only breakouts.
    candle = _candle_shape(item)
    high = candle.get("high")
    breakout_hold_days = int((validation or {}).get("breakout_hold_days") or 0)
    breakout_confirmed = bool((validation or {}).get("breakout_confirmed"))
    intraday_break = (
        isinstance(high, (int, float))
        and breakout_price is not None
        and breakout_price > 0
        and high > breakout_price
    )
    if breakout_confirmed and breakout_hold_days >= 2:
        breakout_score = 25
    elif breakout_price is not None and close is not None and close > breakout_price:
        breakout_score = 18
    elif intraday_break:
        breakout_score = 8
    else:
        breakout_score = 5

    # volume_score: separates healthy red-candle volume expansion from upper-shadow or heavy black-candle risk.
    volume_expanded = _volume_expanded(item)
    volume_ratio = _recent_metric(item, "volume_ratio")
    is_red = bool(candle.get("is_red"))
    is_black = bool(candle.get("is_black"))
    long_upper = bool(candle.get("long_upper"))
    if volume_expanded and is_black and (volume_ratio is None or volume_ratio >= 2.0):
        volume_score = 0
    elif volume_expanded and long_upper:
        volume_score = 10
    elif volume_expanded and is_red:
        volume_score = 20
    elif volume_expanded:
        volume_score = 10
    else:
        volume_score = 5

    # institutional_score: checks whether institutional flow and foreign flow are aligned.
    chip = ((item.get("accumulation_profile") or {}).get("chip") or {})
    inst5 = chip.get("institutional_5d_sum")
    fore5 = chip.get("foreign_5d_sum")
    inst_positive = isinstance(inst5, (int, float)) and inst5 > 0
    fore_positive = isinstance(fore5, (int, float)) and fore5 > 0
    if inst_positive and fore_positive:
        institutional_score = 15
    elif inst_positive or fore_positive:
        institutional_score = 8
    else:
        institutional_score = 0

    # kline_score: keeps the original pattern reading, but compresses it into a 0-10 score.
    cp = item.get("candlestick_profile") or {}
    summary = str(cp.get("summary") or "")
    if any(word in summary for word in ("明確轉弱", "跌破", "轉弱")):
        kline_score = 0
    elif any(word in summary for word in ("弱勢黑K", "長上影")) or (long_upper and is_black):
        kline_score = 2
    elif any(word in summary for word in ("十字", "錘子", "母子", "收斂")):
        kline_score = 6
    elif any(word in summary for word in ("強勢紅K收高", "低點墊高", "收盤轉強", "突破嘗試")):
        kline_score = 10
    else:
        kline_score = 6 if is_red else 2

    total_score = price_score + breakout_score + volume_score + institutional_score + kline_score
    return {
        "price_score": price_score,
        "breakout_score": breakout_score,
        "volume_score": volume_score,
        "institutional_score": institutional_score,
        "kline_score": kline_score,
        "total_score": total_score,
    }


def _attach_candidate_scores(candidates: list[dict], validation_by_ticker: dict[str, dict] | None = None) -> list[dict]:
    validation_by_ticker = validation_by_ticker or {}
    rows: list[dict] = []
    for item in candidates:
        row = dict(item)
        ticker = str(row.get("ticker") or "").upper().strip()
        row.update(_candidate_score_breakdown(row, validation_by_ticker.get(ticker)))
        rows.append(row)
    return rows


def _sort_candidates_by_total_score(
    candidates: list[dict],
    validation_by_ticker: dict[str, dict] | None = None,
) -> list[dict]:
    status_rank = {
        "confirmed_uptrend": 0,
        "new_breakout": 1,
        "watch_only": 2,
        "failed_breakout": 3,
        "invalidated": 4,
    }
    validation_by_ticker = validation_by_ticker or {}

    def rank(item: tuple[int, dict]) -> tuple[float, int, int]:
        index, candidate = item
        ticker = str(candidate.get("ticker") or "").upper().strip()
        status = (validation_by_ticker.get(ticker) or {}).get("signal_status")
        return (
            -float(candidate.get("total_score") or 0),
            status_rank.get(str(status), 9),
            index,
        )

    return [candidate for _, candidate in sorted(enumerate(candidates), key=rank)]


def _signal_record_from_candidate(report_date: str, item: dict, validation: dict | None = None) -> dict | None:
    ticker = str(item.get("ticker") or "").upper().strip()
    if not ticker:
        return None
    validation = validation or {}
    return {
        "ticker": ticker,
        "name": item.get("name") or "",
        "sector": item.get("sector") or item.get("industry") or "",
        "instrument_type": _instrument_type(item),
        "signal_date": report_date,
        "close": _to_float(validation.get("latest_close")) or _candidate_latest_close(item),
        "breakout_price": _to_float(validation.get("breakout_price")) or _candidate_breakout_price(item),
        "signal_low": _candidate_signal_low(item),
        "ma20": _recent_metric(item, "ma20") or _to_float(item.get("ma20")),
        "signal_status": validation.get("signal_status") or "watch_only",
        "price_score": item.get("price_score"),
        "breakout_score": item.get("breakout_score"),
        "volume_score": item.get("volume_score"),
        "institutional_score": item.get("institutional_score"),
        "kline_score": item.get("kline_score"),
        "total_score": item.get("total_score"),
    }


def _daily_signal_records(
    report_date: str,
    candidates: list[dict],
    validation_by_ticker: dict[str, dict],
) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    for item in candidates:
        ticker = str(item.get("ticker") or "").upper().strip()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        record = _signal_record_from_candidate(report_date, item, validation_by_ticker.get(ticker))
        if record:
            records.append(record)
    return records


def _pct_text(value: object) -> str:
    number = _to_float(value)
    if number is None:
        return "—"
    return f"{number:.2f}%"


def _attach_signal_backtest_fields(
    candidates: list[dict],
    latest_backtest_by_ticker: dict[str, dict],
    status_hit_rates: dict[str, dict],
    validation_by_ticker: dict[str, dict],
) -> list[dict]:
    rows: list[dict] = []
    for item in candidates:
        row = dict(item)
        ticker = str(row.get("ticker") or "").upper().strip()
        latest = latest_backtest_by_ticker.get(ticker) or {}
        status = (validation_by_ticker.get(ticker) or {}).get("signal_status") or latest.get("signal_status") or "unknown"
        status_hit = status_hit_rates.get(str(status)) or {}
        row["return_1d"] = latest.get("return_1d")
        row["return_3d"] = latest.get("return_3d")
        row["return_5d"] = latest.get("return_5d")
        row["historical_type_hit_rate"] = status_hit.get("hit_rate")
        row["historical_type_sample_size"] = status_hit.get("sample_size")
        rows.append(row)
    return rows


def _signal_backtest_summary_lines(title: str, summary: dict, *, error: str | None = None) -> list[str]:
    lines = [title]
    if error:
        lines.append(f"- 訊號後績效驗證暫時無法計算：{_table_cell(error, width=120)}")
        lines.append("")
        return lines
    lines.append(
        "| 今日候選數 | 近20日樣本交易日 | 已驗證訊號數 | 近20日平均1日命中率 | 近20日平均3日命中率 | 近20日平均5日命中率 | confirmed_uptrend平均報酬 | failed_breakout比例 |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    lines.append(
        "| "
        + " | ".join(
            [
                _table_cell(_fmt_int(summary.get("today_signal_count"))),
                _table_cell(_fmt_int(summary.get("lookback_signal_days"))),
                _table_cell(_fmt_int(summary.get("evaluated_signal_count"))),
                _table_cell(_pct_text(summary.get("avg_hit_1d"))),
                _table_cell(_pct_text(summary.get("avg_hit_3d"))),
                _table_cell(_pct_text(summary.get("avg_hit_5d"))),
                _table_cell(_pct_text(summary.get("confirmed_uptrend_avg_return"))),
                _table_cell(_pct_text(summary.get("failed_breakout_ratio"))),
            ]
        )
        + " |"
    )
    lines.append("")
    lines.append("- 命中率只統計已有後續交易日可驗證的訊號；今日新訊號會先保存，等後續交易日再納入績效。")
    lines.append("")
    return lines


def _latest_row_on_or_before(rows: list[dict], target_date: str) -> tuple[int, dict] | None:
    if not rows:
        return None
    target = _parse_report_date(target_date)
    if not target:
        return len(rows) - 1, rows[-1]
    selected: tuple[int, dict] | None = None
    for index, row in enumerate(rows):
        row_date = _parse_report_date(row.get("date"))
        if row_date and row_date <= target:
            selected = (index, row)
    return selected or (len(rows) - 1, rows[-1])


def _first_row_on_or_after(rows: list[dict], target_date: str) -> tuple[int, dict] | None:
    target = _parse_report_date(target_date)
    if not rows or not target:
        return None
    for index, row in enumerate(rows):
        row_date = _parse_report_date(row.get("date"))
        if row_date and row_date >= target:
            return index, row
    return len(rows) - 1, rows[-1]


def _ma_from_rows(rows: list[dict], end_index: int, window: int) -> float | None:
    closes = [_to_float(row.get("close")) for row in rows[: end_index + 1]]
    close_values = [float(value) for value in closes if value is not None and value > 0]
    return _simple_ma(close_values, window)


def _signal_status_label(status: str) -> str:
    labels = {
        "confirmed_uptrend": "confirmed_uptrend",
        "new_breakout": "new_breakout",
        "watch_only": "watch_only",
        "failed_breakout": "failed_breakout",
        "invalidated": "invalidated",
    }
    return labels.get(status, status or "watch_only")


def _signal_observation(status: str, row: dict) -> str:
    if status == "confirmed_uptrend":
        return "續強優先觀察；回測確認價不破可續抱，跌破改降風險。"
    if status == "new_breakout":
        return "剛突破，隔日需量能與收盤續站確認價。"
    if status == "watch_only":
        return "連續入選但尚未突破，等待帶量站上確認價。"
    if status == "failed_breakout":
        return "曾突破但收回確認價下，先觀察是否重新站回。"
    if status == "invalidated":
        return "跌破低點或MA20，暫不追蹤為進攻名單。"
    return "維持觀察。"


def _calculate_signal_validation(
    *,
    base_url: str,
    current_candidates: list[dict],
    report_date: str,
    limit: int = 40,
) -> tuple[list[dict], dict[str, dict]]:
    historical_dates, historical_records = _load_recent_historical_signals(report_date)
    current_records = [
        record
        for item in current_candidates
        if (record := _current_signal_record(item, report_date)) is not None
    ]
    window_dates = sorted({*historical_dates, report_date})[-5:]
    last3_dates = set(window_dates[-3:])
    allowed_dates = set(window_dates)

    grouped: dict[str, list[dict]] = {}
    for record in historical_records + current_records:
        signal_date = _parse_report_date(record.get("signal_date"))
        ticker = str(record.get("ticker") or "").upper().strip()
        if not signal_date or signal_date not in allowed_dates or not ticker:
            continue
        grouped.setdefault(ticker, []).append(record)

    rows: list[dict] = []
    price_cache: dict[str, list[dict]] = {}
    for ticker, records in grouped.items():
        records.sort(key=lambda record: str(record.get("signal_date") or ""))
        signal_dates = sorted({_parse_report_date(record.get("signal_date")) for record in records if _parse_report_date(record.get("signal_date"))})
        if not signal_dates:
            continue
        first_signal_date = signal_dates[0]
        latest_signal_date = signal_dates[-1]
        latest_signal_record = records[-1]
        first_signal_record = records[0]

        daily_rows = price_cache.setdefault(ticker, _fetch_recent_daily_rows(base_url, ticker, period="6mo"))
        latest_pair = _latest_row_on_or_before(daily_rows, report_date)
        first_pair = _first_row_on_or_after(daily_rows, first_signal_date)
        latest_index = latest_pair[0] if latest_pair else -1
        latest_row = latest_pair[1] if latest_pair else {}
        first_row = first_pair[1] if first_pair else {}
        latest_trade_date = _parse_report_date(latest_row.get("date")) or report_date

        first_close = _to_float(first_signal_record.get("close")) or _to_float(first_row.get("close"))
        latest_close = _to_float(latest_row.get("close")) or _to_float(latest_signal_record.get("close"))
        breakout_price = _to_float(latest_signal_record.get("breakout_price"))
        if breakout_price is None:
            breakout_price = _to_float(first_signal_record.get("breakout_price"))
        if breakout_price is None:
            breakout_price = _to_float(latest_row.get("high"))
        signal_low = _to_float(first_signal_record.get("signal_low")) or _to_float(first_row.get("low"))
        latest_ma20 = _ma_from_rows(daily_rows, latest_index, 20) if latest_index >= 0 else None

        if first_close is None or first_close <= 0 or latest_close is None or latest_close <= 0:
            continue
        if breakout_price is None or breakout_price <= 0:
            breakout_price = latest_close

        period_rows = [
            row
            for row in daily_rows
            if (row_date := _parse_report_date(row.get("date")))
            and row_date >= first_signal_date
            and row_date <= latest_trade_date
        ]
        if not period_rows and latest_row:
            period_rows = [latest_row]

        max_high = max((_to_float(row.get("high")) or _to_float(row.get("close")) or first_close) for row in period_rows)
        max_gain = ((max_high / first_close) - 1) * 100 if max_high and first_close else 0.0
        price_change = ((latest_close / first_close) - 1) * 100

        running_high = first_close
        max_drawdown = 0.0
        ever_broke = False
        breakout_hold_days = 0
        for row in period_rows:
            high = _to_float(row.get("high")) or _to_float(row.get("close")) or running_high
            low = _to_float(row.get("low")) or _to_float(row.get("close")) or running_high
            close = _to_float(row.get("close"))
            running_high = max(running_high, high)
            if running_high > 0:
                max_drawdown = min(max_drawdown, ((low / running_high) - 1) * 100)
            if close is not None and close > breakout_price:
                ever_broke = True

        for row in reversed(period_rows):
            close = _to_float(row.get("close"))
            if close is not None and close > breakout_price:
                breakout_hold_days += 1
            else:
                break

        breakout_confirmed = latest_close > breakout_price
        invalidated = False
        if signal_low is not None and latest_close < signal_low:
            invalidated = True
        if latest_ma20 is not None and latest_close < latest_ma20:
            invalidated = True

        signal_days_5 = len(set(signal_dates[-5:]))
        signal_days_3 = len({date for date in signal_dates if date in last3_dates})

        if invalidated:
            status = "invalidated"
        elif ever_broke and latest_close <= breakout_price:
            status = "failed_breakout"
        elif signal_days_5 >= 2 and breakout_confirmed and breakout_hold_days >= 2:
            status = "confirmed_uptrend"
        elif breakout_confirmed and breakout_hold_days < 2:
            status = "new_breakout"
        elif signal_days_5 >= 2 and not breakout_confirmed:
            status = "watch_only"
        else:
            status = "watch_only"

        row = {
            "ticker": ticker,
            "name": latest_signal_record.get("name") or first_signal_record.get("name") or "",
            "sector": latest_signal_record.get("sector") or first_signal_record.get("sector") or "",
            "signal_days_3": signal_days_3,
            "signal_days_5": signal_days_5,
            "first_signal_date": first_signal_date,
            "latest_signal_date": latest_signal_date,
            "latest_close": latest_close,
            "breakout_price": breakout_price,
            "price_change_since_first_signal": price_change,
            "max_gain_after_signal": max_gain,
            "drawdown_after_signal": max_drawdown,
            "breakout_confirmed": breakout_confirmed,
            "breakout_hold_days": breakout_hold_days,
            "signal_status": status,
        }
        row["observation"] = _signal_observation(status, row)
        rows.append(row)

    status_rank = {
        "confirmed_uptrend": 0,
        "new_breakout": 1,
        "watch_only": 2,
        "failed_breakout": 3,
        "invalidated": 4,
    }
    rows.sort(
        key=lambda row: (
            status_rank.get(str(row.get("signal_status")), 9),
            -int(row.get("signal_days_5") or 0),
            -float(row.get("max_gain_after_signal") or 0),
            str(row.get("ticker") or ""),
        )
    )
    limited_rows = rows[:limit]
    return limited_rows, {str(row.get("ticker")): row for row in rows}


def _sort_candidates_by_signal_status(candidates: list[dict], validation_by_ticker: dict[str, dict]) -> list[dict]:
    status_rank = {
        "confirmed_uptrend": 0,
        "new_breakout": 1,
        "watch_only": 2,
        "failed_breakout": 3,
        "invalidated": 4,
    }

    def rank(item: tuple[int, dict]) -> tuple[int, int]:
        index, candidate = item
        ticker = str(candidate.get("ticker") or "").upper().strip()
        status = (validation_by_ticker.get(ticker) or {}).get("signal_status")
        return status_rank.get(str(status), 9), index

    return [candidate for _, candidate in sorted(enumerate(candidates), key=rank)]


def _signal_validation_table_lines(title: str, rows: list[dict]) -> list[str]:
    lines = [title]
    if not rows:
        lines.append("- （近 5 個可用報告日尚無足夠訊號可比對。）")
        lines.append("")
        return lines
    lines.append(
        "| 代號 | 名稱 | 產業 | 近 3 日入選次數 | 近 5 日入選次數 | 第一次訊號日 | 最新收盤價 | 突破確認價 | 訊號後漲跌幅 | 最大漲幅 | 最大回落 | 狀態 | 觀察建議 |"
    )
    lines.append("|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|---|")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _table_cell(row.get("ticker")),
                    _table_cell(row.get("name")),
                    _table_cell(row.get("sector") or "—", width=18),
                    _table_cell(_fmt_int(row.get("signal_days_3"))),
                    _table_cell(_fmt_int(row.get("signal_days_5"))),
                    _table_cell(row.get("first_signal_date")),
                    _table_cell(_fmt_num(row.get("latest_close"), 2)),
                    _table_cell(_fmt_num(row.get("breakout_price"), 2)),
                    _table_cell(f"{_fmt_num(row.get('price_change_since_first_signal'), 2)}%"),
                    _table_cell(f"{_fmt_num(row.get('max_gain_after_signal'), 2)}%"),
                    _table_cell(f"{_fmt_num(row.get('drawdown_after_signal'), 2)}%"),
                    _table_cell(_signal_status_label(str(row.get("signal_status") or ""))),
                    _table_cell(row.get("observation"), width=68),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _get_spot_card(taifex: dict, ticker: str) -> dict | None:
    for card in taifex.get("spot_reference") or []:
        if card.get("ticker") == ticker:
            return card
    return None


def _summarize_taifex_position(structured: dict) -> str:
    def pick(section: dict, inst: str) -> dict:
        for row in section.get("items") or []:
            if row.get("institution") == inst:
                return row
        return {}

    fut = structured.get("futures") or {}
    opt = structured.get("options") or {}
    fut_fx = pick(fut, "外資")
    fut_it = pick(fut, "投信")
    fut_dl = pick(fut, "自營商")
    opt_fx = pick(opt, "外資")
    opt_it = pick(opt, "投信")
    opt_dl = pick(opt, "自營商")

    return (
        "臺股期貨(外資/投信/自營商)日盤淨口數="
        f"{_fmt_int(fut_fx.get('trade_net_volume'))}/"
        f"{_fmt_int(fut_it.get('trade_net_volume'))}/"
        f"{_fmt_int(fut_dl.get('trade_net_volume'))}；"
        "OI淨口數="
        f"{_fmt_int(fut_fx.get('oi_net_volume'))}/"
        f"{_fmt_int(fut_it.get('oi_net_volume'))}/"
        f"{_fmt_int(fut_dl.get('oi_net_volume'))}。"
        "臺指選擇權(外資/投信/自營商)日盤淨口數="
        f"{_fmt_int(opt_fx.get('trade_net_volume'))}/"
        f"{_fmt_int(opt_it.get('trade_net_volume'))}/"
        f"{_fmt_int(opt_dl.get('trade_net_volume'))}；"
        "OI淨口數="
        f"{_fmt_int(opt_fx.get('oi_net_volume'))}/"
        f"{_fmt_int(opt_it.get('oi_net_volume'))}/"
        f"{_fmt_int(opt_dl.get('oi_net_volume'))}"
    )


def build_report(*, base_url: str, report_date: str) -> str:
    coverage = _http_json(f"{base_url}/api/tw/universe/coverage?interval=1d", timeout=30)
    history_status = _http_json(f"{base_url}/api/tw/history/status?interval=1d&limit=5000", timeout=60)

    cov = coverage if isinstance(coverage, dict) else {}
    hs = history_status if isinstance(history_status, dict) else {}

    status_items = hs.get("items") or []
    status_counts = Counter(
        it.get("status") for it in status_items if isinstance(it, dict) and it.get("status") is not None
    )
    non_success = sum(status_counts.get(k, 0) for k in ("pending", "running", "empty", "failed"))

    cov_pct = float(cov.get("coverage_pct") or 0)
    covered_count = int(cov.get("covered_count") or 0)
    universe_count = int(cov.get("universe_count") or 0)
    oldest_latest = cov.get("oldest_latest_date")
    newest_latest = cov.get("newest_latest_date")

    data_pool_incomplete = cov_pct < 95.0 or non_success > 0

    screener = _http_json(
        f"{base_url}/api/screener/run",
        method="POST",
        json_body={
            "filters": {
                "market": "TW",
                "setup_type": "accumulation",
                "sort_by": "accumulation_score",
                "limit": 200,
            }
        },
        timeout=180,
    )
    sc = screener if isinstance(screener, dict) else {}
    candidates_raw = sc.get("items") or []
    market_context = sc.get("market_context") if isinstance(sc.get("market_context"), dict) else {}

    momentum_candidates: list[dict] = []
    try:
        momentum_screener = _http_json(
            f"{base_url}/api/screener/run",
            method="POST",
            json_body={
                "filters": {
                    "market": "TW",
                    "setup_type": "any",
                    "sort_by": "score",
                    "limit": 350,
                }
            },
            timeout=180,
        )
        ms = momentum_screener if isinstance(momentum_screener, dict) else {}
        momentum_candidates = _candidates_with_names(base_url, ms.get("items") or [])
    except Exception:
        momentum_candidates = []

    # Optional TAIFEX
    taifex: dict | None = None
    structured: dict = {"futures": {"items": []}, "options": {"items": []}}
    try:
        taifex_obj = _http_json(f"{base_url}/api/taifex/institutional?date={report_date}", timeout=60)
        taifex = taifex_obj if isinstance(taifex_obj, dict) else None
    except Exception:
        taifex = None
    try:
        fut_url = (
            f"{base_url}/api/taifex/structured/futures?date={report_date}&commodity="
            + urllib.parse.quote("臺股期貨")
            + "&limit=50"
        )
        opt_url = (
            f"{base_url}/api/taifex/structured/options?date={report_date}&commodity="
            + urllib.parse.quote("臺指選擇權")
            + "&limit=50"
        )
        structured["futures"] = _http_json(fut_url, timeout=60)
        structured["options"] = _http_json(opt_url, timeout=60)
    except Exception:
        pass

    twii = _get_spot_card(taifex or {}, "^TWII") if taifex else None
    twoii = _get_spot_card(taifex or {}, "^TWOII") if taifex else None

    # Candidates + name fixup
    candidates = _candidates_with_names(base_url, candidates_raw)
    candidates = _sort_candidates_by_total_score(_attach_candidate_scores(candidates))
    momentum_pool = _dedupe_candidates(momentum_candidates + candidates)
    if not momentum_pool:
        momentum_pool = candidates
    common_momentum_pool = [item for item in momentum_pool if _is_common_stock(item)]
    common_momentum_pool = _attach_recent_profiles(base_url, common_momentum_pool, scan_limit=60)
    profiled_common_pool = [item for item in common_momentum_pool if item.get("recent_profile")] or common_momentum_pool
    stock_candidates = [item for item in candidates if _is_common_stock(item)]
    etf_candidates = [item for item in candidates if _is_etf_like(item)]
    selected_stocks = stock_candidates[:20]
    selected_etfs = etf_candidates[:10]
    strong_stock_candidates = _strong_stock_rows(profiled_common_pool, limit=15)
    bullish_stock_candidates = _bullish_stock_rows(profiled_common_pool, limit=15)
    ma5_walk_candidates = _ma5_walk_stock_rows(base_url, profiled_common_pool, limit=15, scan_limit=60)
    strong_stock_candidates = _attach_candidate_scores(strong_stock_candidates)
    bullish_stock_candidates = _attach_candidate_scores(bullish_stock_candidates)
    ma5_walk_candidates = _attach_candidate_scores(ma5_walk_candidates)
    validation_source = _dedupe_candidates(
        selected_stocks + selected_etfs + strong_stock_candidates + bullish_stock_candidates + ma5_walk_candidates
    )
    signal_validation_rows, signal_validation_by_ticker = _calculate_signal_validation(
        base_url=base_url,
        current_candidates=validation_source,
        report_date=report_date,
    )
    candidates = _sort_candidates_by_total_score(_attach_candidate_scores(candidates, signal_validation_by_ticker), signal_validation_by_ticker)
    selected_stocks = _sort_candidates_by_total_score(
        _attach_candidate_scores(selected_stocks, signal_validation_by_ticker),
        signal_validation_by_ticker,
    )
    selected_etfs = _sort_candidates_by_total_score(
        _attach_candidate_scores(selected_etfs, signal_validation_by_ticker),
        signal_validation_by_ticker,
    )
    strong_stock_candidates = _sort_candidates_by_total_score(
        _attach_candidate_scores(strong_stock_candidates, signal_validation_by_ticker),
        signal_validation_by_ticker,
    )
    bullish_stock_candidates = _sort_candidates_by_total_score(
        _attach_candidate_scores(bullish_stock_candidates, signal_validation_by_ticker),
        signal_validation_by_ticker,
    )
    ma5_walk_candidates = _sort_candidates_by_total_score(
        _attach_candidate_scores(ma5_walk_candidates, signal_validation_by_ticker),
        signal_validation_by_ticker,
    )
    sector_rows = _sector_rotation_rows(candidates)
    daily_signal_candidates = _dedupe_candidates(
        selected_stocks + selected_etfs + strong_stock_candidates + bullish_stock_candidates + ma5_walk_candidates
    )
    daily_signals = _daily_signal_records(report_date, daily_signal_candidates, signal_validation_by_ticker)
    signal_file: Path | None = None
    signal_store_error: str | None = None
    try:
        signal_file = signal_validation.save_daily_signals(
            _report_log_dir(),
            report_date,
            daily_signals,
            meta={"source": "ai_daily_report_tw", "base_url": base_url},
        )
    except Exception as exc:  # noqa: BLE001
        signal_store_error = str(exc)

    signal_backtest_error: str | None = None
    signal_backtest_summary: dict = {
        "today_signal_count": len(daily_signals),
        "lookback_signal_days": 0,
        "evaluated_signal_count": 0,
        "avg_hit_1d": None,
        "avg_hit_3d": None,
        "avg_hit_5d": None,
        "confirmed_uptrend_avg_return": None,
        "failed_breakout_ratio": None,
    }
    latest_backtests_by_ticker: dict[str, dict] = {}
    status_hit_rates: dict[str, dict] = {}
    try:
        payloads = signal_validation.load_signal_payloads(_report_log_dir(), before_or_on=report_date, limit=20)
        signal_backtests = signal_validation.compute_backtests(
            payloads,
            lambda ticker: _fetch_recent_daily_rows(base_url, ticker, period="6mo"),
            as_of_date=report_date,
        )
        signal_backtest_summary = signal_validation.summarize_backtests(
            signal_backtests,
            today_count=len(daily_signals),
            lookback_days=20,
        )
        latest_backtests_by_ticker = signal_validation.latest_backtest_by_ticker(signal_backtests)
        status_hit_rates = signal_validation.hit_rate_by_status(signal_backtests, hit_key="hit_5d")
    except Exception as exc:  # noqa: BLE001
        signal_backtest_error = str(exc)

    selected_stocks = _attach_signal_backtest_fields(
        selected_stocks,
        latest_backtests_by_ticker,
        status_hit_rates,
        signal_validation_by_ticker,
    )
    selected_etfs = _attach_signal_backtest_fields(
        selected_etfs,
        latest_backtests_by_ticker,
        status_hit_rates,
        signal_validation_by_ticker,
    )
    selected_candidates = selected_stocks + selected_etfs
    news_records = _enrich_news_for_candidates(base_url, selected_candidates, refresh_limit=12)
    market_news = _market_news_records(sector_rows, report_date=report_date)

    # Institutional bullish (simple)
    inst_bullish: list[dict] = []
    for it in selected_candidates:
        ap = it.get("accumulation_profile") or {}
        chip = ap.get("chip") or {}
        inst5 = chip.get("institutional_5d_sum") or 0
        fore5 = chip.get("foreign_5d_sum") or 0
        if isinstance(inst5, (int, float)) and inst5 > 0 and isinstance(fore5, (int, float)) and fore5 > 0:
            inst_bullish.append(it)
    inst_bullish.sort(
        key=lambda x: ((x.get("accumulation_profile") or {}).get("chip") or {}).get("institutional_5d_sum") or 0,
        reverse=True,
    )
    inst_bullish_stocks = [item for item in inst_bullish if _is_common_stock(item)]
    inst_bullish_etfs = [item for item in inst_bullish if _is_etf_like(item)]

    # Report assembly
    lines: list[str] = []
    dt_tw = _now_tw().strftime("%Y-%m-%d %H:%M")
    lines.append(f"# 每日盤後 AI 交易策略報告（台股）｜{report_date}")
    lines.append(f"生成時間（台北）：{dt_tw}")
    lines.append("")

    lines.append("## 0) API / 資料池檢查（必讀）")
    lines.append(f"- API Base: {base_url}")
    lines.append(
        f"- GET /api/tw/universe/coverage?interval=1d：coverage={_fmt_num(cov_pct,2)}%（{covered_count}/{universe_count}），"
        f"oldest_latest_date/newest_latest_date={oldest_latest} → {newest_latest}"
    )
    lines.append(
        "- GET /api/tw/history/status："
        + "；".join(f"{k}={_fmt_int(v)}" for k, v in sorted(status_counts.items()))
    )
    if data_pool_incomplete:
        lines.append("- **資料池仍在補齊中**（coverage < 95% 或仍有 pending/running/empty/failed）")
    lines.append(
        "- 台股歷史資料僅視為本機資料庫中的 **Fubon API（fubon_neo）** 同步結果；不使用 Yahoo 或其他來源補台股歷史。"
    )
    if signal_file:
        lines.append(f"- 今日 signal JSON 已保存：`{signal_file}`")
    if signal_store_error:
        lines.append(f"- 今日 signal JSON 保存失敗：{_table_cell(signal_store_error, width=120)}")
    lines.append("")

    lines.append("## 1) 今日結論（可執行）")
    lines.append(
        f"- 市場風險={market_context.get('overall_risk','—')} / regime={market_context.get('regime','—')} / posture={market_context.get('trade_posture','—')}"
    )
    drivers = market_context.get("drivers") or []
    if isinstance(drivers, list) and drivers:
        lines.append(
            "- 驅動因子："
            + "、".join(
                f"{d.get('label')} {d.get('value')}" for d in drivers if isinstance(d, dict) and d.get("label")
            )
        )
    if twii:
        lines.append(
            f"- 大盤（^TWII）收={_fmt_num(twii.get('price'),2)}，漲跌={_fmt_num(twii.get('change'),2)}（{_fmt_num(twii.get('change_pct'),2)}%），"
            f"O/H/L={_fmt_num(twii.get('open'),2)}/{_fmt_num(twii.get('high'),2)}/{_fmt_num(twii.get('low'),2)}"
        )
        lines.append(
            f"  - 參考支撐/壓力：支撐先看今日低點 {_fmt_num(twii.get('low'),2)}；壓力先看今日高點 {_fmt_num(twii.get('high'),2)}"
        )
    if twoii:
        lines.append(
            f"- 櫃買（^TWOII）收={_fmt_num(twoii.get('price'),2)}，漲跌={_fmt_num(twoii.get('change'),2)}（{_fmt_num(twoii.get('change_pct'),2)}%）"
        )
    if isinstance(structured.get("futures"), dict) and isinstance(structured.get("options"), dict):
        lines.append(f"- 期貨/選擇權籌碼（TAIFEX 結構化）：{_summarize_taifex_position(structured)}")
    lines.append("- 交易執行：以「突破確認」為主；未達確認不追價，優先控風險與倉位。")
    if data_pool_incomplete:
        lines.append("- 風險提醒：資料池尚未完整，候選僅視為觀察清單，交易前請以下單軟體再核對。")
    lines.append("")

    lines.append("## 2) 法人偏多候選（依標的類型分類）")
    lines.append("- 條件：法人5日>0 且外資5日>0；以下分為個股與 ETF/基金/REIT，避免不同工具混在同一張表。")
    lines.append("")
    lines.extend(_institutional_table_lines("### 2A. 法人偏多個股", inst_bullish_stocks[:12]))
    lines.extend(_institutional_table_lines("### 2B. 法人偏多 ETF / 基金 / REIT", inst_bullish_etfs[:8]))

    lines.append("## 3) 強勢股 / 多頭股 / 沿5日均線上漲")
    lines.append("- 這一節只放個股；ETF / 基金 / REIT 仍維持在後方獨立表格，避免交易工具混在一起。")
    lines.append("- 強勢股偏向價格、量能與近高點相對強度；多頭股偏向均線結構；沿5日線則用近日日線實際計算 MA5。")
    lines.append("")
    lines.extend(_momentum_table_lines("### 3A. 目前強勢股（價格、量能、相對強度）", strong_stock_candidates, mode="strong"))
    lines.extend(_momentum_table_lines("### 3B. 多頭股（收盤站上MA20，且MA20高於MA50）", bullish_stock_candidates, mode="bullish"))
    lines.extend(_ma5_walk_table_lines("### 3C. 持續沿5日均線上漲的個股", ma5_walk_candidates))

    lines.extend(_signal_validation_table_lines("## 4) 近 5 日訊號驗證與續強名單", signal_validation_rows))

    lines.extend(
        _signal_backtest_summary_lines(
            "## 5) 訊號後績效驗證摘要",
            signal_backtest_summary,
            error=signal_backtest_error,
        )
    )

    lines.append("## 6) 可能轉強族群")
    lines.append("| 族群 | 轉強分數 | 候選數 | 平均潛伏總分 | 平均K線分數 | 法人/外資偏多數 | 突破/轉強型態數 | 量能放大數 | 代表標的 | 觀察重點 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
    if not sector_rows:
        lines.append("| — | — | 0 | — | — | 0 | 0 | 0 | — | （目前個股候選不足，暫無可用族群統計） |")
    else:
        for row in sector_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _table_cell(row["sector"]),
                        _table_cell(_fmt_num(row["rotation_score"], 1)),
                        _table_cell(_fmt_int(row["count"])),
                        _table_cell(_fmt_num(row["avg_acc"], 1)),
                        _table_cell(_fmt_num(row["avg_k"], 1)),
                        _table_cell(_fmt_int(row["chip_count"])),
                        _table_cell(_fmt_int(row["breakout_count"])),
                        _table_cell(_fmt_int(row["volume_count"])),
                        _table_cell(row["representatives"], width=68),
                        _table_cell(row["watch"], width=72),
                    ]
                )
                + " |"
            )
    lines.append("")

    lines.extend(_candidate_table_lines("## 7) 個股潛伏起漲候選（Top 20）", selected_stocks))
    lines.extend(_candidate_table_lines("## 8) ETF / 基金 / REIT 候選（Top 10）", selected_etfs))

    lines.append("## 9) 新聞與事件雷達")
    all_news_records = market_news + news_records
    lines.append("| 標的 | 類型 | 日期 | 標題/事件 | 來源 | 連結 |")
    lines.append("|---|---|---|---|---|---|")
    if not all_news_records:
        lines.append("| — | — | — | （今日無可用新聞/事件資料；仍以價格、量能、籌碼確認為主） | — | — |")
    else:
        for record in all_news_records[:28]:
            url = str(record.get("url") or "")
            link = f"[來源]({url})" if url else "—"
            lines.append(
                "| "
                + " | ".join(
                    [
                        _table_cell(record.get("ticker")),
                        _table_cell(record.get("type")),
                        _table_cell(record.get("date")),
                        _table_cell(record.get("title"), width=82),
                        _table_cell(record.get("source"), width=24),
                        _table_cell(link),
                    ]
                )
                + " |"
            )
    lines.append("")
    lines.append(
        "- 新聞解讀原則：若新聞與族群轉強方向一致，隔日仍需等待突破量能確認；若新聞利多但 K 線長上影或跌破低點，視為追價風險。"
    )
    lines.append("")

    lines.append("## 10) 隔日三情境交易策略")
    lines.append("### A. 進攻（突破續強）")
    lines.append("- 進場：候選股「突破今日高點」且量能不縮（volume_expanded=true 更佳）")
    lines.append("- 停損：跌破 MA20 或跌破今日低點（以較高者為準）")
    lines.append("- 停利：分批（1R 先回收、2R 再減碼），或跌破5日/10日線再退出")
    lines.append("- 資金控管：單筆風險 0.3%~0.8% 資金；高相關 ETF 限制同向曝險")
    lines.append("- 不交易：開盤直接跳空大幅超過突破價且量縮/急拉長上影")
    lines.append("")
    lines.append("### B. 防守（高檔震盪/回測）")
    lines.append("- 進場：回測 MA20/箱型上緣不破、出現收腳（下影/收盤回到區間內）")
    lines.append("- 停損：回測失守（收盤跌破 MA20 或有效跌破箱型）")
    lines.append("- 停利：回到箱型上緣先減碼；再突破才轉進攻腳本")
    lines.append("- 資金控管：降低槓桿、分批進出")
    lines.append("")
    lines.append("### C. 觀望（假突破/風險升溫）")
    lines.append("- 不交易條件：大盤跌破今日低點、外資期貨 OI 淨空單擴大且價格轉弱、或資料池仍大幅 incomplete")
    lines.append("- 行動：只保留觀察清單，等待「突破確認」或「回測不破」再出手")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate TW post-market AI strategy report")
    parser.add_argument(
        "--base",
        default=os.environ.get("QV_API_BASE", "http://localhost:8001").rstrip("/"),
        help="API base url (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--date",
        default=_now_tw().strftime("%Y-%m-%d"),
        help="Report date YYYY-MM-DD (default: today in Asia/Taipei)",
    )
    parser.add_argument(
        "--out",
        default="log/ai_daily_tw_report.md",
        help="Output markdown path (default: log/ai_daily_tw_report.md)",
    )
    parser.add_argument(
        "--html-out",
        default="",
        help="Optional output HTML path for email body rendering",
    )
    args = parser.parse_args()

    api = check_api(args.base)
    if not api.ok:
        msg = textwrap.dedent(
            f"""
            # 每日盤後 AI 交易策略報告（台股）｜{args.date}

            ## API 連線失敗
            - API Base: {args.base}
            - 錯誤：{api.error}

            ## 可復原建議（不捏造行情）
            - 確認後端是否啟動：`start.bat` 或 `scripts\\start.bat`（或 Docker: `docker compose up --build`）
            - 預設後端：`http://localhost:8001`，Swagger：`http://localhost:8001/docs`
            - 確認 `.env` 的 `APP_PORT` / MySQL 連線資訊是否正確
            - 若 8001 被占用：改 `.env` 的 `APP_PORT` 後重啟
            """
        ).strip() + "\n"
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(msg, encoding="utf-8")
        if args.html_out:
            html_path = Path(args.html_out)
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(
                markdown_to_email_html(msg, title=f"每日盤後 AI 交易策略報告｜{args.date}"),
                encoding="utf-8",
            )
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode("utf-8", "backslashreplace").decode("ascii", "ignore"))
        return 2

    report = build_report(base_url=args.base, report_date=args.date)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    if args.html_out:
        html_path = Path(args.html_out)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(
            markdown_to_email_html(report, title=f"每日盤後 AI 交易策略報告｜{args.date}"),
            encoding="utf-8",
        )
    try:
        print(report)
    except UnicodeEncodeError:
        print(f"Report written to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
