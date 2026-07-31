import pytest

from gamewake.accounts import (
    Accounts,
    DiscordGuildAlreadyLinkedError,
    IdentityProvider,
    InMemoryAccountRepository,
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
    [identity] = accounts.list_linked_identities(first_sign_in.id)
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
