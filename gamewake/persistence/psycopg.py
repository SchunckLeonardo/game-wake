from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .data_api import Row, SqlParameters, Transaction

_NAMED_PARAMETER = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")


def _psycopg_sql(sql: str) -> str:
    return _NAMED_PARAMETER.sub(r"%(\1)s", sql)


class _PsycopgTransaction:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def execute(self, sql: str, parameters: SqlParameters | None = None) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute(_psycopg_sql(sql), dict(parameters or {}))
            return cursor.rowcount

    def fetch_all(self, sql: str, parameters: SqlParameters | None = None) -> tuple[Row, ...]:
        with self._connection.cursor() as cursor:
            cursor.execute(_psycopg_sql(sql), dict(parameters or {}))
            return tuple(cursor.fetchall())

    def fetch_one(self, sql: str, parameters: SqlParameters | None = None) -> Row | None:
        with self._connection.cursor() as cursor:
            cursor.execute(_psycopg_sql(sql), dict(parameters or {}))
            return cursor.fetchone()


class PsycopgDatabase:
    """Direct PostgreSQL adapter used by migrations, local tooling and integration tests."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN is required")
        import psycopg
        from psycopg.rows import dict_row

        self._dsn = dsn
        self._connect = psycopg.connect
        self._row_factory = dict_row

    @contextmanager
    def transaction(self) -> Iterator[Transaction]:
        connection = self._connect(self._dsn, row_factory=self._row_factory)
        try:
            yield _PsycopgTransaction(connection)
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()
