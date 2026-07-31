from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import gamewake_worker

from gamewake.worlds import OperationPhase, OperationStatus


class Migrations:
    def apply(self):
        return ("0001_initial",)


class Transaction:
    def fetch_all(self, sql):
        if "pending_deletion" in sql:
            return (
                {"account_id": "account-1", "id": "world-delete-1"},
                {"account_id": "account-2", "id": "world-delete-2"},
            )
        if "FROM accounts" in sql:
            return ({"id": "account-1"}, {"id": "account-2"})
        if "FROM worlds" in sql:
            return (
                {"account_id": "account-1", "id": "operation-1"},
                {"account_id": "account-2", "id": "operation-2"},
            )
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

    def monitor_session(self, account_id, world_id, **kwargs):
        assert kwargs["idle_minutes"] == 20
        return SimpleNamespace(id=f"sleep-{world_id}")


class WorldData:
    def __init__(self):
        self.calls = []

    def purge_due_deletion(self, account_id, world_id, *, observed_at):
        self.calls.append((account_id, world_id, observed_at))
        return True


class Storage:
    def __init__(self):
        self.calls = []

    def evaluate(self, account_id, *, wallet_can_fund, observed_at):
        self.calls.append((account_id, wallet_can_fund, observed_at))


class Billing:
    def get_wallet(self, account_id):
        return SimpleNamespace(
            available_balance=Decimal("1.00") if account_id == "account-1" else Decimal("0.00")
        )


def test_worker_composition_source_includes_persistent_runtime_usage_billing():
    source = Path(gamewake_worker.__file__).read_text()

    assert "BillingRuntimeUsageRecorder" in source
    assert "PostgresBillingRepository" in source


def services(orchestrator=None):
    orchestrator = orchestrator or Orchestrator()
    return SimpleNamespace(
        migrations=Migrations(),
        database=Database(),
        worker=Worker(),
        world_data=WorldData(),
        storage=Storage(),
        billing=Billing(),
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


def test_monitor_sessions_dispatches_safe_sleep_operations():
    orchestrator = Orchestrator()
    result = gamewake_worker.handle_event(
        {
            "action": "monitor_sessions",
            "state_machine_arn": "arn:aws:states:us-east-1:123:stateMachine:worlds",
        },
        services=services(orchestrator),
    )

    assert result == {"monitored": 2, "sleep_operations": 2}
    assert orchestrator.calls == [
        ("account-1", "sleep-operation-1"),
        ("account-2", "sleep-operation-2"),
    ]


def test_daily_data_maintenance_purges_due_deletions_and_evaluates_storage_grace():
    composed = services()
    observed_at = datetime(2026, 8, 8, 3, 0, tzinfo=UTC)

    result = gamewake_worker.handle_event(
        {"action": "maintain_data", "observed_at": observed_at.isoformat()},
        services=composed,
    )

    assert result == {"purged": 2, "storage_accounts": 2}
    assert composed.world_data.calls == [
        ("account-1", "world-delete-1", observed_at),
        ("account-2", "world-delete-2", observed_at),
    ]
    assert composed.storage.calls == [
        ("account-1", True, observed_at),
        ("account-2", False, observed_at),
    ]
