"""Unit tests for database helper serializers."""

import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database.helpers import _deserialize_institutional_snapshot, _deserialize_taiwan_chip_snapshot


def test_deserialize_institutional_snapshot_merges_payload_and_dates():
    row = {
        "resolved_date": "2026-04-03",
        "query_date": "2026-04-02",
        "payload_json": '{"overview":[{"institution":"外資"}],"leaderboards":{"futures":[]}}',
    }

    result = _deserialize_institutional_snapshot(row)

    assert result["resolved_date"] == "2026-04-03"
    assert result["query_date"] == "2026-04-02"
    assert result["overview"][0]["institution"] == "外資"
    assert result["leaderboards"] == {"futures": []}


def test_deserialize_taiwan_chip_snapshot_exposes_official_net_columns():
    row = {
        "id": 7,
        "ticker": "2330.TW",
        "market": "TW",
        "snapshot_date": "2026-04-10",
        "margin_balance": None,
        "short_balance": None,
        "securities_lending_balance": None,
        "foreign_net_buy_sell": 1200000,
        "investment_trust_net_buy_sell": -45000,
        "dealer_net_buy_sell": 32000,
        "institutional_net_buy_sell": 1187000,
        "source": "twse_t86",
        "branch_payload_json": '{"security_name":"TSMC","format_version":"current"}',
        "summary_json": '{"bias":"bullish"}',
        "created_at": "2026-04-10T18:30:00",
        "updated_at": "2026-04-10T18:30:00",
    }

    result = _deserialize_taiwan_chip_snapshot(row)

    assert result["ticker"] == "2330.TW"
    assert result["foreign_net_buy_sell"] == 1200000
    assert result["investment_trust_net_buy_sell"] == -45000
    assert result["dealer_net_buy_sell"] == 32000
    assert result["summary"] == {"bias": "bullish"}
