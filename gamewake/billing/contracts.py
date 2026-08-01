from typing import Protocol

from .model import (
    ContributionCheckoutRequest,
    PaymentCheckout,
    WalletContribution,
    WalletSnapshot,
)


class BillingRepository(Protocol):
    def get(self, account_id: str) -> WalletSnapshot: ...

    def save(self, snapshot: WalletSnapshot, *, expected_version: int) -> None: ...

    def find_contribution(self, contribution_id: str) -> WalletContribution | None: ...


class PaymentProvider(Protocol):
    def create_checkout(self, request: ContributionCheckoutRequest) -> PaymentCheckout: ...

    def refund_checkout(self, checkout_id: str, *, reason: str) -> str: ...

    def find_checkout(self, external_id: str) -> PaymentCheckout | None: ...
