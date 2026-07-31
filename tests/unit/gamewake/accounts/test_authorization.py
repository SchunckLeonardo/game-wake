import pytest

from gamewake.accounts import (
    Accounts,
    InMemoryAccountRepository,
    Permission,
    PredefinedRole,
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
    )
    accounts.assign_custom_role(
        account.id,
        actor_user_id="user-owner",
        membership_id=membership.id,
        custom_role_id=backup_operator.id,
        world_id="world-palworld",
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
    )
    accounts.assign_custom_role(
        account.id,
        actor_user_id="user-owner",
        membership_id=organizer.id,
        custom_role_id=role.id,
    )

    [created] = accounts.invite_members(
        account.id,
        inviter_user_id="organizer",
        invited_user_ids=["new-friend"],
    )

    assert created.invited_user_id == "new-friend"
