from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import uuid4

from .model import (
    Backup,
    BackupKind,
    ConfigurationRevision,
    StoredWorldState,
    World,
    WorldExport,
    WorldExportManifest,
)


class InMemoryWorldArchiveStore:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        state_sizes: Mapping[str, int] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._state_sizes = dict(state_sizes or {})
        self._backups: dict[str, Backup] = {}
        self._backup_idempotency: dict[str, str] = {}
        self._exports: dict[str, WorldExport] = {}
        self._export_idempotency: dict[str, str] = {}
        self._deleted_worlds: set[tuple[str, str]] = set()

    def create_automatic(
        self,
        world: World,
        state: StoredWorldState,
        *,
        idempotency_key: str,
    ) -> Backup:
        return self._create_backup(world, state, BackupKind.AUTOMATIC, idempotency_key)

    def create_manual(
        self,
        world: World,
        state: StoredWorldState,
        *,
        idempotency_key: str,
    ) -> Backup:
        return self._create_backup(world, state, BackupKind.MANUAL, idempotency_key)

    def create_restore_point(
        self,
        world: World,
        state: StoredWorldState,
        *,
        idempotency_key: str,
    ) -> Backup:
        return self._create_backup(world, state, BackupKind.RESTORE_POINT, idempotency_key)

    def create_final(
        self,
        world: World,
        state: StoredWorldState,
        *,
        idempotency_key: str,
    ) -> Backup:
        return self._create_backup(world, state, BackupKind.FINAL, idempotency_key)

    def list_backups(self, account_id: str, world_id: str) -> tuple[Backup, ...]:
        return tuple(
            sorted(
                (
                    backup
                    for backup in self._backups.values()
                    if backup.account_id == account_id and backup.world_id == world_id
                ),
                key=lambda backup: backup.created_at or datetime.min.replace(tzinfo=UTC),
            )
        )

    def restore(
        self,
        world: World,
        backup: Backup,
        *,
        idempotency_key: str,
    ) -> StoredWorldState:
        if backup.account_id != world.account_id or backup.world_id != world.id:
            raise KeyError(backup.id)
        return StoredWorldState(
            id=backup.state_id,
            checksum=backup.checksum,
            validated=True,
        )

    def create_export(
        self,
        world: World,
        state: StoredWorldState,
        configuration: ConfigurationRevision,
        *,
        idempotency_key: str,
    ) -> WorldExport:
        existing_id = self._export_idempotency.get(idempotency_key)
        if existing_id is not None:
            return self._exports[existing_id]
        export_id = str(uuid4())
        export = WorldExport(
            id=export_id,
            account_id=world.account_id,
            world_id=world.id,
            download_url=f"memory://exports/{export_id}.zip",
            manifest=WorldExportManifest(
                format_version=1,
                game_template_id=world.game_template_id,
                configuration_revision_id=configuration.id,
                configuration=configuration.entries,
                world_state_id=state.id,
                world_state_checksum=state.checksum,
            ),
            created_at=self._clock(),
        )
        self._exports[export.id] = export
        self._export_idempotency[idempotency_key] = export.id
        return export

    def delete_world_data(
        self,
        account_id: str,
        world_id: str,
        *,
        idempotency_key: str,
    ) -> None:
        self._backups = {
            backup_id: backup
            for backup_id, backup in self._backups.items()
            if backup.account_id != account_id or backup.world_id != world_id
        }
        self._deleted_worlds.add((account_id, world_id))

    def was_world_deleted(self, account_id: str, world_id: str) -> bool:
        return (account_id, world_id) in self._deleted_worlds

    def _create_backup(
        self,
        world: World,
        state: StoredWorldState,
        kind: BackupKind,
        idempotency_key: str,
    ) -> Backup:
        existing_id = self._backup_idempotency.get(idempotency_key)
        if existing_id is not None:
            return self._backups[existing_id]
        if not state.validated:
            raise ValueError("Backup requires a validated World state")
        backup = Backup(
            id=str(uuid4()),
            account_id=world.account_id,
            world_id=world.id,
            state_id=state.id,
            checksum=state.checksum,
            kind=kind,
            size_bytes=self._state_sizes.get(state.id, 0),
            created_at=self._clock(),
        )
        self._backups[backup.id] = backup
        self._backup_idempotency[idempotency_key] = backup.id
        return backup
