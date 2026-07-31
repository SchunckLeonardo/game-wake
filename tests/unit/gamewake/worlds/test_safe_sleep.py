from gamewake.accounts import Accounts, InMemoryAccountRepository
from gamewake.worlds import (
    Backup,
    InMemoryWorldRepository,
    OperationStatus,
    Runtime,
    StoredWorldState,
    WorldOperationWorker,
    Worlds,
    WorldStatus,
)


class RuntimeProvider:
    def __init__(self, events):
        self.events = events

    def provision(self, world, *, idempotency_key):
        return Runtime(id="runtime-123", provider_reference="i-123")

    def release(self, runtime, *, idempotency_key):
        self.events.append("release")


class StateStore:
    def __init__(self, events):
        self.events = events

    def restore(self, world, runtime, *, idempotency_key):
        pass

    def persist_and_validate(self, world, runtime, *, idempotency_key):
        self.events.append("persist")
        return StoredWorldState(id="state-2", checksum="sha256:valid", validated=True)


class InvalidStateStore(StateStore):
    def persist_and_validate(self, world, runtime, *, idempotency_key):
        self.events.append("persist")
        return StoredWorldState(id="state-2", checksum="sha256:invalid", validated=False)


class PalworldTemplate:
    def __init__(self, events):
        self.events = events

    def apply_configuration(self, world, runtime, *, idempotency_key):
        pass

    def start(self, world, runtime, *, idempotency_key):
        pass

    def is_healthy(self, world, runtime):
        return True

    def player_count(self, world, runtime):
        self.events.append("players")
        return 0

    def save(self, world, runtime, *, idempotency_key):
        self.events.append("save")

    def stop(self, world, runtime, *, idempotency_key):
        self.events.append("stop")


class BusyPalworldTemplate(PalworldTemplate):
    def player_count(self, world, runtime):
        self.events.append("players")
        return 2


class TemplateCatalog:
    def __init__(self, template):
        self.template = template

    def resolve(self, game_template_id):
        return self.template


class BackupStore:
    def __init__(self, events):
        self.events = events
        self.backups = []

    def create_automatic(self, world, state, *, idempotency_key):
        self.events.append("backup")
        backup = Backup(
            id="backup-1",
            account_id=world.account_id,
            world_id=world.id,
            state_id=state.id,
            checksum=state.checksum,
        )
        self.backups.append(backup)
        return backup


def test_safe_sleep_releases_runtime_only_after_validated_state_and_backup():
    events = []
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
    runtime_provider = RuntimeProvider(events)
    state_store = StateStore(events)
    template = PalworldTemplate(events)
    backup_store = BackupStore(events)
    worker = WorldOperationWorker(
        repository,
        runtime_provider=runtime_provider,
        state_store=state_store,
        game_templates=TemplateCatalog(template),
        backup_store=backup_store,
    )
    wake = worlds.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="wake-1",
    )
    worker.run_to_completion(account.id, wake.id)
    events.clear()

    sleep = worlds.request_sleep(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="sleep-1",
    )
    worker.run_to_completion(account.id, sleep.id)

    assert events == ["players", "save", "stop", "persist", "backup", "release"]
    assert len(backup_store.backups) == 1
    sleeping = worlds.get_world(
        account.id,
        world.id,
        viewer_user_id="owner",
    )
    assert sleeping.status is WorldStatus.SLEEPING
    assert sleeping.runtime_id is None


def test_invalid_persisted_state_preserves_runtime_and_never_creates_backup():
    events = []
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
    runtime_provider = RuntimeProvider(events)
    state_store = InvalidStateStore(events)
    template = PalworldTemplate(events)
    backup_store = BackupStore(events)
    worker = WorldOperationWorker(
        repository,
        runtime_provider=runtime_provider,
        state_store=state_store,
        game_templates=TemplateCatalog(template),
        backup_store=backup_store,
    )
    wake = worlds.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="wake-1",
    )
    worker.run_to_completion(account.id, wake.id)
    events.clear()
    sleep = worlds.request_sleep(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="sleep-1",
    )

    failed = worker.run_to_completion(account.id, sleep.id)

    assert failed.status is OperationStatus.NEEDS_ATTENTION
    assert events == ["players", "save", "stop", "persist"]
    assert backup_store.backups == []
    attention = worlds.get_world(
        account.id,
        world.id,
        viewer_user_id="owner",
    )
    assert attention.status is WorldStatus.NEEDS_ATTENTION
    assert attention.runtime_id == "runtime-123"


def test_non_forced_sleep_is_cancelled_when_players_are_online():
    events = []
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
    runtime_provider = RuntimeProvider(events)
    state_store = StateStore(events)
    template = BusyPalworldTemplate(events)
    worker = WorldOperationWorker(
        repository,
        runtime_provider=runtime_provider,
        state_store=state_store,
        game_templates=TemplateCatalog(template),
        backup_store=BackupStore(events),
    )
    wake = worlds.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="wake-1",
    )
    worker.run_to_completion(account.id, wake.id)
    events.clear()
    sleep = worlds.request_sleep(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="sleep-1",
    )

    cancelled = worker.run_to_completion(account.id, sleep.id)

    assert cancelled.status is OperationStatus.CANCELLED
    assert events == ["players"]
    assert worlds.get_world(
        account.id,
        world.id,
        viewer_user_id="owner",
    ).status is WorldStatus.ONLINE
