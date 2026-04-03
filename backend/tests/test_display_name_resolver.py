"""Unit tests for display_name_resolver module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from unittest.mock import patch

from display_name_resolver import DISPLAY_NAME_OVERRIDES, resolve_display_name


class TestResolveDisplayName:
    """Tests for resolve_display_name()."""

    def test_override_takes_priority(self):
        """Override ticker names should beat info/quote dict values."""
        result = resolve_display_name("^TWII", info={"name": "Something Else"})
        assert result == "台灣加權指數"

    def test_all_overrides_are_strings(self):
        for ticker, name in DISPLAY_NAME_OVERRIDES.items():
            assert isinstance(name, str) and len(name) > 0, f"Bad override for {ticker}"

    def test_info_dict_name_used(self):
        result = resolve_display_name("AAPL", info={"name": "Apple Inc."})
        assert result == "Apple Inc."

    def test_info_longName_used(self):
        result = resolve_display_name("AAPL", info={"longName": "Apple Inc."})
        assert result == "Apple Inc."

    def test_quote_name_used_when_no_info(self):
        result = resolve_display_name("AAPL", quote={"name": "Apple via Quote"})
        assert result == "Apple via Quote"

    def test_info_beats_quote(self):
        result = resolve_display_name(
            "AAPL",
            info={"name": "From Info"},
            quote={"name": "From Quote"},
        )
        assert result == "From Info"

    def test_fallback_to_ticker(self):
        with patch("display_name_resolver.get_taiwan_ticker_name", return_value=None):
            result = resolve_display_name("UNKNOWN_TICKER")
            assert result == "UNKNOWN_TICKER"

    def test_taiwan_ticker_resolved(self):
        with patch("display_name_resolver.get_taiwan_ticker_name", return_value="台積電"):
            result = resolve_display_name("2330.TW")
            assert result == "台積電"

    def test_none_info_and_quote(self):
        with patch("display_name_resolver.get_taiwan_ticker_name", return_value=None):
            result = resolve_display_name("XYZ", info=None, quote=None)
            assert result == "XYZ"

    def test_empty_name_fields_ignored(self):
        with patch("display_name_resolver.get_taiwan_ticker_name", return_value=None):
            result = resolve_display_name("FOO", info={"name": "", "longName": ""})
            assert result == "FOO"
