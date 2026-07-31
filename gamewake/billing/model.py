from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class InsufficientFundsError(ValueError):
    """Raised before a reservation could make available balance negative."""


class ConcurrentBillingUpdate(RuntimeError):
    """Signals optimistic concurrency so Billing can reload and retry."""


class LedgerEntryType(StrEnum):
    CONTRIBUTION = "contribution"
    RUNTIME_CHARGE = "runtime_charge"
    WAKE_GUARANTEE = "wake_guarantee"
    AVAILABILITY_CREDIT = "availability_credit"
    REFUND = "refund"
    DISPUTE = "dispute"


class ReservationStatus(StrEnum):
    ACTIVE = "active"
    CAPTURED = "captured"
    RELEASED = "released"


@dataclass(frozen=True)
class LedgerEntry:
    id: str
    account_id: str
    entry_type: LedgerEntryType
    amount: Decimal
    reference: str
    idempotency_key: str
    occurred_at: datetime


@dataclass(frozen=True)
class UsageReservation:
    id: str
    account_id: str
    amount: Decimal
    purpose: str
    idempotency_key: str
    status: ReservationStatus
    created_at: datetime
    quote_id: str | None = None


@dataclass(frozen=True)
class SessionQuote:
    id: str
    account_id: str
    world_id: str
    runtime_profile_id: str
    hourly_rate: Decimal
    idempotency_key: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class RuntimeUsage:
    id: str
    account_id: str
    world_id: str
    quote_id: str
    reservation_id: str
    billable_seconds: int
    amount: Decimal
    runtime_started_at: datetime
    runtime_released_at: datetime
    ledger_entry_id: str
    idempotency_key: str


@dataclass(frozen=True)
class WalletSnapshot:
    account_id: str
    entries: tuple[LedgerEntry, ...]
    reservations: tuple[UsageReservation, ...]
    quotes: tuple[SessionQuote, ...]
    usages: tuple[RuntimeUsage, ...]
    version: int


@dataclass(frozen=True)
class Wallet:
    account_id: str
    currency: str
    balance: Decimal
    available_balance: Decimal
    statement: tuple[LedgerEntry, ...]
    reservations: tuple[UsageReservation, ...]
