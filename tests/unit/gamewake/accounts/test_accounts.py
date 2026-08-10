from datetime import UTC, datetime, timedelta

import pytest

from gamewake.accounts import (
    Accounts,
    InMemoryAccountRepository,
    InvitationStatus,
    LastOwnerRemovalError,
    PermissionDeniedError,
    PredefinedRole,
    SensitiveActionConfirmation,
)


def test_creating_an_account_makes_the_creator_its_owner():
    accounts = Accounts(InMemoryAccountRepository())

    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="user-owner")

    memberships = accounts.list_memberships(account.id, viewer_user_id="user-owner")
    assert [(membership.user_id, membership.roles) for membership in memberships] == [
        ("user-owner", frozenset({PredefinedRole.OWNER}))
    ]


def test_the_last_owner_cannot_be_removed_from_an_account():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="user-owner")
    [owner] = accounts.list_memberships(account.id, viewer_user_id="user-owner")
    now = datetime.now(UTC)

    with pytest.raises(LastOwnerRemovalError):
        accounts.remove_membership(
            account.id,
            owner.id,
            actor_user_id="user-owner",
            confirmation=SensitiveActionConfirmation(
                actor_user_id="user-owner",
                reauthenticated_at=now,
                confirmed_resource_name=account.name,
            ),
        )

    assert accounts.list_memberships(account.id, viewer_user_id="user-owner") == [owner]


def test_batch_invitations_stay_independent_and_require_explicit_acceptance():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="user-owner")

    invitations = accounts.invite_members(
        account.id,
        inviter_user_id="user-owner",
        invited_user_ids=["friend-one", "friend-two", "friend-three"],
    )

    assert len({invitation.id for invitation in invitations}) == 3
    assert [invitation.invited_user_id for invitation in invitations] == [
        "friend-one",
        "friend-two",
        "friend-three",
    ]
    assert all(invitation.status is InvitationStatus.PENDING for invitation in invitations)
    assert [
        membership.user_id
        for membership in accounts.list_memberships(
            account.id,
            viewer_user_id="user-owner",
        )
    ] == ["user-owner"]

    membership = accounts.accept_invitation(
        account.id,
        invitations[1].id,
        invited_user_id="friend-two",
    )

    assert membership.user_id == "friend-two"
    assert membership.roles == frozenset({PredefinedRole.PLAYER})
    assert [
        invitation.status
        for invitation in accounts.list_invitations(
            account.id,
            viewer_user_id="user-owner",
        )
    ] == [
        InvitationStatus.PENDING,
        InvitationStatus.ACCEPTED,
        InvitationStatus.PENDING,
    ]


def test_a_player_cannot_invite_members():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="user-owner")
    [invitation] = accounts.invite_members(
        account.id,
        inviter_user_id="user-owner",
        invited_user_ids=["friend-one"],
    )
    accounts.accept_invitation(
        account.id,
        invitation.id,
        invited_user_id="friend-one",
    )

    with pytest.raises(PermissionDeniedError):
        accounts.invite_members(
            account.id,
            inviter_user_id="friend-one",
            invited_user_ids=["friend-two"],
        )

    assert [
        item.invited_user_id
        for item in accounts.list_invitations(
            account.id,
            viewer_user_id="user-owner",
        )
    ] == ["friend-one"]


def test_only_an_owner_can_rebind_the_discord_notification_channel():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(
        name="Sexta com os amigos",
        owner_user_id="user-owner",
        discord_guild_id="guild-1",
        discord_channel_id="old-channel",
    )
    [invitation] = accounts.invite_members(
        account.id,
        inviter_user_id="user-owner",
        invited_user_ids=["friend-one"],
    )
    accounts.accept_invitation(
        account.id,
        invitation.id,
        invited_user_id="friend-one",
    )

    with pytest.raises(PermissionDeniedError):
        accounts.configure_discord_notification_channel(
            account.id,
            actor_user_id="friend-one",
            channel_id="untrusted-channel",
        )

    updated = accounts.configure_discord_notification_channel(
        account.id,
        actor_user_id="user-owner",
        channel_id="new-channel",
    )
    assert updated.discord_channel_id == "new-channel"


def test_only_the_invited_user_can_accept_an_invitation():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="user-owner")
    [invitation] = accounts.invite_members(
        account.id,
        inviter_user_id="user-owner",
        invited_user_ids=["friend-one"],
    )

    with pytest.raises(PermissionDeniedError):
        accounts.accept_invitation(
            account.id,
            invitation.id,
            invited_user_id="someone-else",
        )

    assert accounts.list_invitations(
        account.id,
        viewer_user_id="user-owner",
    ) == [invitation]
    assert [
        membership.user_id
        for membership in accounts.list_memberships(
            account.id,
            viewer_user_id="user-owner",
        )
    ] == ["user-owner"]


def test_shareable_invitation_links_grant_play_or_console_access_once():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    accounts = Accounts(InMemoryAccountRepository(), clock=lambda: now)
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")

    play = accounts.create_invitation_link(
        account.id,
        inviter_user_id="owner",
        role=PredefinedRole.PLAYER,
    )
    manage = accounts.create_invitation_link(
        account.id,
        inviter_user_id="owner",
        role=PredefinedRole.MANAGER,
    )

    player = accounts.accept_invitation(
        account.id,
        play.id,
        invited_user_id="friend-player",
    )
    moderator = accounts.accept_invitation(
        account.id,
        manage.id,
        invited_user_id="friend-moderator",
    )

    assert play.invited_user_id is None
    assert play.expires_at == now + timedelta(days=7)
    assert play.access.value == "play"
    assert player.roles == frozenset({PredefinedRole.PLAYER})
    assert manage.access.value == "console"
    assert moderator.roles == frozenset({PredefinedRole.MANAGER})
    with pytest.raises(ValueError, match="no longer pending"):
        accounts.accept_invitation(
            account.id,
            play.id,
            invited_user_id="someone-else",
        )


def test_expired_shareable_invitation_link_cannot_be_accepted():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    current = [now]
    accounts = Accounts(InMemoryAccountRepository(), clock=lambda: current[0])
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    invitation = accounts.create_invitation_link(
        account.id,
        inviter_user_id="owner",
        role=PredefinedRole.PLAYER,
        expires_in=timedelta(hours=1),
    )
    current[0] = now + timedelta(hours=2)

    with pytest.raises(ValueError, match="expired"):
        accounts.accept_invitation(
            account.id,
            invitation.id,
            invited_user_id="friend",
        )
