from dataclasses import dataclass
from enum import StrEnum

from .model import PredefinedRole, RoleAssignment


class Permission(StrEnum):
    CREATE_WORLD = "world:create"
    VIEW_WORLD = "world:view"
    WAKE_WORLD = "world:wake"
    SLEEP_EMPTY_WORLD = "world:sleep_when_empty"
    EDIT_WORLD = "world:edit"
    RESTART_WORLD = "world:restart"
    UPDATE_WORLD = "world:update"
    FORCE_SLEEP_WORLD = "world:force_sleep"
    VIEW_LOGS = "world:logs:view"
    CREATE_BACKUP = "backup:create"
    RESTORE_BACKUP = "backup:restore"
    MANAGE_MEMBERSHIPS = "membership:manage"
    MANAGE_ROLES = "role:manage"
    MANAGE_INTEGRATIONS = "integration:manage"
    MANAGE_WALLET = "wallet:manage"
    MANAGE_WORLD_BUDGET = "world:budget:manage"
    MIGRATE_WORLD = "world:migrate"
    EXPORT_WORLD = "world:export"
    DELETE_WORLD = "world:delete"
    TRANSFER_OWNERSHIP = "account:ownership:transfer"
    DELETE_ACCOUNT = "account:delete"


@dataclass(frozen=True)
class CustomRole:
    id: str
    account_id: str
    name: str
    permissions: frozenset[Permission]


_PLAYER_PERMISSIONS = frozenset(
    {
        Permission.VIEW_WORLD,
        Permission.WAKE_WORLD,
        Permission.SLEEP_EMPTY_WORLD,
    }
)

_MANAGER_PERMISSIONS = _PLAYER_PERMISSIONS | {
    Permission.EDIT_WORLD,
    Permission.RESTART_WORLD,
    Permission.UPDATE_WORLD,
    Permission.FORCE_SLEEP_WORLD,
    Permission.VIEW_LOGS,
    Permission.CREATE_BACKUP,
    Permission.RESTORE_BACKUP,
}

PREDEFINED_ROLE_PERMISSIONS = {
    PredefinedRole.PLAYER: _PLAYER_PERMISSIONS,
    PredefinedRole.MANAGER: _MANAGER_PERMISSIONS,
    PredefinedRole.OWNER: frozenset(Permission),
}


def permissions_for(
    assignments: tuple[RoleAssignment, ...],
    *,
    custom_roles: tuple[CustomRole, ...],
    world_id: str | None,
) -> frozenset[Permission]:
    custom_permissions = {role.id: role.permissions for role in custom_roles}
    return frozenset(
        permission
        for assignment in assignments
        if assignment.scope.applies_to(world_id)
        for permission in (
            PREDEFINED_ROLE_PERMISSIONS[assignment.predefined_role]
            if assignment.predefined_role is not None
            else custom_permissions[assignment.custom_role_id]
        )
    )
