from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from gamewake.billing import (
    Billing,
    InMemoryBillingRepository,
    InsufficientFundsError,
    LedgerEntryType,
    ReservationStatus,
)


def test_wallet_balance_is_derived_from_an_append_only_ledger():
    billing = Billing(InMemoryBillingRepository())

    credit = billing.credit_wallet(
        "account-1",
        amount=Decimal("100.00"),
        reference="payment-1",
        idempotency_key="payment-event-1",
    )
    repeated = billing.credit_wallet(
        "account-1",
        amount=Decimal("100.00"),
        reference="payment-1",
        idempotency_key="payment-event-1",
    )
    reservation = billing.reserve(
        "account-1",
        amount=Decimal("30.00"),
        purpose="wake:world-1",
        idempotency_key="wake-1",
    )
    charge = billing.capture_reservation(
        "account-1",
        reservation.id,
        amount=Decimal("25.00"),
        idempotency_key="runtime-charge-1",
    )

    wallet = billing.get_wallet("account-1")
    assert repeated.id == credit.id
    assert wallet.balance == Decimal("75.00")
    assert wallet.available_balance == Decimal("75.00")
    assert reservation.status is ReservationStatus.ACTIVE
    assert charge.entry_type is LedgerEntryType.RUNTIME_CHARGE
    assert [entry.amount for entry in wallet.statement] == [
        Decimal("100.00"),
        Decimal("-25.00"),
    ]


def test_concurrent_reservations_never_make_available_balance_negative():
    billing = Billing(InMemoryBillingRepository())
    billing.credit_wallet(
        "account-1",
        amount=Decimal("100.00"),
        reference="payment-1",
        idempotency_key="payment-event-1",
    )

    def reserve(number):
        try:
            return billing.reserve(
                "account-1",
                amount=Decimal("30.00"),
                purpose=f"wake:world-{number}",
                idempotency_key=f"wake-{number}",
            )
        except InsufficientFundsError:
            return None

    with ThreadPoolExecutor(max_workers=10) as executor:
        reservations = list(executor.map(reserve, range(10)))

    successful = [reservation for reservation in reservations if reservation is not None]
    wallet = billing.get_wallet("account-1")
    assert len(successful) == 3
    assert wallet.balance == Decimal("100.00")
    assert wallet.available_balance == Decimal("10.00")
    assert wallet.available_balance >= Decimal("0.00")
