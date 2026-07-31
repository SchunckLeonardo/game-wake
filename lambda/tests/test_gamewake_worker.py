from contextlib import contextmanager
from types import SimpleNamespace

import gamewake_worker

from gamewake.worlds import OperationPhase, OperationStatus


class Migrations:
    def apply(self):
        return ("0001_initial",)


class Transaction:
    def fetch_all(self, sql):
        assert "status IN ('pending', 'running')" in sql
        return (
            {"account_id": "account-1", "id": "operation-1"},
            {"account_id": "account-2", "id": "operation-2"},
        )


class Database:
    @contextmanager
    def transaction(self):
        yield Transaction()


class Orchestrator:
    def __init__(self):
        self.calls = []

    def ensure_running(self, account_id, operation_id):
        self.calls.append((account_id, operation_id))


class Worker:
    def advance(self, account_id, operation_id):
        return SimpleNamespace(
            status=OperationStatus.RUNNING,
            phase=OperationPhase.STARTING_GAME,
        )


def services(orchestrator=None):
    orchestrator = orchestrator or Orchestrator()
    return SimpleNamespace(
        migrations=Migrations(),
        database=Database(),
        worker=Worker(),
        orchestrator_factory=lambda arn: orchestrator,
    )


def test_migration_action_applies_packaged_database_migrations():
    result = gamewake_worker.handle_event({"action": "migrate"}, services=services())

    assert result == {"applied_migrations": ["0001_initial"]}


def test_reconciliation_restarts_every_non_terminal_persisted_operation():
    orchestrator = Orchestrator()

    result = gamewake_worker.handle_event(
        {
            "action": "reconcile",
            "state_machine_arn": "arn:aws:states:us-east-1:123:stateMachine:worlds",
        },
        services=services(orchestrator),
    )

    assert result == {"reconciled": 2}
    assert orchestrator.calls == [
        ("account-1", "operation-1"),
        ("account-2", "operation-2"),
    ]


def test_default_action_advances_exactly_one_world_operation_phase():
    result = gamewake_worker.handle_event(
        {"account_id": "account-1", "operation_id": "operation-1"},
        services=services(),
    )

    assert result == {
        "account_id": "account-1",
        "operation_id": "operation-1",
        "status": "running",
        "phase": "starting_game",
        "terminal": False,
    }
