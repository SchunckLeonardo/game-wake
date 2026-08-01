import pytest

from gamewake.accounts import Accounts, InMemoryAccountRepository
from gamewake.worlds import (
    InMemoryWorldRepository,
    OperationPhase,
    OperationStatus,
    Runtime,
    WorldOperationWorker,
    Worlds,
    WorldStatus,
)


class RecordingRuntimeProvider:
    def __init__(self, events):
        self.events = events

    def provision(self, world, *, idempotency_key):
        self.events.append(("provision", idempotency_key))
        return Runtime(id="runtime-123", provider_reference="i-123")

    def release(self, runtime, *, idempotency_key):
        self.events.append(("release", idempotency_key))


class RecordingWorldStateStore:
    def __init__(self, events):
        self.events = events

    def restore(self, world, runtime, *, idempotency_key):
        self.events.append(("restore", idempotency_key))


class HealthyPalworldTemplate:
    def __init__(self, events):
        self.events = events

    def apply_configuration(self, world, runtime, *, idempotency_key):
        self.events.append(("configure", idempotency_key))

    def start(self, world, runtime, *, idempotency_key):
        self.events.append(("start", idempotency_key))

    def is_healthy(self, world, runtime):
        self.events.append(("health", None))
        return True

    def stop(self, world, runtime, *, idempotency_key):
        self.events.append(("stop", idempotency_key))


class SingleTemplateCatalog:
    def __init__(self, template):
        self.template = template

    def resolve(self, game_template_id):
        assert game_template_id == "palworld:1"
        return self.template


class UnhealthyPalworldTemplate(HealthyPalworldTemplate):
    def is_healthy(self, world, runtime):
        self.events.append(("health", None))
        return False


class IdempotentRuntimeProvider:
    def __init__(self):
        self.calls = []
        self.created = {}

    def provision(self, world, *, idempotency_key):
        self.calls.append(idempotency_key)
        return self.created.setdefault(
            idempotency_key,
            Runtime(id=f"runtime-{len(self.created) + 1}", provider_reference="i-123"),
        )

    def release(self, runtime, *, idempotency_key):
        self.calls.append(idempotency_key)


class FailFirstRuntimePersistence(InMemoryWorldRepository):
    def __init__(self):
        super().__init__()
        self.should_fail = True

    def save_operation(self, operation, **kwargs):
        if self.should_fail and operation.phase is OperationPhase.RESTORING_WORLD:
            self.should_fail = False
            raise RuntimeError("simulated worker interruption")
        return super().save_operation(operation, **kwargs)


def test_worker_reaches_online_only_after_the_game_is_healthy():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    repository = InMemoryWorldRepository()
    worlds = Worlds(repository, access=accounts)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="br-sao-paulo",
        runtime_profile_id="palworld-small",
    )
    operation = worlds.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="discord-command-1",
    )
    events = []
    worker = WorldOperationWorker(
        repository,
        runtime_provider=RecordingRuntimeProvider(events),
        state_store=RecordingWorldStateStore(events),
        game_templates=SingleTemplateCatalog(HealthyPalworldTemplate(events)),
    )

    completed = worker.run_to_completion(account.id, operation.id)

    assert completed.status is OperationStatus.SUCCEEDED
    assert completed.phase is OperationPhase.COMPLETE
    assert [event[0] for event in events] == [
        "provision",
        "restore",
        "configure",
        "start",
        "health",
    ]
    assert len({key for _, key in events if key is not None}) == 4
    online = worlds.get_world(
        account.id,
        world.id,
        viewer_user_id="owner",
    )
    assert online.status is WorldStatus.ONLINE
    assert online.runtime_id == "runtime-123"


def test_failed_health_check_never_marks_the_world_online():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    repository = InMemoryWorldRepository()
    worlds = Worlds(repository, access=accounts)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="br-sao-paulo",
        runtime_profile_id="palworld-small",
    )
    operation = worlds.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="discord-command-1",
    )
    events = []
    worker = WorldOperationWorker(
        repository,
        runtime_provider=RecordingRuntimeProvider(events),
        state_store=RecordingWorldStateStore(events),
        game_templates=SingleTemplateCatalog(UnhealthyPalworldTemplate(events)),
    )

    completed = worker.run_to_completion(account.id, operation.id)

    assert completed.status is OperationStatus.NEEDS_ATTENTION
    assert [event[0] for event in events][-3:] == ["health", "stop", "release"]
    assert (
        worlds.get_world(
            account.id,
            world.id,
            viewer_user_id="owner",
        ).status
        is WorldStatus.NEEDS_ATTENTION
    )


