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
    NEEDS_ATTENTION = "needs_attention"


class OperationPhase(StrEnum):
    REQUESTED = "requested"
    PROVISIONING_RUNTIME = "provisioning_runtime"
    RESTORING_WORLD = "restoring_world"
    APPLYING_CONFIGURATION = "applying_configuration"
    STARTING_GAME = "starting_game"
    CHECKING_GAME_HEALTH = "checking_game_health"
    ONLINE = "online"
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
    version: int


@dataclass(frozen=True)
class Runtime:
    id: str
    provider_reference: str


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
