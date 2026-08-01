from datetime import UTC, datetime

import pytest

from gamewake.accounts import (
    Accounts,
    ActivityAction,
    InMemoryAccountRepository,
    InMemorySecurityNotifier,
    Permission,
    SensitiveActionConfirmation,
    SensitiveActionConfirmationError,
)


def test_revoking_membership_is_confirmed_immediate_audited_and_notified():
    now = datetime(2026, 7, 31, 18, 30, tzinfo=UTC)
    notifier = InMemorySecurityNotifier()
    accounts = Accounts(
        InMemoryAccountRepository(),
        clock=lambda: now,
        security_notifier=notifier,
    )
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    [invitation] = accounts.invite_members(
        account.id,
        inviter_user_id="owner",
        invited_user_ids=["friend"],
    )
    membership = accounts.accept_invitation(
        account.id,
        invitation.id,
        invited_user_id="friend",
    )

    accounts.remove_membership(
        account.id,
        membership.id,
        actor_user_id="owner",
        confirmation=SensitiveActionConfirmation(
            actor_user_id="owner",
            reauthenticated_at=now,
            confirmed_resource_name="Sexta com os amigos",
        ),
    )

    assert not accounts.authorize(
        account.id,
        user_id="friend",
        permission=Permission.VIEW_WORLD,
    )
    [event] = accounts.list_activity_events(account.id, viewer_user_id="owner")
    assert event.action is ActivityAction.MEMBERSHIP_REVOKED
    assert event.subject_id == membership.id
    assert "reauth" not in repr(event).lower()
    assert notifier.notifications == [
        (frozenset({"owner"}), ActivityAction.MEMBERSHIP_REVOKED, membership.id)
    ]


@pytest.mark.parametrize(
    "confirmation",
    [
        SensitiveActionConfirmation(
            actor_user_id="owner",
            reauthenticated_at=datetime(2026, 7, 31, 18, 20, tzinfo=UTC),
            confirmed_resource_name="Sexta com os amigos",
        ),
        SensitiveActionConfirmation(
            actor_user_id="owner",
            reauthenticated_at=datetime(2026, 7, 31, 18, 30, tzinfo=UTC),
            confirmed_resource_name="nome errado",
        ),
    ],
)
def test_revocation_rejects_stale_or_wrong_resource_confirmation(confirmation):
    now = datetime(2026, 7, 31, 18, 30, tzinfo=UTC)
    accounts = Accounts(InMemoryAccountRepository(), clock=lambda: now)
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    [invitation] = accounts.invite_members(
        account.id,
        inviter_user_id="owner",
        invited_user_ids=["friend"],
    )
    membership = accounts.accept_invitation(
        account.id,
        invitation.id,
        invited_user_id="friend",
    )

    with pytest.raises(SensitiveActionConfirmationError):
        accounts.remove_membership(
            account.id,
            membership.id,
            actor_user_id="owner",
            confirmation=confirmation,
        )

    assert accounts.authorize(
        account.id,
        user_id="friend",
        permission=Permission.VIEW_WORLD,
    )
