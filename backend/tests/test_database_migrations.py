import pytest

from database.migrations import (
    BASELINE_SCHEMA_CHECKSUM,
    MIGRATIONS,
    MigrationError,
    SchemaState,
    _schema_definition_checksum,
    build_versioned_migration_plan,
)
from database.core import DatabaseCore
from database import Database
from models.schema import (
    CREATE_TABLE_STATEMENTS,
    REQUIRED_COLUMN_MIGRATIONS,
    REQUIRED_INDEX_MIGRATIONS,
)


def empty_state() -> SchemaState:
    return SchemaState(tables=set(), columns={}, indexes={})


def complete_state() -> SchemaState:
    return SchemaState(
        tables=set(CREATE_TABLE_STATEMENTS),
        columns={
            table_name: set(columns)
            for table_name, columns in REQUIRED_COLUMN_MIGRATIONS.items()
        },
        indexes={
            table_name: set(indexes)
            for table_name, indexes in REQUIRED_INDEX_MIGRATIONS.items()
        },
    )


def applied_baseline(checksum: str = BASELINE_SCHEMA_CHECKSUM):
    return [{"version": MIGRATIONS[0].version, "checksum": checksum}]


def test_migration_registry_is_ordered_and_baseline_checksum_is_frozen():
    versions = [migration.version for migration in MIGRATIONS]

    assert versions == sorted(versions)
    assert len(versions) == len(set(versions))
    assert BASELINE_SCHEMA_CHECKSUM == _schema_definition_checksum()


def test_composed_database_uses_versioned_core_migration_method():
    assert Database.create_tables is DatabaseCore.create_tables


def test_empty_database_has_versioned_baseline_with_schema_statements():
    plan = build_versioned_migration_plan(empty_state())

    assert plan["pending_count"] == 1
    assert plan["pending"][0]["version"] == "20260722_0001"
    assert plan["pending"][0]["statement_count"] > 0
    assert any("CREATE TABLE `asset_accounts`" in sql for sql in plan["pending"][0]["statements"])


def test_existing_complete_database_gets_zero_statement_baseline_record():
    plan = build_versioned_migration_plan(complete_state())

    assert plan["pending_count"] == 1
    assert plan["pending"][0]["statement_count"] == 0
    assert plan["up_to_date"] is False


def test_applied_baseline_is_up_to_date():
    plan = build_versioned_migration_plan(complete_state(), applied_baseline())

    assert plan["pending_count"] == 0
    assert plan["applied_versions"] == ["20260722_0001"]
    assert plan["up_to_date"] is True


def test_applied_migration_checksum_drift_is_rejected():
    with pytest.raises(MigrationError, match="checksum drift"):
        build_versioned_migration_plan(complete_state(), applied_baseline("bad-checksum"))


def test_unknown_newer_migrations_are_reported_as_incompatible():
    rows = [
        *applied_baseline(),
        {"version": "20990101_0001", "checksum": "future"},
    ]

    plan = build_versioned_migration_plan(complete_state(), rows)

    assert plan["unknown_applied_versions"] == ["20990101_0001"]
    assert plan["up_to_date"] is False


class AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeCursor:
    def __init__(self, executed):
        self.executed = executed

    async def execute(self, sql, params=()):
        self.executed.append((sql, params))


class FakeConnection:
    def __init__(self, executed):
        self.executed = executed

    def cursor(self, *_args):
        return AsyncContext(FakeCursor(self.executed))


class FakePool:
    def __init__(self):
        self.executed = []

    def acquire(self):
        return AsyncContext(FakeConnection(self.executed))


@pytest.mark.anyio
async def test_database_core_can_require_explicit_migration_apply(monkeypatch):
    database = DatabaseCore()
    database._pool = FakePool()

    async def fake_inspect(_cur):
        return complete_state()

    async def fake_applied(_cur, _state):
        return []

    monkeypatch.setattr(database, "_inspect_schema", fake_inspect)
    monkeypatch.setattr(database, "_get_applied_migrations", fake_applied)

    with pytest.raises(MigrationError, match="Pending database migrations"):
        await database.create_tables(auto_apply=False)

    assert database._pool.executed == []


@pytest.mark.anyio
async def test_database_core_records_zero_statement_baseline(monkeypatch):
    database = DatabaseCore()
    database._pool = FakePool()

    async def fake_inspect(_cur):
        return complete_state()

    async def fake_applied(_cur, _state):
        return []

    monkeypatch.setattr(database, "_inspect_schema", fake_inspect)
    monkeypatch.setattr(database, "_get_applied_migrations", fake_applied)

    plan = await database.create_tables(auto_apply=True)

    assert plan["pending_count"] == 1
    assert any("CREATE TABLE IF NOT EXISTS `schema_migrations`" in sql for sql, _ in database._pool.executed)
    insert = next((sql, params) for sql, params in database._pool.executed if "INSERT INTO `schema_migrations`" in sql)
    assert insert[1][0] == "20260722_0001"
    assert insert[1][3] == 0
