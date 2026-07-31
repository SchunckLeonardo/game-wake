from typing import Protocol

from .model import WalletSnapshot


class BillingRepository(Protocol):
    def get(self, account_id: str) -> WalletSnapshot: ...

    def save(self, snapshot: WalletSnapshot, *, expected_version: int) -> None: ...
