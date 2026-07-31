from typing import Protocol

from gamewake.accounts import Permission

from .model import World


class AccessControl(Protocol):
    def authorize(
        self,
        account_id: str,
        *,
        user_id: str,
        permission: Permission,
        world_id: str | None = None,
    ) -> bool: ...


class WorldRepository(Protocol):
    def create(self, world: World) -> None: ...

    def get(self, account_id: str, world_id: str) -> World: ...

    def save(self, world: World, expected_version: int) -> None: ...
