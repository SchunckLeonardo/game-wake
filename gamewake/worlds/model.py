from dataclasses import dataclass
from enum import StrEnum


class WorldStatus(StrEnum):
    SLEEPING = "sleeping"
    WAKING = "waking"
    ONLINE = "online"
    GOING_TO_SLEEP = "going_to_sleep"
    NEEDS_ATTENTION = "needs_attention"


class OperationType(StrEnum):
    WAKE = "wake"
    SLEEP = "sleep"
    RECOVER = "recover"


class OperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
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
    version: int


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


@dataclass(frozen=True)
class WorldOperation:
    id: str
    account_id: str
    world_id: str
    operation_type: OperationType
    status: OperationStatus
    phase: OperationPhase
    idempotency_key: str
    version: int
    runtime_id: str | None = None
    runtime_provider_reference: str | None = None
    force: bool = False
    stored_state_id: str | None = None
    stored_state_checksum: str | None = None
    backup_id: str | None = None
