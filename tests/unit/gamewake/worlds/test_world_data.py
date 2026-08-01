from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from gamewake.accounts import (
    Accounts,
    InMemoryAccountRepository,
    SensitiveActionConfirmation,
    SensitiveActionConfirmationError,
)
from gamewake.worlds import (
    BackupKind,
    InMemoryWorldArchiveStore,
    InMemoryWorldRepository,
    WorldData,
    Worlds,
    WorldStatus,
)


def _sleeping_world_with_state(now):
    accounts = Accounts(InMemoryAccountRepository(), clock=lambda: now)
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    repository = InMemoryWorldRepository()
    worlds = Worlds(repository, access=accounts, clock=lambda: now)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="br-sao-paulo",
        runtime_profile_id="palworld-small",
    )
    stored = replace(
        world,
        stored_state_id="state-1",
        stored_state_checksum="sha256:state-1",
        version=world.version + 1,
    )
    repository.save(stored, expected_version=world.version)
    return accounts, account, repository, worlds, stored


def test_manual_backup_and_restore_preserve_a_point_of_return():
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    accounts, account, repository, _, world = _sleeping_world_with_state(now)
    archive = InMemoryWorldArchiveStore(
        clock=lambda: now,
        state_sizes={"state-1": 100, "state-2": 120},
    )
    data = WorldData(repository, access=accounts, archive_store=archive, clock=lambda: now)
    original = data.create_manual_backup(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="manual-1",
    )
    changed = replace(
        repository.get(account.id, world.id),
        stored_state_id="state-2",
        stored_state_checksum="sha256:state-2",
        version=repository.get(account.id, world.id).version + 1,
    )
    repository.save(changed, expected_version=world.version)

    restored = data.restore_backup(
        account.id,
        world.id,
        original.id,
        actor_user_id="owner",
        idempotency_key="restore-1",
    )

    backups = data.list_backups(
        account.id,
        world.id,
        viewer_user_id="owner",
    )
    assert original.kind is BackupKind.MANUAL
    assert original.size_bytes == 100
    assert restored.stored_state_id == "state-1"
    assert restored.stored_state_checksum == "sha256:state-1"
    assert [backup.kind for backup in backups] == [
        BackupKind.MANUAL,
        BackupKind.RESTORE_POINT,
    ]
    assert backups[1].state_id == "state-2"


def test_export_contains_native_state_configuration_and_versions():
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    accounts, account, repository, _, world = _sleeping_world_with_state(now)
    data = WorldData(
        repository,
        access=accounts,
        archive_store=InMemoryWorldArchiveStore(clock=lambda: now),
        clock=lambda: now,
    )

    export = data.create_export(
        account.id,
        world.id,
        actor_user_id="owner",
        idempotency_key="export-1",
    )

    assert export.download_url.endswith(f"/{export.id}.zip")
    assert export.manifest.format_version == 1
    assert export.manifest.game_template_id == "palworld:1"
    assert export.manifest.world_state_id == "state-1"
    assert export.manifest.world_state_checksum == "sha256:state-1"
    assert dict(export.manifest.configuration)["enemy_drop_item_rate"] == 1.0


def test_world_deletion_requires_step_up_and_can_be_cancelled_for_seven_days():
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    accounts, account, repository, _, world = _sleeping_world_with_state(now)
    archive = InMemoryWorldArchiveStore(clock=lambda: now)
    data = WorldData(repository, access=accounts, archive_store=archive, clock=lambda: now)

    with pytest.raises(SensitiveActionConfirmationError):
        data.schedule_deletion(
            account.id,
            world.id,
            actor_user_id="owner",
            confirmation=None,
            idempotency_key="delete-1",
        )
    pending = data.schedule_deletion(
        account.id,
        world.id,
        actor_user_id="owner",
        confirmation=SensitiveActionConfirmation(
            actor_user_id="owner",
            reauthenticated_at=now,
            confirmed_resource_name="Palpagos",
        ),
        idempotency_key="delete-1",
    )

    assert pending.status is WorldStatus.PENDING_DELETION
    assert pending.deletion_scheduled_for == now + timedelta(days=7)
    [final_backup] = data.list_backups(
        account.id,
        world.id,
        viewer_user_id="owner",
    )
    assert final_backup.kind is BackupKind.FINAL
    assert final_backup.id == pending.final_backup_id

    cancelled = data.cancel_deletion(
        account.id,
        world.id,
        actor_user_id="owner",
    )
    assert cancelled.status is WorldStatus.SLEEPING
    assert cancelled.deletion_scheduled_for is None


def test_due_pending_deletion_removes_game_data_but_not_before_deadline():
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    accounts, account, repository, _, world = _sleeping_world_with_state(now)
    archive = InMemoryWorldArchiveStore(clock=lambda: now)
    data = WorldData(repository, access=accounts, archive_store=archive, clock=lambda: now)
    data.schedule_deletion(
        account.id,
        world.id,
        actor_user_id="owner",
        confirmation=SensitiveActionConfirmation(
            actor_user_id="owner",
            reauthenticated_at=now,
            confirmed_resource_name="Palpagos",
        ),
        idempotency_key="delete-1",
    )

    assert (
        data.purge_due_deletion(
            account.id,
            world.id,
            observed_at=now + timedelta(days=6),
        )
        is False
    )
    assert repository.get(account.id, world.id).status is WorldStatus.PENDING_DELETION

    assert (
        data.purge_due_deletion(
            account.id,
            world.id,
            observed_at=now + timedelta(days=7),
        )
        is True
    )
    with pytest.raises(KeyError):
        repository.get(account.id, world.id)
    assert archive.was_world_deleted(account.id, world.id)
