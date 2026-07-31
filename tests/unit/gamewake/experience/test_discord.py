from dataclasses import replace

from gamewake.accounts import Accounts, InMemoryAccountRepository
from gamewake.billing import Billing, InMemoryBillingRepository
from gamewake.control_plane import ConnectionDetails, GameWakeApplication
from gamewake.experience import (
    DiscordCommandController,
    DiscordInteraction,
    DiscordInteractionAdapter,
    DiscordUser,
)
from gamewake.game_catalog import GameCatalog
from gamewake.worlds import InMemoryWorldRepository, Worlds, WorldStatus


class StubConnectionDetailsProvider:
    def issue(self, world, *, viewer_user_id):
        return ConnectionDetails(
            host="203.0.113.10",
            port=8211,
            password="segredo-do-grupo",
        )


def test_start_command_bootstraps_the_guild_account_with_the_caller_as_owner():
    repository = InMemoryAccountRepository()
    accounts = Accounts(repository)
    catalog = GameCatalog.with_palworld()
    controller = DiscordCommandController(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog),
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        ),
        console_url="https://app.gamewake.example",
    )

    response = controller.handle(
        DiscordInteraction(
            id="start-1",
            guild_id="guild-new",
            discord_user_id="discord-owner",
            display_name="Leonardo",
            command="comecar",
        )
    )

    account = accounts.find_account_by_discord_guild("guild-new")
    assert account is not None
    owner = accounts.sign_in_with_discord(
        discord_user_id="discord-owner",
        display_name="Leonardo",
    )
    [membership] = accounts.list_memberships(account.id, viewer_user_id=owner.id)
    assert {role.value for role in membership.roles} == {"owner"}
    assert response.ephemeral is True
    assert response.links[0][1].endswith(f"/accounts/{account.id}")


def test_invite_command_creates_one_private_invitation_for_each_selected_friend():
    account_repository = InMemoryAccountRepository()
    accounts = Accounts(account_repository)
    owner = accounts.sign_in_with_discord(
        discord_user_id="discord-owner",
        display_name="Leonardo",
    )
    account = accounts.create_account(
        name="Sexta com os amigos",
        owner_user_id=owner.id,
        discord_guild_id="guild-1",
    )
    catalog = GameCatalog.with_palworld()
    application = GameWakeApplication(
        accounts=accounts,
        worlds=Worlds(
            InMemoryWorldRepository(),
            access=accounts,
            game_catalog=catalog,
        ),
        billing=Billing(InMemoryBillingRepository()),
        game_catalog=catalog,
    )
    controller = DiscordCommandController(
        application,
        console_url="https://app.gamewake.example",
    )

    response = controller.handle(
        DiscordInteraction(
            id="interaction-1",
            guild_id="guild-1",
            discord_user_id="discord-owner",
            display_name="Leonardo",
            command="convidar",
            selected_users=(
                DiscordUser("discord-friend-1", "Ana"),
                DiscordUser("discord-friend-2", "Bia"),
                DiscordUser("discord-friend-3", "Caio"),
            ),
        )
    )

    invitations = accounts.list_invitations(account.id, viewer_user_id=owner.id)
    invited_users = {
        accounts.sign_in_with_discord(
            discord_user_id=f"discord-friend-{number}",
            display_name=name,
        ).id
        for number, name in ((1, "Ana"), (2, "Bia"), (3, "Caio"))
    }
    assert response.ephemeral is True
    assert "3 convites" in response.content
    assert len(invitations) == 3
    assert {invitation.invited_user_id for invitation in invitations} == invited_users


