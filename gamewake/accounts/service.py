from uuid import uuid4

from .model import Account, LastOwnerRemovalError, Membership, PredefinedRole
from .repository import AccountRepository, AccountSnapshot


class Accounts:
    def __init__(self, repository: AccountRepository) -> None:
        self._repository = repository

    def create_account(self, *, name: str, owner_user_id: str) -> Account:
        account = Account(id=str(uuid4()), name=name)
        owner = Membership(
            id=str(uuid4()),
            account_id=account.id,
            user_id=owner_user_id,
            roles=frozenset({PredefinedRole.OWNER}),
        )
        self._repository.create(account, owner)
        return account

    def list_memberships(self, account_id: str) -> list[Membership]:
        return list(self._repository.get(account_id).memberships)

    def remove_membership(self, account_id: str, membership_id: str) -> None:
        snapshot = self._repository.get(account_id)
        membership = next(
            membership
            for membership in snapshot.memberships
            if membership.id == membership_id
        )
        if PredefinedRole.OWNER in membership.roles and self._owner_count(snapshot) == 1:
            raise LastOwnerRemovalError("an account must retain at least one Owner")

        remaining = tuple(
            membership
            for membership in snapshot.memberships
            if membership.id != membership_id
        )
        self._repository.save(
            AccountSnapshot(snapshot.account, remaining, snapshot.version),
            expected_version=snapshot.version,
        )

    @staticmethod
    def _owner_count(snapshot: AccountSnapshot) -> int:
        return sum(
            PredefinedRole.OWNER in membership.roles
            for membership in snapshot.memberships
        )
