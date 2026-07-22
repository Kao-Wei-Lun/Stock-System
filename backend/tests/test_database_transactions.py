import pytest

from database.core import DatabaseCore


class AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeCursor:
    rowcount = 1
    lastrowid = 17

    def __init__(self, connection):
        self.connection = connection

    async def execute(self, sql, params=()):
        self.connection.executed.append((sql, params))


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.begin_count = 0
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(self, *_args):
        return AsyncContext(FakeCursor(self))

    async def begin(self):
        self.begin_count += 1

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


class FakePool:
    def __init__(self):
        self.connection = FakeConnection()
        self.acquire_count = 0

    def acquire(self):
        self.acquire_count += 1
        return AsyncContext(self.connection)


@pytest.mark.anyio
async def test_transaction_reuses_one_connection_and_commits():
    database = DatabaseCore()
    database._pool = FakePool()

    async with database.transaction():
        assert database.in_transaction is True
        await database._execute("UPDATE sample SET value=%s", (1,))
        inserted_id = await database._execute_insert("INSERT INTO sample(value) VALUES (%s)", (2,))

    assert inserted_id == 17
    assert database.in_transaction is False
    assert database._pool.acquire_count == 1
    assert database._pool.connection.begin_count == 1
    assert database._pool.connection.commit_count == 1
    assert database._pool.connection.rollback_count == 0


@pytest.mark.anyio
async def test_transaction_rolls_back_and_restores_context_after_failure():
    database = DatabaseCore()
    database._pool = FakePool()

    with pytest.raises(RuntimeError, match="stop import"):
        async with database.transaction():
            await database._execute("DELETE FROM sample")
            raise RuntimeError("stop import")

    assert database.in_transaction is False
    assert database._pool.connection.commit_count == 0
    assert database._pool.connection.rollback_count == 1


@pytest.mark.anyio
async def test_nested_transactions_are_rejected():
    database = DatabaseCore()
    database._pool = FakePool()

    async with database.transaction():
        with pytest.raises(RuntimeError, match="Nested"):
            async with database.transaction():
                pass
