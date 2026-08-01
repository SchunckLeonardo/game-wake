from collections import deque
from contextlib import contextmanager

from gamewake.persistence import PostgresRecoverySecretStore


class Transaction:
    def __init__(self, *, execute=(), fetch_one=()):
        self.execute_results = deque(execute)
        self.fetch_one_results = deque(fetch_one)
        self.calls = []

    def execute(self, sql, parameters=None):
        self.calls.append((sql, parameters))
        return self.execute_results.popleft()

    def fetch_one(self, sql, parameters=None):
        self.calls.append((sql, parameters))
        return self.fetch_one_results.popleft()


class Database:
    def __init__(self, transaction):
        self.transaction_value = transaction

    @contextmanager
    def transaction(self):
        yield self.transaction_value


def test_postgres_owner_recovery_replaces_codes_and_consumes_each_hash_atomically():
    transaction = Transaction(execute=(1, 2, 1, 1, 1), fetch_one=({"enabled": 1},))
    store = PostgresRecoverySecretStore(Database(transaction))

    store.put("owner-1", "owner@example.com", frozenset({"hash-b", "hash-a"}))
    enabled = store.is_enabled("owner-1")
    consumed = store.consume("owner-1", "hash-a")

    assert enabled is True
    assert consumed is True
    assert "DELETE FROM owner_recovery_codes" in transaction.calls[1][0]
    assert transaction.calls[-1][1] == {
        "owner_user_id": "owner-1",
        "code_hash": "hash-a",
    }
