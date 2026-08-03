from .model import (
    Account,
    DiscordGuildAlreadyLinkedError,
    IdentityProvider,
    LinkedIdentity,
    Membership,
    User,
)
from .repository import AccountSnapshot


class InMemoryAccountRepository:
    """Transactional test adapter for the Accounts repository contract."""

    def __init__(self) -> None:
        self._snapshots: dict[str, AccountSnapshot] = {}
        self._users: dict[str, User] = {}
        self._identities: dict[tuple[IdentityProvider, str], LinkedIdentity] = {}

    def create(self, account: Account, owner: Membership) -> None:
        if (
            account.discord_guild_id is not None
            and self.find_by_discord_guild(account.discord_guild_id) is not None
        ):
            raise DiscordGuildAlreadyLinkedError(
                "the Discord Guild is already linked to a GameWake Account"
            )
        self._snapshots[account.id] = AccountSnapshot(
            account=account,
            memberships=(owner,),
            invitations=(),
            custom_roles=(),
            activity_events=(),
            version=1,
        )

    def get(self, account_id: str) -> AccountSnapshot:
        return self._snapshots[account_id]

    def find_by_discord_guild(self, discord_guild_id: str) -> AccountSnapshot | None:
        return next(
            (
                snapshot
                for snapshot in self._snapshots.values()
                if snapshot.account.discord_guild_id == discord_guild_id
            ),
            None,
        )

    def list_for_user(self, user_id: str) -> tuple[AccountSnapshot, ...]:
        return tuple(
            snapshot
            for snapshot in self._snapshots.values()
            if any(membership.user_id == user_id for membership in snapshot.memberships)
        )

    def save(self, snapshot: AccountSnapshot, expected_version: int) -> None:
        current = self._snapshots[snapshot.account.id]
        if current.version != expected_version:
            raise RuntimeError("account was changed concurrently")
        if snapshot.account.discord_guild_id is not None:
            linked = self.find_by_discord_guild(snapshot.account.discord_guild_id)
            if linked is not None and linked.account.id != snapshot.account.id:
                raise DiscordGuildAlreadyLinkedError(
                    "the Discord Guild is already linked to a GameWake Account"
                )
        self._snapshots[snapshot.account.id] = AccountSnapshot(
            account=snapshot.account,
            memberships=snapshot.memberships,
            invitations=snapshot.invitations,
            custom_roles=snapshot.custom_roles,
            activity_events=snapshot.activity_events,
            version=expected_version + 1,
        )

    def find_user_by_identity(
        self,
        provider: IdentityProvider,
        provider_user_id: str,
    ) -> User | None:
        identity = self._identities.get((provider, provider_user_id))
        return self._users.get(identity.user_id) if identity is not None else None

    def create_user(self, user: User, identity: LinkedIdentity) -> None:
        self._users[user.id] = user
        self._identities[(identity.provider, identity.provider_user_id)] = identity

    def replace_identity(self, identity: LinkedIdentity) -> None:
        self._identities = {
            key: current
            for key, current in self._identities.items()
            if not (current.user_id == identity.user_id and current.provider is identity.provider)
        }
        self._identities[(identity.provider, identity.provider_user_id)] = identity

    def list_linked_identities(self, user_id: str) -> tuple[LinkedIdentity, ...]:
        return tuple(
            identity for identity in self._identities.values() if identity.user_id == user_id
        )
