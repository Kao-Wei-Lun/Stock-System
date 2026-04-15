from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from repositories.taiwan_chip import _build_taifex_structured_snapshot


def test_build_taifex_structured_snapshot_splits_payload_into_tables():
    payload = {
        "query_date": "2026-04-10",
        "resolved_date": "2026-04-09",
        "previous_date": "2026-04-08",
        "default_futures_commodity": "臺股期貨",
        "default_options_commodity": "臺指選擇權",
        "cash_summary_source": "twse",
        "cash_summary_warning": None,
        "overview": [
            {
                "institution": "外資",
                "trade_long_futures_volume": 11,
                "trade_long_options_volume": 12,
                "trade_long_futures_amount": 13,
                "trade_long_options_amount": 14,
                "trade_short_futures_volume": 15,
                "trade_short_options_volume": 16,
                "trade_short_futures_amount": 17,
                "trade_short_options_amount": 18,
                "trade_net_futures_volume": -4,
                "trade_net_options_volume": 6,
                "trade_net_futures_amount": -100,
                "trade_net_options_amount": 120,
                "trade_net_futures_volume_change": 2,
                "trade_net_options_volume_change": -3,
                "trade_net_futures_amount_change": 30,
                "trade_net_options_amount_change": -40,
            }
        ],
        "futures": [
            {
                "rank": 1,
                "commodity": "臺股期貨",
                "institution": "外資",
                "trade_long_volume": 101,
                "trade_long_amount": 102,
                "trade_short_volume": 103,
                "trade_short_amount": 104,
                "trade_net_volume": -2,
                "trade_net_amount": -50,
                "oi_long_volume": 105,
                "oi_long_amount": 106,
                "oi_short_volume": 107,
                "oi_short_amount": 108,
                "oi_net_volume": -2,
                "oi_net_amount": -60,
                "trade_net_volume_change": 5,
                "trade_net_amount_change": 6,
                "oi_net_volume_change": 7,
                "oi_net_amount_change": 8,
            }
        ],
        "options": [
            {
                "rank": 2,
                "commodity": "臺指選擇權",
                "institution": "自營商",
                "trade_long_volume": 201,
                "trade_long_amount": 202,
                "trade_short_volume": 203,
                "trade_short_amount": 204,
                "trade_net_volume": 1,
                "trade_net_amount": 20,
                "oi_long_volume": 205,
                "oi_long_amount": 206,
                "oi_short_volume": 207,
                "oi_short_amount": 208,
                "oi_net_volume": 1,
                "oi_net_amount": 30,
                "trade_net_volume_change": 9,
                "trade_net_amount_change": 10,
                "oi_net_volume_change": 11,
                "oi_net_amount_change": 12,
            }
        ],
        "call_puts": [
            {
                "rank": 3,
                "commodity": "臺指選擇權",
                "option_side": "買權",
                "institution": "外資",
                "trade_buy_volume": 301,
                "trade_buy_amount": 302,
                "trade_sell_volume": 303,
                "trade_sell_amount": 304,
                "trade_net_volume": 5,
                "trade_net_amount": 50,
                "oi_buy_volume": 305,
                "oi_buy_amount": 306,
                "oi_sell_volume": 307,
                "oi_sell_amount": 308,
                "oi_net_volume": 10,
                "oi_net_amount": 80,
                "trade_net_volume_change": 13,
                "trade_net_amount_change": 14,
                "oi_net_volume_change": 15,
                "oi_net_amount_change": 16,
            }
        ],
        "cash_summary": [
            {
                "institution": "外資及陸資(不含外資自營商)",
                "buy_amount": 401,
                "sell_amount": 402,
                "net_amount": -1,
                "net_amount_change": 17,
            }
        ],
    }

    result = _build_taifex_structured_snapshot(payload)

    assert result["meta"]["resolved_date"] == "2026-04-09"
    assert result["meta"]["query_date"] == "2026-04-10"
    assert result["meta"]["previous_date"] == "2026-04-08"
    assert result["meta"]["default_futures_commodity"] == "臺股期貨"
    assert result["meta"]["cash_summary_source"] == "twse"

    assert len(result["overview_rows"]) == 1
    assert result["overview_rows"][0]["institution"] == "外資"
    assert result["overview_rows"][0]["trade_net_futures_amount_change"] == 30

    assert len(result["futures_rows"]) == 1
    assert result["futures_rows"][0]["commodity"] == "臺股期貨"
    assert result["futures_rows"][0]["oi_net_amount_change"] == 8

    assert len(result["options_rows"]) == 1
    assert result["options_rows"][0]["institution"] == "自營商"
    assert result["options_rows"][0]["trade_net_volume_change"] == 9

    assert len(result["call_put_rows"]) == 1
    assert result["call_put_rows"][0]["option_side"] == "買權"
    assert result["call_put_rows"][0]["oi_net_volume_change"] == 15

    assert len(result["cash_summary_rows"]) == 1
    assert result["cash_summary_rows"][0]["institution"] == "外資及陸資(不含外資自營商)"
    assert result["cash_summary_rows"][0]["net_amount_change"] == 17
