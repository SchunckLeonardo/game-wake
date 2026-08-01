from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import gamewake_worker

from gamewake.billing import InsufficientFundsError
from gamewake.worlds import OperationPhase, OperationStatus, OperationType, WorldStatus


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
    def __init__(self):
        self.monitor_calls = []

    def advance(self, account_id, operation_id):
        return SimpleNamespace(
            world_id="world-1",
            operation_type=OperationType.WAKE,
            status=OperationStatus.RUNNING,
            phase=OperationPhase.STARTING_GAME,
        )

    def monitor_session(self, account_id, world_id, **kwargs):
        assert kwargs["idle_minutes"] is None
        self.monitor_calls.append((account_id, world_id))
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
        return SimpleNamespace(excess_bytes=1024**3 if account_id == "account-1" else 2 * 1024**3)


class Billing:
    def __init__(self):
        self.storage_calls = []

    def charge_monthly_storage(self, account_id, **kwargs):
        self.storage_calls.append((account_id, kwargs))
        if account_id == "account-2":
            raise InsufficientFundsError("insufficient")
        return SimpleNamespace(id="storage-charge-1")


class Repository:
    def __init__(self, *, world_status=WorldStatus.ONLINE):
        self.world_status = world_status

    def get_operation(self, account_id, operation_id):
        return SimpleNamespace(
            id=operation_id,
            world_id="world-1",
            operation_type=OperationType.SLEEP,
            status=OperationStatus.PENDING,
        )

    def get(self, account_id, world_id):
        return SimpleNamespace(id=world_id, status=self.world_status)

    def list_operations(self, account_id, world_id):
        return ()


class AccountRepository:
    def get(self, account_id):
        return SimpleNamespace(account=SimpleNamespace(id=account_id))


class Notifier:
    def __init__(self):
        self.calls = []

    def notify(self, account, world, operation):
        self.calls.append((account.id, world.id, operation.id))
        return True


def test_worker_composition_source_includes_persistent_runtime_usage_billing():
    source = Path(gamewake_worker.__file__).read_text()

    assert "BillingRuntimeUsageRecorder" in source
    assert "PostgresBillingRepository" in source


def services(orchestrator=None, *, repository=None):
    orchestrator = orchestrator or Orchestrator()
    repository = repository or Repository()
    return SimpleNamespace(
        migrations=Migrations(),
        database=Database(),
        worker=Worker(),
        world_data=WorldData(),
        storage=Storage(),
        billing=Billing(),
        storage_rate_per_gib_month=Decimal("2.00"),
        world_repository=repository,
        account_repository=AccountRepository(),
        notifier=Notifier(),
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
        "world_id": "world-1",
        "operation_type": "wake",
        "status": "running",
        "phase": "starting_game",
        "terminal": False,
    }


def test_terminal_operation_notifies_the_accounts_discord_channel():
    composed = services()
    composed.worker.advance = lambda account_id, operation_id: SimpleNamespace(
        status=OperationStatus.SUCCEEDED,
        phase=OperationPhase.COMPLETE,
        world_id="world-1",
        operation_type=OperationType.WAKE,
    )

    result = gamewake_worker.handle_event(
        {"account_id": "account-1", "operation_id": "operation-1"},
        services=composed,
    )

    assert result["terminal"] is True
    assert result["notified"] is True
    assert composed.notifier.calls == [("account-1", "world-1", "operation-1")]


def test_active_world_monitor_dispatches_one_safe_sleep_operation_and_stops_looping():
    orchestrator = Orchestrator()
    composed = services(orchestrator)
    result = gamewake_worker.handle_event(
        {
            "action": "monitor_session",
            "account_id": "account-1",
            "world_id": "world-1",
            "monitor_checks": 41,
            "state_machine_arn": "arn:aws:states:us-east-1:123:stateMachine:worlds",
        },
        services=composed,
    )

    assert result == {
        "account_id": "account-1",
        "world_id": "world-1",
        "session_monitor": True,
        "monitor_checks": 42,
        "continue_monitoring": False,
        "sleep_operation_id": "sleep-world-1",
    }
    assert composed.worker.monitor_calls == [("account-1", "world-1")]
    assert orchestrator.calls == [("account-1", "sleep-world-1")]


def test_active_world_monitor_keeps_looping_while_the_world_needs_no_sleep():
    composed = services()
    composed.worker.monitor_session = lambda *args, **kwargs: None

    result = gamewake_worker.handle_event(
        {
            "action": "monitor_session",
            "account_id": "account-1",
            "world_id": "world-1",
            "state_machine_arn": "arn:aws:states:us-east-1:123:stateMachine:worlds",
        },
        services=composed,
    )

    assert result["continue_monitoring"] is True
    assert result["sleep_operation_id"] is None
    assert result["monitor_checks"] == 1


def test_active_world_monitor_recovers_a_sleep_dispatch_after_a_retry():
    repository = Repository(world_status=WorldStatus.GOING_TO_SLEEP)
    repository.list_operations = lambda account_id, world_id: (
        SimpleNamespace(
            id="sleep-existing",
            operation_type=OperationType.SLEEP,
            status=OperationStatus.PENDING,
        ),
    )
    orchestrator = Orchestrator()
    composed = services(orchestrator, repository=repository)

    result = gamewake_worker.handle_event(
        {
            "action": "monitor_session",
            "account_id": "account-1",
            "world_id": "world-1",
            "state_machine_arn": "arn:aws:states:us-east-1:123:stateMachine:worlds",
        },
        services=composed,
    )

    assert result["continue_monitoring"] is False
    assert result["sleep_operation_id"] == "sleep-existing"
    assert result["monitor_checks"] == 1
    assert composed.worker.monitor_calls == []
    assert orchestrator.calls == [("account-1", "sleep-existing")]


def test_daily_data_maintenance_purges_due_deletions_and_evaluates_storage_grace():
    composed = services()
    observed_at = datetime(2026, 8, 8, 3, 0, tzinfo=UTC)

    result = gamewake_worker.handle_event(
        {"action": "maintain_data", "observed_at": observed_at.isoformat()},
        services=composed,
    )

    assert result == {"purged": 2, "storage_accounts": 2, "storage_charges": 1}
    assert composed.world_data.calls == [
        ("account-1", "world-delete-1", observed_at),
        ("account-2", "world-delete-2", observed_at),
    ]
    assert composed.storage.calls == [
        ("account-1", False, observed_at),
        ("account-1", True, observed_at),
        ("account-2", False, observed_at),
    ]
    assert composed.billing.storage_calls == [
        (
            "account-1",
            {
                "excess_bytes": 1024**3,
                "rate_per_gib_month": Decimal("2.00"),
                "billing_month": "2026-08",
                "idempotency_key": "storage:account-1:2026-08",
            },
        ),
        (
            "account-2",
            {
                "excess_bytes": 2 * 1024**3,
                "rate_per_gib_month": Decimal("2.00"),
                "billing_month": "2026-08",
                "idempotency_key": "storage:account-2:2026-08",
            },
        ),
    ]
