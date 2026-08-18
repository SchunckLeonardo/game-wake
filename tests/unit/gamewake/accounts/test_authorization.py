from datetime import UTC, datetime

import pytest

from gamewake.accounts import (
    Accounts,
    InMemoryAccountRepository,
    LastOwnerRemovalError,
    Permission,
    PermissionDeniedError,
    PredefinedRole,
    SensitiveActionConfirmation,
    SensitiveActionConfirmationError,
)

PLAYER_PERMISSIONS = {
    Permission.VIEW_WORLD,
    Permission.WAKE_WORLD,
    Permission.SLEEP_EMPTY_WORLD,
}
MANAGER_PERMISSIONS = PLAYER_PERMISSIONS | {
    Permission.EDIT_WORLD,
    Permission.RESTART_WORLD,
    Permission.UPDATE_WORLD,
    Permission.FORCE_SLEEP_WORLD,
    Permission.VIEW_LOGS,
    Permission.CREATE_BACKUP,
    Permission.RESTORE_BACKUP,
}
OWNER_PERMISSIONS = set(Permission)


def confirmed(account, actor_user_id: str) -> SensitiveActionConfirmation:
    return SensitiveActionConfirmation(
        actor_user_id=actor_user_id,
        reauthenticated_at=datetime.now(UTC),
        confirmed_resource_name=account.name,
    )


@pytest.mark.parametrize(
    ("role", "expected_permissions"),
    [
        (PredefinedRole.PLAYER, PLAYER_PERMISSIONS),
        (PredefinedRole.MANAGER, MANAGER_PERMISSIONS),
        (PredefinedRole.OWNER, OWNER_PERMISSIONS),
    ],
)
def test_predefined_roles_have_the_documented_permission_matrix(
    role: PredefinedRole,
    expected_permissions: set[Permission],
):
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="user-owner")
    user_id = "user-owner"

    if role is not PredefinedRole.OWNER:
        user_id = "friend"
        [invitation] = accounts.invite_members(
            account.id,
            inviter_user_id="user-owner",
            invited_user_ids=[user_id],
        )
        membership = accounts.accept_invitation(
            account.id,
            invitation.id,
            invited_user_id=user_id,
        )
        if role is PredefinedRole.MANAGER:
            accounts.assign_predefined_role(
                account.id,
                actor_user_id="user-owner",
                membership_id=membership.id,
                role=role,
                confirmation=confirmed(account, "user-owner"),
            )

    actual_permissions = {
        permission
        for permission in Permission
        if accounts.authorize(account.id, user_id=user_id, permission=permission)
    }

    assert actual_permissions == expected_permissions


def test_a_world_scoped_manager_cannot_manage_another_world():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="user-owner")
    [invitation] = accounts.invite_members(
        account.id,
        inviter_user_id="user-owner",
        invited_user_ids=["friend"],
    )
    membership = accounts.accept_invitation(
        account.id,
        invitation.id,
        invited_user_id="friend",
    )
    accounts.assign_predefined_role(
        account.id,
        actor_user_id="user-owner",
        membership_id=membership.id,
        role=PredefinedRole.MANAGER,
        world_id="world-palworld",
        confirmation=confirmed(account, "user-owner"),
    )

    assert accounts.authorize(
        account.id,
        user_id="friend",
        permission=Permission.EDIT_WORLD,
        world_id="world-palworld",
    )
    assert not accounts.authorize(
        account.id,
        user_id="friend",
        permission=Permission.EDIT_WORLD,
        world_id="world-minecraft",
    )
    assert not accounts.authorize(
        account.id,
        user_id="friend",
        permission=Permission.MANAGE_ROLES,
    )


def test_custom_roles_add_only_the_selected_permissions_inside_their_scope():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="user-owner")
    [invitation] = accounts.invite_members(
        account.id,
        inviter_user_id="user-owner",
        invited_user_ids=["friend"],
    )
    membership = accounts.accept_invitation(
        account.id,
        invitation.id,
        invited_user_id="friend",
    )
    backup_operator = accounts.create_custom_role(
        account.id,
        actor_user_id="user-owner",
        name="Operador de backup",
        permissions={Permission.VIEW_LOGS, Permission.CREATE_BACKUP},
        confirmation=confirmed(account, "user-owner"),
    )
    accounts.assign_custom_role(
        account.id,
        actor_user_id="user-owner",
        membership_id=membership.id,
        custom_role_id=backup_operator.id,
        world_id="world-palworld",
        confirmation=confirmed(account, "user-owner"),
    )

    assert accounts.authorize(
        account.id,
        user_id="friend",
        permission=Permission.CREATE_BACKUP,
        world_id="world-palworld",
    )
    assert not accounts.authorize(
        account.id,
        user_id="friend",
        permission=Permission.CREATE_BACKUP,
        world_id="world-minecraft",
    )
    assert not accounts.authorize(
        account.id,
        user_id="friend",
        permission=Permission.RESTORE_BACKUP,
        world_id="world-palworld",
    )


