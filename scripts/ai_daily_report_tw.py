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


THEME_TICKER_TAGS: dict[str, tuple[str, ...]] = {
    # Optical communication / CPO / silicon photonics watchlist.
    "3081": ("矽光通訊/CPO", "光通訊"),
    "3163": ("矽光通訊/CPO", "光通訊"),
    "3363": ("矽光通訊/CPO", "光通訊"),
    "3450": ("矽光通訊/CPO", "光通訊"),
    "4908": ("矽光通訊/CPO", "光通訊"),
    "4977": ("光通訊",),
    "4979": ("矽光通訊/CPO", "光通訊"),
    "6426": ("光通訊",),
    "6442": ("光通訊",),
    "6530": ("光通訊",),
    "6863": ("光通訊",),
    # Passive components.
    "2327": ("被動元件",),
    "2375": ("被動元件",),
    "2428": ("被動元件",),
    "2456": ("被動元件",),
    "2478": ("被動元件",),
    "2492": ("被動元件",),
    "3026": ("被動元件",),
    "3042": ("被動元件",),
    "6173": ("被動元件",),
    "6207": ("被動元件",),
    # PCB / ABF / CCL.
    "2313": ("PCB",),
    "2368": ("PCB", "AI Server"),
    "2383": ("PCB", "AI Server"),
    "2402": ("PCB",),
    "3037": ("ABF/載板", "PCB"),
    "3044": ("PCB",),
    "3189": ("ABF/載板", "PCB"),
    "4958": ("PCB",),
    "5469": ("PCB",),
    "6153": ("PCB",),
    "6191": ("PCB",),
    "6213": ("PCB",),
    "6274": ("PCB",),
    "8046": ("ABF/載板", "PCB"),
    "8358": ("CCL", "PCB"),
    "8933": ("CCL", "PCB"),
    # LED / optics.
    "2340": ("LED",),
    "2448": ("LED",),
    "2466": ("LED",),
    "2486": ("LED",),
    "3031": ("LED",),
    "3038": ("光電/LED", "LED"),
    "3591": ("LED",),
    "3714": ("LED",),
    "4935": ("LED",),
    "5230": ("LED",),
    "5243": ("LED",),
    "6278": ("LED",),
    # AI server / thermal / power.
    "2308": ("電源/重電",),
    "2317": ("AI Server", "其他電子"),
    "2356": ("AI Server", "電腦週邊"),
    "2376": ("AI Server", "電腦週邊"),
    "2377": ("AI Server", "電腦週邊"),
    "2382": ("AI Server", "電腦週邊"),
    "2395": ("AI Server", "電腦週邊"),
    "3013": ("機殼/散熱", "AI Server"),
    "3231": ("AI Server", "電腦週邊"),
    "3324": ("機殼/散熱", "AI Server"),
    "3653": ("AI Server", "電腦週邊"),
    "3706": ("AI Server", "電腦週邊"),
    "6117": ("機殼/散熱", "AI Server"),
    "6669": ("機殼/散熱", "AI Server"),
    # Transportation and other common topical groups.
    "1503": ("重電",),
    "1513": ("重電",),
    "1514": ("重電",),
    "1605": ("電線電纜",),
    "1609": ("電線電纜",),
    "1611": ("電線電纜",),
    "2603": ("航運",),
    "2609": ("航運",),
    "2615": ("航運",),
    "5607": ("航運",),
    # Semiconductor chain.
    "2330": ("晶圓代工", "先進封裝/CoWoS"),
    "2303": ("晶圓代工",),
    "5347": ("晶圓代工",),
    "2454": ("IC設計",),
    "2379": ("IC設計",),
    "3035": ("IC設計", "ASIC/IP"),
    "3443": ("IC設計", "ASIC/IP"),
    "3661": ("ASIC/IP", "IC設計"),
    "5274": ("IC設計",),
    "6415": ("IC設計",),
    "6531": ("IC設計",),
    "2451": ("記憶體/HBM",),
    "2344": ("記憶體/HBM",),
    "2408": ("記憶體/HBM",),
    "3006": ("記憶體/HBM",),
    "3260": ("記憶體/HBM",),
    "8299": ("記憶體/HBM",),
    "3711": ("封測", "先進封裝/CoWoS"),
    "2449": ("封測",),
    "3264": ("封測",),
    "6239": ("封測",),
    "6257": ("封測",),
    "3131": ("半導體設備",),
    "3413": ("半導體設備",),
    "3583": ("半導體設備",),
    "6187": ("半導體設備",),
    "6196": ("半導體設備",),
    "6640": ("半導體設備",),
    "7556": ("半導體設備",),
    # Networking / IPC / distribution.
    "2345": ("網通",),
    "2419": ("網通",),
    "3025": ("網通",),
    "3380": ("網通",),
    "3596": ("網通",),
    "3704": ("網通",),
    "4906": ("網通",),
    "6285": ("網通", "低軌衛星"),
    "6416": ("網通",),
    "2395": ("工業電腦", "AI Server"),
    "3088": ("工業電腦",),
    "3213": ("工業電腦", "電腦週邊"),
    "3416": ("工業電腦",),
    "3479": ("工業電腦",),
    "3577": ("工業電腦",),
    "6414": ("工業電腦",),
    "6577": ("工業電腦",),
    "8114": ("工業電腦",),
    "2347": ("電子通路",),
    "2459": ("電子通路",),
    "3036": ("電子通路",),
    "3702": ("電子通路",),
    "5434": ("電子通路",),
    "8112": ("電子通路",),
    # Display, consumer electronics, connectors, automation.
    "2409": ("面板",),
    "3481": ("面板",),
    "6116": ("面板",),
    "3008": ("消費電子/蘋概", "感測/鏡頭"),
    "3406": ("消費電子/蘋概", "感測/鏡頭"),
    "2474": ("消費電子/蘋概",),
    "4938": ("消費電子/蘋概",),
    "3023": ("連接器/線束",),
    "3321": ("連接器/線束",),
    "5457": ("連接器/線束",),
    "6205": ("連接器/線束",),
    "6217": ("連接器/線束",),
    "8039": ("連接器/線束",),
    "2359": ("車用電子",),
    "3605": ("車用電子",),
    "3665": ("車用電子",),
    "3669": ("車用電子",),
    "6279": ("車用電子", "連接器/線束"),
    "1590": ("機器人/自動化",),
    "2049": ("機器人/自動化",),
    "2354": ("機器人/自動化",),
    "2464": ("機器人/自動化",),
    "3379": ("機器人/自動化",),
    "6180": ("機器人/自動化",),
    "6207": ("被動元件",),
    "3356": ("安控",),
    "3454": ("安控",),
    "3293": ("軍工電子/無人機",),
    "4916": ("軍工電子/無人機",),
    "8033": ("軍工電子/無人機",),
}


THEME_KEYWORD_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("矽光", ("矽光通訊/CPO",)),
    ("CPO", ("矽光通訊/CPO",)),
    ("光通訊", ("光通訊",)),
    ("被動元件", ("被動元件",)),
    ("國巨", ("被動元件",)),
    ("華新科", ("被動元件",)),
    ("PCB", ("PCB",)),
    ("印刷電路板", ("PCB",)),
    ("ABF", ("ABF/載板",)),
    ("載板", ("ABF/載板",)),
    ("銅箔基板", ("CCL", "PCB")),
    ("CCL", ("CCL", "PCB")),
    ("LED", ("LED",)),
    ("光電", ("光電/LED",)),
    ("AI伺服器", ("AI Server",)),
    ("AI Server", ("AI Server",)),
    ("伺服器", ("AI Server",)),
    ("散熱", ("機殼/散熱",)),
    ("機殼", ("機殼/散熱",)),
    ("重電", ("重電",)),
    ("電線電纜", ("電線電纜",)),
    ("航運", ("航運",)),
    ("晶圓代工", ("晶圓代工",)),
    ("IC設計", ("IC設計",)),
    ("ASIC", ("ASIC/IP",)),
    ("記憶體", ("記憶體/HBM",)),
    ("HBM", ("記憶體/HBM",)),
    ("封測", ("封測",)),
    ("先進封裝", ("先進封裝/CoWoS",)),
    ("CoWoS", ("先進封裝/CoWoS",)),
    ("半導體設備", ("半導體設備",)),
    ("網通", ("網通",)),
    ("低軌", ("低軌衛星",)),
    ("衛星", ("低軌衛星",)),
    ("工業電腦", ("工業電腦",)),
    ("電子通路", ("電子通路",)),
    ("面板", ("面板",)),
    ("蘋概", ("消費電子/蘋概",)),
    ("鏡頭", ("感測/鏡頭",)),
    ("感測", ("感測/鏡頭",)),
    ("連接器", ("連接器/線束",)),
    ("線束", ("連接器/線束",)),
    ("車用", ("車用電子",)),
    ("機器人", ("機器人/自動化",)),
    ("自動化", ("機器人/自動化",)),
    ("安控", ("安控",)),
    ("軍工", ("軍工電子/無人機",)),
    ("無人機", ("軍工電子/無人機",)),
)


ELECTRONIC_THEME_TAGS: set[str] = {
    "AI Server",
    "PCB",
    "ABF/載板",
    "CCL",
    "被動元件",
    "矽光通訊/CPO",
    "光通訊",
    "LED",
    "光電/LED",
    "機殼/散熱",
    "電源/重電",
    "半導體設備",
    "先進封裝/CoWoS",
    "ASIC/IP",
    "IC設計",
    "記憶體/HBM",
    "晶圓代工",
    "封測",
    "面板",
    "網通",
    "低軌衛星",
    "工業電腦",
    "電子通路",
    "安控",
    "車用電子",
    "機器人/自動化",
    "軍工電子/無人機",
    "消費電子/蘋概",
    "連接器/線束",
    "感測/鏡頭",
    "電腦週邊",
    "其他電子",
}


def _theme_tags_for_item(item: dict) -> list[str]:
    """Return focused topical tags for daily rotation analysis."""

    ticker_root = _ticker_root(item.get("ticker"))
    tags: list[str] = list(THEME_TICKER_TAGS.get(ticker_root, ()))
    haystack = " ".join(
        str(item.get(key) or "")
        for key in ("ticker", "name", "sector", "industry", "theme", "themes", "tags", "news_event_digest")
    )
    haystack_lower = haystack.lower()
    for keyword, keyword_tags in THEME_KEYWORD_RULES:
        if keyword.lower() in haystack_lower:
            tags.extend(keyword_tags)
    return list(dict.fromkeys(tag for tag in tags if tag))


def _with_theme_tags(item: dict) -> dict:
    row = dict(item)
    row["theme_tags"] = _theme_tags_for_item(row)
    return row


def _theme_text(item: dict) -> str:
    tags = item.get("theme_tags")
    if not isinstance(tags, list):
        tags = _theme_tags_for_item(item)
    return "、".join(str(tag) for tag in tags if tag) or "—"


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
    theme = _theme_text(item)
    if theme != "—":
        reasons.append(f"主題：{theme}")
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


