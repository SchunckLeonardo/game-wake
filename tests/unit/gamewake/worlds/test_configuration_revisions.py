from gamewake.accounts import Accounts, InMemoryAccountRepository
from gamewake.game_catalog import GameCatalog
from gamewake.worlds import (
    InMemoryWorldRepository,
    Runtime,
    WorldOperationWorker,
    Worlds,
)


class RuntimeProvider:
    def provision(self, world, *, idempotency_key):
        return Runtime(id="runtime-123", provider_reference="i-123")


class StateStore:
    def restore(self, world, runtime, *, idempotency_key):
        pass


class Template:
    def __init__(self):
        self.applied_revision_id = None

    def apply_configuration(self, world, runtime, *, idempotency_key):
        self.applied_revision_id = world.pending_configuration_revision_id

    def start(self, world, runtime, *, idempotency_key):
        pass

    def is_healthy(self, world, runtime):
        return True


class TemplateCatalog:
    def __init__(self, template):
        self.template = template

    def resolve(self, game_template_id):
        return self.template


def test_configuration_change_is_previewed_and_stored_as_an_immutable_revision():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    repository = InMemoryWorldRepository()
    worlds = Worlds(repository, access=accounts, game_catalog=GameCatalog.with_palworld())
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="br-sao-paulo",
        runtime_profile_id="palworld-small",
    )
    initial = worlds.get_configuration(
        account.id,
        world.id,
        viewer_user_id="owner",
    )

    preview = worlds.preview_configuration_change(
        account.id,
        world.id,
        actor_user_id="owner",
        changes={"enemy_drop_item_rate": "3,5"},
    )
    revision = worlds.update_configuration(
        account.id,
        world.id,
        actor_user_id="owner",
        changes={"enemy_drop_item_rate": "3,5"},
        idempotency_key="discord-config-1",
    )
    repeated = worlds.update_configuration(
        account.id,
        world.id,
        actor_user_id="owner",
        changes={"enemy_drop_item_rate": "3,5"},
        idempotency_key="discord-config-1",
    )

    assert initial.number == 1
    assert initial.values["enemy_drop_item_rate"] == 1.0
    [change] = preview.changes
    assert (change.key, change.current, change.proposed) == (
        "enemy_drop_item_rate",
        1.0,
        3.5,
    )
    assert change.restart_required
    assert revision.number == 2
    assert revision.values["enemy_drop_item_rate"] == 3.5
    assert repeated.id == revision.id
    assert initial.values["enemy_drop_item_rate"] == 1.0
    updated_world = worlds.get_world(
        account.id,
        world.id,
        viewer_user_id="owner",
    )
    assert updated_world.configuration_revision_id == initial.id
    assert updated_world.pending_configuration_revision_id == revision.id


def test_pending_configuration_becomes_effective_only_after_wake_applies_it():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    repository = InMemoryWorldRepository()
    worlds = Worlds(repository, access=accounts, game_catalog=GameCatalog.with_palworld())
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="br-sao-paulo",
        runtime_profile_id="palworld-small",
    )
    revision = worlds.update_configuration(
        account.id,
        world.id,
        actor_user_id="owner",
        changes={"enemy_drop_item_rate": 3.5},
        idempotency_key="web-config-1",
    )
    template = Template()
    worker = WorldOperationWorker(
        repository,
        runtime_provider=RuntimeProvider(),
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

    effective = worlds.get_world(
        account.id,
        world.id,
        viewer_user_id="owner",
    )
    assert template.applied_revision_id == revision.id
    assert effective.configuration_revision_id == revision.id
    assert effective.pending_configuration_revision_id is None
