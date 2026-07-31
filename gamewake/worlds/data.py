from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from gamewake.accounts import (
    Permission,
    PermissionDeniedError,
    SensitiveActionConfirmation,
    SensitiveActionConfirmationError,
)

from .contracts import AccessControl, WorldArchiveStore, WorldRepository
from .model import Backup, StoredWorldState, World, WorldExport, WorldStatus


class WorldData:
    def __init__(
        self,
        repository: WorldRepository,
        *,
        access: AccessControl,
        archive_store: WorldArchiveStore,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._access = access
        self._archive_store = archive_store
        self._clock = clock or (lambda: datetime.now(UTC))

    def list_backups(
        self,
        account_id: str,
        world_id: str,
        *,
        viewer_user_id: str,
    ) -> tuple[Backup, ...]:
        self._require_permission(
            account_id,
            world_id,
            viewer_user_id,
            Permission.VIEW_WORLD,
        )
        return self._archive_store.list_backups(account_id, world_id)

    def create_manual_backup(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
    ) -> Backup:
        self._require_permission(
            account_id,
            world_id,
            actor_user_id,
            Permission.CREATE_BACKUP,
        )
        world = self._repository.get(account_id, world_id)
        self._require_sleeping(world)
        return self._archive_store.create_manual(
            world,
            self._stored_state(world),
            idempotency_key=idempotency_key,
        )

    def restore_backup(
        self,
        account_id: str,
        world_id: str,
        backup_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
    ) -> World:
        self._require_permission(
            account_id,
            world_id,
            actor_user_id,
            Permission.RESTORE_BACKUP,
        )
        world = self._repository.get(account_id, world_id)
        self._require_sleeping(world)
        if idempotency_key in world.applied_data_operations:
            return world
        backup = next(
            item
            for item in self._archive_store.list_backups(account_id, world_id)
            if item.id == backup_id
        )
        self._archive_store.create_restore_point(
            world,
            self._stored_state(world),
            idempotency_key=f"{idempotency_key}:restore-point",
        )
        restored = self._archive_store.restore(
            world,
            backup,
            idempotency_key=f"{idempotency_key}:restore",
        )
        if not restored.validated:
            raise ValueError("restored World state did not validate")
        updated = replace(
            world,
            stored_state_id=restored.id,
            stored_state_checksum=restored.checksum,
            applied_data_operations=(*world.applied_data_operations, idempotency_key),
            version=world.version + 1,
        )
        self._repository.save(updated, expected_version=world.version)
        return updated

    def create_export(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
    ) -> WorldExport:
        self._require_permission(
            account_id,
            world_id,
            actor_user_id,
            Permission.EXPORT_WORLD,
        )
        world = self._repository.get(account_id, world_id)
        configuration = self._repository.get_configuration(
            account_id,
            world_id,
            world.configuration_revision_id,
        )
        return self._archive_store.create_export(
            world,
            self._stored_state(world),
            configuration,
            idempotency_key=idempotency_key,
        )

    def schedule_deletion(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        confirmation: SensitiveActionConfirmation | None,
        idempotency_key: str,
    ) -> World:
        self._require_permission(
            account_id,
            world_id,
            actor_user_id,
            Permission.DELETE_WORLD,
        )
        world = self._repository.get(account_id, world_id)
        self._verify_sensitive_confirmation(world, actor_user_id, confirmation)
        if world.status is WorldStatus.PENDING_DELETION:
            return world
        self._require_sleeping(world)
        final_backup = self._archive_store.create_final(
            world,
            self._stored_state(world),
            idempotency_key=f"{idempotency_key}:final-backup",
        )
        pending = replace(
            world,
            status=WorldStatus.PENDING_DELETION,
            deletion_scheduled_for=self._clock() + timedelta(days=7),
            final_backup_id=final_backup.id,
            version=world.version + 1,
        )
        self._repository.save(pending, expected_version=world.version)
        return pending

    def cancel_deletion(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
    ) -> World:
        self._require_permission(
            account_id,
            world_id,
            actor_user_id,
            Permission.DELETE_WORLD,
        )
        world = self._repository.get(account_id, world_id)
        if world.status is not WorldStatus.PENDING_DELETION:
            raise ValueError("World is not pending deletion")
        restored = replace(
            world,
            status=WorldStatus.SLEEPING,
            deletion_scheduled_for=None,
            final_backup_id=None,
            version=world.version + 1,
        )
        self._repository.save(restored, expected_version=world.version)
        return restored

    def purge_due_deletion(
        self,
        account_id: str,
        world_id: str,
        *,
        observed_at: datetime,
    ) -> bool:
        world = self._repository.get(account_id, world_id)
        if (
            world.status is not WorldStatus.PENDING_DELETION
            or world.deletion_scheduled_for is None
            or observed_at < world.deletion_scheduled_for
        ):
            return False
        self._archive_store.delete_world_data(
            account_id,
            world_id,
            idempotency_key=f"world:{world_id}:purge",
        )
        self._repository.delete(account_id, world_id)
        return True

    def _require_permission(
        self,
        account_id: str,
        world_id: str,
        user_id: str,
        permission: Permission,
    ) -> None:
        if not self._access.authorize(
            account_id,
            user_id=user_id,
            permission=permission,
            world_id=world_id,
        ):
            raise PermissionDeniedError(f"the User lacks {permission.value}")

    @staticmethod
    def _require_sleeping(world: World) -> None:
        if world.status is not WorldStatus.SLEEPING:
            raise ValueError("World data mutation requires a Sleeping World")

    @staticmethod
    def _stored_state(world: World) -> StoredWorldState:
        if world.stored_state_id is None or world.stored_state_checksum is None:
            raise ValueError("World has no validated stored state")
        return StoredWorldState(
            id=world.stored_state_id,
            checksum=world.stored_state_checksum,
            validated=True,
        )

    def _verify_sensitive_confirmation(
        self,
        world: World,
        actor_user_id: str,
        confirmation: SensitiveActionConfirmation | None,
    ) -> None:
        if confirmation is None:
            raise SensitiveActionConfirmationError(
                "World deletion requires recent reauthentication and exact name confirmation"
            )
        age = self._clock() - confirmation.reauthenticated_at
        if (
            confirmation.actor_user_id != actor_user_id
            or confirmation.confirmed_resource_name != world.name
            or age < timedelta(0)
            or age > timedelta(minutes=5)
        ):
            raise SensitiveActionConfirmationError(
                "World deletion requires recent reauthentication and exact name confirmation"
            )