def _display_ticker(record: dict) -> str:
    payload = record.get("payload")
    if isinstance(payload, dict):
        display = str(payload.get("display_ticker") or "").strip()
        if display:
            return display
    return str(record.get("ticker") or "—")


def _record_published_at(record: dict, *, report_date: str) -> str:
    published = str(record.get("published_at") or "").strip()
    if published:
        return published
    date_text = str(record.get("date") or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_text):
        return f"{date_text}T12:00:00+08:00"
    return f"{report_date}T12:00:00+08:00"


def _news_article_payloads_from_records(records: list[dict], *, report_date: str) -> list[dict]:
    articles: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        if str(record.get("type") or "") != "新聞":
            continue
        title = str(record.get("title") or "").strip()
        if not title:
            continue
        ticker = str(record.get("ticker") or "MARKET").strip()[:32] or "MARKET"
        published_at = _record_published_at(record, report_date=report_date)
        key = (ticker, published_at, title)
        if key in seen:
            continue
        seen.add(key)
        payload = dict(record.get("payload") or {})
        if record.get("query") and "query" not in payload:
            payload["query"] = record.get("query")
        display_ticker = str(record.get("display_ticker") or "").strip()
        if display_ticker:
            payload["display_ticker"] = display_ticker
        articles.append(
            {
                "ticker": ticker,
                "market": record.get("market") or "TW",
                "title": title,
                "summary": record.get("summary") or record.get("query") or record.get("source"),
                "published_at": published_at,
                "source": record.get("source") or "news",
                "url": record.get("url") or "",
                "sentiment": record.get("sentiment"),
                "payload": payload,
            }
        )
    return articles


def _store_news_records(base_url: str, records: list[dict], *, report_date: str) -> int:
    articles = _news_article_payloads_from_records(records, report_date=report_date)
    if not articles:
        return 0
    # Persist Google RSS records in the same DB-backed news pool used by the API.
    try:
        response = _http_json(
            f"{base_url}/api/news/articles",
            method="POST",
            json_body={"items": articles},
            timeout=30,
        )
    except Exception:
        return 0
    if isinstance(response, dict):
        try:
            return int(response.get("stored") or 0)
        except Exception:
            return 0
    return 0


def _article_to_news_record(article: dict) -> dict:
    published_at = str(article.get("published_at") or "")
    payload = article.get("payload") if isinstance(article.get("payload"), dict) else {}
    return {
        "ticker": payload.get("display_ticker") or article.get("ticker") or "—",
        "type": "新聞",
        "date": published_at[:10] if published_at else "—",
        "title": article.get("title") or "",
        "source": article.get("source") or article.get("summary") or "news",
        "url": article.get("url") or "",
        "published_at": published_at,
        "payload": payload,
    }


def _fetch_db_news_records(
    base_url: str,
    *,
    report_date: str,
    date_window_days: int = 3,
    limit: int = 24,
) -> list[dict]:
    try:
        target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
    except ValueError:
        target_date = _now_tw().date()
    date_from = (target_date - timedelta(days=date_window_days)).isoformat()
    query = urllib.parse.urlencode(
        {
            "market": "TW",
            "date_from": date_from,
            "date_to": target_date.isoformat(),
            "limit": str(limit),
        }
    )
    payload = _fetch_optional_json(f"{base_url}/api/news?{query}", timeout=25)
    return [_article_to_news_record(item) for item in payload.get("items") or [] if isinstance(item, dict)]


def _dedupe_news_records(records: list[dict], *, limit: int | None = None) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        title = str(record.get("title") or "").strip()
        if not title:
            continue
        key = (str(record.get("date") or ""), title)
        if key in seen:
            continue
        seen.add(key)
        rows.append(record)
        if limit is not None and len(rows) >= limit:
            break
    return rows


def _news_category(record: dict) -> str:
    ticker = str(record.get("ticker") or "").upper().strip()
    display = _display_ticker(record).upper()
    title = str(record.get("title") or "")
    query = str(record.get("query") or (record.get("payload") or {}).get("query") or "")
    text = f"{title} {query}".lower()
    if ticker in {"MARKET", "^TWII", "^TWOII"} or "市場" in display:
        return "market"
    if any(keyword.lower() in text for keyword in ["vix", "nvidia", "walmart", "美元", "美債", "費半", "nasdaq", "dow", "sox"]):
        return "global_macro"
    if any(keyword in query for keyword in ["族群", "轉強", "半導體", "ai 伺服器"]):
        return "sector"
    if ticker and ticker not in {"MARKET"}:
        return "candidate"
    return "other"


def _news_relevance(record: dict, *, candidate_tickers: set[str], sectors: set[str]) -> tuple[int, str]:
    ticker = str(record.get("ticker") or "").upper().strip()
    title = str(record.get("title") or "")
    query = str(record.get("query") or (record.get("payload") or {}).get("query") or "")
    text = f"{title} {query}"
    if ticker in candidate_tickers:
        return 95, "新聞直接對應候選標的"
    for sector in sectors:
        if sector and sector in text:
            return 80, f"新聞提及候選族群：{sector}"
    if any(keyword in text for keyword in ["台股", "盤後", "法人", "期貨", "選擇權", "費半", "美元", "美債", "VIX"]):
        return 65, "市場或風險因子相關"
    if any(keyword.lower() in text.lower() for keyword in ["nvidia", "walmart", "sox", "nasdaq"]):
        return 55, "國際事件可能影響風險偏好"
    return 25, "與候選標的或族群連結較弱，僅作事件備查"


def _news_record_for_ai(record: dict, *, candidate_tickers: set[str], sectors: set[str]) -> dict:
    relevance_score, relevance_reason = _news_relevance(record, candidate_tickers=candidate_tickers, sectors=sectors)
    return {
        "ticker": record.get("ticker"),
        "display_ticker": _display_ticker(record),
        "category": _news_category(record),
        "date": record.get("date"),
        "published_at": record.get("published_at"),
        "title": record.get("title"),
        "source": record.get("source"),
        "url": record.get("url"),
        "relevance_score": relevance_score,
        "relevance_reason": relevance_reason,
        "query": record.get("query") or (record.get("payload") or {}).get("query"),
    }


def _news_packet_for_ai(
    *,
    candidates: list[dict],
    sector_rows: list[dict],
    news_records: list[dict],
    market_news: list[dict],
    limit: int = 40,
) -> dict:
    candidate_tickers = {str(item.get("ticker") or "").upper().strip() for item in candidates if item.get("ticker")}
    sectors = {str(item.get("sector") or item.get("industry") or "").strip() for item in candidates}
    sectors.update(str(row.get("sector") or "").strip() for row in sector_rows)
    sectors.discard("")
    rows = [
        _news_record_for_ai(record, candidate_tickers=candidate_tickers, sectors=sectors)
        for record in _dedupe_news_records(market_news + news_records, limit=limit)
    ]
    rows.sort(key=lambda row: (row.get("relevance_score") or 0, str(row.get("published_at") or row.get("date") or "")), reverse=True)
    grouped: dict[str, list[dict]] = {
        "candidate_news": [],
        "sector_news": [],
        "market_news": [],
        "global_macro_news": [],
        "low_relevance_news": [],
    }
    for row in rows:
        category = row.get("category")
        relevance = int(row.get("relevance_score") or 0)
        if relevance < 40:
            grouped["low_relevance_news"].append(row)
        elif category == "candidate":
            grouped["candidate_news"].append(row)
        elif category == "sector":
            grouped["sector_news"].append(row)
        elif category == "global_macro":
            grouped["global_macro_news"].append(row)
        else:
            grouped["market_news"].append(row)
    return {
        "policy": "AI should interpret high/medium relevance news and leave low relevance items as appendix-only evidence.",
        "items": rows,
        **grouped,
    }


def _data_quality_flags_for_ai(*, coverage: dict, status_counts: Counter, taifex: dict | None) -> list[dict]:
    flags: list[dict] = []
    cov_pct = _to_float(coverage.get("coverage_pct")) or 0.0
    if cov_pct < 95:
        flags.append(
            {
                "level": "warning",
                "label": "台股日K資料池未完整",
                "detail": f"coverage={_fmt_num(cov_pct, 2)}%，AI 對低流動性或缺資料標的需降權。",
            }
        )
    non_success = sum(int(v or 0) for key, v in status_counts.items() if key != "success")
    if non_success:
        flags.append(
            {
                "level": "warning",
                "label": "仍有未成功同步標的",
                "detail": "；".join(f"{key}={_fmt_int(value)}" for key, value in sorted(status_counts.items()) if key != "success"),
            }
        )
    if isinstance(taifex, dict):
        for ticker, threshold in {"^TWII": 10.0, "^TWOII": 15.0}.items():
            card = _get_spot_card(taifex, ticker)
            change_pct = _to_float((card or {}).get("change_pct")) if isinstance(card, dict) else None
            if change_pct is not None and abs(change_pct) >= threshold:
                flags.append(
                    {
                        "level": "warning",
                        "label": f"{ticker} 指數漲跌幅疑似異常",
                        "detail": f"change_pct={_fmt_num(change_pct, 2)}%，AI 不應將此數字單獨視為市場常態訊號。",
                    }
                )
    return flags


def _news_event_digest(
    base_url: str,
    ticker: str,
    *,
    name: str = "",
    report_date: str = "",
    refresh: bool = False,
) -> tuple[str, list[dict]]:
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
    if not any(record.get("type") == "新聞" for record in records) and report_date:
        google_records = _fetch_google_news_records(
            f"{name} {ticker} 台股",
            report_date=report_date,
            limit=2,
            ticker=ticker,
            display_ticker=f"{ticker} {name}".strip(),
        )
        for record in google_records[:2]:
            title = record.get("title")
            if not title:
                continue
            fragments.append(f"新聞：{title}（{record.get('source') or 'Google News'} {record.get('date') or '—'}）")
            records.append(record)
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


def _enrich_news_for_candidates(
    base_url: str,
    candidates: list[dict],
    *,
    report_date: str,
    refresh_limit: int = 12,
) -> list[dict]:
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
            report_date=report_date,
            refresh=index < refresh_limit,
        )
        item["news_event_digest"] = digest
        all_records.extend(records)
    _store_news_records(base_url, all_records, report_date=report_date)
    return all_records


def _parse_rss_date(value: str) -> datetime | None:
    try:
        return parsedate_to_datetime(value)
    except Exception:
        return None


