from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class WorldStatus(StrEnum):
    SLEEPING = "sleeping"
    WAKING = "waking"
    ONLINE = "online"
    GOING_TO_SLEEP = "going_to_sleep"
    NEEDS_ATTENTION = "needs_attention"
    PENDING_DELETION = "pending_deletion"


class BackupKind(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    RESTORE_POINT = "restore_point"
    FINAL = "final"


class OperationType(StrEnum):
    WAKE = "wake"
    SLEEP = "sleep"
    RECOVER = "recover"


class OperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
    FAILED = "failed"
    NEEDS_ATTENTION = "needs_attention"


class OperationPhase(StrEnum):
    REQUESTED = "requested"
    PROVISIONING_RUNTIME = "provisioning_runtime"
    RESTORING_WORLD = "restoring_world"
    APPLYING_CONFIGURATION = "applying_configuration"
    STARTING_GAME = "starting_game"
    CHECKING_GAME_HEALTH = "checking_game_health"
    ONLINE = "online"
    CHECKING_PLAYERS = "checking_players"
    SAVING_GAME = "saving_game"
    STOPPING_GAME = "stopping_game"
    PERSISTING_WORLD = "persisting_world"
    CREATING_BACKUP = "creating_backup"
    RELEASING_RUNTIME = "releasing_runtime"
    COMPLETE = "complete"


@dataclass(frozen=True)
class World:
    id: str
    account_id: str
    name: str
    game_template_id: str
    region: str
    runtime_profile_id: str
    status: WorldStatus
    runtime_id: str | None
    runtime_provider_reference: str | None
    configuration_revision_id: str
    pending_configuration_revision_id: str | None
    stored_state_id: str | None
    stored_state_checksum: str | None
    version: int
    session_quote_id: str | None = None
    usage_reservation_id: str | None = None
    runtime_started_at: datetime | None = None
    empty_since: datetime | None = None
    deletion_scheduled_for: datetime | None = None
    final_backup_id: str | None = None
    applied_data_operations: tuple[str, ...] = ()
    auto_sleep_minutes: int | None = 20


@dataclass(frozen=True)
class Runtime:
    id: str
    provider_reference: str


@dataclass(frozen=True)
class StoredWorldState:
    id: str
    checksum: str
    validated: bool


@dataclass(frozen=True)
class Backup:
    id: str
    account_id: str
    world_id: str
    state_id: str
    checksum: str
    kind: BackupKind = BackupKind.AUTOMATIC
    size_bytes: int = 0
    created_at: datetime | None = None


@dataclass(frozen=True)
class WorldExportManifest:
    format_version: int
    game_template_id: str
    configuration_revision_id: str
    configuration: tuple[tuple[str, ConfigurationValue], ...]
    world_state_id: str
    world_state_checksum: str


@dataclass(frozen=True)
class WorldExport:
    id: str
    account_id: str
    world_id: str
    download_url: str
    manifest: WorldExportManifest
    created_at: datetime


ConfigurationValue = str | int | float | bool


@dataclass(frozen=True)
class ConfigurationRevision:
    id: str
    account_id: str
    world_id: str
    game_template_id: str
    number: int
    entries: tuple[tuple[str, ConfigurationValue], ...]
    idempotency_key: str
    created_at: datetime
    actor_user_id: str = "system"
    origin: str = "system"

    @property
    def values(self) -> dict[str, ConfigurationValue]:
        return dict(self.entries)


@dataclass(frozen=True)
class ConfigurationChange:
    key: str
    current: ConfigurationValue
    proposed: ConfigurationValue
    restart_required: bool


@dataclass(frozen=True)
class ConfigurationChangePreview:
    world_id: str
    base_revision_id: str
    changes: tuple[ConfigurationChange, ...]
    proposed_entries: tuple[tuple[str, ConfigurationValue], ...]


@dataclass(frozen=True)
class WorldOperation:
    id: str
    account_id: str
    world_id: str
    operation_type: OperationType
    status: OperationStatus
    phase: OperationPhase
    idempotency_key: str
    created_at: datetime
    version: int
    runtime_id: str | None = None
    runtime_provider_reference: str | None = None
    force: bool = False
    stored_state_id: str | None = None
    stored_state_checksum: str | None = None
    backup_id: str | None = None
    attempt_number: int = 0
    session_quote_id: str | None = None
    usage_reservation_id: str | None = None
    runtime_started_at: datetime | None = None
