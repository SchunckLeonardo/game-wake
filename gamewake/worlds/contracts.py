from typing import Protocol

from gamewake.accounts import Permission

from .model import Backup, Runtime, StoredWorldState, World, WorldOperation


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

    def begin_operation(
        self,
        world: World,
        operation: WorldOperation,
        *,
        expected_world_version: int,
    ) -> WorldOperation: ...

    def list_operations(
        self,
        account_id: str,
        world_id: str,
    ) -> tuple[WorldOperation, ...]: ...

    def get_operation(self, account_id: str, operation_id: str) -> WorldOperation: ...

    def save_operation(
        self,
        operation: WorldOperation,
        *,
        expected_operation_version: int,
        world: World | None = None,
        expected_world_version: int | None = None,
    ) -> None: ...


class RuntimeProvider(Protocol):
    def provision(self, world: World, *, idempotency_key: str) -> Runtime: ...

    def release(self, runtime: Runtime, *, idempotency_key: str) -> None: ...


class WorldStateStore(Protocol):
    def restore(
        self,
        world: World,
        runtime: Runtime,
        *,
        idempotency_key: str,
    ) -> None: ...

    def persist_and_validate(
        self,
        world: World,
        runtime: Runtime,
        *,
        idempotency_key: str,
    ) -> StoredWorldState: ...


class GameTemplate(Protocol):
    def apply_configuration(
        self,
        world: World,
        runtime: Runtime,
        *,
        idempotency_key: str,
    ) -> None: ...

    def start(
        self,
        world: World,
        runtime: Runtime,
        *,
        idempotency_key: str,
    ) -> None: ...

    def is_healthy(self, world: World, runtime: Runtime) -> bool: ...

    def player_count(self, world: World, runtime: Runtime) -> int: ...

    def save(
        self,
        world: World,
        runtime: Runtime,
        *,
        idempotency_key: str,
    ) -> None: ...

    def stop(
        self,
        world: World,
        runtime: Runtime,
        *,
        idempotency_key: str,
    ) -> None: ...


class GameTemplateResolver(Protocol):
    def resolve(self, game_template_id: str) -> GameTemplate: ...


class BackupStore(Protocol):
    def create_automatic(
        self,
        world: World,
        state: StoredWorldState,
        *,
        idempotency_key: str,
    ) -> Backup: ...
