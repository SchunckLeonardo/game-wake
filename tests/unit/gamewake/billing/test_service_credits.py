from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gamewake.billing import (
    Billing,
    InMemoryBillingRepository,
    LedgerEntryType,
    ReservationStatus,
)


def test_failed_wake_gets_one_full_wake_guarantee_credit():
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    billing = Billing(InMemoryBillingRepository(), clock=lambda: now)
    billing.credit_wallet(
        "account-1",
        amount=Decimal("20.00"),
        reference="initial-credit",
        idempotency_key="credit-1",
    )
    quote = billing.create_session_quote(
        "account-1",
        world_id="world-1",
        runtime_profile_id="palworld-small",
        hourly_rate=Decimal("3.60"),
        idempotency_key="quote-1",
    )
    reservation = billing.reserve_for_wake(
        "account-1",
        quote.id,
        idempotency_key="reservation-1",
    )
    usage = billing.capture_runtime_usage(
        "account-1",
        quote_id=quote.id,
        reservation_id=reservation.id,
        runtime_started_at=now,
        runtime_released_at=now + timedelta(seconds=90),
        idempotency_key="usage-1",
    )

    credit = billing.apply_wake_guarantee(
        "account-1",
        usage.id,
        reached_online=False,
        idempotency_key="wake-guarantee-1",
    )
    repeated = billing.apply_wake_guarantee(
        "account-1",
        usage.id,
        reached_online=False,
        idempotency_key="wake-guarantee-1",
    )

    assert repeated == credit
    assert credit.entry_type is LedgerEntryType.WAKE_GUARANTEE
    assert credit.amount == usage.amount
    assert billing.get_wallet("account-1").balance == Decimal("20.00")


def test_unused_usage_reservation_is_released_idempotently():
    billing = Billing(InMemoryBillingRepository())
    billing.credit_wallet(
        "account-1",
        amount=Decimal("20.00"),
        reference="initial-credit",
        idempotency_key="credit-1",
    )
    reservation = billing.reserve(
        "account-1",
        amount=Decimal("5.00"),
        purpose="wake:world-1",
        idempotency_key="reservation-1",
    )

    released = billing.release_reservation("account-1", reservation.id)
    repeated = billing.release_reservation("account-1", reservation.id)

    assert repeated == released
    assert released.status is ReservationStatus.RELEASED
    assert billing.get_wallet("account-1").available_balance == Decimal("20.00")


def test_three_minute_confirmed_outage_gets_one_availability_credit():
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    billing = Billing(InMemoryBillingRepository(), clock=lambda: now)
    billing.credit_wallet(
        "account-1",
        amount=Decimal("20.00"),
        reference="initial-credit",
        idempotency_key="credit-1",
    )
    quote = billing.create_session_quote(
        "account-1",
        world_id="world-1",
        runtime_profile_id="palworld-small",
        hourly_rate=Decimal("3.60"),
        idempotency_key="quote-1",
    )
    reservation = billing.reserve_for_wake(
        "account-1",
        quote.id,
        idempotency_key="reservation-1",
    )
    usage = billing.capture_runtime_usage(
        "account-1",
        quote_id=quote.id,
        reservation_id=reservation.id,
        runtime_started_at=now,
        runtime_released_at=now + timedelta(minutes=10),
        idempotency_key="usage-1",
    )

    credit = billing.apply_availability_credit(
        "account-1",
        usage.id,
        unavailable_at=now + timedelta(minutes=2),
        recovered_at=now + timedelta(minutes=5),
        idempotency_key="availability-1",
    )
    repeated = billing.apply_availability_credit(
        "account-1",
        usage.id,
        unavailable_at=now + timedelta(minutes=2),
        recovered_at=now + timedelta(minutes=5),
        idempotency_key="availability-1",
    )

    assert repeated == credit
    assert credit.entry_type is LedgerEntryType.AVAILABILITY_CREDIT
    assert credit.amount == Decimal("0.18")
    assert billing.get_wallet("account-1").balance == Decimal("19.58")
