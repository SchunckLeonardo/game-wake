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
