from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, ROUND_UP, Decimal
from math import ceil
from uuid import uuid4

from .contracts import BillingRepository
from .model import (
    ConcurrentBillingUpdate,
    InsufficientFundsError,
    LedgerEntry,
    LedgerEntryType,
    ReservationStatus,
    RuntimeUsage,
    SessionQuote,
    UsageReservation,
    Wallet,
    WalletSnapshot,
)

_CENT = Decimal("0.01")


class Billing:
    def __init__(
        self,
        repository: BillingRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_wallet(self, account_id: str) -> Wallet:
        snapshot = self._repository.get(account_id)
        balance = sum((entry.amount for entry in snapshot.entries), start=Decimal("0.00"))
        reserved = sum(
            (
                reservation.amount
                for reservation in snapshot.reservations
                if reservation.status is ReservationStatus.ACTIVE
            ),
            start=Decimal("0.00"),
        )
        return Wallet(
            account_id=account_id,
            currency="BRL",
            balance=balance,
            available_balance=balance - reserved,
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
