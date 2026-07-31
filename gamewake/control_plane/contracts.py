from dataclasses import dataclass
from typing import Protocol

from gamewake.worlds import World


@dataclass(frozen=True)
class ConnectionDetails:
    host: str
    port: int
    password: str | None = None


class ConnectionDetailsProvider(Protocol):
    def issue(self, world: World, *, viewer_user_id: str) -> ConnectionDetails: ...
