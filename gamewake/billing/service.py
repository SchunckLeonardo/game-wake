from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, ROUND_UP, Decimal
from math import ceil
from uuid import uuid4

from .contracts import BillingRepository, PaymentProvider
from .model import (
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

    def reserve(
        self,
        account_id: str,
        *,
        amount: Decimal,
        purpose: str,
        idempotency_key: str,
        quote_id: str | None = None,
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
            reservation = UsageReservation(
                id=str(uuid4()),
                account_id=account_id,
                amount=normalized,
                purpose=purpose,
                idempotency_key=idempotency_key,
                status=ReservationStatus.ACTIVE,
                created_at=self._clock(),
                quote_id=quote_id,
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
