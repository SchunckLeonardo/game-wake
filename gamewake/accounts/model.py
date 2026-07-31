from dataclasses import dataclass
from enum import StrEnum


class PredefinedRole(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    PLAYER = "player"


class LastOwnerRemovalError(ValueError):
    """Raised when a mutation would leave an account without an Owner."""


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
