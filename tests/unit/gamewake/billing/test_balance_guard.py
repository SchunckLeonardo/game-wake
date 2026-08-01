from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gamewake.billing import Billing, InMemoryBillingRepository


def test_balance_guard_extends_session_hold_and_emits_30_10_5_minute_alerts():
    started_at = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    billing = Billing(InMemoryBillingRepository(), clock=lambda: started_at)
    billing.credit_wallet(
        "account-1",
        amount=Decimal("5.00"),
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

    at_50_minutes = billing.protect_active_session(
        "account-1",
        quote_id=quote.id,
        reservation_id=reservation.id,
        runtime_started_at=started_at,
        observed_at=started_at + timedelta(minutes=50),
    )
    at_70_minutes = billing.protect_active_session(
        "account-1",
        quote_id=quote.id,
        reservation_id=reservation.id,
        runtime_started_at=started_at,
        observed_at=started_at + timedelta(minutes=70),
    )
    at_74_minutes = billing.protect_active_session(
        "account-1",
        quote_id=quote.id,
        reservation_id=reservation.id,
        runtime_started_at=started_at,
        observed_at=started_at + timedelta(minutes=74),
    )
    exhausted = billing.protect_active_session(
        "account-1",
        quote_id=quote.id,
        reservation_id=reservation.id,
        runtime_started_at=started_at,
        observed_at=started_at + timedelta(minutes=78),
    )

    assert at_50_minutes.new_alert_minutes == (30,)
    assert at_70_minutes.new_alert_minutes == (10,)
    assert at_74_minutes.new_alert_minutes == (5,)
    assert at_74_minutes.reserved_amount == Decimal("4.74")
    assert exhausted.should_sleep is True
    assert exhausted.reason == "insufficient_wallet_balance"
    assert exhausted.safe_sleep_reserved is True
    assert exhausted.new_alert_minutes == ()
    assert billing.get_wallet("account-1").available_balance == Decimal("0.02")
