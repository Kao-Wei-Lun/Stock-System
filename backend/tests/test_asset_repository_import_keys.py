from pathlib import Path
import sys

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from repositories.assets import AssetMixin


class FakeAssetRepository(AssetMixin):
    def __init__(self):
        self.queries = []

    async def _fetchall(self, sql, params=()):
        self.queries.append((sql, params))
        return [{"id": 8, "import_key": "key-b"}]


@pytest.mark.anyio
async def test_find_asset_import_keys_uses_scoped_parameterized_query():
    repository = FakeAssetRepository()

    result = await repository.find_asset_trade_import_keys(["key-a", "key-b", "key-a", ""], owner_id=3)

    assert result == {"key-b": 8}
    sql, params = repository.queries[0]
    assert "FROM `asset_trade_ledger`" in sql
    assert "`owner_id`=%s" in sql
    assert "`import_key` IN (%s, %s)" in sql
    assert params == (3, "key-a", "key-b")


@pytest.mark.anyio
async def test_find_asset_import_keys_skips_query_for_empty_keys():
    repository = FakeAssetRepository()

    result = await repository.find_asset_cash_import_keys([], owner_id=1)

    assert result == {}
    assert repository.queries == []
