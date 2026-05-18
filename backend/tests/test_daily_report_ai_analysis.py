from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for path in (str(PROJECT_ROOT), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from scripts import ai_daily_report_tw as report_tw  # noqa: E402


def test_daily_rows_for_ai_keeps_configured_one_month_window():
    rows = [
        {"date": f"2026-04-{day:02d}", "open": day, "high": day + 1, "low": day - 1, "close": day + 0.5, "volume": day * 1000}
        for day in range(1, 31)
    ]

    compact = report_tw._daily_rows_for_ai(rows, history_days=22)

    assert len(compact) == 22
    assert compact[0]["date"] == "2026-04-09"
    assert compact[-1] == {"date": "2026-04-30", "open": 30.0, "high": 31.0, "low": 29.0, "close": 30.5, "volume": 30000.0}


def _sample_daily_rows(count: int = 35) -> list[dict]:
    rows: list[dict] = []
    for index in range(count):
        day = index + 1
        close = 50 + index * 0.4
        rows.append(
            {
                "date": f"2026-04-{day:02d}" if day <= 30 else f"2026-05-{day - 30:02d}",
                "open": close - 0.3,
                "high": close + 0.8,
                "low": close - 0.8,
                "close": close,
                "volume": 100000 + index * 5000,
            }
        )
    return rows


def test_technical_profile_for_ai_calculates_one_month_levels():
    candidate = {
        "ticker": "2330.TW",
        "name": "台積電",
        "signal_status": "watch_only",
        "candlestick_profile": {
            "summary": "放量紅K / 突破嘗試",
            "latest": {"high": 64.4, "low": 62.8, "close": 63.6},
        },
    }
    rows = report_tw._daily_rows_for_ai(_sample_daily_rows(), history_days=30)

    profile = report_tw._technical_profile_for_ai(candidate, rows)

    assert profile["daily_bar_count"] == 30
    assert profile["ma5"] is not None
    assert profile["ma10"] is not None
    assert profile["ma20"] is not None
    assert profile["volume_ratio_20d"] is not None
    assert profile["support_levels"]
    assert profile["resistance_levels"]
    assert profile["breakout_trigger"] == 64.4
    assert profile["failure_level"] == 62.8
    assert "突破" in profile["continuation_condition"]


def test_codex_context_includes_news_packet_and_technical_profiles(monkeypatch):
    candidate = {
        "ticker": "2330.TW",
        "name": "台積電",
        "sector": "半導體業",
        "total_score": 70,
        "price_score": 20,
        "breakout_score": 5,
        "volume_score": 20,
        "institutional_score": 15,
        "kline_score": 10,
        "candlestick_profile": {
            "summary": "放量紅K / 突破嘗試",
            "patterns": [{"label": "突破嘗試"}],
            "latest": {"high": 64.4, "low": 62.8, "close": 63.6, "volume_expanded": True},
        },
        "accumulation_profile": {
            "chip": {"institutional_5d_sum": 1000, "foreign_5d_sum": 800, "investment_trust_10d_sum": 0}
        },
    }
    monkeypatch.setattr(report_tw, "_fetch_recent_daily_rows", lambda *_args, **_kwargs: _sample_daily_rows())

    context = report_tw._build_codex_analysis_context(
        base_url="http://qv",
        report_date="2026-05-18",
        coverage={"coverage_pct": 84.73},
        status_counts=Counter({"success": 10, "failed": 1}),
        market_context={"overall_risk": "high"},
        taifex=None,
        structured={"futures": {"items": []}, "options": {"items": []}},
        sector_rows=[{"sector": "半導體業"}],
        selected_stocks=[candidate],
        selected_etfs=[],
        strong_stock_candidates=[],
        bullish_stock_candidates=[],
        ma5_walk_candidates=[],
        signal_validation_rows=[],
        signal_backtest_summary={},
        news_records=[
            {
                "ticker": "2330.TW",
                "date": "2026-05-18",
                "title": "台積電帶動半導體族群",
                "source": "UnitTest",
                "url": "https://example.com/a",
            }
        ],
        market_news=[
            {
                "ticker": "MARKET",
                "display_ticker": "市場/族群",
                "date": "2026-05-18",
                "title": "台股盤後法人期貨焦點",
                "source": "UnitTest",
                "url": "https://example.com/b",
            }
        ],
        validation_by_ticker={},
        max_tickers=4,
        history_days=30,
    )

    assert context["ai_output_contract"]["allowed_sections"]
    assert context["data_quality_flags"]
    assert context["news_packet"]["items"]
    assert context["news_packet"]["candidate_news"][0]["relevance_score"] == 95
    assert len(context["candidates"][0]["daily_bars_1m"]) == 30
    assert context["candidates"][0]["technical_profile"]["ma20"] is not None
    assert context["candidates"][0]["support_resistance"]["breakout_trigger"] == 64.4


def test_extract_openai_response_text_supports_responses_output_shape():
    payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "第一段分析"},
                    {"type": "output_text", "text": "第二段分析"},
                ],
            }
        ]
    }

    assert report_tw._extract_openai_response_text(payload) == "第一段分析\n\n第二段分析"


