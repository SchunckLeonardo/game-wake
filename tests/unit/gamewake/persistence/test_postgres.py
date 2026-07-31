from collections import deque
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from gamewake.accounts import Account, ActivityAction, ActivityEvent
from gamewake.accounts.repository import AccountSnapshot
from gamewake.billing import LedgerEntry, LedgerEntryType
from gamewake.billing.model import WalletSnapshot
from gamewake.persistence import (
    PostgresAccountRepository,
    PostgresBillingRepository,
    encode_domain,
)


class ScriptedTransaction:
    def __init__(self, *, execute=(), fetch_one=(), fetch_all=()) -> None:
        self.execute_results = deque(execute)
        self.fetch_one_results = deque(fetch_one)
        self.fetch_all_results = deque(fetch_all)

    def execute(self, _sql, _parameters=None):
        return self.execute_results.popleft()

    def fetch_one(self, _sql, _parameters=None):
        return self.fetch_one_results.popleft()

    def fetch_all(self, _sql, _parameters=None):
        return self.fetch_all_results.popleft()


class ScriptedDatabase:
    def __init__(self, transaction: ScriptedTransaction) -> None:
        self.script = transaction

    @contextmanager
    def transaction(self):
        yield self.script


def test_account_save_rejects_changed_replay_of_immutable_activity() -> None:
    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    original = ActivityEvent(
        "activity-1",
        "account-1",
        "owner-1",
        ActivityAction.MEMBERSHIP_REVOKED,
        "member-1",
        now,
    )
    changed = replace(original, subject_id="different-member")
    snapshot = AccountSnapshot(Account("account-1", "Sexta"), (), (), (), (changed,), 2)
    transaction = ScriptedTransaction(
        execute=(1, 0),
        fetch_one=({"payload": encode_domain(original)},),
    )

    with pytest.raises(ValueError, match="immutable Activity Event"):
        PostgresAccountRepository(ScriptedDatabase(transaction)).save(snapshot, expected_version=2)


def test_wallet_save_rejects_changed_replay_of_immutable_ledger_entry() -> None:
    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    original = LedgerEntry(
        "entry-1",
        "account-1",
        LedgerEntryType.CONTRIBUTION,
        Decimal("50.00"),
        "contribution-1",
        "payment-1",
        now,
    )
    changed = replace(original, amount=Decimal("49.00"))
    snapshot = WalletSnapshot(
        "account-1",
        (changed,),
        (),
        (),
        (),
        (),
        (),
        (),
        (),
        (),
        1,
    )
    transaction = ScriptedTransaction(
        execute=(1, 0),
        fetch_one=({"payload": encode_domain(original)},),
    )

    with pytest.raises(ValueError, match="immutable Ledger Entry"):
        PostgresBillingRepository(ScriptedDatabase(transaction)).save(
            snapshot,
            expected_version=1,
        )
