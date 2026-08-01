from datetime import datetime
from typing import Protocol

from gamewake.accounts import Permission
from gamewake.game_catalog import GameTemplateDefinition
from gamewake.game_catalog.model import ConfigurationValue

from .model import (
    Backup,
    ConfigurationRevision,
    Runtime,
    StoredWorldState,
    World,
    WorldExport,
    WorldOperation,
)


class AccessControl(Protocol):
    def authorize(
        self,
        account_id: str,
        *,
        user_id: str,
        permission: Permission,
        world_id: str | None = None,
    ) -> bool: ...


class StorageGate(Protocol):
    def can_create_world(self, account_id: str) -> bool: ...

    def can_create_manual_backup(self, account_id: str) -> bool: ...

    def can_wake(self, account_id: str) -> bool: ...


class WorldRepository(Protocol):
    def create(self, world: World, initial_configuration: ConfigurationRevision) -> None: ...

    def get(self, account_id: str, world_id: str) -> World: ...

    def list_worlds(self, account_id: str) -> tuple[World, ...]: ...

    def save(self, world: World, expected_version: int) -> None: ...

    def delete(self, account_id: str, world_id: str) -> None: ...

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

    def get_configuration(
        self,
        account_id: str,
        world_id: str,
        revision_id: str,
    ) -> ConfigurationRevision: ...

    def append_configuration(
        self,
        world: World,
        revision: ConfigurationRevision,
        *,
        expected_world_version: int,
    ) -> ConfigurationRevision: ...


class GameConfigurationCatalog(Protocol):
    def resolve(self, game_template_id: str) -> GameTemplateDefinition: ...

    def validate_configuration(
        self,
        game_template_id: str,
        values: object,
        *,
        partial: bool = False,
    ) -> dict[str, ConfigurationValue]: ...


class RuntimeProvider(Protocol):
    def provision(self, world: World, *, idempotency_key: str) -> Runtime: ...

    def release(self, runtime: Runtime, *, idempotency_key: str) -> None: ...


class RuntimeUsageRecorder(Protocol):
    def protect(self, world: World, *, observed_at: datetime) -> object: ...

    def cancel(self, operation: WorldOperation) -> object: ...

    def record_release(
        self,
        operation: WorldOperation,
        *,
        runtime_released_at: datetime,
        reached_online: bool,
    ) -> object: ...


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


class WorldArchiveStore(BackupStore, Protocol):
    def create_manual(
        self,
        world: World,
        state: StoredWorldState,
        *,
        idempotency_key: str,
    ) -> Backup: ...

    def create_restore_point(
        self,
        world: World,
        state: StoredWorldState,
        *,
        idempotency_key: str,
    ) -> Backup: ...

    def create_final(
        self,
        world: World,
        state: StoredWorldState,
        *,
        idempotency_key: str,
    ) -> Backup: ...

    def list_backups(self, account_id: str, world_id: str) -> tuple[Backup, ...]: ...

    def restore(
        self,
        world: World,
        backup: Backup,
        *,
        idempotency_key: str,
    ) -> StoredWorldState: ...

    def create_export(
        self,
        world: World,
        state: StoredWorldState,
        configuration: ConfigurationRevision,
        *,
        idempotency_key: str,
    ) -> WorldExport: ...

    def delete_world_data(
        self,
        account_id: str,
        world_id: str,
        *,
        idempotency_key: str,
    ) -> None: ...
