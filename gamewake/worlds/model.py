from dataclasses import dataclass
from enum import StrEnum


class WorldStatus(StrEnum):
    SLEEPING = "sleeping"
    WAKING = "waking"
    ONLINE = "online"
    GOING_TO_SLEEP = "going_to_sleep"
    NEEDS_ATTENTION = "needs_attention"


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
