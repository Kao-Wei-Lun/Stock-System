"""Unit tests for database helper serializers."""

import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database.helpers import _deserialize_institutional_snapshot


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
