from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class PredefinedRole(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    PLAYER = "player"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"


class InvitationAccess(StrEnum):
    PLAY = "play"
    CONSOLE = "console"


class IdentityProvider(StrEnum):
    DISCORD = "discord"


class LastOwnerRemovalError(ValueError):
    """Raised when a mutation would leave an account without an Owner."""


class PermissionDeniedError(PermissionError):
    """Raised when a Membership does not grant the requested action."""


class DiscordGuildAlreadyLinkedError(ValueError):
    """Raised when a Discord Guild is already linked to another account."""


@dataclass(frozen=True)
class User:
    id: str
    display_name: str


@dataclass(frozen=True)
class LinkedIdentity:
    id: str
    user_id: str
    provider: IdentityProvider
    provider_user_id: str


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    discord_guild_id: str | None = None
    discord_channel_id: str | None = None


@dataclass(frozen=True)
class ResourceScope:
    account_id: str
    world_id: str | None = None

    def applies_to(self, world_id: str | None) -> bool:
        if self.world_id is None:
            return True
        return world_id is not None and self.world_id == world_id


@dataclass(frozen=True)
class RoleAssignment:
    id: str
    scope: ResourceScope
    predefined_role: PredefinedRole | None = None
    custom_role_id: str | None = None

    def __post_init__(self) -> None:
        if (self.predefined_role is None) == (self.custom_role_id is None):
            raise ValueError("a Role Assignment must reference exactly one Role")


@dataclass(frozen=True)
class Membership:
    id: str
    account_id: str
    user_id: str
    assignments: tuple[RoleAssignment, ...]

    @property
    def roles(self) -> frozenset[PredefinedRole]:
        return frozenset(
            assignment.predefined_role
            for assignment in self.assignments
            if assignment.predefined_role is not None
        )


@dataclass(frozen=True)
class Invitation:
    id: str
    account_id: str
    inviter_user_id: str
    invited_user_id: str | None
    status: InvitationStatus
    access: InvitationAccess = InvitationAccess.PLAY
    predefined_role: PredefinedRole | None = PredefinedRole.PLAYER
    custom_role_id: str | None = None
    world_id: str | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if (self.predefined_role is None) == (self.custom_role_id is None):
            raise ValueError("an Invitation must grant exactly one Role")
        if self.access is InvitationAccess.PLAY and (
            self.predefined_role is not PredefinedRole.PLAYER or self.custom_role_id is not None
        ):
            raise ValueError("play Invitations must grant the Player Role")