def _fetch_google_news_records(
    query: str,
    *,
    report_date: str,
    limit: int = 4,
    ticker: str = "MARKET",
    display_ticker: str = "市場/族群",
) -> list[dict]:
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
                "ticker": ticker,
                "display_ticker": display_ticker,
                "market": "TW",
                "type": "新聞",
                "date": published_date.isoformat() if published_date else "—",
                "title": title,
                "source": source,
                "url": link,
                "published_at": published_dt.isoformat() if published_dt else "",
                "query": query,
                "payload": {
                    "query": query,
                    "display_ticker": display_ticker,
                    "google_news_rss": True,
                },
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
        sector = str(row.get("theme") or row.get("sector") or "").strip()
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


def _theme_rotation_rows(candidates: list[dict], *, limit: int = 10, min_count: int = 2) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for item in candidates:
        if not _is_common_stock(item):
            continue
        for tag in _theme_tags_for_item(item):
            buckets.setdefault(tag, []).append(item)

    rows: list[dict] = []
    for theme, items in buckets.items():
        if len(items) < min_count:
            continue
        acc_values = [
            float(item.get("total_score") if item.get("total_score") is not None else item.get("accumulation_score") or 0)
            for item in items
        ]
        k_values = [float(item.get("candlestick_score") or 0) for item in items]
        momentum_values = [_strong_stock_score(item) for item in items]
        chip_count = sum(1 for item in items if _positive_chip(item))
        breakout_count = sum(1 for item in items if _has_breakout_signal(item))
        volume_count = sum(1 for item in items if _volume_expanded(item))
        ma20_count = 0
        for item in items:
            close = _recent_metric(item, "latest_close", "close")
            ma20 = _recent_metric(item, "ma20")
            if close is not None and ma20 is not None and close >= ma20:
                ma20_count += 1
        avg_acc = sum(acc_values) / len(acc_values)
        avg_k = sum(k_values) / len(k_values)
        avg_momentum = sum(momentum_values) / len(momentum_values)
        strength_score = (
            avg_momentum * 0.35
            + avg_acc * 0.25
            + avg_k * 0.15
            + chip_count / len(items) * 12
            + breakout_count / len(items) * 10
            + volume_count / len(items) * 8
            + ma20_count / len(items) * 8
        )
        reps = sorted(
            items,
            key=lambda item: (
                _strong_stock_score(item),
                item.get("total_score") if item.get("total_score") is not None else item.get("accumulation_score") or 0,
                item.get("candlestick_score") or 0,
            ),
            reverse=True,
        )[:5]
        rows.append(
            {
                "theme": theme,
                "strength_score": round(strength_score, 1),
                "count": len(items),
                "avg_momentum": round(avg_momentum, 1),
                "avg_acc": round(avg_acc, 1),
                "avg_k": round(avg_k, 1),
                "chip_count": chip_count,
                "breakout_count": breakout_count,
                "volume_count": volume_count,
                "ma20_count": ma20_count,
                "representatives": "、".join(f"{r.get('ticker')} {r.get('name')}" for r in reps),
                "watch": (
                    f"觀察{theme}代表股是否同步站上短中期均線；若代表股跌破當日低點或量能退潮，先降為觀察。"
                ),
            }
        )
    for row in rows:
        row["state"] = _theme_state(row)
    return sorted(rows, key=lambda row: row["strength_score"], reverse=True)[:limit]


def _theme_state(row: dict) -> str:
    count = max(1, int(row.get("count") or 1))
    strength = _to_float(row.get("strength_score")) or 0
    breakout_ratio = (int(row.get("breakout_count") or 0)) / count
    volume_ratio = (int(row.get("volume_count") or 0)) / count
    ma20_ratio = (int(row.get("ma20_count") or 0)) / count
    chip_ratio = (int(row.get("chip_count") or 0)) / count
    if count <= 2 and strength >= 85 and max(breakout_ratio, volume_ratio) >= 0.5:
        return "單點/小群強勢"
    if strength >= 95 and ma20_ratio >= 0.6 and (breakout_ratio >= 0.5 or volume_ratio >= 0.5):
        return "主線延續"
    if breakout_ratio >= 0.5 and volume_ratio >= 0.4 and ma20_ratio >= 0.5:
        return "轉強確認"
    if chip_ratio >= 0.5 and ma20_ratio >= 0.5:
        return "法人支撐"
    if strength >= 70:
        return "題材雷達"
    return "補漲觀察"


def _electronic_theme_rotation_rows(candidates: list[dict], *, limit: int = 8) -> list[dict]:
    rows = _theme_rotation_rows(candidates, limit=40, min_count=2)
    electronic_rows = [row for row in rows if row.get("theme") in ELECTRONIC_THEME_TAGS]
    return electronic_rows[:limit]


def _data_status_warning_reasons(
    *,
    cov_pct: float,
    universe_count: int,
    newest_latest: object,
    expected_latest_date: str,
    status_counts: Counter,
) -> list[str]:
    reasons: list[str] = []
    newest_text = str(newest_latest or "").strip()
    if newest_text and newest_text < expected_latest_date:
        reasons.append(f"日K最新日期={newest_text}，低於報告日期{expected_latest_date}")
    if cov_pct < 85.0:
        reasons.append(f"coverage={_fmt_num(cov_pct, 2)}%")
    if status_counts.get("pending", 0) or status_counts.get("running", 0):
        reasons.append(
            f"仍有 pending/running={_fmt_int(status_counts.get('pending', 0))}/{_fmt_int(status_counts.get('running', 0))}"
        )
    failed_count = int(status_counts.get("failed", 0) or 0)
    failed_warning_threshold = max(10, int(universe_count * 0.005)) if universe_count > 0 else 10
    if failed_count > failed_warning_threshold:
        reasons.append(f"failed={_fmt_int(failed_count)}")
    return reasons


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


