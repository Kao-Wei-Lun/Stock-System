from __future__ import annotations

import pytest

from chip_archive_codec import encode_chip_branch_archive
from repositories.taiwan_chip import TaiwanChipMixin


class FakeTaiwanChipRepository(TaiwanChipMixin):
    def __init__(self, row, archive=None):
        self.row = row
        self.archive = archive
        self.queries = []

    async def _fetchone(self, sql, params=()):
        self.queries.append((sql, params))
        return dict(self.row) if self.row else None

    async def _fetchall(self, sql, params=()):
        self.queries.append((sql, params))
        return [dict(self.row)] if self.row else []

    async def get_chip_branch_archive(self, **_kwargs):
        return self.archive


def build_row():
    return {
        "id": 1,
        "ticker": "2330.TW",
        "market": "TW",
        "snapshot_date": "2024-01-10",
        "margin_balance": 10,
        "source": "twse_t86",
        "branch_payload_json": None,
        "summary_json": '{"bias":"bullish"}',
    }


@pytest.mark.anyio
async def test_recent_chip_queries_do_not_select_large_branch_json_by_default():
    repo = FakeTaiwanChipRepository(build_row())

    snapshot = await repo.get_taiwan_chip_snapshot("2330.TW")
    history = await repo.list_taiwan_chip_snapshots("2330.TW", limit=20)

    assert snapshot["branch_payload"] == {}
    assert history[0]["branch_payload"] == {}
    assert all("NULL AS `branch_payload_json`" in sql for sql, _params in repo.queries)
    assert all("SELECT *" not in sql for sql, _params in repo.queries)


@pytest.mark.anyio
async def test_explicit_chip_detail_falls_back_to_verified_archive():
    encoded = encode_chip_branch_archive(
        [
            {
                "id": 1,
                "ticker": "2330.TW",
                "branch_payload": {"branches": [{"name": "A", "net": 15}]},
            }
        ]
    )
    archive = {
        "payload_blob": encoded["payload_blob"],
        "payload_sha256": encoded["payload_sha256"],
        "source_row_count": 1,
    }
    repo = FakeTaiwanChipRepository(build_row(), archive=archive)

    snapshot = await repo.get_taiwan_chip_snapshot(
        "2330.TW",
        include_branch_payload=True,
    )

    assert snapshot["branch_payload"] == {
        "branches": [{"name": "A", "net": 15}]
    }
    assert snapshot["branch_payload_source"] == "archive"
    assert "`branch_payload_json`" in repo.queries[0][0]