def test_an_account_scoped_custom_role_can_grant_invitation_management():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="user-owner")
    [invitation] = accounts.invite_members(
        account.id,
        inviter_user_id="user-owner",
        invited_user_ids=["organizer"],
    )
    organizer = accounts.accept_invitation(
        account.id,
        invitation.id,
        invited_user_id="organizer",
    )
    role = accounts.create_custom_role(
        account.id,
        actor_user_id="user-owner",
        name="Organizador",
        permissions={Permission.MANAGE_MEMBERSHIPS},
        confirmation=confirmed(account, "user-owner"),
    )
    accounts.assign_custom_role(
        account.id,
        actor_user_id="user-owner",
        membership_id=organizer.id,
        custom_role_id=role.id,
        confirmation=confirmed(account, "user-owner"),
    )

    [created] = accounts.invite_members(
        account.id,
        inviter_user_id="organizer",
        invited_user_ids=["new-friend"],
    )

    assert created.invited_user_id == "new-friend"


def test_role_assignment_rejects_missing_step_up_confirmation():
    accounts = Accounts(InMemoryAccountRepository())
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
        accounts.assign_predefined_role(
            account.id,
            actor_user_id="owner",
            membership_id=membership.id,
            role=PredefinedRole.MANAGER,
        )


def test_the_last_owner_assignment_cannot_be_removed():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    [owner] = accounts.list_memberships(account.id, viewer_user_id="owner")
    [owner_assignment] = owner.assignments

    with pytest.raises(LastOwnerRemovalError):
        accounts.remove_role_assignment(
            account.id,
            actor_user_id="owner",
            membership_id=owner.id,
            role_assignment_id=owner_assignment.id,
            confirmation=confirmed(account, "owner"),
        )


def test_assigning_a_role_replaces_the_previous_role_and_removing_it_revokes_all_access():
    accounts = Accounts(InMemoryAccountRepository())
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
    membership = accounts.assign_predefined_role(
        account.id,
        actor_user_id="owner",
        membership_id=membership.id,
        role=PredefinedRole.MANAGER,
        world_id="world-palworld",
        confirmation=confirmed(account, "owner"),
    )

    [manager_assignment] = membership.assignments
    assert manager_assignment.predefined_role is PredefinedRole.MANAGER
    assert membership.roles == frozenset({PredefinedRole.MANAGER})

    accounts.remove_role_assignment(
        account.id,
        actor_user_id="owner",
        membership_id=membership.id,
        role_assignment_id=manager_assignment.id,
        confirmation=confirmed(account, "owner"),
    )

    [updated] = [
        item
        for item in accounts.list_memberships(account.id, viewer_user_id="owner")
        if item.id == membership.id
    ]
    assert updated.assignments == ()
    assert not accounts.authorize(
        account.id,
        user_id="friend",
        permission=Permission.VIEW_WORLD,
        world_id="world-palworld",
    )


def test_the_last_owner_role_cannot_be_replaced_with_a_less_privileged_role():
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    [owner] = accounts.list_memberships(account.id, viewer_user_id="owner")

    with pytest.raises(LastOwnerRemovalError):
        accounts.assign_predefined_role(
            account.id,
            actor_user_id="owner",
            membership_id=owner.id,
            role=PredefinedRole.PLAYER,
            confirmation=confirmed(account, "owner"),
        )


def test_a_user_from_another_account_cannot_list_memberships():
    accounts = Accounts(InMemoryAccountRepository())
    first = accounts.create_account(name="Primeiro grupo", owner_user_id="first-owner")
    accounts.create_account(name="Segundo grupo", owner_user_id="second-owner")

    with pytest.raises(PermissionDeniedError):
        accounts.list_memberships(first.id, viewer_user_id="second-owner")
