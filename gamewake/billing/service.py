from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from .contracts import BillingRepository
from .model import (
    ConcurrentBillingUpdate,
    InsufficientFundsError,
    LedgerEntry,
    LedgerEntryType,
    ReservationStatus,
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
