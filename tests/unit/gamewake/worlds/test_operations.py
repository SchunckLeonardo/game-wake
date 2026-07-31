from concurrent.futures import ThreadPoolExecutor

from gamewake.accounts import Accounts, InMemoryAccountRepository
from gamewake.worlds import (
    InMemoryWorldRepository,
    OperationPhase,
    OperationStatus,
    Worlds,
    WorldStatus,
)


def test_concurrent_wake_commands_join_one_world_operation():
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

    with ThreadPoolExecutor(max_workers=10) as executor:
        operations = list(
            executor.map(
                lambda command_number: worlds.request_wake(
                    account.id,
                    world.id,
                    actor_user_id="owner",
                    idempotency_key=f"discord-command-{command_number}",
                ),
                range(10),
            )
        )

    assert len({operation.id for operation in operations}) == 1
    [operation] = worlds.list_operations(
        account.id,
        world.id,
        viewer_user_id="owner",
    )
    assert operation.status is OperationStatus.PENDING
    assert operation.phase is OperationPhase.REQUESTED
    assert worlds.get_world(
        account.id,
        world.id,
        viewer_user_id="owner",
    ).status is WorldStatus.WAKING
