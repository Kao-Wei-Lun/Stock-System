from tw_symbol_lookup import get_taiwan_ticker_name

DISPLAY_NAME_OVERRIDES = {
    "^TWII": "台灣加權指數",
    "^TWOII": "櫃買指數",
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ 指數",
    "^SOX": "費城半導體",
    "^DJI": "道瓊工業指數",
    "^N225": "日經 225",
    "^HSI": "恆生指數",
    "000001.SS": "上證綜合指數",
    "^STOXX50E": "Euro Stoxx 50",
    "GC=F": "黃金",
    "SI=F": "白銀",
    "HG=F": "銅",
    "CL=F": "WTI 原油",
    "BZ=F": "布蘭特原油",
    "NG=F": "天然氣",
}


def resolve_display_name(ticker: str, info: dict | None = None, quote: dict | None = None) -> str:
    info_name = None
    if info:
        info_name = info.get("name") or info.get("longName") or info.get("shortName")

    quote_name = None
    if quote:
        quote_name = quote.get("name") or quote.get("longName") or quote.get("shortName")

    return (
        DISPLAY_NAME_OVERRIDES.get(ticker)
        or get_taiwan_ticker_name(ticker)
        or info_name
        or quote_name
        or ticker
    )
