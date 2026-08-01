from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gamewake.billing import Billing, InMemoryBillingRepository


def test_session_quote_locks_rate_and_runtime_usage_rounds_once_per_second():
    now = datetime(2026, 7, 31, 21, 0, tzinfo=UTC)
    billing = Billing(InMemoryBillingRepository(), clock=lambda: now)
    billing.credit_wallet(
        "account-1",
        amount=Decimal("20.00"),
        reference="payment-1",
        idempotency_key="payment-event-1",
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
        idempotency_key="wake-1",
    )

    usage = billing.capture_runtime_usage(
        "account-1",
        quote_id=quote.id,
        reservation_id=reservation.id,
        runtime_started_at=now,
        runtime_released_at=now + timedelta(seconds=90, milliseconds=400),
        idempotency_key="usage-1",
    )

    assert quote.hourly_rate == Decimal("3.60")
    assert reservation.amount == Decimal("1.50")
    assert usage.billable_seconds == 91
    assert usage.amount == Decimal("0.09")
    assert billing.get_wallet("account-1").balance == Decimal("19.91")


def test_runtime_usage_has_a_sixty_second_minimum():
    now = datetime(2026, 7, 31, 21, 0, tzinfo=UTC)
    billing = Billing(InMemoryBillingRepository(), clock=lambda: now)
    billing.credit_wallet(
        "account-1",
        amount=Decimal("20.00"),
        reference="payment-1",
        idempotency_key="payment-event-1",
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
        idempotency_key="wake-1",
    )

    usage = billing.capture_runtime_usage(
        "account-1",
        quote_id=quote.id,
        reservation_id=reservation.id,
        runtime_started_at=now,
        runtime_released_at=now + timedelta(seconds=3),
        idempotency_key="usage-1",
    )

    assert usage.billable_seconds == 60
    assert usage.amount == Decimal("0.06")
