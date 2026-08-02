from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from gamewake.persistence import AuroraDataApi


class FakeRdsDataClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def begin_transaction(self, **kwargs):
        self.calls.append(("begin", kwargs))
        return {"transactionId": "tx-1"}

    def execute_statement(self, **kwargs):
        self.calls.append(("execute", kwargs))
        return {
            "formattedRecords": '[{"answer":42,"label":"ready"}]',
            "numberOfRecordsUpdated": 1,
        }

    def commit_transaction(self, **kwargs):
        self.calls.append(("commit", kwargs))

    def rollback_transaction(self, **kwargs):
        self.calls.append(("rollback", kwargs))


class DatabaseResumingError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Aurora is resuming")
        self.response = {"Error": {"Code": "DatabaseResumingException"}}


class ResumingRdsDataClient(FakeRdsDataClient):
    def __init__(self) -> None:
        super().__init__()
        self.begin_attempts = 0

    def begin_transaction(self, **kwargs):
        self.begin_attempts += 1
        self.calls.append(("begin", kwargs))
        if self.begin_attempts < 3:
            raise DatabaseResumingError()
        return {"transactionId": "tx-1"}


def test_executes_typed_named_parameters_and_commits() -> None:
    client = FakeRdsDataClient()
    database = AuroraDataApi(
        resource_arn="cluster-arn",
        secret_arn="secret-arn",
        database="gamewake",
        client=client,
    )

    with database.transaction() as transaction:
        rows = transaction.fetch_all(
            "SELECT :amount",
            {
                "amount": Decimal("12.50"),
                "attempt": 2,
                "ratio": 1.5,
                "enabled": True,
                "missing": None,
                "created": datetime(2026, 7, 31, 12, 30, tzinfo=UTC),
                "day": date(2026, 7, 31),
                "payload": {"safe": True},
            },
        )

    assert rows == ({"answer": 42, "label": "ready"},)
    assert [name for name, _ in client.calls] == ["begin", "execute", "commit"]
    execute = client.calls[1][1]
    assert execute["transactionId"] == "tx-1"
    assert execute["formatRecordsAs"] == "JSON"
    assert execute["parameters"] == [
        {"name": "amount", "typeHint": "DECIMAL", "value": {"stringValue": "12.50"}},
        {"name": "attempt", "value": {"longValue": 2}},
        {"name": "ratio", "value": {"doubleValue": 1.5}},
        {"name": "enabled", "value": {"booleanValue": True}},
        {"name": "missing", "value": {"isNull": True}},
        {
            "name": "created",
            "typeHint": "TIMESTAMP",
            "value": {"stringValue": "2026-07-31 12:30:00"},
        },
        {"name": "day", "typeHint": "DATE", "value": {"stringValue": "2026-07-31"}},
        {
            "name": "payload",
            "typeHint": "JSON",
            "value": {"stringValue": '{"safe":true}'},
        },
    ]


def test_rolls_back_when_transaction_body_fails() -> None:
    client = FakeRdsDataClient()
    database = AuroraDataApi("cluster-arn", "secret-arn", "gamewake", client=client)

    with pytest.raises(RuntimeError, match="boom"), database.transaction():
        raise RuntimeError("boom")

    assert [name for name, _ in client.calls] == ["begin", "rollback"]


def test_retries_begin_transaction_while_aurora_is_resuming() -> None:
    client = ResumingRdsDataClient()
    delays: list[float] = []
    database = AuroraDataApi(
        "cluster-arn",
        "secret-arn",
        "gamewake",
        client=client,
        sleep=delays.append,
    )

    with database.transaction():
        pass

    assert [name for name, _ in client.calls] == ["begin", "begin", "begin", "commit"]
    assert delays == [1, 2]
