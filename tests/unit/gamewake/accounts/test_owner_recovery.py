from datetime import UTC, datetime

import pytest

from gamewake.accounts import (
    Accounts,
    ActivityAction,
    InMemoryAccountRepository,
    InMemoryRecoverySecretStore,
    InMemorySecurityNotifier,
    InvalidRecoveryCodeError,
    PredefinedRole,
    SensitiveActionConfirmation,
)


def test_a_sole_owner_can_recover_the_same_user_with_a_one_time_code():
    repository = InMemoryAccountRepository()
    recovery_secrets = InMemoryRecoverySecretStore()
    notifier = InMemorySecurityNotifier()
    accounts = Accounts(
        repository,
        recovery_secret_store=recovery_secrets,
        security_notifier=notifier,
    )
    owner = accounts.sign_in_with_discord(
        discord_user_id="lost-discord-id",
        display_name="Owner",
    )
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id=owner.id)

    recovery_codes = accounts.enable_owner_recovery(
        account.id,
        owner_user_id=owner.id,
        verified_email="owner@example.com",
    )

    assert len(recovery_codes) == 8
    assert len(set(recovery_codes)) == 8
    assert accounts.owner_recovery_ready(account.id)

    accounts.recover_owner_discord_identity(
        account.id,
        owner_user_id=owner.id,
        recovery_code=recovery_codes[0],
        new_discord_user_id="replacement-discord-id",
    )

    recovered = accounts.sign_in_with_discord(
        discord_user_id="replacement-discord-id",
        display_name="Recovered Owner",
    )
    assert recovered.id == owner.id
    assert notifier.notifications[-1] == (
        frozenset({owner.id}),
        ActivityAction.OWNER_RECOVERED,
        owner.id,
    )
    with pytest.raises(InvalidRecoveryCodeError):
        accounts.recover_owner_discord_identity(
            account.id,
            owner_user_id=owner.id,
            recovery_code=recovery_codes[0],
            new_discord_user_id="attacker-discord-id",
        )


def test_a_sole_owner_is_not_payment_ready_before_recovery_is_enabled():
    accounts = Accounts(
        InMemoryAccountRepository(),
        recovery_secret_store=InMemoryRecoverySecretStore(),
    )
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")

    assert not accounts.owner_recovery_ready(account.id)


def test_another_owner_can_replace_a_lost_discord_identity_without_support():
    repository = InMemoryAccountRepository()
    notifier = InMemorySecurityNotifier()
    now = datetime(2026, 7, 31, 19, 0, tzinfo=UTC)
    accounts = Accounts(repository, security_notifier=notifier, clock=lambda: now)
    lost_owner = accounts.sign_in_with_discord(
        discord_user_id="lost-discord-id",
        display_name="Lost Owner",
    )
    co_owner = accounts.sign_in_with_discord(
        discord_user_id="co-owner-discord-id",
        display_name="Co-owner",
    )
    account = accounts.create_account(
        name="Sexta com os amigos",
        owner_user_id=lost_owner.id,
    )
    [invitation] = accounts.invite_members(
        account.id,
        inviter_user_id=lost_owner.id,
        invited_user_ids=[co_owner.id],
    )
    co_owner_membership = accounts.accept_invitation(
        account.id,
        invitation.id,
        invited_user_id=co_owner.id,
    )
    accounts.assign_predefined_role(
        account.id,
        actor_user_id=lost_owner.id,
        membership_id=co_owner_membership.id,
        role=PredefinedRole.OWNER,
    )

    accounts.recover_owner_discord_identity_by_co_owner(
        account.id,
        actor_owner_user_id=co_owner.id,
        lost_owner_user_id=lost_owner.id,
        new_discord_user_id="replacement-discord-id",
        confirmation=SensitiveActionConfirmation(
            actor_user_id=co_owner.id,
            reauthenticated_at=now,
            confirmed_resource_name=account.name,
        ),
    )

    recovered = accounts.sign_in_with_discord(
        discord_user_id="replacement-discord-id",
        display_name="Recovered Owner",
    )
    assert recovered.id == lost_owner.id
    assert accounts.owner_recovery_ready(account.id)
    assert notifier.notifications[-1] == (
        frozenset({lost_owner.id, co_owner.id}),
        ActivityAction.OWNER_RECOVERED,
        lost_owner.id,
    )
