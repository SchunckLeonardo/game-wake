from .model import Account, Membership
from .repository import AccountSnapshot


class InMemoryAccountRepository:
    """Transactional test adapter for the Accounts repository contract."""

    def __init__(self) -> None:
        self._snapshots: dict[str, AccountSnapshot] = {}

    def create(self, account: Account, owner: Membership) -> None:
        self._snapshots[account.id] = AccountSnapshot(
            account=account,
            memberships=(owner,),
            invitations=(),
            custom_roles=(),
            version=1,
        )

    def get(self, account_id: str) -> AccountSnapshot:
        return self._snapshots[account_id]

    def save(self, snapshot: AccountSnapshot, expected_version: int) -> None:
        current = self._snapshots[snapshot.account.id]
        if current.version != expected_version:
            raise RuntimeError("account was changed concurrently")
        self._snapshots[snapshot.account.id] = AccountSnapshot(
            account=snapshot.account,
            memberships=snapshot.memberships,
            invitations=snapshot.invitations,
            custom_roles=snapshot.custom_roles,
            version=expected_version + 1,
        )
