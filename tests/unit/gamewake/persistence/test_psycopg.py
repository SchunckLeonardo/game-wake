import pytest

from gamewake.persistence import PsycopgDatabase


class FakeCursor:
    def __init__(self, connection) -> None:
        self.connection = connection
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, parameters):
        self.connection.executions.append((sql, parameters))

    def fetchall(self):
        return [{"id": "row-1"}]

    def fetchone(self):
        return {"id": "row-1"}


class FakeConnection:
    def __init__(self) -> None:
        self.executions = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def database_with(connection: FakeConnection) -> PsycopgDatabase:
    database = object.__new__(PsycopgDatabase)
    database._dsn = "postgresql://gamewake_test"
    database._row_factory = object()
    database._connect = lambda *_args, **_kwargs: connection
    return database


def test_translates_named_parameters_and_commits() -> None:
    connection = FakeConnection()
    database = database_with(connection)

    with database.transaction() as transaction:
        assert transaction.fetch_one("SELECT :id AS id", {"id": "row-1"}) == {"id": "row-1"}

    assert connection.executions == [("SELECT %(id)s AS id", {"id": "row-1"})]
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True


def test_rolls_back_and_closes_connection_on_failure() -> None:
    connection = FakeConnection()
    database = database_with(connection)

    with pytest.raises(RuntimeError, match="boom"), database.transaction():
        raise RuntimeError("boom")

    assert connection.committed is False
    assert connection.rolled_back is True
    assert connection.closed is True
