from dataclasses import dataclass
from enum import StrEnum


class PredefinedRole(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    PLAYER = "player"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"


class LastOwnerRemovalError(ValueError):
    """Raised when a mutation would leave an account without an Owner."""


class PermissionDeniedError(PermissionError):
    """Raised when a Membership does not grant the requested action."""


@dataclass(frozen=True)
class Account:
    id: str
    name: str


@dataclass(frozen=True)
class Membership:
    id: str
    account_id: str
    user_id: str
    roles: frozenset[PredefinedRole]


@dataclass(frozen=True)
class Invitation:
    id: str
    account_id: str
    inviter_user_id: str
    invited_user_id: str
    status: InvitationStatus
