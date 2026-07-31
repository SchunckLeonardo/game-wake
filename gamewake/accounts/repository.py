from dataclasses import dataclass
from typing import Protocol

from .model import Account, IdentityProvider, Invitation, LinkedIdentity, Membership, User
from .policy import CustomRole
from .security import ActivityEvent


@dataclass(frozen=True)
class AccountSnapshot:
    account: Account
    memberships: tuple[Membership, ...]
    invitations: tuple[Invitation, ...]
    custom_roles: tuple[CustomRole, ...]
    activity_events: tuple[ActivityEvent, ...]
    version: int


class AccountRepository(Protocol):
    def create(self, account: Account, owner: Membership) -> None: ...

    def get(self, account_id: str) -> AccountSnapshot: ...

    def find_by_discord_guild(self, discord_guild_id: str) -> AccountSnapshot | None: ...

    def save(self, snapshot: AccountSnapshot, expected_version: int) -> None: ...


class IdentityRepository(Protocol):
    def find_user_by_identity(
        self,
        provider: IdentityProvider,
        provider_user_id: str,
    ) -> User | None: ...

    def create_user(self, user: User, identity: LinkedIdentity) -> None: ...

    def replace_identity(self, identity: LinkedIdentity) -> None: ...

    def list_linked_identities(self, user_id: str) -> tuple[LinkedIdentity, ...]: ...
