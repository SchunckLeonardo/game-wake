from decimal import Decimal

from gamewake.billing import Billing, InMemoryBillingRepository, LedgerEntryType


def test_monthly_storage_overage_is_charged_once_from_exact_byte_usage():
    billing = Billing(InMemoryBillingRepository())
    billing.credit_wallet(
        "account-1",
        amount=Decimal("20.00"),
        reference="initial-credit",
        idempotency_key="credit-1",
    )

    charge = billing.charge_monthly_storage(
        "account-1",
        excess_bytes=1_610_612_736,
        rate_per_gib_month=Decimal("2.00"),
        billing_month="2026-08",
        idempotency_key="storage:2026-08",
    )
    repeated = billing.charge_monthly_storage(
        "account-1",
        excess_bytes=1_610_612_736,
        rate_per_gib_month=Decimal("2.00"),
        billing_month="2026-08",
        idempotency_key="storage:2026-08",
    )

    assert repeated == charge
    assert charge.entry_type is LedgerEntryType.STORAGE_CHARGE
    assert charge.amount == Decimal("-3.00")
    assert charge.reference == "storage:2026-08"
    assert billing.get_wallet("account-1").balance == Decimal("17.00")