def test_worker_retry_reuses_the_same_runtime_effect_key_after_interruption():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    repository = FailFirstRuntimePersistence()
    worlds = Worlds(repository, access=accounts)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="br-sao-paulo",
        runtime_profile_id="palworld-small",
    )
    operation = worlds.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="discord-command-1",
    )
    events = []
    provider = IdempotentRuntimeProvider()
    worker = WorldOperationWorker(
        repository,
        runtime_provider=provider,
        state_store=RecordingWorldStateStore(events),
        game_templates=SingleTemplateCatalog(HealthyPalworldTemplate(events)),
    )
    worker.advance(account.id, operation.id)

    with pytest.raises(RuntimeError, match="simulated worker interruption"):
        worker.advance(account.id, operation.id)

    completed = worker.run_to_completion(account.id, operation.id)

    assert completed.status is OperationStatus.SUCCEEDED
    assert len(provider.created) == 1
    assert provider.calls == [provider.calls[0], provider.calls[0]]


def test_worker_marks_a_non_terminal_operation_as_needing_attention():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    repository = InMemoryWorldRepository()
    worlds = Worlds(repository, access=accounts)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="br-sao-paulo",
        runtime_profile_id="palworld-small",
    )
    operation = worlds.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="discord-command-1",
    )
    worker = WorldOperationWorker(
        repository,
        runtime_provider=RecordingRuntimeProvider([]),
        state_store=RecordingWorldStateStore([]),
        game_templates=SingleTemplateCatalog(HealthyPalworldTemplate([])),
    )

    failed = worker.mark_needs_attention(account.id, operation.id)

    assert failed.status is OperationStatus.NEEDS_ATTENTION
    assert (
        worlds.get_world(
            account.id,
            world.id,
            viewer_user_id="owner",
        ).status
        is WorldStatus.NEEDS_ATTENTION
    )


def test_worker_failure_cleanup_releases_allocated_compute_and_billing_hold():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    repository = InMemoryWorldRepository()
    worlds = Worlds(repository, access=accounts)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )
    operation = worlds.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="wake-1",
    )
    operation = worlds.attach_billing_session(
        account.id,
        operation.id,
        session_quote_id="quote-1",
        usage_reservation_id="reservation-1",
    )
    events = []

    class Usage:
        def cancel(self, operation):
            events.append(("cancel", operation.id))

        def record_release(self, operation, *, runtime_released_at, reached_online):
            events.append(("usage", reached_online))

    provider = RecordingRuntimeProvider(events)
    worker = WorldOperationWorker(
        repository,
        runtime_provider=provider,
        state_store=RecordingWorldStateStore(events),
        game_templates=SingleTemplateCatalog(HealthyPalworldTemplate(events)),
        usage_recorder=Usage(),
    )
    worker.advance(account.id, operation.id)
    worker.advance(account.id, operation.id)

    failed = worker.mark_needs_attention(account.id, operation.id)

    assert failed.status is OperationStatus.NEEDS_ATTENTION
    assert [event[0] for event in events][-2:] == ["release", "usage"]
    current = worlds.get_world(account.id, world.id, viewer_user_id="owner")
    assert current.runtime_id is None
    assert current.usage_reservation_id is None


def test_marking_an_already_terminal_operation_is_idempotent():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    repository = InMemoryWorldRepository()
    worlds = Worlds(repository, access=accounts)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="br-sao-paulo",
        runtime_profile_id="palworld-small",
    )
    operation = worlds.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="discord-command-1",
    )
    worker = WorldOperationWorker(
        repository,
        runtime_provider=RecordingRuntimeProvider([]),
        state_store=RecordingWorldStateStore([]),
        game_templates=SingleTemplateCatalog(HealthyPalworldTemplate([])),
    )
    completed = worker.run_to_completion(account.id, operation.id)

    unchanged = worker.mark_needs_attention(account.id, operation.id)

    assert unchanged == completed
