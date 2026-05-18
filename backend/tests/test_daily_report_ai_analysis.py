from __future__ import annotations

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