def test_invited_friend_explicitly_accepts_from_discord_and_receives_player_access():
    repository = InMemoryAccountRepository()
    accounts = Accounts(repository)
    owner = accounts.sign_in_with_discord(
        discord_user_id="discord-owner",
        display_name="Leonardo",
    )
    account = accounts.create_account(
        name="Sexta com os amigos",
        owner_user_id=owner.id,
        discord_guild_id="guild-1",
    )
    catalog = GameCatalog.with_palworld()
    application = GameWakeApplication(
        accounts=accounts,
        worlds=Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog),
        billing=Billing(InMemoryBillingRepository()),
        game_catalog=catalog,
    )
    controller = DiscordCommandController(
        application,
        console_url="https://app.gamewake.example",
    )
    controller.handle(
        DiscordInteraction(
            id="invite-1",
            guild_id="guild-1",
            discord_user_id="discord-owner",
            display_name="Leonardo",
            command="convidar",
            selected_users=(DiscordUser("discord-friend", "Ana"),),
        )
    )

    accepted = controller.handle(
        DiscordInteraction(
            id="accept-1",
            guild_id="guild-1",
            discord_user_id="discord-friend",
            display_name="Ana",
            command="aceitar",
        )
    )

    friend = accounts.sign_in_with_discord(
        discord_user_id="discord-friend",
        display_name="Ana",
    )
    membership = next(
        item
        for item in accounts.list_memberships(account.id, viewer_user_id=friend.id)
        if item.user_id == friend.id
    )
    assert accepted.ephemeral is True
    assert "Player" in accepted.content
    assert {role.value for role in membership.roles} == {"player"}


def test_status_auto_selects_one_world_and_offers_only_allowed_choices_when_ambiguous():
    account_repository = InMemoryAccountRepository()
    world_repository = InMemoryWorldRepository()
    accounts = Accounts(account_repository)
    owner = accounts.sign_in_with_discord(
        discord_user_id="discord-owner",
        display_name="Leonardo",
    )
    account = accounts.create_account(
        name="Sexta com os amigos",
        owner_user_id=owner.id,
        discord_guild_id="guild-1",
    )
    catalog = GameCatalog.with_palworld()
    worlds = Worlds(world_repository, access=accounts, game_catalog=catalog)
    application = GameWakeApplication(
        accounts=accounts,
        worlds=worlds,
        billing=Billing(InMemoryBillingRepository()),
        game_catalog=catalog,
    )
    controller = DiscordCommandController(
        application,
        console_url="https://app.gamewake.example",
    )
    first = worlds.create_world(
        account.id,
        actor_user_id=owner.id,
        name="Palpagos",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )

    automatic = controller.handle(
        DiscordInteraction(
            id="interaction-status-1",
            guild_id="guild-1",
            discord_user_id="discord-owner",
            display_name="Leonardo",
            command="status",
        )
    )

    assert automatic.ephemeral is False
    assert automatic.world_options == ()
    assert "Palpagos" in automatic.content
    assert "dormindo" in automatic.content

    second = worlds.create_world(
        account.id,
        actor_user_id=owner.id,
        name="Ilha B",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )
    ambiguous = controller.handle(
        DiscordInteraction(
            id="interaction-status-2",
            guild_id="guild-1",
            discord_user_id="discord-owner",
            display_name="Leonardo",
            command="status",
        )
    )

    assert ambiguous.ephemeral is True
    assert "Escolha um World" in ambiguous.content
    assert {option.id for option in ambiguous.world_options} == {first.id, second.id}


def test_repeated_wake_command_observes_the_same_world_operation():
    account_repository = InMemoryAccountRepository()
    world_repository = InMemoryWorldRepository()
    accounts = Accounts(account_repository)
    owner = accounts.sign_in_with_discord(
        discord_user_id="discord-owner",
        display_name="Leonardo",
    )
    account = accounts.create_account(
        name="Sexta com os amigos",
        owner_user_id=owner.id,
        discord_guild_id="guild-1",
    )
    catalog = GameCatalog.with_palworld()
    worlds = Worlds(world_repository, access=accounts, game_catalog=catalog)
    world = worlds.create_world(
        account.id,
        actor_user_id=owner.id,
        name="Palpagos",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )
    controller = DiscordCommandController(
        GameWakeApplication(
            accounts=accounts,
            worlds=worlds,
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        ),
        console_url="https://app.gamewake.example",
    )
    interaction = DiscordInteraction(
        id="interaction-wake-1",
        guild_id="guild-1",
        discord_user_id="discord-owner",
        display_name="Leonardo",
        command="acordar",
    )

    first = controller.handle(interaction)
    repeated = controller.handle(interaction)

    operations = worlds.list_operations(
        account.id,
        world.id,
        viewer_user_id=owner.id,
    )
    assert first.ephemeral is False
    assert first.content == repeated.content
    assert "acordando" in first.content
    assert len(operations) == 1


