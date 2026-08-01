from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Protocol

from .contracts import WorldRepository
from .model import Backup, World


class StorageBlockedError(ValueError):
    """Raised when unpaid storage policy blocks a data-growing action or wake."""


@dataclass(frozen=True)
class StoragePolicy:
    allowance_bytes: int
    grace_days: int = 30

    def __post_init__(self) -> None:
        if self.allowance_bytes < 0 or self.grace_days <= 0:
            raise ValueError("Storage Policy values must be non-negative")


@dataclass(frozen=True)
class StorageGraceState:
    account_id: str
    started_at: datetime
    version: int


@dataclass(frozen=True)
class StorageStatus:
    account_id: str
    used_bytes: int
    allowance_bytes: int
    excess_bytes: int
    grace_started_at: datetime | None
    grace_ends_at: datetime | None
    manual_backups_blocked: bool
    new_worlds_blocked: bool
    wake_blocked: bool
    pruned_backup_ids: tuple[str, ...]


class StoragePolicyRepository(Protocol):
    def get(self, account_id: str) -> StorageGraceState | None: ...

    def save(self, state: StorageGraceState, *, expected_version: int) -> None: ...

    def clear(self, account_id: str, *, expected_version: int) -> None: ...

    def get_status(self, account_id: str) -> StorageStatus | None: ...

    def save_status(self, status: StorageStatus) -> None: ...


class StorageArchive(Protocol):
    def storage_usage(self, account_id: str, worlds: tuple[World, ...]) -> int: ...

    def prune_oldest_automatic(
        self,
        account_id: str,
        worlds: tuple[World, ...],
        *,
        bytes_to_free: int,
    ) -> tuple[Backup, ...]: ...


class InMemoryStoragePolicyRepository:
    def __init__(self) -> None:
        self._states: dict[str, StorageGraceState] = {}
        self._statuses: dict[str, StorageStatus] = {}
        self._lock = RLock()

    def get(self, account_id: str) -> StorageGraceState | None:
        return self._states.get(account_id)

    def save(self, state: StorageGraceState, *, expected_version: int) -> None:
        with self._lock:
            current = self._states.get(state.account_id)
            current_version = current.version if current is not None else 0
            if current_version != expected_version:
                raise RuntimeError("Storage Grace Period was changed concurrently")
            self._states[state.account_id] = StorageGraceState(
                account_id=state.account_id,
                started_at=state.started_at,
                version=expected_version + 1,
            )

    def clear(self, account_id: str, *, expected_version: int) -> None:
        with self._lock:
            current = self._states.get(account_id)
            current_version = current.version if current is not None else 0
            if current_version != expected_version:
                raise RuntimeError("Storage Grace Period was changed concurrently")
            self._states.pop(account_id, None)

    def get_status(self, account_id: str) -> StorageStatus | None:
        return self._statuses.get(account_id)

    def save_status(self, status: StorageStatus) -> None:
        self._statuses[status.account_id] = status


class StoragePolicyService:
    def __init__(
        self,
        worlds: WorldRepository,
        *,
        archive_store: StorageArchive,
        repository: StoragePolicyRepository,
        policy: StoragePolicy,
    ) -> None:
        self._worlds = worlds
        self._archive_store = archive_store
        self._repository = repository
        self._policy = policy

    def evaluate(
        self,
        account_id: str,
        *,
        wallet_can_fund: bool,
        observed_at: datetime,
    ) -> StorageStatus:
        worlds = self._worlds.list_worlds(account_id)
        used = self._archive_store.storage_usage(account_id, worlds)
        grace = self._repository.get(account_id)
        if used <= self._policy.allowance_bytes or wallet_can_fund:
            if grace is not None:
                self._repository.clear(account_id, expected_version=grace.version)
            return self._persist_status(
                self._status(account_id, used, None, (), wake_blocked=False)
            )

        if grace is None:
            self._repository.save(
                StorageGraceState(account_id=account_id, started_at=observed_at, version=0),
                expected_version=0,
            )
            grace = self._repository.get(account_id)
        if grace is None:
            raise RuntimeError("Storage Grace Period was not persisted")
        grace_ends_at = grace.started_at + timedelta(days=self._policy.grace_days)
        pruned: tuple[Backup, ...] = ()
        if observed_at >= grace_ends_at:
            pruned = self._archive_store.prune_oldest_automatic(
                account_id,
                worlds,
                bytes_to_free=used - self._policy.allowance_bytes,
            )
            used = self._archive_store.storage_usage(account_id, worlds)
            if used <= self._policy.allowance_bytes:
                self._repository.clear(account_id, expected_version=grace.version)
                grace = None
        return self._persist_status(
            self._status(
                account_id,
                used,
                grace,
                tuple(backup.id for backup in pruned),
                wake_blocked=grace is not None and observed_at >= grace_ends_at,
            )
        )

    def can_create_world(self, account_id: str) -> bool:
        status = self._repository.get_status(account_id)
        return status is None or not status.new_worlds_blocked

    def can_create_manual_backup(self, account_id: str) -> bool:
        status = self._repository.get_status(account_id)
        return status is None or not status.manual_backups_blocked

    def can_wake(self, account_id: str) -> bool:
        status = self._repository.get_status(account_id)
        return status is None or not status.wake_blocked

    def _persist_status(self, status: StorageStatus) -> StorageStatus:
        self._repository.save_status(status)
        return status

    def _status(
        self,
        account_id: str,
        used_bytes: int,
        grace: StorageGraceState | None,
        pruned_backup_ids: tuple[str, ...],
        *,
        wake_blocked: bool,
    ) -> StorageStatus:
        grace_ends_at = (
            grace.started_at + timedelta(days=self._policy.grace_days)
            if grace is not None
            else None
        )
        blocked = grace is not None
        return StorageStatus(
            account_id=account_id,
            used_bytes=used_bytes,
            allowance_bytes=self._policy.allowance_bytes,
            excess_bytes=max(0, used_bytes - self._policy.allowance_bytes),
            grace_started_at=grace.started_at if grace is not None else None,
            grace_ends_at=grace_ends_at,
            manual_backups_blocked=blocked,
            new_worlds_blocked=blocked,
            wake_blocked=wake_blocked,
            pruned_backup_ids=pruned_backup_ids,
        )