def test_codex_analysis_section_skips_without_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DAILY_REPORT_AI_ANALYSIS_ENABLED", "auto")
    monkeypatch.setenv("DAILY_REPORT_CODEX_ANALYSIS_PATH", "__missing_codex_analysis__.md")

    lines = report_tw._codex_analysis_section({"report_date": "2026-05-13"})

    assert lines[0] == "## 1A) Codex/AI 綜合分析"
    assert "尚未找到 Codex 自動化分析檔" in lines[1]


def test_codex_analysis_section_prefers_codex_automation_file(monkeypatch, tmp_path):
    analysis_path = tmp_path / "codex_ai_analysis_2026-05-13.md"
    analysis_path.write_text("Codex 自動化產出的分析內容", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DAILY_REPORT_CODEX_ANALYSIS_PATH", str(analysis_path))

    lines = report_tw._codex_analysis_section({"report_date": "2026-05-13"})

    assert lines[0] == "## 1A) Codex/AI 綜合分析"
    assert str(analysis_path) in lines[1]
    assert "Codex 自動化產出的分析內容" in lines[3]


def test_codex_analysis_section_removes_duplicate_report_sections(monkeypatch, tmp_path):
    analysis_path = tmp_path / "codex_ai_analysis_2026-05-13.md"
    analysis_path.write_text(
        "\n".join(
            [
                "# Codex/AI 綜合分析",
                "## AI 今日主結論",
                "今日偏防守。",
                "## 可能轉強族群",
                "| 族群 | 分數 |",
                "|---|---:|",
                "| 半導體 | 60 |",
                "## 技術面重點",
                "新巨接近突破價。",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DAILY_REPORT_CODEX_ANALYSIS_PATH", str(analysis_path))

    lines = report_tw._codex_analysis_section({"report_date": "2026-05-13"})
    joined = "\n".join(lines)

    assert "今日偏防守" in joined
    assert "新巨接近突破價" in joined
    assert "| 半導體 | 60 |" not in joined
    assert "已省略 AI 檔內與正式資料表重複的章節" in joined


def test_codex_analysis_section_uses_model_when_enabled(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DAILY_REPORT_AI_ANALYSIS_ENABLED", "true")
    monkeypatch.setenv("DAILY_REPORT_CODEX_ANALYSIS_PATH", "__missing_codex_analysis__.md")

    def fake_call(context):
        assert context["report_date"] == "2026-05-13"
        return "AI 分析內容", None

    monkeypatch.setattr(report_tw, "_call_openai_for_codex_analysis", fake_call)

    lines = report_tw._codex_analysis_section({"report_date": "2026-05-13"})

    assert lines == ["## 1A) Codex/AI 綜合分析", "AI 分析內容", ""]


def test_candidate_tables_are_split_for_email_readability():
    candidate = {
        "ticker": "2330.TW",
        "name": "台積電",
        "sector": "半導體",
        "total_score": 88,
        "price_score": 30,
        "breakout_score": 18,
        "volume_score": 20,
        "institutional_score": 10,
        "kline_score": 10,
        "return_1d": 1.2,
        "return_3d": 2.3,
        "return_5d": 3.4,
        "historical_type_hit_rate": 55.5,
        "historical_type_sample_size": 12,
        "accumulation_score": 73,
        "candlestick_score": 82,
        "candlestick_profile": {"summary": "紅K轉強", "bias": "bullish"},
        "accumulation_profile": {"chip": {}},
    }

    lines = report_tw._candidate_table_lines("## 7) 個股潛伏起漲候選（Top 20）", [candidate])
    table_headers = [line for line in lines if line.startswith("|") and not line.startswith("|---")]

    assert any("total_score" in line for line in table_headers)
    assert any("price_score" in line and "kline_score" in line for line in table_headers)
    assert any("AI篩選說明" in line and "隔日策略" in line for line in table_headers)
    assert all(len(report_tw._split_markdown_table_row(line)) <= 9 for line in table_headers)

    html = report_tw.markdown_to_email_html("\n".join(lines))
    assert "table-layout:fixed" in html
    assert "overflow-wrap:anywhere" in html


def test_google_news_records_are_db_article_payloads():
    records = [
        {
            "ticker": "MARKET",
            "display_ticker": "市場/族群",
            "market": "TW",
            "type": "新聞",
            "date": "2026-05-18",
            "title": "台股盤後焦點",
            "source": "Google News",
            "url": "https://example.com/news",
            "query": "台股 盤後 2026-05-18",
            "payload": {"display_ticker": "市場/族群"},
        }
    ]

    payloads = report_tw._news_article_payloads_from_records(records, report_date="2026-05-18")

    assert payloads == [
        {
            "ticker": "MARKET",
            "market": "TW",
            "title": "台股盤後焦點",
            "summary": "台股 盤後 2026-05-18",
            "published_at": "2026-05-18T12:00:00+08:00",
            "source": "Google News",
            "url": "https://example.com/news",
            "sentiment": None,
            "payload": {"display_ticker": "市場/族群", "query": "台股 盤後 2026-05-18"},
        }
    ]


def test_news_record_dedupe_uses_date_and_title():
    rows = report_tw._dedupe_news_records(
        [
            {"ticker": "MARKET", "date": "2026-05-18", "title": "同一則新聞"},
            {"ticker": "2330.TW 台積電", "date": "2026-05-18", "title": "同一則新聞"},
            {"ticker": "MARKET", "date": "2026-05-18", "title": "另一則新聞"},
        ]
    )

    assert [row["title"] for row in rows] == ["同一則新聞", "另一則新聞"]
