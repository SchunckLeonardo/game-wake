import pytest

from gamewake.accounts import (
    Accounts,
    DiscordGuildAlreadyLinkedError,
    IdentityProvider,
    InMemoryAccountRepository,
    PermissionDeniedError,
)


def test_discord_sign_in_resolves_a_stable_internal_user():
    accounts = Accounts(InMemoryAccountRepository())

    first_sign_in = accounts.sign_in_with_discord(
        discord_user_id="discord-123",
        display_name="Leo",
    )
    second_sign_in = accounts.sign_in_with_discord(
        discord_user_id="discord-123",
        display_name="Leonardo",
    )

    assert second_sign_in.id == first_sign_in.id
    [identity] = accounts.list_linked_identities(
        first_sign_in.id,
        viewer_user_id=first_sign_in.id,
    )
    assert identity.provider is IdentityProvider.DISCORD
    assert identity.provider_user_id == "discord-123"


def test_a_discord_guild_can_belong_to_only_one_gamewake_account():
    accounts = Accounts(InMemoryAccountRepository())
    owner = accounts.sign_in_with_discord(
        discord_user_id="discord-owner",
        display_name="Owner",
    )
    account = accounts.create_account(
        name="Sexta com os amigos",
        owner_user_id=owner.id,
        discord_guild_id="guild-123",
    )

    with pytest.raises(DiscordGuildAlreadyLinkedError):
        accounts.create_account(
            name="Outro grupo",
            owner_user_id=owner.id,
            discord_guild_id="guild-123",
        )

    assert accounts.find_account_by_discord_guild("guild-123") == account


def test_owner_can_change_the_linked_discord_server_without_recreating_the_account():
    accounts = Accounts(InMemoryAccountRepository())
    owner = accounts.sign_in_with_discord(
        discord_user_id="discord-owner",
        display_name="Owner",
    )
    account = accounts.create_account(
        name="Sexta com os amigos",
        owner_user_id=owner.id,
        discord_guild_id="123456789012345678",
    )

    updated = accounts.configure_discord_guild(
        account.id,
        actor_user_id=owner.id,
        discord_guild_id="987654321098765432",
    )

    assert updated.discord_guild_id == "987654321098765432"
    assert accounts.find_account_by_discord_guild("123456789012345678") is None
    assert accounts.find_account_by_discord_guild("987654321098765432") == updated


def test_linked_identities_are_private_to_the_user():
    accounts = Accounts(InMemoryAccountRepository())
    first = accounts.sign_in_with_discord(
        discord_user_id="discord-first",
        display_name="First",
    )
    second = accounts.sign_in_with_discord(
        discord_user_id="discord-second",
        display_name="Second",
    )

    with pytest.raises(PermissionDeniedError):
        accounts.list_linked_identities(first.id, viewer_user_id=second.id)
