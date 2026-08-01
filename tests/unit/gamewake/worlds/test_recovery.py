from datetime import UTC, datetime, timedelta

from gamewake.accounts import Accounts, InMemoryAccountRepository
from gamewake.worlds import (
    InMemoryWorldRepository,
    OperationStatus,
    OperationType,
    Runtime,
    WorldOperationWorker,
    Worlds,
    WorldStatus,
)


class RuntimeProvider:
    def __init__(self):
        self.provision_calls = 0

    def provision(self, world, *, idempotency_key):
        self.provision_calls += 1
        return Runtime(id="runtime-123", provider_reference="i-123")


class StateStore:
    def restore(self, world, runtime, *, idempotency_key):
        pass


class MutableHealthTemplate:
    def __init__(self):
        self.healthy = True
        self.start_calls = 0

    def apply_configuration(self, world, runtime, *, idempotency_key):
        pass

    def start(self, world, runtime, *, idempotency_key):
        self.start_calls += 1

    def is_healthy(self, world, runtime):
        return self.healthy


class TemplateCatalog:
    def __init__(self, template):
        self.template = template

    def resolve(self, game_template_id):
        return self.template


def test_automatic_recovery_stops_after_three_attempts_in_fifteen_minutes():
    now = datetime(2026, 7, 31, 20, 0, tzinfo=UTC)
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    repository = InMemoryWorldRepository()
    worlds = Worlds(repository, access=accounts, clock=lambda: now)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="br-sao-paulo",
        runtime_profile_id="palworld-small",
    )
    provider = RuntimeProvider()
    template = MutableHealthTemplate()
    worker = WorldOperationWorker(
        repository,
        runtime_provider=provider,
        state_store=StateStore(),
        game_templates=TemplateCatalog(template),
    )
    wake = worlds.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="wake-1",
    )
    worker.run_to_completion(account.id, wake.id)
    template.healthy = False

    attempts = []
    for attempt_number in range(1, 4):
        operation = worlds.request_automatic_recovery(
            account.id,
            world.id,
            detected_at=now + timedelta(minutes=attempt_number),
            idempotency_key=f"health-event-{attempt_number}",
        )
        attempts.append(worker.run_to_completion(account.id, operation.id))

    assert [attempt.attempt_number for attempt in attempts] == [1, 2, 3]
    assert [attempt.status for attempt in attempts] == [
        OperationStatus.FAILED,
        OperationStatus.FAILED,
        OperationStatus.NEEDS_ATTENTION,
    ]
    assert all(attempt.operation_type is OperationType.RECOVER for attempt in attempts)
    assert provider.provision_calls == 1
    assert template.start_calls == 4
    assert (
        worlds.get_world(
            account.id,
            world.id,
            viewer_user_id="owner",
        ).status
        is WorldStatus.NEEDS_ATTENTION
    )
    assert (
        worlds.request_automatic_recovery(
            account.id,
            world.id,
            detected_at=now + timedelta(minutes=4),
            idempotency_key="health-event-4",
        )
        is None
    )
