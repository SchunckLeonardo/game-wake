from dataclasses import dataclass
from typing import Protocol

from .model import Account, Membership


@dataclass(frozen=True)
class AccountSnapshot:
    account: Account
    memberships: tuple[Membership, ...]
    version: int


class AccountRepository(Protocol):
    def create(self, account: Account, owner: Membership) -> None: ...

    def get(self, account_id: str) -> AccountSnapshot: ...

    def save(self, snapshot: AccountSnapshot, expected_version: int) -> None: ...
