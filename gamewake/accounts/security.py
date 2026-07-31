from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class ActivityAction(StrEnum):
    MEMBERSHIP_REVOKED = "membership.revoked"


@dataclass(frozen=True)
class ActivityEvent:
    id: str
    account_id: str
    actor_user_id: str
    action: ActivityAction
    subject_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class SensitiveActionConfirmation:
    actor_user_id: str
    reauthenticated_at: datetime
    confirmed_resource_name: str


class SensitiveActionConfirmationError(PermissionError):
    """Raised when a sensitive mutation lacks valid recent confirmation."""


class SecurityNotifier(Protocol):
    def notify_owners(
        self,
        owner_user_ids: frozenset[str],
        action: ActivityAction,
        subject_id: str,
    ) -> None: ...


class NoOpSecurityNotifier:
    def notify_owners(
        self,
        owner_user_ids: frozenset[str],
        action: ActivityAction,
        subject_id: str,
    ) -> None:
        pass


class InMemorySecurityNotifier:
    def __init__(self) -> None:
        self.notifications: list[tuple[frozenset[str], ActivityAction, str]] = []

    def notify_owners(
        self,
        owner_user_ids: frozenset[str],
        action: ActivityAction,
        subject_id: str,
    ) -> None:
        self.notifications.append((owner_user_ids, action, subject_id))
