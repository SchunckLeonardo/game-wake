from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Protocol

SqlParameters = Mapping[str, object]
Row = Mapping[str, object]
_DATABASE_RESUME_RETRY_DELAYS = (1.0, 2.0, 4.0, 8.0)


class Transaction(Protocol):
    def execute(self, sql: str, parameters: SqlParameters | None = None) -> int: ...

    def fetch_one(self, sql: str, parameters: SqlParameters | None = None) -> Row | None: ...

    def fetch_all(self, sql: str, parameters: SqlParameters | None = None) -> tuple[Row, ...]: ...


class Database(Protocol):
    def transaction(self) -> Any: ...


def _parameter_value(value: object) -> tuple[dict[str, object], str | None]:
    if value is None:
        return {"isNull": True}, None
    if isinstance(value, bool):
        return {"booleanValue": value}, None
    if isinstance(value, int):
        return {"longValue": value}, None
    if isinstance(value, float):
        return {"doubleValue": value}, None
    if isinstance(value, Decimal):
        return {"stringValue": str(value)}, "DECIMAL"
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value
        return {"stringValue": normalized.isoformat(sep=" ")}, "TIMESTAMP"
    if isinstance(value, date):
        return {"stringValue": value.isoformat()}, "DATE"
    if isinstance(value, bytes):
        return {"blobValue": value}, None
    if isinstance(value, dict | list | tuple):
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return {"stringValue": encoded}, "JSON"
    if isinstance(value, str):
        return {"stringValue": value}, None
    raise TypeError(f"unsupported Data API parameter: {type(value).__name__}")


def _parameters(values: SqlParameters | None) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for name, value in (values or {}).items():
        encoded, type_hint = _parameter_value(value)
        parameter: dict[str, object] = {"name": name, "value": encoded}
        if type_hint is not None:
            parameter["typeHint"] = type_hint
        result.append(parameter)
    return result


class _AuroraTransaction:
    def __init__(self, database: AuroraDataApi, transaction_id: str) -> None:
        self._database = database
        self._transaction_id = transaction_id

    def _run(self, sql: str, parameters: SqlParameters | None) -> dict[str, Any]:
        return self._database._client.execute_statement(
            resourceArn=self._database.resource_arn,
            secretArn=self._database.secret_arn,
            database=self._database.database,
            transactionId=self._transaction_id,
            sql=sql,
            parameters=_parameters(parameters),
            formatRecordsAs="JSON",
            resultSetOptions={"decimalReturnType": "STRING", "longReturnType": "LONG"},
        )

    def execute(self, sql: str, parameters: SqlParameters | None = None) -> int:
        return int(self._run(sql, parameters).get("numberOfRecordsUpdated", 0))

    def fetch_all(self, sql: str, parameters: SqlParameters | None = None) -> tuple[Row, ...]:
        response = self._run(sql, parameters)
        formatted = response.get("formattedRecords")
        if not formatted:
            return ()
        decoded = json.loads(formatted)
        if not isinstance(decoded, list) or not all(isinstance(row, dict) for row in decoded):
            raise ValueError("Aurora Data API returned an invalid JSON row set")
        return tuple(decoded)

    def fetch_one(self, sql: str, parameters: SqlParameters | None = None) -> Row | None:
        rows = self.fetch_all(sql, parameters)
        return rows[0] if rows else None


class AuroraDataApi:
    def __init__(
        self,
        resource_arn: str,
        secret_arn: str,
        database: str,
        *,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        resume_retry_delays: tuple[float, ...] = _DATABASE_RESUME_RETRY_DELAYS,
    ) -> None:
        if not resource_arn or not secret_arn or not database:
            raise ValueError("Aurora resource ARN, secret ARN and database are required")
        if client is None:
            import boto3

            client = boto3.client("rds-data")
        self.resource_arn = resource_arn
        self.secret_arn = secret_arn
        self.database = database
        self._client = client
        self._sleep = sleep
        self._resume_retry_delays = resume_retry_delays

    @staticmethod
    def _is_database_resuming(error: Exception) -> bool:
        response = getattr(error, "response", None)
        if not isinstance(response, Mapping):
            return False
        details = response.get("Error")
        return isinstance(details, Mapping) and details.get("Code") == ("DatabaseResumingException")

    def _begin_transaction(self) -> dict[str, Any]:
        for attempt in range(len(self._resume_retry_delays) + 1):
            try:
                return self._client.begin_transaction(
                    resourceArn=self.resource_arn,
                    secretArn=self.secret_arn,
                    database=self.database,
                )
            except Exception as error:
                if not self._is_database_resuming(error) or attempt == len(
                    self._resume_retry_delays
                ):
                    raise
                self._sleep(self._resume_retry_delays[attempt])
        raise AssertionError("unreachable")

    @contextmanager
    def transaction(self) -> Iterator[Transaction]:
        response = self._begin_transaction()
        transaction_id = response["transactionId"]
        transaction = _AuroraTransaction(self, transaction_id)
        try:
            yield transaction
        except BaseException:
            self._client.rollback_transaction(
                resourceArn=self.resource_arn,
                secretArn=self.secret_arn,
                transactionId=transaction_id,
            )
            raise
        else:
            self._client.commit_transaction(
                resourceArn=self.resource_arn,
                secretArn=self.secret_arn,
                transactionId=transaction_id,
            )
