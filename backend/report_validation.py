"""Validation helpers for generated report delivery."""

from __future__ import annotations


REQUIRED_DAILY_TW_REPORT_SECTIONS = (
    "API/資料池檢查",
    "今日結論",
    "Codex/AI 綜合分析",
    "法人偏多個股與 ETF 分類",
    "強勢股",
    "多頭股",
    "持續沿5日均線上漲的個股",
    "近5日訊號驗證",
    "訊號後績效驗證",
    "可能轉強族群",
    "個股潛伏起漲候選",
    "ETF/基金/REIT 候選",
    "新聞與事件雷達",
    "隔日三情境交易策略",
)


def missing_daily_tw_report_sections(markdown_text: str) -> list[str]:
    """Return required report sections that are absent from the final Markdown."""

    return [section for section in REQUIRED_DAILY_TW_REPORT_SECTIONS if section not in markdown_text]


def validate_daily_tw_report_sections(markdown_text: str) -> None:
    """Fail before email delivery when the final daily report is incomplete."""

    missing = missing_daily_tw_report_sections(markdown_text)
    if missing:
        raise ValueError("Daily TW report is missing required sections: " + ", ".join(missing))
