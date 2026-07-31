from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from gamewake.accounts import Permission, PermissionDeniedError
from gamewake.game_catalog import GameCatalog

from .contracts import AccessControl, GameConfigurationCatalog, StorageGate, WorldRepository
from .model import (
    ConfigurationChange,
    ConfigurationChangePreview,
    ConfigurationRevision,
    OperationPhase,
    OperationStatus,
    OperationType,
    World,
    WorldOperation,
    WorldStatus,
)
from .storage import StorageBlockedError


class Worlds:
    def __init__(
        self,
        repository: WorldRepository,
        *,
        access: AccessControl,
        clock: Callable[[], datetime] | None = None,
        game_catalog: GameConfigurationCatalog | None = None,
        storage_gate: StorageGate | None = None,
    ) -> None:
        self._repository = repository
        self._access = access
        self._clock = clock or (lambda: datetime.now(UTC))
        self._game_catalog = game_catalog or GameCatalog.with_palworld()
        self._storage_gate = storage_gate

    def create_world(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        name: str,
        game_template_id: str,
        region: str,
        runtime_profile_id: str,
    ) -> World:
        if not self._access.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.CREATE_WORLD,
        ):
            raise PermissionDeniedError("creating a World requires Owner permission")
        if self._storage_gate is not None and not self._storage_gate.can_create_world(
            account_id
        ):
            raise StorageBlockedError("Storage Grace Period blocks new Worlds")
        world_id = str(uuid4())
        template = self._game_catalog.resolve(game_template_id)
        defaults = {
            field.key: field.default
            for field in template.configuration_fields
        }
        validated_defaults = self._game_catalog.validate_configuration(
            game_template_id,
            defaults,
        )
        initial_configuration = ConfigurationRevision(
            id=str(uuid4()),
            account_id=account_id,
            world_id=world_id,
            game_template_id=game_template_id,
            number=1,
            entries=tuple(validated_defaults.items()),
            idempotency_key=f"world:{world_id}:initial-configuration",
            created_at=self._clock(),
        )
        world = World(
            id=world_id,
            account_id=account_id,
            name=name,
            game_template_id=game_template_id,
            region=region,
            runtime_profile_id=runtime_profile_id,
            status=WorldStatus.SLEEPING,
            runtime_id=None,
            runtime_provider_reference=None,
            configuration_revision_id=initial_configuration.id,
            pending_configuration_revision_id=None,
            stored_state_id=None,
            stored_state_checksum=None,
            version=1,
        )
        self._repository.create(world, initial_configuration)
        return world

    def get_world(
        self,
        account_id: str,
        world_id: str,
        *,
        viewer_user_id: str,
    ) -> World:
        if not self._access.authorize(
            account_id,
            user_id=viewer_user_id,
            permission=Permission.VIEW_WORLD,
            world_id=world_id,
        ):
            raise PermissionDeniedError("the User cannot view this World")
        return self._repository.get(account_id, world_id)

    def get_configuration(
        self,
        account_id: str,
        world_id: str,
        *,
        viewer_user_id: str,
    ) -> ConfigurationRevision:
        world = self.get_world(
            account_id,
            world_id,
            viewer_user_id=viewer_user_id,
        )
        return self._repository.get_configuration(
            account_id,
            world_id,
            world.configuration_revision_id,
        )

    def preview_configuration_change(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        changes: object,
    ) -> ConfigurationChangePreview:
        if not self._access.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.EDIT_WORLD,
            world_id=world_id,
        ):
            raise PermissionDeniedError("the User cannot edit this World")
        world = self._repository.get(account_id, world_id)
        base_revision_id = (
            world.pending_configuration_revision_id
            or world.configuration_revision_id
        )
        base = self._repository.get_configuration(
            account_id,
            world_id,
            base_revision_id,
        )
        normalized_changes = self._game_catalog.validate_configuration(
            world.game_template_id,
            changes,
            partial=True,
        )
        proposed = {**base.values, **normalized_changes}
        validated = self._game_catalog.validate_configuration(
            world.game_template_id,
            proposed,
        )
        fields = {
            field.key: field
            for field in self._game_catalog.resolve(
                world.game_template_id
            ).configuration_fields
        }
        diff = tuple(
            ConfigurationChange(
                key=key,
                current=base.values[key],
                proposed=value,
                restart_required=fields[key].restart_required,
            )
            for key, value in normalized_changes.items()
            if value != base.values[key]
        )
        return ConfigurationChangePreview(
            world_id=world_id,
            base_revision_id=base.id,
            changes=diff,
            proposed_entries=tuple(validated.items()),
        )

    def update_configuration(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        changes: object,
        idempotency_key: str,
    ) -> ConfigurationRevision:
        preview = self.preview_configuration_change(
            account_id,
            world_id,
            actor_user_id=actor_user_id,
            changes=changes,
        )
        world = self._repository.get(account_id, world_id)
        base = self._repository.get_configuration(
            account_id,
            world_id,
            preview.base_revision_id,
        )
        revision = ConfigurationRevision(
            id=str(uuid4()),
            account_id=account_id,
            world_id=world_id,
            game_template_id=world.game_template_id,
            number=base.number + 1,
            entries=preview.proposed_entries,
            idempotency_key=idempotency_key,
            created_at=self._clock(),
        )
        return self._repository.append_configuration(
            replace(
                world,
                pending_configuration_revision_id=revision.id,
                version=world.version + 1,
            ),
            revision,
            expected_world_version=world.version,
        )

    def request_wake(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
    ) -> WorldOperation:
        if not self._access.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.WAKE_WORLD,
            world_id=world_id,
        ):
            raise PermissionDeniedError("the User cannot wake this World")
        if self._storage_gate is not None and not self._storage_gate.can_wake(account_id):
            raise StorageBlockedError("unfunded storage excess blocks waking Worlds")
        world = self._repository.get(account_id, world_id)
        operation = WorldOperation(
            id=str(uuid4()),
            account_id=account_id,
            world_id=world_id,
            operation_type=OperationType.WAKE,
            status=OperationStatus.PENDING,
            phase=OperationPhase.REQUESTED,
            idempotency_key=idempotency_key,
            created_at=self._clock(),
            version=1,
            runtime_id=None,
            runtime_provider_reference=None,
        )
        return self._repository.begin_operation(
            replace(
                world,
                status=WorldStatus.WAKING,
                version=world.version + 1,
            ),
            operation,
            expected_world_version=world.version,
        )

    def request_sleep(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
        force: bool = False,
    ) -> WorldOperation:
        permission = Permission.FORCE_SLEEP_WORLD if force else Permission.SLEEP_EMPTY_WORLD
        if not self._access.authorize(
            account_id,
            user_id=actor_user_id,
            permission=permission,
            world_id=world_id,
        ):
            raise PermissionDeniedError("the User cannot sleep this World")
        world = self._repository.get(account_id, world_id)
        if world.status is not WorldStatus.ONLINE:
            raise ValueError("only an Online World can begin safe sleep")
        operation = WorldOperation(
            id=str(uuid4()),
            account_id=account_id,
            world_id=world_id,
            operation_type=OperationType.SLEEP,
            status=OperationStatus.PENDING,
            phase=OperationPhase.REQUESTED,
            idempotency_key=idempotency_key,
            created_at=self._clock(),
            version=1,
            runtime_id=world.runtime_id,
            runtime_provider_reference=world.runtime_provider_reference,
            force=force,
        )
        return self._repository.begin_operation(
            replace(
                world,
                status=WorldStatus.GOING_TO_SLEEP,
                version=world.version + 1,
            ),
            operation,
            expected_world_version=world.version,
        )

    def request_automatic_recovery(
        self,
        account_id: str,
        world_id: str,
        *,
        detected_at: datetime,
        idempotency_key: str,
    ) -> WorldOperation | None:
        world = self._repository.get(account_id, world_id)
        recent_attempts = [
            operation
            for operation in self._repository.list_operations(account_id, world_id)
            if operation.operation_type is OperationType.RECOVER
            and operation.created_at >= detected_at - timedelta(minutes=15)
        ]
        if len(recent_attempts) >= 3 or world.status is WorldStatus.NEEDS_ATTENTION:
            return None
        if world.status not in {WorldStatus.ONLINE, WorldStatus.WAKING}:
            raise ValueError("Automatic Recovery requires an active Runtime session")
        operation = WorldOperation(
            id=str(uuid4()),
            account_id=account_id,
            world_id=world_id,
            operation_type=OperationType.RECOVER,
            status=OperationStatus.PENDING,
            phase=OperationPhase.REQUESTED,
            idempotency_key=idempotency_key,
            created_at=detected_at,
            version=1,
            runtime_id=world.runtime_id,
            runtime_provider_reference=world.runtime_provider_reference,
            attempt_number=len(recent_attempts) + 1,
        )
        return self._repository.begin_operation(
            replace(
                world,
                status=WorldStatus.WAKING,
                version=world.version + 1,
            ),
            operation,
            expected_world_version=world.version,
        )

    def list_operations(
        self,
        account_id: str,
        world_id: str,
        *,
        viewer_user_id: str,
    ) -> list[WorldOperation]:
        if not self._access.authorize(
            account_id,
            user_id=viewer_user_id,
            permission=Permission.VIEW_WORLD,
            world_id=world_id,
        ):
            raise PermissionDeniedError("the User cannot view this World's operations")
        return list(self._repository.list_operations(account_id, world_id))