def test_forged_world_selection_is_rejected_without_disclosing_the_resource():
    account_repository = InMemoryAccountRepository()
    accounts = Accounts(account_repository)
    owner = accounts.sign_in_with_discord(
        discord_user_id="discord-owner",
        display_name="Leonardo",
    )
    accounts.create_account(
        name="Sexta com os amigos",
        owner_user_id=owner.id,
        discord_guild_id="guild-1",
    )
    catalog = GameCatalog.with_palworld()
    controller = DiscordCommandController(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(
                InMemoryWorldRepository(),
                access=accounts,
                game_catalog=catalog,
            ),
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        ),
        console_url="https://app.gamewake.example",
    )

    response = controller.handle(
        DiscordInteraction(
            id="interaction-forged",
            guild_id="guild-1",
            discord_user_id="discord-owner",
            display_name="Leonardo",
            command="status",
            world_id="world-from-another-account",
        )
    )

    assert response.ephemeral is True
    assert response.content == "O World solicitado não está disponível para você."


def test_connection_is_private_status_is_redacted_and_sleep_is_safe():
    account_repository = InMemoryAccountRepository()
    world_repository = InMemoryWorldRepository()
    accounts = Accounts(account_repository)
    owner = accounts.sign_in_with_discord(
        discord_user_id="discord-owner",
        display_name="Leonardo",
    )
    account = accounts.create_account(
        name="Sexta com os amigos",
        owner_user_id=owner.id,
        discord_guild_id="guild-1",
    )
    catalog = GameCatalog.with_palworld()
    worlds = Worlds(world_repository, access=accounts, game_catalog=catalog)
    world = worlds.create_world(
        account.id,
        actor_user_id=owner.id,
        name="Palpagos",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )
    online = replace(
        world,
        status=WorldStatus.ONLINE,
        runtime_id="runtime-1",
        runtime_provider_reference="i-123",
        version=world.version + 1,
    )
    world_repository.save(online, expected_version=world.version)
    controller = DiscordCommandController(
        GameWakeApplication(
            accounts=accounts,
            worlds=worlds,
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
            connection_details_provider=StubConnectionDetailsProvider(),
        ),
        console_url="https://app.gamewake.example",
    )

    status = controller.handle(
        DiscordInteraction(
            id="interaction-status",
            guild_id="guild-1",
            discord_user_id="discord-owner",
            display_name="Leonardo",
            command="status",
        )
    )
    connection = controller.handle(
        DiscordInteraction(
            id="interaction-connect",
            guild_id="guild-1",
            discord_user_id="discord-owner",
            display_name="Leonardo",
            command="conectar",
        )
    )
    configuration = controller.handle(
        DiscordInteraction(
            id="interaction-config",
            guild_id="guild-1",
            discord_user_id="discord-owner",
            display_name="Leonardo",
            command="configurar",
        )
    )
    sleeping = controller.handle(
        DiscordInteraction(
            id="interaction-sleep",
            guild_id="guild-1",
            discord_user_id="discord-owner",
            display_name="Leonardo",
            command="dormir",
        )
    )

    assert status.ephemeral is False
    assert "203.0.113.10" not in status.content
    assert "segredo-do-grupo" not in status.content
    assert connection.ephemeral is True
    assert "203.0.113.10:8211" in connection.content
    assert "segredo-do-grupo" in connection.content
    assert configuration.ephemeral is True
    assert configuration.links == (
        (
            "Abrir configurações",
            f"https://app.gamewake.example/accounts/{account.id}/worlds/{world.id}/configuration",
        ),
    )
    assert sleeping.ephemeral is False
    assert "sono seguro" in sleeping.content
    assert (
        len(
            worlds.list_operations(
                account.id,
                world.id,
                viewer_user_id=owner.id,
            )
        )
        == 1
    )


