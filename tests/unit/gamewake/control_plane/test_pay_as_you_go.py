from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gamewake.accounts import Accounts, InMemoryAccountRepository
from gamewake.billing import (
    Billing,
    InMemoryBillingRepository,
    InsufficientFundsError,
    ReservationStatus,
)
from gamewake.control_plane import GameWakeApplication
from gamewake.game_catalog import GameCatalog
from gamewake.worlds import InMemoryWorldRepository, OperationStatus, Worlds, WorldStatus


class Dispatcher:
    def __init__(self):
        self.calls = []

    def start(self, account_id, operation_id):
        self.calls.append((account_id, operation_id))


def setup_application(*, credit: Decimal):
    now = datetime(2026, 7, 31, 20, 0, tzinfo=UTC)
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Grupo", owner_user_id="owner")
    repository = InMemoryWorldRepository()
    catalog = GameCatalog.with_palworld()
    worlds = Worlds(repository, access=accounts, game_catalog=catalog)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="sa-east-1",
        runtime_profile_id="palworld-small",
    )
    billing_repository = InMemoryBillingRepository()
    billing = Billing(billing_repository, clock=lambda: now)
    if credit:
        billing.credit_wallet(
            account.id,
            amount=credit,
            reference="beta-credit",
            idempotency_key="credit-1",
        )
    dispatcher = Dispatcher()
    application = GameWakeApplication(
        accounts=accounts,
        worlds=worlds,
        billing=billing,
        game_catalog=catalog,
        operation_dispatcher=dispatcher,
        runtime_profile_hourly_rates={"palworld-small": Decimal("3.60")},
    )
    return application, billing_repository, dispatcher, account, world


def test_wake_reserves_a_locked_session_price_before_dispatching_compute():
    application, billing_repository, dispatcher, account, world = setup_application(
        credit=Decimal("20.00")
    )

    first = application.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="wake-1",
    )
    repeated = application.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="wake-1",
    )

    snapshot = billing_repository.get(account.id)
    assert repeated.id == first.id
    assert len(snapshot.quotes) == 1
    assert len(snapshot.reservations) == 1
    assert snapshot.reservations[0].amount == Decimal("1.50")
    assert first.session_quote_id == snapshot.quotes[0].id
    assert first.usage_reservation_id == snapshot.reservations[0].id
    assert dispatcher.calls == [(account.id, first.id), (account.id, first.id)]


def test_insufficient_credit_fails_the_pending_wake_without_dispatching_compute():
    application, billing_repository, dispatcher, account, world = setup_application(
        credit=Decimal("0.00")
    )

    with pytest.raises(InsufficientFundsError):
        application.request_wake(
            account.id,
            world.id,
            actor_user_id="owner",
            idempotency_key="wake-1",
        )

    [operation] = application.worlds.list_operations(
        account.id,
        world.id,
        viewer_user_id="owner",
    )
    assert operation.status is OperationStatus.FAILED
    assert (
        application.worlds.get_world(
            account.id,
            world.id,
            viewer_user_id="owner",
        ).status
        is WorldStatus.SLEEPING
    )
    assert billing_repository.get(account.id).reservations == ()
    assert dispatcher.calls == []


def test_concurrent_wake_requests_share_one_quote_and_one_reservation():
    application, billing_repository, _dispatcher, account, world = setup_application(
        credit=Decimal("20.00")
    )

    def wake(_number):
        return application.request_wake(
            account.id,
            world.id,
            actor_user_id="owner",
            idempotency_key="wake-shared",
        )

    with ThreadPoolExecutor(max_workers=10) as executor:
        operations = list(executor.map(wake, range(10)))

    snapshot = billing_repository.get(account.id)
    assert len({operation.id for operation in operations}) == 1
    assert len(snapshot.quotes) == 1
    assert len(snapshot.reservations) == 1


def test_conflicting_request_cannot_dispatch_an_operation_before_its_reservation_exists():
    application, billing_repository, dispatcher, account, world = setup_application(
        credit=Decimal("20.00")
    )
    pending = application.worlds.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="first-command",
    )

    observed = application.request_wake(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="conflicting-command",
    )

    assert observed.id == pending.id
    assert billing_repository.get(account.id).reservations == ()
    assert dispatcher.calls == []


def test_failed_wake_usage_is_charged_then_compensated_exactly_once():
    from gamewake.billing import BillingRuntimeUsageRecorder, LedgerEntryType
    from gamewake.worlds import WorldOperation

    now = datetime(2026, 7, 31, 20, 0, tzinfo=UTC)
    billing_repository = InMemoryBillingRepository()
    billing = Billing(billing_repository, clock=lambda: now)
    billing.credit_wallet(
        "account-1",
        amount=Decimal("20.00"),
        reference="credit",
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
    operation = WorldOperation(
        id="operation-1",
        account_id="account-1",
        world_id="world-1",
        operation_type="wake",
        status="running",
        phase="checking_game_health",
        idempotency_key="wake-1",
        created_at=now,
        version=1,
        session_quote_id=quote.id,
        usage_reservation_id=reservation.id,
        runtime_started_at=now,
    )
    recorder = BillingRuntimeUsageRecorder(billing)

    recorder.record_release(
        operation,
        runtime_released_at=now + timedelta(seconds=90),
        reached_online=False,
    )
    recorder.record_release(
        operation,
        runtime_released_at=now + timedelta(seconds=90),
        reached_online=False,
    )

    snapshot = billing_repository.get("account-1")
    assert len(snapshot.usages) == 1
    assert snapshot.reservations[0].status is ReservationStatus.CAPTURED
    assert [entry.entry_type for entry in snapshot.entries] == [
        LedgerEntryType.CONTRIBUTION,
        LedgerEntryType.RUNTIME_CHARGE,
        LedgerEntryType.WAKE_GUARANTEE,
    ]
    assert billing.get_wallet("account-1").balance == Decimal("20.00")