def _env_flag_auto(name: str, *, default: str = "auto") -> str:
    value = str(os.environ.get(name, default) or "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return "true"
    if value in {"0", "false", "no", "off"}:
        return "false"
    return "auto"


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _round_float(value: object, digits: int = 2) -> float | None:
    numeric = _to_float(value)
    return round(numeric, digits) if numeric is not None else None


def _daily_rows_for_ai(rows: list[dict], *, history_days: int) -> list[dict]:
    compact_rows: list[dict] = []
    for row in rows[-history_days:]:
        if not isinstance(row, dict):
            continue
        compact_rows.append(
            {
                "date": str(row.get("date") or "")[:10],
                "open": _round_float(row.get("open")),
                "high": _round_float(row.get("high")),
                "low": _round_float(row.get("low")),
                "close": _round_float(row.get("close")),
                "volume": _round_float(row.get("volume"), 0),
            }
        )
    return compact_rows


def _last_float_values(rows: list[dict], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = _to_float(row.get(key))
        if value is not None:
            values.append(value)
    return values


def _average(values: list[float]) -> float | None:
    usable = [value for value in values if value is not None]
    return sum(usable) / len(usable) if usable else None


def _round_unique_levels(levels: list[float | None], *, limit: int = 3) -> list[float]:
    rounded: list[float] = []
    for level in levels:
        if level is None or level <= 0:
            continue
        value = round(float(level), 2)
        if any(abs(value - existing) <= max(0.02, existing * 0.001) for existing in rounded):
            continue
        rounded.append(value)
        if len(rounded) >= limit:
            break
    return rounded


_KLINE_STRUCTURE_LABELS = {
    "insufficient_bars": "K線資料不足",
    "false_breakout_risk": "假突破風險",
    "overextended_surge": "短線乖離偏大",
    "platform_breakout_attempt": "平台突破嘗試",
    "pullback_reclaim": "回測後站回短均",
    "trend_continuation": "趨勢延續",
    "box_range": "箱型整理",
    "watch_only_structure": "觀察型態",
}


_KLINE_TREND_QUALITY_LABELS = {
    "higher_high_higher_low": "高低點同步墊高",
    "constructive_uptrend": "均線多方排列",
    "near_high_but_needs_confirmation": "接近波段高點但需確認",
    "below_ma20": "收盤低於月線",
    "sideways_or_mixed": "整理或多空混合",
}


_KLINE_CLOSE_LOCATION_LABELS = {
    "unknown": "位置不明",
    "near_20d_high": "接近20日高點",
    "mid_range": "區間中上緣",
    "near_20d_low": "接近20日低點",
}


_KLINE_VOLUME_SIGNATURE_LABELS = {
    "no_volume_data": "量能資料不足",
    "breakout_with_volume": "放量挑戰突破",
    "volume_expansion": "量能放大",
    "volume_insufficient": "量能不足",
    "volume_neutral": "量能中性",
}


_RISK_FLAG_LABELS = {
    "failed_recent_signal": "近期訊號轉弱",
    "overextended_ma5": "短線乖離5日線",
    "overextended_ma20": "短線乖離月線",
    "long_upper_shadow": "上影線偏長",
    "thin_volume": "量能偏薄",
    "single_stock_theme": "族群廣度不足",
    "low_hit_rate_type": "歷史命中率偏低",
    "no_focused_theme": "缺少明確主題",
    "close_far_above_ma5": "收盤遠離5日線",
    "close_far_above_ma20": "收盤遠離月線",
    "volume_not_confirmed": "量能未確認",
    "failed_to_close_above_breakout": "未收過突破價",
    "below_failure_level": "跌破失敗價",
}


def _label_from_map(value: object, labels: dict[str, str]) -> str:
    key = str(value or "").strip()
    return labels.get(key, key)


def _risk_flag_label(flag: object) -> str:
    return _label_from_map(flag, _RISK_FLAG_LABELS)


def _risk_flag_labels(flags: list[object]) -> list[str]:
    return [_risk_flag_label(flag) for flag in flags if str(flag or "").strip()]


def _risk_flag_text(flags: list[object]) -> str:
    labels = _risk_flag_labels(flags)
    return "、".join(labels) if labels else "—"


_USER_FACING_REPORT_TERM_LABELS = {
    **_KLINE_STRUCTURE_LABELS,
    **_KLINE_TREND_QUALITY_LABELS,
    **_KLINE_CLOSE_LOCATION_LABELS,
    **_KLINE_VOLUME_SIGNATURE_LABELS,
    **_RISK_FLAG_LABELS,
    "strength_score": "主題強度",
    "candidate_priority_score": "優先分",
    "candidate_grade": "分級",
    "risk_flags": "風險旗標",
    "risk_flag_labels": "風險說明",
    "structure_type": "K線結構代碼",
    "structure_label": "K線結構",
    "trend_quality": "趨勢品質代碼",
    "trend_quality_label": "趨勢品質",
    "close_location": "收盤位置代碼",
    "close_location_label": "收盤位置",
    "volume_signature": "量能狀態代碼",
    "volume_signature_label": "量能狀態",
    "support_zone": "支撐區",
    "resistance_zone": "壓力區",
    "breakout_trigger": "突破觸發價",
    "failure_level": "失敗價",
    "daily_bars_1m": "近一個月日K",
    "one_month_daily_bars": "近一個月日K",
    "technical_profile": "技術輪廓",
    "kline_structure": "K線結構",
    "graded_candidates": "分級候選",
    "ai_candidate_tickers": "AI深度分析標的",
    "ai_candidate_ticker_count": "AI深度分析檔數",
    "count": "檔數",
}


def _localize_user_facing_report_terms(text: str) -> str:
    """Translate internal metric names/enums before text reaches the user-facing report."""

    localized = text
    for raw, label in sorted(_USER_FACING_REPORT_TERM_LABELS.items(), key=lambda pair: len(pair[0]), reverse=True):
        localized = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(raw)}(?![A-Za-z0-9_])", label, localized)
    return localized


def _one_month_trend_state(*, close: float | None, ma5: float | None, ma10: float | None, ma20: float | None, month_return: float | None) -> str:
    if close is None:
        return "insufficient_data"
    if ma5 is not None and ma10 is not None and ma20 is not None:
        if close >= ma5 >= ma10 >= ma20:
            return "short_term_uptrend"
        if close >= ma20 and ma5 is not None and ma10 is not None and ma5 >= ma10:
            return "constructive_above_ma20"
        if close < ma20:
            return "below_ma20"
    if month_return is not None and month_return > 8:
        return "one_month_momentum"
    if month_return is not None and month_return < -5:
        return "one_month_weak"
    return "sideways_to_breakout"


def _technical_risk_notes(
    *,
    item: dict,
    latest_row: dict,
    close: float | None,
    ma20: float | None,
    volume_ratio_20d: float | None,
    breakout_price: float | None,
) -> list[str]:
    notes: list[str] = []
    if str(item.get("signal_status") or "").lower() == "invalidated":
        notes.append("訊號狀態已失效，需等待重新轉強")
    high = _to_float(latest_row.get("high"))
    low = _to_float(latest_row.get("low"))
    if high is not None and low is not None and close is not None and high > low:
        upper_shadow_ratio = (high - close) / (high - low)
        if upper_shadow_ratio >= 0.45:
            notes.append("上影線偏長，追價風險較高")
    if close is not None and ma20 is not None and ma20 > 0 and (close / ma20 - 1) * 100 >= 12:
        notes.append("短線離 MA20 偏遠，回測風險升高")
    if breakout_price is not None and close is not None and close < breakout_price and volume_ratio_20d is not None and volume_ratio_20d < 0.8:
        notes.append("尚未突破且量能不足")
    return notes[:3]


def _kline_structure_for_ai(item: dict, daily_rows: list[dict], technical_profile: dict) -> dict:
    rows = [row for row in daily_rows if isinstance(row, dict)]
    closes = _last_float_values(rows, "close")
    highs = _last_float_values(rows, "high")
    lows = _last_float_values(rows, "low")
    latest_row = rows[-1] if rows else {}
    latest_close = closes[-1] if closes else _candidate_latest_close(item)
    latest_high = highs[-1] if highs else _to_float(latest_row.get("high"))
    latest_low = lows[-1] if lows else _to_float(latest_row.get("low"))
    latest_open = _to_float(latest_row.get("open"))
    breakout_price = _to_float(technical_profile.get("breakout_trigger")) or _candidate_breakout_price(item)
    failure_level = _to_float(technical_profile.get("failure_level")) or _candidate_signal_low(item)
    ma5 = _to_float(technical_profile.get("ma5"))
    ma10 = _to_float(technical_profile.get("ma10"))
    ma20 = _to_float(technical_profile.get("ma20"))
    ma5_slope = _to_float(technical_profile.get("ma5_slope_pct"))
    close_vs_ma5 = _to_float(technical_profile.get("close_vs_ma5_pct"))
    close_vs_ma20 = _to_float(technical_profile.get("close_vs_ma20_pct"))
    volume_ratio_20d = _to_float(technical_profile.get("volume_ratio_20d"))
    volume_ratio_5d = _to_float(technical_profile.get("volume_ratio_5d"))
    high_20 = max(highs[-20:]) if highs else None
    low_20 = min(lows[-20:]) if lows else None
    high_5 = max(highs[-5:]) if len(highs) >= 5 else None
    low_5 = min(lows[-5:]) if len(lows) >= 5 else None
    prev_high_5 = max(highs[-10:-5]) if len(highs) >= 10 else None
    prev_low_5 = min(lows[-10:-5]) if len(lows) >= 10 else None
    higher_high_5d = bool(high_5 is not None and prev_high_5 is not None and high_5 > prev_high_5)
    higher_low_5d = bool(low_5 is not None and prev_low_5 is not None and low_5 > prev_low_5)
    range_position = (
        (latest_close - low_20) / (high_20 - low_20)
        if latest_close is not None and high_20 is not None and low_20 is not None and high_20 > low_20
        else None
    )
    upper_shadow_ratio = (
        (latest_high - latest_close) / (latest_high - latest_low)
        if latest_high is not None and latest_low is not None and latest_close is not None and latest_high > latest_low
        else None
    )
    body_position = (
        (latest_close - latest_open) / latest_open * 100
        if latest_close is not None and latest_open is not None and latest_open > 0
        else None
    )
    prev_close = closes[-2] if len(closes) >= 2 else None
    prev_ma5 = _simple_ma(closes, 5, end_index=len(closes) - 1) if len(closes) >= 6 else None

    if volume_ratio_20d is None and volume_ratio_5d is None:
        volume_signature = "no_volume_data"
    elif breakout_price is not None and latest_close is not None and latest_close >= breakout_price * 0.995 and (volume_ratio_20d or 0) >= 1.2:
        volume_signature = "breakout_with_volume"
    elif (volume_ratio_20d or volume_ratio_5d or 0) >= 1.4:
        volume_signature = "volume_expansion"
    elif (volume_ratio_20d or volume_ratio_5d or 0) < 0.8:
        volume_signature = "volume_insufficient"
    else:
        volume_signature = "volume_neutral"

    if range_position is None:
        close_location = "unknown"
    elif range_position >= 0.82:
        close_location = "near_20d_high"
    elif range_position <= 0.25:
        close_location = "near_20d_low"
    else:
        close_location = "mid_range"

    risk_flags: list[str] = []
    if close_vs_ma5 is not None and close_vs_ma5 >= 8:
        risk_flags.append("close_far_above_ma5")
    if close_vs_ma20 is not None and close_vs_ma20 >= 15:
        risk_flags.append("close_far_above_ma20")
    if upper_shadow_ratio is not None and upper_shadow_ratio >= 0.45:
        risk_flags.append("long_upper_shadow")
    if volume_signature == "volume_insufficient":
        risk_flags.append("volume_not_confirmed")
    if breakout_price is not None and latest_high is not None and latest_close is not None and latest_high >= breakout_price and latest_close < breakout_price:
        risk_flags.append("failed_to_close_above_breakout")
    if failure_level is not None and latest_close is not None and latest_close < failure_level:
        risk_flags.append("below_failure_level")

    reclaim_ma5 = bool(
        prev_close is not None
        and prev_ma5 is not None
        and ma5 is not None
        and latest_close is not None
        and prev_close < prev_ma5
        and latest_close >= ma5
    )
    uptrend_alignment = bool(latest_close is not None and ma5 is not None and ma10 is not None and ma20 is not None and latest_close >= ma5 >= ma10 >= ma20)
    breakout_attempt = bool(breakout_price is not None and latest_close is not None and latest_close >= breakout_price * 0.995)
    false_breakout = "failed_to_close_above_breakout" in risk_flags or "below_failure_level" in risk_flags

    if len(rows) < 12:
        structure_type = "insufficient_bars"
    elif false_breakout:
        structure_type = "false_breakout_risk"
    elif close_vs_ma5 is not None and close_vs_ma5 >= 8 and close_vs_ma20 is not None and close_vs_ma20 >= 14:
        structure_type = "overextended_surge"
    elif breakout_attempt:
        structure_type = "platform_breakout_attempt"
    elif reclaim_ma5:
        structure_type = "pullback_reclaim"
    elif uptrend_alignment and higher_low_5d and (ma5_slope is None or ma5_slope >= 0):
        structure_type = "trend_continuation"
    elif close_location == "mid_range" and not breakout_attempt:
        structure_type = "box_range"
    else:
        structure_type = "watch_only_structure"
    structure_label = _label_from_map(structure_type, _KLINE_STRUCTURE_LABELS)

    if higher_high_5d and higher_low_5d:
        trend_quality = "higher_high_higher_low"
    elif uptrend_alignment:
        trend_quality = "constructive_uptrend"
    elif close_location == "near_20d_high":
        trend_quality = "near_high_but_needs_confirmation"
    elif latest_close is not None and ma20 is not None and latest_close < ma20:
        trend_quality = "below_ma20"
    else:
        trend_quality = "sideways_or_mixed"

    hint_parts = [structure_label]
    if close_location != "unknown":
        hint_parts.append(f"收盤位置={_label_from_map(close_location, _KLINE_CLOSE_LOCATION_LABELS)}")
    if volume_signature != "no_volume_data":
        hint_parts.append(f"量能={_label_from_map(volume_signature, _KLINE_VOLUME_SIGNATURE_LABELS)}")
    if risk_flags:
        hint_parts.append("風險=" + "、".join(_risk_flag_labels(risk_flags[:3])))
    ai_prompt_hint = "；".join(hint_parts)

    return {
        "structure_type": structure_type,
        "structure_label": structure_label,
        "trend_quality": trend_quality,
        "trend_quality_label": _label_from_map(trend_quality, _KLINE_TREND_QUALITY_LABELS),
        "high_low_structure": {
            "higher_high_5d_vs_prev": higher_high_5d,
            "higher_low_5d_vs_prev": higher_low_5d,
            "five_day_high": _round_float(high_5),
            "five_day_low": _round_float(low_5),
            "previous_five_day_high": _round_float(prev_high_5),
            "previous_five_day_low": _round_float(prev_low_5),
        },
        "close_location": close_location,
        "close_location_label": _label_from_map(close_location, _KLINE_CLOSE_LOCATION_LABELS),
        "range_position_pct": _round_float(range_position * 100 if range_position is not None else None),
        "volume_signature": volume_signature,
        "volume_signature_label": _label_from_map(volume_signature, _KLINE_VOLUME_SIGNATURE_LABELS),
        "latest_candle": {
            "body_change_pct": _round_float(body_position),
            "upper_shadow_ratio": _round_float(upper_shadow_ratio),
        },
        "support_zone": technical_profile.get("support_levels") or [],
        "resistance_zone": technical_profile.get("resistance_levels") or [],
        "breakout_trigger": _round_float(breakout_price),
        "failure_level": _round_float(failure_level),
        "risk_flags": risk_flags[:5],
        "risk_flag_labels": _risk_flag_labels(risk_flags[:5]),
        "continuation_condition": technical_profile.get("continuation_condition"),
        "invalidation_condition": technical_profile.get("invalidation_condition"),
        "ai_prompt_hint": ai_prompt_hint,
    }


def _technical_profile_for_ai(item: dict, daily_rows: list[dict]) -> dict:
    rows = [row for row in daily_rows if isinstance(row, dict)]
    closes = _last_float_values(rows, "close")
    highs = _last_float_values(rows, "high")
    lows = _last_float_values(rows, "low")
    volumes = _last_float_values(rows, "volume")
    latest_row = rows[-1] if rows else {}
    latest_close = closes[-1] if closes else _candidate_latest_close(item)
    ma5 = _simple_ma(closes, 5) if len(closes) >= 5 else None
    ma10 = _simple_ma(closes, 10) if len(closes) >= 10 else None
    ma20 = _simple_ma(closes, 20) if len(closes) >= 20 else None
    prev_ma5 = _simple_ma(closes, 5, end_index=len(closes) - 1) if len(closes) >= 6 else None
    ma5_slope = ((ma5 / prev_ma5) - 1) * 100 if ma5 is not None and prev_ma5 and prev_ma5 > 0 else None
    avg_vol_5 = _average(volumes[-6:-1]) if len(volumes) >= 6 else _average(volumes[:-1])
    avg_vol_20 = _average(volumes[-21:-1]) if len(volumes) >= 21 else _average(volumes[:-1])
    latest_volume = volumes[-1] if volumes else None
    volume_ratio_5 = latest_volume / avg_vol_5 if latest_volume is not None and avg_vol_5 and avg_vol_5 > 0 else None
    volume_ratio_20 = latest_volume / avg_vol_20 if latest_volume is not None and avg_vol_20 and avg_vol_20 > 0 else None
    month_return = ((latest_close / closes[0]) - 1) * 100 if latest_close is not None and closes and closes[0] else None
    high_20 = max(highs[-20:]) if highs else None
    low_20 = min(lows[-20:]) if lows else None
    high_5 = max(highs[-5:]) if highs else None
    low_5 = min(lows[-5:]) if lows else None
    breakout_price = _candidate_breakout_price(item)
    signal_low = _candidate_signal_low(item)

    support_levels = _round_unique_levels(
        sorted(
            [
                signal_low,
                low_5,
                ma5 if ma5 is not None and latest_close is not None and ma5 <= latest_close else None,
                ma10 if ma10 is not None and latest_close is not None and ma10 <= latest_close else None,
                ma20 if ma20 is not None and latest_close is not None and ma20 <= latest_close else None,
                low_20,
            ],
            key=lambda value: abs((latest_close or 0) - (value or 0)) if value is not None else float("inf"),
        ),
        limit=4,
    )
    resistance_levels = _round_unique_levels(
        sorted(
            [
                breakout_price,
                high_5,
                high_20,
                ma5 if ma5 is not None and latest_close is not None and ma5 > latest_close else None,
                ma10 if ma10 is not None and latest_close is not None and ma10 > latest_close else None,
                ma20 if ma20 is not None and latest_close is not None and ma20 > latest_close else None,
            ],
            key=lambda value: abs((latest_close or 0) - (value or 0)) if value is not None else float("inf"),
        ),
        limit=4,
    )
    trend_state = _one_month_trend_state(
        close=latest_close,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        month_return=month_return,
    )
    technical_risks = _technical_risk_notes(
        item=item,
        latest_row=latest_row,
        close=latest_close,
        ma20=ma20,
        volume_ratio_20d=volume_ratio_20,
        breakout_price=breakout_price,
    )
    return {
        "daily_bar_count": len(rows),
        "as_of_date": str(latest_row.get("date") or "")[:10] if latest_row else None,
        "latest_close": _round_float(latest_close),
        "ma5": _round_float(ma5),
        "ma10": _round_float(ma10),
        "ma20": _round_float(ma20),
        "ma5_slope_pct": _round_float(ma5_slope),
        "close_vs_ma5_pct": _round_float(((latest_close / ma5) - 1) * 100 if latest_close is not None and ma5 else None),
        "close_vs_ma20_pct": _round_float(((latest_close / ma20) - 1) * 100 if latest_close is not None and ma20 else None),
        "one_month_return_pct": _round_float(month_return),
        "month_high": _round_float(high_20),
        "month_low": _round_float(low_20),
        "five_day_high": _round_float(high_5),
        "five_day_low": _round_float(low_5),
        "volume_avg_5d": _round_float(avg_vol_5, 0),
        "volume_avg_20d": _round_float(avg_vol_20, 0),
        "volume_ratio_5d": _round_float(volume_ratio_5),
        "volume_ratio_20d": _round_float(volume_ratio_20),
        "one_month_trend": trend_state,
        "candle_pattern": ((item.get("candlestick_profile") or {}).get("summary") or ""),
        "support_levels": support_levels,
        "resistance_levels": resistance_levels,
        "breakout_trigger": _round_float(breakout_price),
        "failure_level": _round_float(signal_low or low_5 or ma20),
        "continuation_condition": (
            f"突破並收盤站上 {_fmt_num(breakout_price, 2)}，且量比20日不低於1"
            if breakout_price is not None
            else "量價同步轉強且收盤站回短期均線"
        ),
        "invalidation_condition": (
            f"跌破 {_fmt_num(signal_low or low_5 or ma20, 2)}"
            if (signal_low or low_5 or ma20) is not None
            else "跌破最近有效低點"
        ),
        "technical_risk": "；".join(technical_risks) if technical_risks else "等待突破與量能確認",
    }


def _primary_role_for_ai(item: dict, validation: dict) -> str:
    status = str(validation.get("signal_status") or item.get("signal_status") or "").lower()
    if status == "confirmed_uptrend":
        return "validation_followup"
    if status in {"failed_breakout", "invalidated"}:
        return "risk_watch"
    if _is_etf_like(item):
        return "etf_tool"
    if _has_breakout_signal(item):
        return "technical_breakout"
    if _positive_chip(item):
        return "institutional_accumulation"
    return "appendix_only"


def _candidate_for_ai(item: dict, validation_by_ticker: dict[str, dict], daily_rows: list[dict]) -> dict:
    ticker = str(item.get("ticker") or "").upper().strip()
    validation = validation_by_ticker.get(ticker) or {}
    ap = item.get("accumulation_profile") or {}
    chip = ap.get("chip") or {}
    cp = item.get("candlestick_profile") or {}
    technical_profile = _technical_profile_for_ai(item, daily_rows)
    kline_structure = _kline_structure_for_ai(item, daily_rows, technical_profile)
    return {
        "ticker": ticker,
        "name": item.get("name"),
        "instrument_type": _instrument_type(item),
        "sector": item.get("sector") or item.get("industry"),
        "theme_tags": _theme_tags_for_item(item),
        "candidate_grade": item.get("candidate_grade"),
        "candidate_priority_score": item.get("candidate_priority_score"),
        "risk_flags": item.get("risk_flags") or [],
        "risk_flag_labels": _risk_flag_labels(item.get("risk_flags") or []),
        "grade_reason": item.get("grade_reason"),
        "primary_theme": item.get("primary_theme"),
        "primary_theme_strength": item.get("primary_theme_strength"),
        "primary_role": _primary_role_for_ai(item, validation),
        "total_score": item.get("total_score"),
        "score_breakdown": {
            "price_score": item.get("price_score"),
            "breakout_score": item.get("breakout_score"),
            "volume_score": item.get("volume_score"),
            "institutional_score": item.get("institutional_score"),
            "kline_score": item.get("kline_score"),
        },
        "signal_status": validation.get("signal_status") or item.get("signal_status"),
        "latest_close": _round_float(validation.get("latest_close") or _candidate_latest_close(item)),
        "breakout_price": _round_float(validation.get("breakout_price") or _candidate_breakout_price(item)),
        "signal_low": _round_float(_candidate_signal_low(item)),
        "return_1d": item.get("return_1d"),
        "return_3d": item.get("return_3d"),
        "return_5d": item.get("return_5d"),
        "historical_hit_rate": item.get("historical_status_hit_rate"),
        "kline_summary": cp.get("summary"),
        "kline_detail": _k_text(item),
        "chip": {
            "institutional_5d_sum": chip.get("institutional_5d_sum"),
            "foreign_5d_sum": chip.get("foreign_5d_sum"),
            "investment_trust_10d_sum": chip.get("investment_trust_10d_sum"),
            "dealer_5d_sum": chip.get("dealer_5d_sum"),
        },
        "news_event_digest": item.get("news_event_digest"),
        "one_month_daily_bars": daily_rows,
        "daily_bars_1m": daily_rows,
        "technical_profile": technical_profile,
        "kline_structure": kline_structure,
        "support_resistance": {
            "support_levels": technical_profile.get("support_levels"),
            "resistance_levels": technical_profile.get("resistance_levels"),
            "breakout_trigger": technical_profile.get("breakout_trigger"),
            "failure_level": technical_profile.get("failure_level"),
            "continuation_condition": technical_profile.get("continuation_condition"),
            "invalidation_condition": technical_profile.get("invalidation_condition"),
        },
        "volume_profile": {
            "volume_avg_5d": technical_profile.get("volume_avg_5d"),
            "volume_avg_20d": technical_profile.get("volume_avg_20d"),
            "volume_ratio_5d": technical_profile.get("volume_ratio_5d"),
            "volume_ratio_20d": technical_profile.get("volume_ratio_20d"),
        },
    }


def _ai_context_ticker_pool(
    *,
    graded_candidates: list[dict],
    selected_stocks: list[dict],
    selected_etfs: list[dict],
    strong_stock_candidates: list[dict],
    bullish_stock_candidates: list[dict],
    ma5_walk_candidates: list[dict],
    max_tickers: int,
) -> list[dict]:
    """Prioritize candidates the AI is expected to judge, then fill with supporting lists."""

    graded_watchlist = [item for item in graded_candidates if str(item.get("candidate_grade") or "X").upper() != "X"]
    if len(graded_watchlist) < min(max_tickers, 12):
        graded_watchlist.extend(
            item
            for item in graded_candidates
            if str(item.get("candidate_grade") or "X").upper() == "X"
        )
    graded_focus = graded_watchlist[: min(max_tickers, 12)]
    supplemental = (
        selected_etfs[:6]
        + selected_stocks[:12]
        + strong_stock_candidates[:8]
        + bullish_stock_candidates[:8]
        + ma5_walk_candidates[:8]
    )
    return _dedupe_candidates(graded_focus + supplemental)[:max_tickers]


def _build_codex_analysis_context(
    *,
    base_url: str,
    report_date: str,
    coverage: dict,
    status_counts: Counter,
    market_context: dict,
    taifex: dict | None,
    structured: dict,
    sector_rows: list[dict],
    theme_rows: list[dict],
    electronic_theme_rows: list[dict],
    graded_candidates: list[dict],
    selected_stocks: list[dict],
    selected_etfs: list[dict],
    strong_stock_candidates: list[dict],
    bullish_stock_candidates: list[dict],
    ma5_walk_candidates: list[dict],
    signal_validation_rows: list[dict],
    signal_backtest_summary: dict,
    news_records: list[dict],
    market_news: list[dict],
    validation_by_ticker: dict[str, dict],
    max_tickers: int,
    history_days: int,
) -> dict:
    ticker_pool = _ai_context_ticker_pool(
        graded_candidates=graded_candidates,
        selected_stocks=selected_stocks,
        selected_etfs=selected_etfs,
        strong_stock_candidates=strong_stock_candidates,
        bullish_stock_candidates=bullish_stock_candidates,
        ma5_walk_candidates=ma5_walk_candidates,
        max_tickers=max_tickers,
    )
    graded_by_ticker = {str(item.get("ticker") or "").upper().strip(): item for item in graded_candidates}
    candidates_for_ai: list[dict] = []
    for item in ticker_pool:
        ticker = str(item.get("ticker") or "").upper().strip()
        if ticker in graded_by_ticker:
            item = {**item, **graded_by_ticker[ticker]}
        rows = _fetch_recent_daily_rows(base_url, ticker, period="3mo") if ticker else []
        daily_rows = _daily_rows_for_ai(rows, history_days=history_days)
        candidates_for_ai.append(_candidate_for_ai(item, validation_by_ticker, daily_rows))

    return {
        "report_date": report_date,
        "codex_analysis_output_path": str(_codex_automation_analysis_path(report_date)),
        "ai_output_contract": {
            "allowed_sections": [
                "一句話結論",
                "主線排序",
                "K線結構判讀",
                "優先觀察標的",
                "反證與降權",
                "明日盯盤劇本",
                "今日不做什麼",
            ],
            "avoid_duplicate_sections": [
                "可能轉強族群",
                "ETF / 基金 / REIT 候選",
                "新聞與事件雷達",
                "隔日三情境交易策略",
                "完整候選表",
            ],
            "decision_limits": {
                "max_themes": 3,
                "max_stocks": 5,
                "max_etf_fund_reit": 3,
                "max_rejection_points": 5,
            },
            "primary_evidence": [
                "graded_candidates",
                "electronic_theme_rotation",
                "theme_rotation",
                "candidates.kline_structure",
                "candidates.technical_profile",
                "candidates.daily_bars_1m",
                "signal_backtest_summary",
                "news_packet",
            ],
            "note": "AI section is a decision memo: rank, select, reject, and define invalidation. Deterministic tables remain the single source of tabular truth later in the report.",
        },
        "data_policy": {
            "history_days_per_candidate": history_days,
            "ai_candidate_ticker_count": len(ticker_pool),
            "ai_candidate_tickers": [item.get("ticker") for item in ticker_pool],
            "note": "AI receives at least one month of compact daily bars, technical profiles, news packet, and computed scores for every ticker in candidates; top graded watchlist names are prioritized before supplemental lists.",
        },
        "memo_policy": {
            "style": "盤後決策 Memo，不重述表格，不寫固定模板句。",
            "must_explain": ["為什麼列入", "如果判斷錯了看什麼反證", "隔日只觀察哪些價格或條件"],
            "watchlist_only": "候選標的是觀察清單，不是買賣建議。",
            "kline_rule": "K線型態只能根據 kline_structure、technical_profile 與 daily_bars_1m 判讀，不可自行補價格；輸出時優先使用 *_label 與 risk_flag_labels，不要把工程 enum 直接寫進報告。",
        },
        "coverage": coverage,
        "history_status_counts": dict(status_counts),
        "data_quality_flags": _data_quality_flags_for_ai(coverage=coverage, status_counts=status_counts, taifex=taifex),
        "market_context": market_context,
        "taifex_summary": {
            "resolved_date": (taifex or {}).get("resolved_date") if isinstance(taifex, dict) else None,
            "position_summary": _summarize_taifex_position(structured),
        },
        "electronic_theme_rotation": electronic_theme_rows[:8],
        "theme_rotation": theme_rows[:10],
        "sector_rotation": sector_rows[:8],
        "signal_validation": signal_validation_rows[:15],
        "signal_backtest_summary": signal_backtest_summary,
        "graded_candidates": [
            {
                "ticker": item.get("ticker"),
                "name": item.get("name"),
                "instrument_type": _instrument_type(item),
                "sector": item.get("sector") or item.get("industry"),
                "theme_tags": _theme_tags_for_item(item),
                "primary_theme": item.get("primary_theme"),
                "candidate_grade": item.get("candidate_grade"),
                "candidate_priority_score": item.get("candidate_priority_score"),
                "risk_flags": item.get("risk_flags") or [],
                "risk_flag_labels": _risk_flag_labels(item.get("risk_flags") or []),
                "grade_reason": item.get("grade_reason"),
                "breakout_price": _round_float(_candidate_breakout_price(item)),
                "signal_low": _round_float(_candidate_signal_low(item)),
            }
            for item in graded_candidates[:15]
        ],
        "candidates": candidates_for_ai,
        "news_packet": _news_packet_for_ai(
            candidates=ticker_pool,
            sector_rows=sector_rows,
            news_records=news_records,
            market_news=market_news,
            limit=40,
        ),
        "news_events": _dedupe_news_records(market_news + news_records, limit=40),
    }


def _codex_automation_analysis_path(report_date: str) -> Path:
    raw_path = str(os.environ.get("DAILY_REPORT_CODEX_ANALYSIS_PATH") or "").strip()
    if raw_path:
        path = Path(raw_path.format(date=report_date))
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / path
        return path
    return _report_log_dir() / f"codex_ai_analysis_{report_date}.md"


def _read_codex_automation_analysis(report_date: str) -> tuple[str | None, Path]:
    path = _codex_automation_analysis_path(report_date)
    if not path.exists():
        return None, path
    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception as exc:  # noqa: BLE001
        return f"Codex analysis file read failed: {type(exc).__name__}: {exc}", path
    if not text:
        return None, path
    return text[:12000], path


def _extract_openai_response_text(payload: dict) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    chunks: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    return "\n\n".join(chunks).strip()


_DUPLICATE_AI_SECTION_KEYWORDS = (
    "可能轉強族群",
    "主題族群雷達",
    "個股觀察清單",
    "ETF / 基金 / REIT 觀察",
    "ETF / 基金 / REIT 候選",
    "新聞與事件雷達",
    "隔日三情境交易策略",
    "訊號後績效驗證摘要",
    "法人偏多候選",
    "強勢股 / 多頭股",
    "完整候選表",
)


def _sanitize_codex_analysis_text(text: str) -> tuple[str, list[str]]:
    """Keep Codex/AI output focused on synthesis and remove duplicate report tables."""

    removed: list[str] = []
    kept: list[str] = []
    skipping = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        heading = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
        if heading:
            title = heading.group(2).strip()
            if title.lower().startswith("codex/ai"):
                skipping = False
                continue
            duplicate = next((keyword for keyword in _DUPLICATE_AI_SECTION_KEYWORDS if keyword in title), None)
            if duplicate:
                removed.append(title)
                skipping = True
                continue
            skipping = False
        if not skipping:
            kept.append(line)
    sanitized = "\n".join(kept).strip()
    if removed:
        sanitized += (
            "\n\n> 已省略 AI 檔內與正式資料表重複的章節："
            + "、".join(dict.fromkeys(removed))
            + "。完整表格請以下方程式產生區塊為準。"
        )
    return _localize_user_facing_report_terms(sanitized), removed


def _call_openai_for_codex_analysis(context: dict) -> tuple[str | None, str | None]:
    api_key = str(os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None, "OPENAI_API_KEY is not set"
    model = str(os.environ.get("DAILY_REPORT_AI_MODEL") or "gpt-5").strip()
    max_output_tokens = _env_int("DAILY_REPORT_AI_MAX_OUTPUT_TOKENS", 2200, minimum=600, maximum=6000)
    timeout_seconds = _env_int("DAILY_REPORT_AI_TIMEOUT_SECONDS", 90, minimum=20, maximum=300)
    instructions = (
        "你是保守、嚴謹的台股盤後交易策略分析助理。"
        "只能根據輸入 JSON 的資料解讀，不得編造未提供的價格、新聞、財報或籌碼。"
        "請使用繁體中文，輸出 Markdown。"
        "請把輸出寫成『Codex/AI 盤後決策 Memo』，不是一般摘要。"
        "AI 段落只能做決策綜合：必須排序、選擇、降權與排除，不要重複輸出正式報告後段已有的完整資料表。"
        "必須使用以下小節標題：### 一句話結論、### 主線排序、### K線結構判讀、### 優先觀察標的、### 反證與降權、### 明日盯盤劇本、### 今日不做什麼。"
        "請優先使用 graded_candidates；若你的排序不同於 candidate_grade 或 candidate_priority_score，必須說明差異原因。"
        "主線最多列 3 個，個股最多列 5 檔，ETF/基金/REIT 最多列 3 檔；其餘只放入降權或不處理原因。"
        "K線結構判讀必須根據每檔候選的 kline_structure、daily_bars_1m 與 technical_profile，分類為平台突破嘗試、趨勢延續、回測後站回短均、箱型整理、短線乖離偏大或假突破風險。"
        "輸出時請優先使用中文說明，不得直接輸出 strength_score、count、structure_label、trend_quality_label、close_location_label、volume_signature_label、risk_flag_labels、false_breakout_risk、breakout_with_volume、near_20d_high、low_hit_rate_type 這類欄位名或工程 enum。"
        "支撐、壓力、突破價、失敗價只能引用 JSON 中 support_resistance、kline_structure 或 technical_profile 已提供的數字。"
        "每個被選入的主線或標的都要寫『因為』與『如果錯了怎麼辦』；避免只寫突破確認、量能不縮這類沒有價格或條件的空泛句。"
        "新聞解讀需使用 news_packet，區分高相關、中相關與低相關；低相關新聞只做風險或背景提醒。"
        "候選標的是觀察清單，不是買賣建議；避免保證式語氣。"
    )
    user_text = (
        "請根據以下程式篩選後的候選標的與近一個月資料，寫出可放進每日報告的 Codex/AI 盤後決策 Memo。\n\n"
        + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    )
    payload = {
        "model": model,
        "instructions": instructions,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": user_text}]}],
        "max_output_tokens": max_output_tokens,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        method="POST",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            result = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    text = _extract_openai_response_text(result if isinstance(result, dict) else {})
    if not text:
        return None, "OpenAI response did not contain output text"
    return text, None


def _codex_analysis_section(context: dict) -> list[str]:
    report_date = str(context.get("report_date") or _now_tw().strftime("%Y-%m-%d"))
    automation_text, automation_path = _read_codex_automation_analysis(report_date)
    if automation_text and not automation_text.startswith("Codex analysis file read failed:"):
        sanitized_text, _removed = _sanitize_codex_analysis_text(automation_text)
        return [
            "## 1A) Codex/AI 綜合分析",
            f"- 來源：Codex 自動化分析檔 `{automation_path}`",
            "",
            sanitized_text or "（Codex/AI 分析檔沒有可放入主報告的摘要內容。）",
            "",
        ]

    enabled = _env_flag_auto("DAILY_REPORT_AI_ANALYSIS_ENABLED", default="auto")
    has_key = bool(str(os.environ.get("OPENAI_API_KEY") or "").strip())
    if enabled == "false" or (enabled == "auto" and not has_key):
        extra = (
            f"- 尚未找到 Codex 自動化分析檔：`{automation_path}`。"
            "Codex 自動化可先讀取 `codex_report_context_YYYY-MM-DD.json`，寫出此檔後再寄送正式報告。"
        )
        if automation_text:
            extra = f"- {automation_text}"
        return [
            "## 1A) Codex/AI 綜合分析",
            extra,
            "- 若不使用 Codex 自動化，也可在 `.env` 設定 `OPENAI_API_KEY` 啟用 API 版 AI 解讀。",
            "- 目前報告仍由程式規則完成：篩選、分數、訊號驗證、族群與新聞整理皆會正常輸出。",
            "",
        ]
    text, error = _call_openai_for_codex_analysis(context)
    if error:
        return [
            "## 1A) Codex/AI 綜合分析",
            f"- AI 二次解讀失敗：{_table_cell(error, width=140)}",
            "- 已改用程式規則報告；候選標的、分數、訊號驗證與新聞事件仍正常輸出。",
            "",
        ]
    sanitized_text, _removed = _sanitize_codex_analysis_text(text or "")
    return ["## 1A) Codex/AI 綜合分析", sanitized_text or "（AI 未回傳內容）", ""]


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

    # Gmail has a narrow reading pane and ignores some responsive CSS, so the
    # candidate section is split into smaller bordered tables instead of one
    # very wide table. This preserves every score/detail while avoiding overflow.
    lines.append(
        "| 類型 | 代號 | 名稱 | 族群/產業 | total_score | 近1日績效 | 近3日績效 | 近5日績效 | 歷史同類型命中率 |"
    )
    lines.append("|---|---|---|---|---:|---:|---:|---:|---:|")
    for it in candidates:
        sector = it.get("sector") or it.get("industry") or "—"
        theme = _theme_text(it)
        if theme != "—":
            sector = f"{sector} / {theme}"
        lines.append(
            "| "
            + " | ".join(
                [
                    _table_cell(_instrument_type(it)),
                    _table_cell(it.get("ticker")),
                    _table_cell(it.get("name")),
                    _table_cell(sector, width=32),
                    _table_cell(_fmt_int(it.get("total_score"))),
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
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("**分項分數**")
    lines.append(
        "| 代號 | price_score | breakout_score | volume_score | institutional_score | kline_score | API原始潛伏分 | K線分數 |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for it in candidates:
        lines.append(
            "| "
            + " | ".join(
                [
                    _table_cell(it.get("ticker")),
                    _table_cell(_fmt_int(it.get("price_score"))),
                    _table_cell(_fmt_int(it.get("breakout_score"))),
                    _table_cell(_fmt_int(it.get("volume_score"))),
                    _table_cell(_fmt_int(it.get("institutional_score"))),
                    _table_cell(_fmt_int(it.get("kline_score"))),
                    _table_cell(_fmt_int(it.get("accumulation_score"))),
                    _table_cell(_fmt_int(it.get("candlestick_score"))),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("**觀察說明**")
    lines.append("| 代號 | AI篩選說明 | K線判讀 | 籌碼重點 | 新聞/事件 | 隔日策略 |")
    lines.append("|---|---|---|---|---|---|")
    for it in candidates:
        cp = it.get("candlestick_profile") or {}
        k_level = _classify_k(it.get("candlestick_score"), cp.get("bias"))
        k_summary = f"{cp.get('summary') or '未見明確型態'}（{k_level}）"
        lines.append(
            "| "
            + " | ".join(
                [
                    _table_cell(it.get("ticker")),
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


def _graded_candidate_table_lines(title: str, candidates: list[dict], *, limit: int = 12) -> list[str]:
    lines = [title]
    if not candidates:
        lines.append("- （目前沒有可分級的候選標的。）")
        lines.append("")
        return lines

    visible = [item for item in candidates if item.get("candidate_grade") != "X"][:limit]
    if not visible:
        visible = candidates[: min(limit, len(candidates))]
    x_count = sum(1 for item in candidates if item.get("candidate_grade") == "X")
    lines.append(
        f"- 依主題強度、量價、法人、訊號驗證與風險旗標重新排序；X 級 {x_count} 檔僅保留在後方完整表格或附錄觀察。"
    )
    lines.append("| 等級 | 類型 | 代號 | 名稱 | 主題 | 優先分 | 觸發價 | 失敗線 | 觀察理由 | 風險旗標 |")
    lines.append("|---|---|---|---|---|---:|---:|---:|---|---|")
    for item in visible:
        trigger = _candidate_breakout_price(item)
        failure = _candidate_signal_low(item)
        flags = item.get("risk_flags") if isinstance(item.get("risk_flags"), list) else []
        lines.append(
            "| "
            + " | ".join(
                [
                    _table_cell(item.get("candidate_grade")),
                    _table_cell(_instrument_type(item)),
                    _table_cell(item.get("ticker")),
                    _table_cell(item.get("name")),
                    _table_cell(item.get("primary_theme") or _theme_text(item), width=26),
                    _table_cell(_fmt_num(item.get("candidate_priority_score"), 1)),
                    _table_cell(_fmt_num(trigger, 2)),
                    _table_cell(_fmt_num(failure, 2)),
                    _table_cell(item.get("grade_reason"), width=86),
                    _table_cell(_risk_flag_text(flags), width=48),
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
    "table_wrap": "margin:12px 0 22px;background:#ffffff;max-width:100%;",
    "table": (
        "border-collapse:collapse;width:100%;max-width:100%;table-layout:fixed;"
        "font-size:13px;border:1px solid #9ca3af;"
    ),
    "th": (
        "border:1px solid #9ca3af;padding:8px 10px;text-align:left;vertical-align:top;"
        "background:#eef2f7;color:#111827;font-weight:700;white-space:normal;"
        "word-break:break-word;overflow-wrap:anywhere;"
    ),
    "td": (
        "border:1px solid #9ca3af;padding:8px 10px;text-align:left;vertical-align:top;"
        "background:#ffffff;color:#1f2937;white-space:normal;word-break:break-word;overflow-wrap:anywhere;"
    ),
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


def _theme_strength_lookup(*rows_groups: list[dict]) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for rows in rows_groups:
        for row in rows:
            theme = str(row.get("theme") or "").strip()
            if not theme:
                continue
            current = lookup.get(theme)
            if current is None or float(row.get("strength_score") or 0) > float(current.get("strength_score") or 0):
                lookup[theme] = row
    return lookup


def _candidate_theme_row(item: dict, theme_lookup: dict[str, dict]) -> dict:
    best: dict = {}
    for tag in _theme_tags_for_item(item):
        row = theme_lookup.get(tag) or {}
        if float(row.get("strength_score") or 0) > float(best.get("strength_score") or 0):
            best = row
    return best


def _candidate_risk_flags(item: dict, validation: dict, theme_row: dict) -> list[str]:
    flags: list[str] = []
    status = str(validation.get("signal_status") or item.get("signal_status") or "").lower()
    if status in {"failed_breakout", "invalidated"}:
        flags.append("failed_recent_signal")

    close = _candidate_latest_close(item)
    ma5 = _recent_metric(item, "ma5")
    ma20 = _recent_metric(item, "ma20") or _to_float(item.get("ma20"))
    if close is not None and ma5 is not None and ma5 > 0 and (close - ma5) / ma5 * 100 >= 8:
        flags.append("overextended_ma5")
    if close is not None and ma20 is not None and ma20 > 0 and (close - ma20) / ma20 * 100 >= 15:
        flags.append("overextended_ma20")

    latest = (item.get("candlestick_profile") or {}).get("latest") or {}
    high = _to_float(latest.get("high"))
    open_ = _to_float(latest.get("open"))
    close_latest = _to_float(latest.get("close"))
    if high is not None and open_ is not None and close_latest is not None:
        body = abs(close_latest - open_)
        upper = high - max(close_latest, open_)
        if upper > max(body * 1.5, close_latest * 0.01):
            flags.append("long_upper_shadow")

    if not _volume_expanded(item) and float(item.get("volume_score") or 0) < 12:
        flags.append("thin_volume")

    if str(theme_row.get("state") or "") == "單點/小群強勢":
        flags.append("single_stock_theme")

    hit_rate = _to_float(item.get("historical_type_hit_rate"))
    sample_size = _to_float(item.get("historical_type_sample_size")) or 0
    if hit_rate is not None and sample_size >= 20 and hit_rate < 35:
        flags.append("low_hit_rate_type")

    if not _theme_tags_for_item(item):
        flags.append("no_focused_theme")

    return list(dict.fromkeys(flags))


def _grade_from_priority(priority_score: float, risk_flags: list[str], validation: dict) -> str:
    status = str(validation.get("signal_status") or "").lower()
    blocking = {"failed_recent_signal", "long_upper_shadow"}
    if status in {"failed_breakout", "invalidated"} or blocking.intersection(risk_flags):
        return "X"
    if priority_score >= 78 and len(risk_flags) <= 1:
        return "A"
    if priority_score >= 64 and len(risk_flags) <= 3:
        return "B"
    if priority_score >= 48:
        return "C"
    return "X"


def _grade_reason(item: dict, grade: str, theme_row: dict, risk_flags: list[str]) -> str:
    reasons: list[str] = []
    theme_text = _theme_text(item)
    if theme_text != "—":
        theme_score = theme_row.get("strength_score")
        if theme_score is not None:
            reasons.append(f"主題{theme_text}強度{_fmt_num(theme_score, 1)}")
        else:
            reasons.append(f"主題{theme_text}")
    if _has_breakout_signal(item):
        reasons.append("型態轉強/突破嘗試")
    if _volume_expanded(item):
        reasons.append("量能放大")
    if _positive_chip(item):
        reasons.append("法人籌碼偏多")
    if risk_flags:
        reasons.append("風險：" + _risk_flag_text(risk_flags[:3]))
    if not reasons:
        reasons.append("條件未完整，先列雷達觀察")
    return f"{grade}級：" + "；".join(reasons[:4])


def _attach_candidate_grades(
    candidates: list[dict],
    *,
    theme_lookup: dict[str, dict],
    validation_by_ticker: dict[str, dict],
) -> list[dict]:
    rows: list[dict] = []
    for item in candidates:
        row = dict(item)
        ticker = str(row.get("ticker") or "").upper().strip()
        validation = validation_by_ticker.get(ticker) or {}
        theme_row = _candidate_theme_row(row, theme_lookup)
        theme_score = min(float(theme_row.get("strength_score") or 0), 120.0) / 120.0 * 100.0
        base_score = float(row.get("total_score") or row.get("accumulation_score") or 0)
        momentum_score = min(max(_strong_stock_score(row), 0.0), 220.0) / 220.0 * 100.0
        volume_score = min(float(row.get("volume_score") or 0), 20.0) / 20.0 * 100.0
        institutional_score = min(float(row.get("institutional_score") or 0), 15.0) / 15.0 * 100.0
        validation_score = 50.0
        status = str(validation.get("signal_status") or row.get("signal_status") or "").lower()
        if status == "confirmed_uptrend":
            validation_score = 85.0
        elif status == "new_breakout":
            validation_score = 75.0
        elif status == "watch_only":
            validation_score = 55.0
        elif status in {"failed_breakout", "invalidated"}:
            validation_score = 10.0

        risk_flags = _candidate_risk_flags(row, validation, theme_row)
        risk_penalty = min(28.0, len(risk_flags) * 7.0)
        priority_score = (
            base_score * 0.35
            + theme_score * 0.2
            + momentum_score * 0.15
            + volume_score * 0.1
            + institutional_score * 0.1
            + validation_score * 0.1
            - risk_penalty
        )
        grade = _grade_from_priority(priority_score, risk_flags, validation)
        row["candidate_priority_score"] = round(priority_score, 1)
        row["candidate_grade"] = grade
        row["risk_flags"] = risk_flags
        row["grade_reason"] = _grade_reason(row, grade, theme_row, risk_flags)
        row["primary_theme"] = str(theme_row.get("theme") or (_theme_tags_for_item(row) or [""])[0] or "")
        row["primary_theme_strength"] = theme_row.get("strength_score")
        rows.append(row)

    grade_rank = {"A": 0, "B": 1, "C": 2, "X": 3}
    return sorted(
        rows,
        key=lambda row: (
            grade_rank.get(str(row.get("candidate_grade") or "X"), 9),
            -float(row.get("candidate_priority_score") or 0),
            str(row.get("ticker") or ""),
        ),
    )


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

    data_warning_reasons = _data_status_warning_reasons(
        cov_pct=cov_pct,
        universe_count=universe_count,
        newest_latest=newest_latest,
        expected_latest_date=report_date,
        status_counts=status_counts,
    )
    data_pool_incomplete = bool(data_warning_reasons)

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
        momentum_candidates = [_with_theme_tags(item) for item in _candidates_with_names(base_url, ms.get("items") or [])]
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
    candidates = [_with_theme_tags(item) for item in _candidates_with_names(base_url, candidates_raw)]
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
    electronic_theme_rows = _electronic_theme_rotation_rows(profiled_common_pool)
    theme_rows = _theme_rotation_rows(profiled_common_pool)
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
    theme_lookup = _theme_strength_lookup(electronic_theme_rows, theme_rows)
    graded_candidates = _attach_candidate_grades(
        _dedupe_candidates(
            selected_stocks
            + selected_etfs
            + strong_stock_candidates
            + bullish_stock_candidates
            + ma5_walk_candidates
        ),
        theme_lookup=theme_lookup,
        validation_by_ticker=signal_validation_by_ticker,
    )
    selected_candidates = selected_stocks + selected_etfs
    news_records = _enrich_news_for_candidates(
        base_url,
        selected_candidates,
        report_date=report_date,
        refresh_limit=12,
    )
    generated_market_news = _market_news_records(electronic_theme_rows + theme_rows + sector_rows, report_date=report_date)
    _store_news_records(base_url, generated_market_news, report_date=report_date)
    market_news = _dedupe_news_records(
        _fetch_db_news_records(base_url, report_date=report_date, limit=24) + generated_market_news,
        limit=24,
    )
    ai_max_tickers = _env_int("DAILY_REPORT_AI_MAX_TICKERS", 18, minimum=4, maximum=40)
    ai_history_days = _env_int("DAILY_REPORT_AI_HISTORY_DAYS", 30, minimum=22, maximum=60)
    codex_context = _build_codex_analysis_context(
        base_url=base_url,
        report_date=report_date,
        coverage=cov,
        status_counts=status_counts,
        market_context=market_context,
        taifex=taifex,
        structured=structured,
        sector_rows=sector_rows,
        theme_rows=theme_rows,
        electronic_theme_rows=electronic_theme_rows,
        graded_candidates=graded_candidates,
        selected_stocks=selected_stocks,
        selected_etfs=selected_etfs,
        strong_stock_candidates=strong_stock_candidates,
        bullish_stock_candidates=bullish_stock_candidates,
        ma5_walk_candidates=ma5_walk_candidates,
        signal_validation_rows=signal_validation_rows,
        signal_backtest_summary=signal_backtest_summary,
        news_records=news_records,
        market_news=market_news,
        validation_by_ticker=signal_validation_by_ticker,
        max_tickers=ai_max_tickers,
        history_days=ai_history_days,
    )
    codex_context_file: Path | None = None
    codex_context_error: str | None = None
    try:
        codex_context_file = _report_log_dir() / f"codex_report_context_{report_date}.json"
        codex_context_file.write_text(json.dumps(codex_context, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        codex_context_error = str(exc)

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

    if data_pool_incomplete:
        lines.append("## 0) 資料狀態警示")
        lines.append("- 資料狀態：警示；候選清單需降權觀察。")
        lines.append("- 警示原因：" + "；".join(data_warning_reasons))
        lines.append("- 完整 API / 資料池檢查已移至文末附錄。")
        lines.append("")

    lines.append("## 1) 今日結論（可執行）")
    if data_pool_incomplete:
        lines.append("- 資料狀態：警示；" + "；".join(data_warning_reasons))
    else:
        lines.append("- 資料狀態：正常；完整 API / 資料池檢查請見文末附錄。")
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

    lines.extend(_codex_analysis_section(codex_context))

    lines.extend(_graded_candidate_table_lines("## 1B) 今日優先觀察清單（A/B/C 分級）", graded_candidates))

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

    lines.append("## 6) 電子主題強弱雷達")
    lines.append(
        "- 這一節只看電子大族群內的細分供應鏈，優先回答：電子股裡今天資金集中在哪些主題。"
    )
    lines.append("| 電子主題 | 狀態 | 強度分數 | 樣本數 | 動能均分 | 法人/外資偏多數 | 突破/轉強數 | 量能放大數 | 站上MA20數 | 代表標的 | 觀察重點 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
    if not electronic_theme_rows:
        lines.append("| — | — | — | 0 | — | 0 | 0 | 0 | 0 | — | （目前電子細分主題樣本不足，暫無可用統計） |")
    else:
        for row in electronic_theme_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _table_cell(row["theme"]),
                        _table_cell(row.get("state")),
                        _table_cell(_fmt_num(row["strength_score"], 1)),
                        _table_cell(_fmt_int(row["count"])),
                        _table_cell(_fmt_num(row["avg_momentum"], 1)),
                        _table_cell(_fmt_int(row["chip_count"])),
                        _table_cell(_fmt_int(row["breakout_count"])),
                        _table_cell(_fmt_int(row["volume_count"])),
                        _table_cell(_fmt_int(row["ma20_count"])),
                        _table_cell(row["representatives"], width=72),
                        _table_cell(row["watch"], width=78),
                    ]
                )
                + " |"
            )
    lines.append("")

    lines.append("## 6A) 主題族群雷達（全市場細分）")
    lines.append(
        "- 這一節以主題/供應鏈標籤計算，例如矽光通訊/CPO、被動元件、ABF/載板、PCB、LED、AI Server 等；來源涵蓋較大的強勢股池，不只限於潛伏候選。"
    )
    lines.append("| 主題族群 | 強度分數 | 樣本數 | 動能均分 | 平均潛伏總分 | 平均K線分數 | 法人/外資偏多數 | 突破/轉強數 | 量能放大數 | 站上MA20數 | 代表標的 | 觀察重點 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|")
    if not theme_rows:
        lines.append("| — | — | 0 | — | — | — | 0 | 0 | 0 | 0 | — | （目前主題標籤樣本不足，暫無可用細分族群統計） |")
    else:
        for row in theme_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _table_cell(row["theme"]),
                        _table_cell(_fmt_num(row["strength_score"], 1)),
                        _table_cell(_fmt_int(row["count"])),
                        _table_cell(_fmt_num(row["avg_momentum"], 1)),
                        _table_cell(_fmt_num(row["avg_acc"], 1)),
                        _table_cell(_fmt_num(row["avg_k"], 1)),
                        _table_cell(_fmt_int(row["chip_count"])),
                        _table_cell(_fmt_int(row["breakout_count"])),
                        _table_cell(_fmt_int(row["volume_count"])),
                        _table_cell(_fmt_int(row["ma20_count"])),
                        _table_cell(row["representatives"], width=72),
                        _table_cell(row["watch"], width=78),
                    ]
                )
                + " |"
            )
    lines.append("")

    lines.append("## 6B) 可能轉強族群（交易所產業）")
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
    all_news_records = _dedupe_news_records(market_news + news_records, limit=28)
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
                        _table_cell(_display_ticker(record)),
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
    lines.append("- 不交易條件：大盤跌破今日低點、外資期貨 OI 淨空單擴大且價格轉弱、或資料狀態出現重大警示")
    lines.append("- 行動：只保留觀察清單，等待「突破確認」或「回測不破」再出手")
    lines.append("")

    lines.append("## 附錄 A) API / 資料池檢查")
    lines.append(f"- API Base: {base_url}")
    lines.append(
        f"- GET /api/tw/universe/coverage?interval=1d：coverage={_fmt_num(cov_pct,2)}%（{covered_count}/{universe_count}），"
        f"oldest_latest_date/newest_latest_date={oldest_latest} → {newest_latest}"
    )
    lines.append(
        "- GET /api/tw/history/status："
        + "；".join(f"{k}={_fmt_int(v)}" for k, v in sorted(status_counts.items()))
    )
    lines.append("- 資料狀態：" + ("警示；" + "；".join(data_warning_reasons) if data_pool_incomplete else "正常"))
    lines.append(
        "- 台股歷史資料僅視為本機資料庫中的 **Fubon API（fubon_neo）** 同步結果；不使用 Yahoo 或其他來源補台股歷史。"
    )
    if signal_file:
        lines.append(f"- 今日 signal JSON 已保存：`{signal_file}`")
    if signal_store_error:
        lines.append(f"- 今日 signal JSON 保存失敗：{_table_cell(signal_store_error, width=120)}")
    if codex_context_file:
        lines.append(f"- Codex/AI 分析輸入 JSON 已保存：`{codex_context_file}`")
    if codex_context_error:
        lines.append(f"- Codex/AI 分析輸入保存失敗：{_table_cell(codex_context_error, width=120)}")

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
