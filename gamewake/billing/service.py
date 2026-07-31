from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, ROUND_UP, Decimal
from math import ceil
from uuid import uuid4

from .contracts import BillingRepository, PaymentProvider
from .model import (
    BalanceGuardDecision,
    BalanceGuardState,
    ConcurrentBillingUpdate,
    ContributionCheckoutRequest,
    ContributionPackage,
    ContributionStatus,
    InsufficientFundsError,
    LedgerEntry,
    LedgerEntryType,
    PaymentMethodSummary,
    ProcessedPaymentEvent,
    ReservationStatus,
    RuntimeUsage,
    SessionQuote,
    UsageReservation,
    Wallet,
    WalletContribution,
    WalletSnapshot,
    WorldBudget,
    WorldBudgetAlertState,
    WorldBudgetExceeded,
    WorldBudgetStatus,
)

_CENT = Decimal("0.01")


class Billing:
    def __init__(
        self,
        repository: BillingRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        payment_provider: PaymentProvider | None = None,
        contribution_packages: tuple[ContributionPackage, ...] = (),
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._payment_provider = payment_provider
        self._contribution_packages = {item.id: item for item in contribution_packages}

    def create_contribution(
        self,
        account_id: str,
        *,
        payer_user_id: str,
        package_id: str,
        return_url: str,
        completion_url: str,
        idempotency_key: str,
    ) -> WalletContribution:
        if self._payment_provider is None:
            raise RuntimeError("Payment Provider is not configured")
        try:
            package = self._contribution_packages[package_id]
        except KeyError as error:
            raise ValueError("unknown contribution package") from error
        amount = self._positive_money(package.amount)
        contribution_id = str(uuid4())
        contribution = WalletContribution(
            id=contribution_id,
            account_id=account_id,
            payer_user_id=payer_user_id,
            package_id=package.id,
            amount=amount,
            provider_product_id=package.provider_product_id,
            provider_checkout_id=None,
            checkout_url=None,
            return_url=return_url,
            completion_url=completion_url,
            status=ContributionStatus.CREATING_CHECKOUT,
            idempotency_key=idempotency_key,
            created_at=self._clock(),
            payment_method=None,
            provider_refund_id=None,
        )
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            existing = next(
                (
                    item
                    for item in snapshot.contributions
                    if item.idempotency_key == idempotency_key
                ),
                None,
            )
            if existing is not None:
                if (
                    existing.payer_user_id != payer_user_id
                    or existing.package_id != package_id
                ):
                    raise ValueError("idempotency key was used for another contribution")
                return existing
            if self._try_save(
                replace(snapshot, contributions=(*snapshot.contributions, contribution)),
                expected_version=snapshot.version,
            ):
                break
        else:
            raise ConcurrentBillingUpdate("could not start contribution after retries")

        checkout = self._payment_provider.create_checkout(
            ContributionCheckoutRequest(
                external_id=contribution.id,
                provider_product_id=contribution.provider_product_id,
                expected_amount=contribution.amount,
                return_url=return_url,
                completion_url=completion_url,
            )
        )
        pending = replace(
            contribution,
            provider_checkout_id=checkout.id,
            checkout_url=checkout.url,
            status=ContributionStatus.PENDING,
        )
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            current = next(item for item in snapshot.contributions if item.id == contribution.id)
            if current.status is ContributionStatus.PENDING:
                return current
            contributions = tuple(
                pending if item.id == contribution.id else item
                for item in snapshot.contributions
            )
            if self._try_save(
                replace(snapshot, contributions=contributions),
                expected_version=snapshot.version,
            ):
                return pending
        raise ConcurrentBillingUpdate("could not attach contribution checkout after retries")

    def get_contribution(
        self,
        account_id: str,
        contribution_id: str,
        *,
        requesting_user_id: str,
    ) -> WalletContribution:
        contribution = next(
            item
            for item in self._repository.get(account_id).contributions
            if item.id == contribution_id
        )
        if contribution.payer_user_id == requesting_user_id:
            return contribution
        return replace(
            contribution,
            provider_checkout_id=None,
            checkout_url=None,
            payment_method=None,
        )

    def request_contribution_refund(
        self,
        account_id: str,
        contribution_id: str,
        *,
        requesting_user_id: str,
        reason: str,
    ) -> WalletContribution:
        if self._payment_provider is None:
            raise RuntimeError("Payment Provider is not configured")
        snapshot = self._repository.get(account_id)
        contribution = next(
            item for item in snapshot.contributions if item.id == contribution_id
        )
        if contribution.payer_user_id != requesting_user_id:
            raise PermissionError("only the payer can request this refund")
        if contribution.status in {
            ContributionStatus.REFUND_REQUESTED,
            ContributionStatus.REFUNDED,
        }:
            return contribution
        if contribution.status is not ContributionStatus.COMPLETED:
            raise ValueError("only a completed contribution can be refunded")
        if self._available_balance(snapshot) < contribution.amount:
            raise InsufficientFundsError("contribution credit has already been used")
        if contribution.provider_checkout_id is None:
            raise ValueError("contribution has no provider checkout")

        refund_id = self._payment_provider.refund_checkout(
            contribution.provider_checkout_id,
            reason=reason,
        )
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            current = next(
                item for item in snapshot.contributions if item.id == contribution_id
            )
            if current.status in {
                ContributionStatus.REFUND_REQUESTED,
                ContributionStatus.REFUNDED,
            }:
                return current
            if current.status is not ContributionStatus.COMPLETED:
                raise ValueError("contribution changed while requesting refund")
            requested = replace(
                current,
                status=ContributionStatus.REFUND_REQUESTED,
                provider_refund_id=refund_id,
            )
            contributions = tuple(
                requested if item.id == contribution_id else item
                for item in snapshot.contributions
            )
            if self._try_save(
                replace(snapshot, contributions=contributions),
                expected_version=snapshot.version,
            ):
                return requested
        raise ConcurrentBillingUpdate("could not record contribution refund request")

    def reconcile_contribution(
        self,
        account_id: str,
        contribution_id: str,
    ) -> WalletContribution:
        if self._payment_provider is None:
            raise RuntimeError("Payment Provider is not configured")
        contribution = next(
            item
            for item in self._repository.get(account_id).contributions
            if item.id == contribution_id
        )
        checkout = self._payment_provider.find_checkout(contribution.id)
        if checkout is None:
            return contribution
        if checkout.external_id != contribution.id or checkout.amount != contribution.amount:
            raise ValueError("reconciled checkout does not match contribution")

        if contribution.status is ContributionStatus.CREATING_CHECKOUT:
            pending = replace(
                contribution,
                provider_checkout_id=checkout.id,
                checkout_url=checkout.url,
                status=ContributionStatus.PENDING,
            )
            for _ in range(100):
                snapshot = self._repository.get(account_id)
                current = next(
                    item for item in snapshot.contributions if item.id == contribution.id
                )
                if current.status is not ContributionStatus.CREATING_CHECKOUT:
                    contribution = current
                    break
                contributions = tuple(
                    pending if item.id == contribution.id else item
                    for item in snapshot.contributions
                )
                if self._try_save(
                    replace(snapshot, contributions=contributions),
                    expected_version=snapshot.version,
                ):
                    contribution = pending
                    break
            else:
                raise ConcurrentBillingUpdate("could not reconcile contribution checkout")

        event_type = {
            "PAID": "checkout.completed",
            "REFUNDED": "checkout.refunded",
        }.get(checkout.status)
        if event_type is not None:
            self.process_payment_event(
                {
                    "id": f"reconcile:{checkout.id}:{checkout.status.lower()}",
                    "event": event_type,
                    "apiVersion": 2,
                    "data": {
                        "checkout": {
                            "id": checkout.id,
                            "externalId": checkout.external_id,
                            "amount": int(checkout.amount * 100),
                            "paidAmount": (
                                int(checkout.paid_amount * 100)
                                if checkout.paid_amount is not None
                                else None
                            ),
                            "status": checkout.status,
                        }
                    },
                }
            )
            contribution = next(
                item
                for item in self._repository.get(account_id).contributions
                if item.id == contribution_id
            )
        return contribution

    def process_payment_event(
        self,
        payload: Mapping[str, object],
    ) -> ProcessedPaymentEvent:
        event_id = self._required_string(payload, "id")
        event_type = self._required_string(payload, "event")
        if payload.get("apiVersion") != 2:
            raise ValueError("unsupported AbacatePay webhook API version")
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise ValueError("AbacatePay webhook data is missing")
        checkout = data.get("checkout")
        if not isinstance(checkout, Mapping):
            raise ValueError("AbacatePay webhook checkout is missing")
        contribution_id = self._required_string(checkout, "externalId")
        located = self._repository.find_contribution(contribution_id)
        if located is None:
            raise ValueError("AbacatePay webhook references an unknown contribution")

        for _ in range(100):
            snapshot = self._repository.get(located.account_id)
            existing = next(
                (item for item in snapshot.payment_events if item.id == event_id),
                None,
            )
            if existing is not None:
                return existing
            contribution = next(
                item for item in snapshot.contributions if item.id == contribution_id
            )
            if self._required_string(checkout, "id") != contribution.provider_checkout_id:
                raise ValueError("AbacatePay checkout does not match contribution")

            entries = snapshot.entries
            updated = contribution
            if event_type == "checkout.completed":
                updated, entries = self._complete_contribution(
                    contribution,
                    checkout=checkout,
                    data=data,
                    event_id=event_id,
                    entries=entries,
                )
            elif event_type in {"checkout.refunded", "checkout.disputed"}:
                updated, entries = self._reverse_contribution(
                    contribution,
                    event_type=event_type,
                    event_id=event_id,
                    entries=entries,
                    available_balance=self._available_balance(snapshot),
                )
            event = ProcessedPaymentEvent(
                id=event_id,
                event_type=event_type,
                contribution_id=contribution.id,
                processed_at=self._clock(),
            )
            contributions = tuple(
                updated if item.id == contribution.id else item
                for item in snapshot.contributions
            )
            if self._try_save(
                replace(
                    snapshot,
                    entries=entries,
                    contributions=contributions,
                    payment_events=(*snapshot.payment_events, event),
                ),
                expected_version=snapshot.version,
            ):
                return event
        raise ConcurrentBillingUpdate("could not process payment event after retries")

    def _complete_contribution(
        self,
        contribution: WalletContribution,
        *,
        checkout: Mapping[str, object],
        data: Mapping[str, object],
        event_id: str,
        entries: tuple[LedgerEntry, ...],
    ) -> tuple[WalletContribution, tuple[LedgerEntry, ...]]:
        if contribution.status in {
            ContributionStatus.COMPLETED,
            ContributionStatus.REFUND_REQUESTED,
            ContributionStatus.REFUNDED,
            ContributionStatus.DISPUTED,
        }:
            return contribution, entries
        paid_amount = self._cents_to_money(checkout.get("paidAmount"))
        checkout_amount = self._cents_to_money(checkout.get("amount"))
        if paid_amount != contribution.amount or checkout_amount != contribution.amount:
            return replace(contribution, status=ContributionStatus.NEEDS_REVIEW), entries
        payment_method = self._payment_method_summary(data.get("payerInformation"))
        entry = LedgerEntry(
            id=str(uuid4()),
            account_id=contribution.account_id,
            entry_type=LedgerEntryType.CONTRIBUTION,
            amount=contribution.amount,
            reference=contribution.id,
            idempotency_key=f"abacatepay:{event_id}",
            occurred_at=self._clock(),
        )
        return (
            replace(
                contribution,
                status=ContributionStatus.COMPLETED,
                payment_method=payment_method,
            ),
            (*entries, entry),
        )

    def _reverse_contribution(
        self,
        contribution: WalletContribution,
        *,
        event_type: str,
        event_id: str,
        entries: tuple[LedgerEntry, ...],
        available_balance: Decimal,
    ) -> tuple[WalletContribution, tuple[LedgerEntry, ...]]:
        status = (
            ContributionStatus.REFUNDED
            if event_type == "checkout.refunded"
            else ContributionStatus.DISPUTED
        )
        if contribution.status in {
            ContributionStatus.REFUNDED,
            ContributionStatus.DISPUTED,
        }:
            return contribution, entries
        if contribution.status not in {
            ContributionStatus.COMPLETED,
            ContributionStatus.REFUND_REQUESTED,
        }:
            return replace(contribution, status=status), entries
        if available_balance < contribution.amount:
            return replace(contribution, status=ContributionStatus.NEEDS_REVIEW), entries
        entry_type = (
            LedgerEntryType.REFUND
            if event_type == "checkout.refunded"
            else LedgerEntryType.DISPUTE
        )
        entry = LedgerEntry(
            id=str(uuid4()),
            account_id=contribution.account_id,
            entry_type=entry_type,
            amount=-contribution.amount,
            reference=contribution.id,
            idempotency_key=f"abacatepay:{event_id}",
            occurred_at=self._clock(),
        )
        return replace(contribution, status=status), (*entries, entry)

    def get_wallet(self, account_id: str) -> Wallet:
        snapshot = self._repository.get(account_id)
        balance = sum((entry.amount for entry in snapshot.entries), start=Decimal("0.00"))
        return Wallet(
            account_id=account_id,
            currency="BRL",
            balance=balance,
            available_balance=self._available_balance(snapshot),
            statement=snapshot.entries,
            reservations=snapshot.reservations,
        )

    def create_session_quote(
        self,
        account_id: str,
        *,
        world_id: str,
        runtime_profile_id: str,
        hourly_rate: Decimal,
        idempotency_key: str,
    ) -> SessionQuote:
        normalized_rate = self._positive_money(hourly_rate)
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            existing = next(
                (
                    quote
                    for quote in snapshot.quotes
                    if quote.idempotency_key == idempotency_key
                ),
                None,
            )
            if existing is not None:
                return existing
            created_at = self._clock()
            quote = SessionQuote(
                id=str(uuid4()),
                account_id=account_id,
                world_id=world_id,
                runtime_profile_id=runtime_profile_id,
                hourly_rate=normalized_rate,
                idempotency_key=idempotency_key,
                created_at=created_at,
                expires_at=created_at + timedelta(minutes=15),
            )
            if self._try_save(
                replace(snapshot, quotes=(*snapshot.quotes, quote)),
                expected_version=snapshot.version,
            ):
                return quote
        raise ConcurrentBillingUpdate("could not create Session Quote after retries")

    def reserve_for_wake(
        self,
        account_id: str,
        quote_id: str,
        *,
        idempotency_key: str,
    ) -> UsageReservation:
        snapshot = self._repository.get(account_id)
        quote = next(item for item in snapshot.quotes if item.id == quote_id)
        if self._clock() > quote.expires_at:
            raise ValueError("Session Quote has expired")
        reserved_seconds = Decimal(25 * 60)
        amount = (quote.hourly_rate * reserved_seconds / Decimal(3600)).quantize(
            _CENT,
            rounding=ROUND_UP,
        )
        return self.reserve(
            account_id,
            amount=amount,
            purpose=f"wake:{quote.world_id}",
            idempotency_key=idempotency_key,
            quote_id=quote.id,
            world_id=quote.world_id,
        )

    def set_world_budget(
        self,
        account_id: str,
        *,
        world_id: str,
        monthly_limit: Decimal,
        idempotency_key: str,
    ) -> WorldBudget:
        limit = self._positive_money(monthly_limit)
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            existing_command = next(
                (
                    budget
                    for budget in snapshot.world_budgets
                    if budget.idempotency_key == idempotency_key
                ),
                None,
            )
            if existing_command is not None:
                return existing_command
            current = next(
                (budget for budget in snapshot.world_budgets if budget.world_id == world_id),
                None,
            )
            budget = WorldBudget(
                id=current.id if current is not None else str(uuid4()),
                account_id=account_id,
                world_id=world_id,
                monthly_limit=limit,
                idempotency_key=idempotency_key,
                updated_at=self._clock(),
            )
            budgets = tuple(
                budget if item.world_id == world_id else item
                for item in snapshot.world_budgets
            )
            if current is None:
                budgets = (*budgets, budget)
            if self._try_save(
                replace(snapshot, world_budgets=budgets),
                expected_version=snapshot.version,
            ):
                return budget
        raise ConcurrentBillingUpdate("could not set World Budget after retries")

    def get_world_budget_status(
        self,
        account_id: str,
        world_id: str,
        *,
        observed_at: datetime | None = None,
    ) -> WorldBudgetStatus | None:
        snapshot = self._repository.get(account_id)
        budget = self._world_budget(snapshot, world_id)
        if budget is None:
            return None
        now = observed_at or self._clock()
        spent = self._world_budget_spent(snapshot, world_id, now)
        reserved = self._world_budget_reserved(snapshot, world_id)
        committed = spent + reserved
        percentage = (committed / budget.monthly_limit * Decimal(100)).quantize(
            _CENT,
            rounding=ROUND_HALF_UP,
        )
        return WorldBudgetStatus(
            world_id=world_id,
            period=self._month_key(now),
            monthly_limit=budget.monthly_limit,
            spent=spent,
            reserved=reserved,
            committed=committed,
            percentage=percentage,
            wake_allowed=committed < budget.monthly_limit,
        )

    def credit_wallet(
        self,
        account_id: str,
        *,
        amount: Decimal,
        reference: str,
        idempotency_key: str,
    ) -> LedgerEntry:
        normalized = self._positive_money(amount)
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            existing = next(
                (
                    entry
                    for entry in snapshot.entries
                    if entry.idempotency_key == idempotency_key
                ),
                None,
            )
            if existing is not None:
                return existing
            entry = LedgerEntry(
                id=str(uuid4()),
                account_id=account_id,
                entry_type=LedgerEntryType.CONTRIBUTION,
                amount=normalized,
                reference=reference,
                idempotency_key=idempotency_key,
                occurred_at=self._clock(),
            )
            if self._try_save(
                replace(snapshot, entries=(*snapshot.entries, entry)),
                expected_version=snapshot.version,
            ):
                return entry
        raise ConcurrentBillingUpdate("could not credit Wallet after concurrent retries")

    def charge_monthly_storage(
        self,
        account_id: str,
        *,
        excess_bytes: int,
        rate_per_gib_month: Decimal,
        billing_month: str,
        idempotency_key: str,
    ) -> LedgerEntry:
        if excess_bytes <= 0:
            raise ValueError("storage excess must be positive")
        try:
            datetime.strptime(billing_month, "%Y-%m")
        except ValueError as error:
            raise ValueError("billing month must use YYYY-MM") from error
        rate = self._positive_money(rate_per_gib_month)
        amount = (
            rate * Decimal(excess_bytes) / Decimal(1024**3)
        ).quantize(_CENT, rounding=ROUND_HALF_UP)
        if amount <= 0:
            raise ValueError("storage charge rounds below one cent")
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            existing = next(
                (
                    entry
                    for entry in snapshot.entries
                    if entry.idempotency_key == idempotency_key
                ),
                None,
            )
            if existing is not None:
                return existing
            if self._available_balance(snapshot) < amount:
                raise InsufficientFundsError("Wallet cannot fund storage excess")
            entry = LedgerEntry(
                id=str(uuid4()),
                account_id=account_id,
                entry_type=LedgerEntryType.STORAGE_CHARGE,
                amount=-amount,
                reference=f"storage:{billing_month}",
                idempotency_key=idempotency_key,
                occurred_at=self._clock(),
            )
            if self._try_save(
                replace(snapshot, entries=(*snapshot.entries, entry)),
                expected_version=snapshot.version,
            ):
                return entry
        raise ConcurrentBillingUpdate("could not charge storage after retries")

    def reserve(
        self,
        account_id: str,
        *,
        amount: Decimal,
        purpose: str,
        idempotency_key: str,
        quote_id: str | None = None,
        world_id: str | None = None,
    ) -> UsageReservation:
        normalized = self._positive_money(amount)
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            existing = next(
                (
                    reservation
                    for reservation in snapshot.reservations
                    if reservation.idempotency_key == idempotency_key
                ),
                None,
            )
            if existing is not None:
                return existing
            if self._available_balance(snapshot) < normalized:
                raise InsufficientFundsError("Wallet has insufficient available balance")
            if (
                world_id is not None
                and self._world_budget_available(snapshot, world_id, self._clock())
                < normalized
            ):
                raise WorldBudgetExceeded("World Budget cannot fund this reservation")
            reservation = UsageReservation(
                id=str(uuid4()),
                account_id=account_id,
                amount=normalized,
                purpose=purpose,
                idempotency_key=idempotency_key,
                status=ReservationStatus.ACTIVE,
                created_at=self._clock(),
                quote_id=quote_id,
                world_id=world_id,
            )
            if self._try_save(
                replace(
                    snapshot,
                    reservations=(*snapshot.reservations, reservation),
                ),
                expected_version=snapshot.version,
            ):
                return reservation
        raise ConcurrentBillingUpdate("could not reserve Wallet after concurrent retries")

    def protect_active_session(
        self,
        account_id: str,
        *,
        quote_id: str,
        reservation_id: str,
        runtime_started_at: datetime,
        observed_at: datetime,
        safe_sleep_seconds: int = 5 * 60,
        guard_interval_seconds: int = 60,
    ) -> BalanceGuardDecision:
        elapsed = (observed_at - runtime_started_at).total_seconds()
        if elapsed < 0:
            raise ValueError("Balance Guard observation cannot precede Runtime start")
        if safe_sleep_seconds <= 0 or guard_interval_seconds <= 0:
            raise ValueError("Balance Guard intervals must be positive")
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            quote = next(item for item in snapshot.quotes if item.id == quote_id)
            reservation = next(
                item for item in snapshot.reservations if item.id == reservation_id
            )
            if reservation.quote_id != quote.id:
                raise ValueError("Usage Reservation does not belong to Session Quote")
            if reservation.status is not ReservationStatus.ACTIVE:
                raise ValueError("Balance Guard requires an active Usage Reservation")
            guard = next(
                (
                    item
                    for item in snapshot.balance_guards
                    if item.reservation_id == reservation.id
                ),
                BalanceGuardState(
                    reservation_id=reservation.id,
                    notified_alert_minutes=(),
                ),
            )
            elapsed_seconds = ceil(elapsed)
            required_amount = (
                quote.hourly_rate
                * Decimal(elapsed_seconds + safe_sleep_seconds)
                / Decimal(3600)
            ).quantize(_CENT, rounding=ROUND_UP)
            additional_hold = max(Decimal("0.00"), required_amount - reservation.amount)
            wallet_available = self._available_balance(snapshot)
            budget = self._world_budget(snapshot, quote.world_id)
            budget_available = (
                self._world_budget_available(snapshot, quote.world_id, observed_at)
                if budget is not None
                else None
            )
            can_extend_wallet = additional_hold <= wallet_available
            can_extend_budget = (
                budget_available is None or additional_hold <= budget_available
            )
            can_extend = can_extend_wallet and can_extend_budget
            reserved_amount = required_amount if can_extend else reservation.amount
            wallet_after = (
                wallet_available - additional_hold if can_extend else Decimal("0.00")
            )
            budget_after = (
                budget_available - additional_hold
                if can_extend and budget_available is not None
                else None
            )
            available_after = (
                min(wallet_after, budget_after)
                if budget_after is not None
                else wallet_after
            )
            rate_per_minute = quote.hourly_rate / Decimal(60)
            remaining_minutes_decimal = (
                available_after / rate_per_minute
                if rate_per_minute > 0
                else Decimal("0.00")
            )
            remaining_minutes = max(0, int(remaining_minutes_decimal))
            eligible = {
                threshold
                for threshold in (30, 10, 5)
                if remaining_minutes_decimal <= threshold
            }
            already_notified = set(guard.notified_alert_minutes)
            newly_eligible = eligible - already_notified
            new_alerts = (min(newly_eligible),) if newly_eligible else ()
            notified = tuple(sorted(already_notified | eligible, reverse=True))
            budget_alert_state = None
            budget_new_alerts: tuple[int, ...] = ()
            if budget is not None:
                period = self._month_key(observed_at)
                budget_alert_state = next(
                    (
                        item
                        for item in snapshot.world_budget_alerts
                        if item.world_id == quote.world_id and item.period == period
                    ),
                    WorldBudgetAlertState(
                        world_id=quote.world_id,
                        period=period,
                        notified_percentages=(),
                    ),
                )
                committed = (
                    self._world_budget_spent(snapshot, quote.world_id, observed_at)
                    + self._world_budget_reserved(snapshot, quote.world_id)
                    + (additional_hold if can_extend else Decimal("0.00"))
                )
                percentage = committed / budget.monthly_limit * Decimal(100)
                eligible_budget_alerts = {
                    threshold for threshold in (50, 80, 100) if percentage >= threshold
                }
                notified_budget_alerts = set(
                    budget_alert_state.notified_percentages
                )
                new_budget_eligible = eligible_budget_alerts - notified_budget_alerts
                budget_new_alerts = (
                    (max(new_budget_eligible),) if new_budget_eligible else ()
                )
                budget_alert_state = replace(
                    budget_alert_state,
                    notified_percentages=tuple(
                        sorted(notified_budget_alerts | eligible_budget_alerts)
                    ),
                )
            safe_sleep_reserved = can_extend
            should_sleep = not can_extend or (
                available_after
                < quote.hourly_rate
                * Decimal(guard_interval_seconds)
                / Decimal(3600)
            )
            if should_sleep:
                budget_is_limiter = budget_after is not None and budget_after <= wallet_after
                reason = (
                    "world_budget_exhausted"
                    if budget_is_limiter or not can_extend_budget
                    else "insufficient_wallet_balance"
                )
            else:
                reason = None
            decision = BalanceGuardDecision(
                reservation_id=reservation.id,
                reserved_amount=reserved_amount,
                remaining_minutes=remaining_minutes,
                new_alert_minutes=new_alerts,
                new_budget_alert_percentages=budget_new_alerts,
                safe_sleep_reserved=safe_sleep_reserved,
                should_sleep=should_sleep,
                reason=reason,
            )
            extended = replace(reservation, amount=reserved_amount)
            reservations = tuple(
                extended if item.id == reservation.id else item
                for item in snapshot.reservations
            )
            updated_guard = replace(guard, notified_alert_minutes=notified)
            balance_guards = tuple(
                updated_guard if item.reservation_id == reservation.id else item
                for item in snapshot.balance_guards
            )
            if not any(
                item.reservation_id == reservation.id for item in snapshot.balance_guards
            ):
                balance_guards = (*balance_guards, updated_guard)
            budget_alerts = snapshot.world_budget_alerts
            if budget_alert_state is not None:
                budget_alerts = tuple(
                    budget_alert_state
                    if item.world_id == budget_alert_state.world_id
                    and item.period == budget_alert_state.period
                    else item
                    for item in snapshot.world_budget_alerts
                )
                if not any(
                    item.world_id == budget_alert_state.world_id
                    and item.period == budget_alert_state.period
                    for item in snapshot.world_budget_alerts
                ):
                    budget_alerts = (*budget_alerts, budget_alert_state)
            if (
                reservations == snapshot.reservations
                and balance_guards == snapshot.balance_guards
                and budget_alerts == snapshot.world_budget_alerts
            ):
                return decision
            if self._try_save(
                replace(
                    snapshot,
                    reservations=reservations,
                    balance_guards=balance_guards,
                    world_budget_alerts=budget_alerts,
                ),
                expected_version=snapshot.version,
            ):
                return decision
        raise ConcurrentBillingUpdate("could not apply Balance Guard after retries")

    def release_reservation(
        self,
        account_id: str,
        reservation_id: str,
    ) -> UsageReservation:
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            reservation = next(
                item for item in snapshot.reservations if item.id == reservation_id
            )
            if reservation.status is ReservationStatus.RELEASED:
                return reservation
            if reservation.status is ReservationStatus.CAPTURED:
                raise ValueError("captured Usage Reservation cannot be released")
            released = replace(reservation, status=ReservationStatus.RELEASED)
            reservations = tuple(
                released if item.id == reservation_id else item
                for item in snapshot.reservations
            )
            if self._try_save(
                replace(snapshot, reservations=reservations),
                expected_version=snapshot.version,
            ):
                return released
        raise ConcurrentBillingUpdate("could not release Usage Reservation after retries")

    def apply_wake_guarantee(
        self,
        account_id: str,
        usage_id: str,
        *,
        reached_online: bool,
        idempotency_key: str,
    ) -> LedgerEntry:
        if reached_online:
            raise ValueError("Wake Guarantee applies only before a World reaches Online")
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            usage = next(item for item in snapshot.usages if item.id == usage_id)
            existing = next(
                (
                    entry
                    for entry in snapshot.entries
                    if entry.entry_type is LedgerEntryType.WAKE_GUARANTEE
                    and entry.reference == usage.id
                ),
                None,
            )
            if existing is not None:
                return existing
            entry = LedgerEntry(
                id=str(uuid4()),
                account_id=account_id,
                entry_type=LedgerEntryType.WAKE_GUARANTEE,
                amount=usage.amount,
                reference=usage.id,
                idempotency_key=idempotency_key,
                occurred_at=self._clock(),
            )
            if self._try_save(
                replace(snapshot, entries=(*snapshot.entries, entry)),
                expected_version=snapshot.version,
            ):
                return entry
        raise ConcurrentBillingUpdate("could not apply Wake Guarantee after retries")

    def apply_availability_credit(
        self,
        account_id: str,
        usage_id: str,
        *,
        unavailable_at: datetime,
        recovered_at: datetime,
        idempotency_key: str,
    ) -> LedgerEntry | None:
        elapsed = (recovered_at - unavailable_at).total_seconds()
        if elapsed <= 120:
            return None
        reference = (
            f"{usage_id}:{unavailable_at.isoformat()}:{recovered_at.isoformat()}"
        )
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            usage = next(item for item in snapshot.usages if item.id == usage_id)
            if (
                unavailable_at < usage.runtime_started_at
                or recovered_at > usage.runtime_released_at
            ):
                raise ValueError("Availability interval must be inside Runtime Usage")
            existing = next(
                (
                    entry
                    for entry in snapshot.entries
                    if entry.entry_type is LedgerEntryType.AVAILABILITY_CREDIT
                    and entry.reference == reference
                ),
                None,
            )
            if existing is not None:
                return existing
            quote = next(item for item in snapshot.quotes if item.id == usage.quote_id)
            unavailable_seconds = ceil(elapsed)
            amount = (
                quote.hourly_rate * Decimal(unavailable_seconds) / Decimal(3600)
            ).quantize(_CENT, rounding=ROUND_HALF_UP)
            amount = min(amount, usage.amount)
            if amount <= 0:
                return None
            entry = LedgerEntry(
                id=str(uuid4()),
                account_id=account_id,
                entry_type=LedgerEntryType.AVAILABILITY_CREDIT,
                amount=amount,
                reference=reference,
                idempotency_key=idempotency_key,
                occurred_at=self._clock(),
            )
            if self._try_save(
                replace(snapshot, entries=(*snapshot.entries, entry)),
                expected_version=snapshot.version,
            ):
                return entry
        raise ConcurrentBillingUpdate("could not apply Availability Credit after retries")

    def capture_reservation(
        self,
        account_id: str,
        reservation_id: str,
        *,
        amount: Decimal,
        idempotency_key: str,
    ) -> LedgerEntry:
        normalized = self._positive_money(amount)
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            existing = next(
                (
                    entry
                    for entry in snapshot.entries
                    if entry.idempotency_key == idempotency_key
                ),
                None,
            )
            if existing is not None:
                return existing
            reservation = next(
                item for item in snapshot.reservations if item.id == reservation_id
            )
            if reservation.status is not ReservationStatus.ACTIVE:
                raise ValueError("Usage Reservation is no longer active")
            if normalized > reservation.amount:
                raise ValueError("Runtime Charge exceeds its Usage Reservation")
            charge = LedgerEntry(
                id=str(uuid4()),
                account_id=account_id,
                entry_type=LedgerEntryType.RUNTIME_CHARGE,
                amount=-normalized,
                reference=reservation.purpose,
                idempotency_key=idempotency_key,
                occurred_at=self._clock(),
            )
            captured = replace(reservation, status=ReservationStatus.CAPTURED)
            reservations = tuple(
                captured if item.id == reservation_id else item
                for item in snapshot.reservations
            )
            if self._try_save(
                replace(
                    snapshot,
                    entries=(*snapshot.entries, charge),
                    reservations=reservations,
                ),
                expected_version=snapshot.version,
            ):
                return charge
        raise ConcurrentBillingUpdate("could not charge Wallet after concurrent retries")

    def capture_runtime_usage(
        self,
        account_id: str,
        *,
        quote_id: str,
        reservation_id: str,
        runtime_started_at: datetime,
        runtime_released_at: datetime,
        idempotency_key: str,
    ) -> RuntimeUsage:
        elapsed = (runtime_released_at - runtime_started_at).total_seconds()
        if elapsed < 0:
            raise ValueError("Runtime release cannot precede Runtime start")
        billable_seconds = max(60, ceil(elapsed))
        for _ in range(100):
            snapshot = self._repository.get(account_id)
            existing = next(
                (
                    usage
                    for usage in snapshot.usages
                    if usage.idempotency_key == idempotency_key
                ),
                None,
            )
            if existing is not None:
                return existing
            quote = next(item for item in snapshot.quotes if item.id == quote_id)
            reservation = next(
                item for item in snapshot.reservations if item.id == reservation_id
            )
            if reservation.status is not ReservationStatus.ACTIVE:
                raise ValueError("Usage Reservation is no longer active")
            amount = (
                quote.hourly_rate * Decimal(billable_seconds) / Decimal(3600)
            ).quantize(_CENT, rounding=ROUND_HALF_UP)
            if amount > reservation.amount:
                raise ValueError("Runtime Usage exceeds its active reservation")
            charge = LedgerEntry(
                id=str(uuid4()),
                account_id=account_id,
                entry_type=LedgerEntryType.RUNTIME_CHARGE,
                amount=-amount,
                reference=f"runtime:{quote.world_id}",
                idempotency_key=f"{idempotency_key}:ledger",
                occurred_at=self._clock(),
            )
            usage = RuntimeUsage(
                id=str(uuid4()),
                account_id=account_id,
                world_id=quote.world_id,
                quote_id=quote.id,
                reservation_id=reservation.id,
                billable_seconds=billable_seconds,
                amount=amount,
                runtime_started_at=runtime_started_at,
                runtime_released_at=runtime_released_at,
                ledger_entry_id=charge.id,
                idempotency_key=idempotency_key,
            )
            captured = replace(reservation, status=ReservationStatus.CAPTURED)
            reservations = tuple(
                captured if item.id == reservation_id else item
                for item in snapshot.reservations
            )
            if self._try_save(
                replace(
                    snapshot,
                    entries=(*snapshot.entries, charge),
                    reservations=reservations,
                    usages=(*snapshot.usages, usage),
                ),
                expected_version=snapshot.version,
            ):
                return usage
        raise ConcurrentBillingUpdate("could not record Runtime Usage after retries")

    def _try_save(self, snapshot: WalletSnapshot, *, expected_version: int) -> bool:
        try:
            self._repository.save(snapshot, expected_version=expected_version)
            return True
        except ConcurrentBillingUpdate:
            return False

    def _available_balance(self, snapshot: WalletSnapshot) -> Decimal:
        if any(
            contribution.status is ContributionStatus.NEEDS_REVIEW
            for contribution in snapshot.contributions
        ):
            return Decimal("0.00")
        balance = sum((entry.amount for entry in snapshot.entries), start=Decimal("0.00"))
        reserved = sum(
            (
                reservation.amount
                for reservation in snapshot.reservations
                if reservation.status is ReservationStatus.ACTIVE
            ),
            start=Decimal("0.00"),
        )
        return balance - reserved

    @staticmethod
    def _world_budget(snapshot: WalletSnapshot, world_id: str) -> WorldBudget | None:
        return next(
            (budget for budget in snapshot.world_budgets if budget.world_id == world_id),
            None,
        )

    def _world_budget_available(
        self,
        snapshot: WalletSnapshot,
        world_id: str,
        observed_at: datetime,
    ) -> Decimal:
        budget = self._world_budget(snapshot, world_id)
        if budget is None:
            return Decimal("Infinity")
        committed = self._world_budget_spent(snapshot, world_id, observed_at) + (
            self._world_budget_reserved(snapshot, world_id)
        )
        return max(Decimal("0.00"), budget.monthly_limit - committed)

    @staticmethod
    def _world_budget_reserved(snapshot: WalletSnapshot, world_id: str) -> Decimal:
        return sum(
            (
                reservation.amount
                for reservation in snapshot.reservations
                if reservation.world_id == world_id
                and reservation.status is ReservationStatus.ACTIVE
            ),
            start=Decimal("0.00"),
        )

    def _world_budget_spent(
        self,
        snapshot: WalletSnapshot,
        world_id: str,
        observed_at: datetime,
    ) -> Decimal:
        period = self._month_key(observed_at)
        spent = Decimal("0.00")
        for usage in snapshot.usages:
            if usage.world_id != world_id or self._month_key(usage.runtime_released_at) != period:
                continue
            credits = sum(
                (
                    entry.amount
                    for entry in snapshot.entries
                    if entry.entry_type
                    in {
                        LedgerEntryType.WAKE_GUARANTEE,
                        LedgerEntryType.AVAILABILITY_CREDIT,
                    }
                    and (
                        entry.reference == usage.id
                        or entry.reference.startswith(f"{usage.id}:")
                    )
                ),
                start=Decimal("0.00"),
            )
            spent += max(Decimal("0.00"), usage.amount - credits)
        return spent

    @staticmethod
    def _month_key(value: datetime) -> str:
        return f"{value.year:04d}-{value.month:02d}"

    @staticmethod
    def _positive_money(amount: Decimal) -> Decimal:
        normalized = Decimal(amount).quantize(_CENT, rounding=ROUND_HALF_UP)
        if not normalized.is_finite() or normalized <= 0:
            raise ValueError("amount must be a positive finite BRL value")
        return normalized

    @staticmethod
    def _required_string(value: Mapping[str, object], key: str) -> str:
        result = value.get(key)
        if not isinstance(result, str) or not result:
            raise ValueError(f"AbacatePay webhook {key} is missing")
        return result

    @staticmethod
    def _cents_to_money(value: object) -> Decimal:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("AbacatePay webhook amount is invalid")
        return (Decimal(value) / Decimal(100)).quantize(_CENT)

    @staticmethod
    def _payment_method_summary(value: object) -> PaymentMethodSummary | None:
        if not isinstance(value, Mapping):
            return None
        method = value.get("method")
        if not isinstance(method, str):
            return None
        if method != "CARD":
            return PaymentMethodSummary(method=method)
        card = value.get("CARD")
        if not isinstance(card, Mapping):
            return PaymentMethodSummary(method=method)
        number = card.get("number")
        brand = card.get("brand")
        return PaymentMethodSummary(
            method=method,
            card_last_four=number if isinstance(number, str) else None,
            card_brand=brand if isinstance(brand, str) else None,
        )
