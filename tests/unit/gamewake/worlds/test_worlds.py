import pytest

from gamewake.accounts import Accounts, InMemoryAccountRepository, PermissionDeniedError
from gamewake.worlds import InMemoryWorldRepository, Worlds, WorldStatus


def test_an_owner_creates_a_sleeping_world_without_a_runtime():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    worlds = Worlds(InMemoryWorldRepository(), access=accounts)

    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="br-sao-paulo",
        runtime_profile_id="palworld-small",
    )

    assert world.account_id == account.id
    assert world.status is WorldStatus.SLEEPING
    assert world.runtime_id is None
    assert worlds.get_world(
        account.id,
        world.id,
        viewer_user_id="owner",
    ) == world


def test_a_user_from_another_account_cannot_observe_a_world():
    accounts = Accounts(InMemoryAccountRepository())
    first_account = accounts.create_account(name="Primeiro", owner_user_id="first-owner")
    accounts.create_account(name="Segundo", owner_user_id="second-owner")
    worlds = Worlds(InMemoryWorldRepository(), access=accounts)
    world = worlds.create_world(
        first_account.id,
        actor_user_id="first-owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="br-sao-paulo",
        runtime_profile_id="palworld-small",
    )

    with pytest.raises(PermissionDeniedError):
        worlds.get_world(
            first_account.id,
            world.id,
            viewer_user_id="second-owner",
        )
