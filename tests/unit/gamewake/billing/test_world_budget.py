from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gamewake.billing import (
    Billing,
    InMemoryBillingRepository,
    WorldBudgetExceeded,
)


def test_world_budget_alerts_at_50_80_100_percent_and_orders_safe_sleep():
    started_at = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    billing = Billing(InMemoryBillingRepository(), clock=lambda: started_at)
    billing.credit_wallet(
        "account-1",
        amount=Decimal("20.00"),
        reference="initial-credit",
        idempotency_key="credit-1",
    )
    budget = billing.set_world_budget(
        "account-1",
        world_id="world-1",
        monthly_limit=Decimal("2.00"),
        idempotency_key="budget-1",
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

    above_50 = billing.protect_active_session(
        "account-1",
        quote_id=quote.id,
        reservation_id=reservation.id,
        runtime_started_at=started_at,
        observed_at=started_at + timedelta(minutes=12),
    )
    above_80 = billing.protect_active_session(
        "account-1",
        quote_id=quote.id,
        reservation_id=reservation.id,
        runtime_started_at=started_at,
        observed_at=started_at + timedelta(minutes=24),
    )
    at_100 = billing.protect_active_session(
        "account-1",
        quote_id=quote.id,
        reservation_id=reservation.id,
        runtime_started_at=started_at,
        observed_at=started_at + timedelta(seconds=1700),
    )

    assert budget.monthly_limit == Decimal("2.00")
    assert above_50.new_budget_alert_percentages == (50,)
    assert above_80.new_budget_alert_percentages == (80,)
    assert at_100.new_budget_alert_percentages == (100,)
    assert at_100.reserved_amount == Decimal("2.00")
    assert at_100.safe_sleep_reserved is True
    assert at_100.should_sleep is True
    assert at_100.reason == "world_budget_exhausted"
    status = billing.get_world_budget_status("account-1", "world-1")
    assert status.committed == Decimal("2.00")
    assert status.percentage == Decimal("100.00")
    assert status.wake_allowed is False


def test_world_cannot_wake_when_initial_reservation_exceeds_its_budget():
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    billing = Billing(InMemoryBillingRepository(), clock=lambda: now)
    billing.credit_wallet(
        "account-1",
        amount=Decimal("20.00"),
        reference="initial-credit",
        idempotency_key="credit-1",
    )
    billing.set_world_budget(
        "account-1",
        world_id="world-1",
        monthly_limit=Decimal("1.00"),
        idempotency_key="budget-1",
    )
    quote = billing.create_session_quote(
        "account-1",
        world_id="world-1",
        runtime_profile_id="palworld-small",
        hourly_rate=Decimal("3.60"),
        idempotency_key="quote-1",
    )

    with pytest.raises(WorldBudgetExceeded):
        billing.reserve_for_wake(
            "account-1",
            quote.id,
            idempotency_key="reservation-1",
        )
