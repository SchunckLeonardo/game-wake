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


@dataclass(frozen=True)
class WorldPasswordSettings:
    mode: str


class WorldPasswordManager(Protocol):
    def get(self, world: World) -> WorldPasswordSettings: ...

    def configure(
        self,
        world: World,
        *,
        mode: str,
        password: str | None,
    ) -> WorldPasswordSettings: ...


class OperationDispatcher(Protocol):
    def start(self, account_id: str, operation_id: str) -> object: ...