def test_open_console_is_private_and_links_to_the_discord_account():
    account_repository = InMemoryAccountRepository()
    accounts = Accounts(account_repository)
    owner = accounts.sign_in_with_discord(
        discord_user_id="discord-owner",
        display_name="Leonardo",
    )
    account = accounts.create_account(
        name="Sexta com os amigos",
        owner_user_id=owner.id,
        discord_guild_id="guild-1",
    )
    catalog = GameCatalog.with_palworld()
    controller = DiscordCommandController(
        GameWakeApplication(
            accounts=accounts,
            worlds=Worlds(
                InMemoryWorldRepository(),
                access=accounts,
                game_catalog=catalog,
            ),
            billing=Billing(InMemoryBillingRepository()),
            game_catalog=catalog,
        ),
        console_url="https://app.gamewake.example/",
    )

    response = controller.handle(
        DiscordInteraction(
            id="interaction-console",
            guild_id="guild-1",
            discord_user_id="discord-owner",
            display_name="Leonardo",
            command="console",
        )
    )

    assert response.ephemeral is True
    assert response.links == (
        ("Abrir GameWake Console", f"https://app.gamewake.example/accounts/{account.id}"),
    )

    help_response = controller.handle(
        DiscordInteraction(
            id="interaction-help",
            guild_id="guild-1",
            discord_user_id="discord-owner",
            display_name="Leonardo",
            command="ajuda",
        )
    )
    assert help_response.ephemeral is True
    assert "/gamewake convidar" in help_response.content
    assert "/gamewake conectar" in help_response.content


def test_discord_adapter_maps_real_slash_options_and_world_selector_components():
    account_repository = InMemoryAccountRepository()
    accounts = Accounts(account_repository)
    owner = accounts.sign_in_with_discord(
        discord_user_id="discord-owner",
        display_name="Leonardo",
    )
    account = accounts.create_account(
        name="Sexta com os amigos",
        owner_user_id=owner.id,
        discord_guild_id="guild-1",
    )
    catalog = GameCatalog.with_palworld()
    worlds = Worlds(InMemoryWorldRepository(), access=accounts, game_catalog=catalog)
    first = worlds.create_world(
        account.id,
        actor_user_id=owner.id,
        name="Palpagos",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )
    worlds.create_world(
        account.id,
        actor_user_id=owner.id,
        name="Ilha B",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )
    adapter = DiscordInteractionAdapter(
        DiscordCommandController(
            GameWakeApplication(
                accounts=accounts,
                worlds=worlds,
                billing=Billing(InMemoryBillingRepository()),
                game_catalog=catalog,
            ),
            console_url="https://app.gamewake.example",
        )
    )
    base = {
        "id": "interaction-raw",
        "guild_id": "guild-1",
        "member": {
            "user": {
                "id": "discord-owner",
                "username": "Leonardo",
            }
        },
    }

    invitation = adapter.handle(
        {
            **base,
            "type": 2,
            "data": {
                "name": "gamewake",
                "options": [
                    {
                        "type": 1,
                        "name": "convidar",
                        "options": [
                            {"type": 6, "name": "amigo1", "value": "friend-1"},
                            {"type": 6, "name": "amigo2", "value": "friend-2"},
                            {"type": 6, "name": "amigo3", "value": "friend-3"},
                        ],
                    }
                ],
                "resolved": {
                    "users": {
                        "friend-1": {"id": "friend-1", "username": "Ana"},
                        "friend-2": {"id": "friend-2", "username": "Bia"},
                        "friend-3": {"id": "friend-3", "username": "Caio"},
                    }
                },
            },
        }
    )
    selector = adapter.handle(
        {
            **base,
            "type": 2,
            "data": {
                "name": "gamewake",
                "options": [{"type": 1, "name": "status"}],
            },
        }
    )
    wake_selector = adapter.handle(
        {
            **base,
            "type": 2,
            "data": {
                "name": "gamewake",
                "options": [{"type": 1, "name": "acordar"}],
            },
        }
    )
    selected = adapter.handle(
        {
            **base,
            "id": "interaction-component",
            "type": 3,
            "data": {
                "custom_id": "gamewake:world:status",
                "component_type": 3,
                "values": [first.id],
            },
        }
    )

    assert invitation["type"] == 4
    assert invitation["data"]["flags"] == 64
    assert invitation["data"]["allowed_mentions"] == {"parse": []}
    assert selector["data"]["components"][0]["components"][0]["type"] == 3
    assert (
        wake_selector["data"]["components"][0]["components"][0]["custom_id"]
        == "gamewake:world:acordar"
    )
    assert selected["type"] == 4
    assert selected["data"].get("flags") is None
    assert "Palpagos" in selected["data"]["content"]
