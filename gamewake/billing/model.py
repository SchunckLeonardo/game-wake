from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class InsufficientFundsError(ValueError):
    """Raised before a reservation could make available balance negative."""


class ConcurrentBillingUpdate(RuntimeError):
    """Signals optimistic concurrency so Billing can reload and retry."""


class WorldBudgetExceeded(ValueError):
    """Raised before a reservation could exceed a World's monthly limit."""


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


class ContributionStatus(StrEnum):
    CREATING_CHECKOUT = "creating_checkout"
    PENDING = "pending"
    COMPLETED = "completed"
    REFUND_REQUESTED = "refund_requested"
    REFUNDED = "refunded"
    DISPUTED = "disputed"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True)
class ContributionPackage:
    id: str
    amount: Decimal
    provider_product_id: str


@dataclass(frozen=True)
class ContributionCheckoutRequest:
    external_id: str
    provider_product_id: str
    expected_amount: Decimal
    return_url: str
    completion_url: str


@dataclass(frozen=True)
class PaymentCheckout:
    id: str
    external_id: str
    url: str
    amount: Decimal
    status: str = "PENDING"
    paid_amount: Decimal | None = None


@dataclass(frozen=True)
class PaymentMethodSummary:
    method: str
    card_last_four: str | None = None
    card_brand: str | None = None


@dataclass(frozen=True)
class WalletContribution:
    id: str
    account_id: str
    payer_user_id: str
    package_id: str
    amount: Decimal
    provider_product_id: str
    provider_checkout_id: str | None
    checkout_url: str | None
    return_url: str
    completion_url: str
    status: ContributionStatus
    idempotency_key: str
    created_at: datetime
    payment_method: PaymentMethodSummary | None
    provider_refund_id: str | None


@dataclass(frozen=True)
class ProcessedPaymentEvent:
    id: str
    event_type: str
    contribution_id: str
    processed_at: datetime


@dataclass(frozen=True)
class BalanceGuardState:
    reservation_id: str
    notified_alert_minutes: tuple[int, ...]


@dataclass(frozen=True)
class BalanceGuardDecision:
    reservation_id: str
    reserved_amount: Decimal
    remaining_minutes: int
    new_alert_minutes: tuple[int, ...]
    new_budget_alert_percentages: tuple[int, ...]
    safe_sleep_reserved: bool
    should_sleep: bool
    reason: str | None


@dataclass(frozen=True)
class WorldBudget:
    id: str
    account_id: str
    world_id: str
    monthly_limit: Decimal
    idempotency_key: str
    updated_at: datetime


@dataclass(frozen=True)
class WorldBudgetAlertState:
    world_id: str
    period: str
    notified_percentages: tuple[int, ...]


@dataclass(frozen=True)
class WorldBudgetStatus:
    world_id: str
    period: str
    monthly_limit: Decimal
    spent: Decimal
    reserved: Decimal
    committed: Decimal
    percentage: Decimal
    wake_allowed: bool


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
    world_id: str | None = None


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
    contributions: tuple[WalletContribution, ...]
    payment_events: tuple[ProcessedPaymentEvent, ...]
    balance_guards: tuple[BalanceGuardState, ...]
    world_budgets: tuple[WorldBudget, ...]
    world_budget_alerts: tuple[WorldBudgetAlertState, ...]
    version: int


@dataclass(frozen=True)
class Wallet:
    account_id: str
    currency: str
    balance: Decimal
    available_balance: Decimal
    statement: tuple[LedgerEntry, ...]
    reservations: tuple[UsageReservation, ...]
