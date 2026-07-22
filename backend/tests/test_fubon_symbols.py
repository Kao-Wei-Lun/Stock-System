import fubon_symbols


def test_tw_ticker_to_fubon_supports_numeric_and_alphanumeric_taiwan_tickers(monkeypatch):
    mapping = {
        "0050": "0050.TW",
        "0050.TW": "0050.TW",
        "00981A": "00981A.TW",
        "00981A.TW": "00981A.TW",
        "00981B": "00981B.TWO",
        "00981B.TWO": "00981B.TWO",
    }

    monkeypatch.setattr(
        fubon_symbols,
        "resolve_taiwan_ticker",
        lambda ticker: mapping.get(str(ticker or "").strip().upper()),
    )

    assert fubon_symbols.tw_ticker_to_fubon("0050") == "0050"
    assert fubon_symbols.tw_ticker_to_fubon("00981A.TW") == "00981A"
    assert fubon_symbols.tw_ticker_to_fubon("00981B") == "00981B"


def test_taiwan_stock_detection_uses_lookup_for_full_english_symbols(monkeypatch):
    mapping = {
        "QQQW": "QQQW.TW",
        "QQQW.TW": "QQQW.TW",
    }

    monkeypatch.setattr(
        fubon_symbols,
        "resolve_taiwan_ticker",
        lambda ticker: mapping.get(str(ticker or "").strip().upper()),
    )

    assert fubon_symbols.is_taiwan_stock_ticker("QQQW") is True
    assert fubon_symbols.supports_fubon_stock_realtime_ticker("QQQW.TW") is True
    assert fubon_symbols.tw_ticker_to_fubon("QQQW") == "QQQW"


def test_unknown_pure_english_symbol_is_not_treated_as_taiwan_stock(monkeypatch):
    monkeypatch.setattr(fubon_symbols, "resolve_taiwan_ticker", lambda _ticker: None)

    assert fubon_symbols.is_taiwan_stock_ticker("AAPL") is False
    assert fubon_symbols.tw_ticker_to_fubon("AAPL") is None


def test_taiwan_market_indexes_are_supported_by_fubon_symbols():
    assert fubon_symbols.is_taiwan_market_index_ticker("^TWII") is True
    assert fubon_symbols.is_taiwan_market_index_ticker("^TWOII") is True
    assert fubon_symbols.fubon_index_ticker_to_symbol("^TWII") == "IX0001"
    assert fubon_symbols.fubon_index_ticker_to_symbol("^TWOII") == "IX0043"
    assert fubon_symbols.supports_fubon_stock_realtime_ticker("^TWOII") is True


def test_futopt_symbol_helpers_support_future_and_option_contracts():
    assert fubon_symbols.normalize_futopt_symbol_query("*TXFF") == "TXF"
    assert fubon_symbols.normalize_futopt_symbol_query("*tmff") == "TMF"
    assert fubon_symbols.is_dynamic_futopt_alias("*TXFF") is True
    assert fubon_symbols.is_exact_futopt_contract("TXFE6") is True
    assert fubon_symbols.is_exact_futopt_contract("TXO20000E4") is True
    assert fubon_symbols.derive_futopt_product_query("TXFE6") == "TXF"
    assert fubon_symbols.derive_futopt_product_query("TXO20000E4") == "TXO"
    assert fubon_symbols.derive_futopt_product_query("TXO200") == "TXO"
    assert fubon_symbols.looks_like_futopt_search_query("TXO") is True
    assert fubon_symbols.looks_like_futopt_search_query("TXO200") is True
    assert fubon_symbols.looks_like_futopt_search_query("*TMFF") is True
