from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from gamewake.accounts import Accounts, InMemoryAccountRepository
from gamewake.worlds import (
    BackupKind,
    InMemoryStoragePolicyRepository,
    InMemoryWorldArchiveStore,
    InMemoryWorldRepository,
    StorageBlockedError,
    StoragePolicy,
    StoragePolicyService,
    StoredWorldState,
    WorldData,
    Worlds,
)


def test_unfunded_excess_gets_thirty_day_grace_then_prunes_only_automatic_backups():
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    accounts = Accounts(InMemoryAccountRepository())
    account = accounts.create_account(name="Sexta com os amigos", owner_user_id="owner")
    worlds_repository = InMemoryWorldRepository()
    worlds = Worlds(worlds_repository, access=accounts)
    world = worlds.create_world(
        account.id,
        actor_user_id="owner",
        name="Palpagos",
        game_template_id="palworld:1",
        region="br-sao-paulo",
        runtime_profile_id="palworld-small",
    )
    current = replace(
        world,
        stored_state_id="current",
        stored_state_checksum="sha256:current",
        version=world.version + 1,
    )
    worlds_repository.save(current, expected_version=world.version)
    archive = InMemoryWorldArchiveStore(
        clock=lambda: now,
        state_sizes={
            "current": 60,
            "automatic-1": 30,
            "automatic-2": 40,
            "manual": 50,
        },
    )
    archive.create_automatic(
        current,
        StoredWorldState("automatic-1", "sha256:auto-1", True),
        idempotency_key="automatic-1",
    )
    archive.create_automatic(
        current,
        StoredWorldState("automatic-2", "sha256:auto-2", True),
        idempotency_key="automatic-2",
    )
    archive.create_manual(
        current,
        StoredWorldState("manual", "sha256:manual", True),
        idempotency_key="manual-1",
    )
    service = StoragePolicyService(
        worlds_repository,
        archive_store=archive,
        repository=InMemoryStoragePolicyRepository(),
        policy=StoragePolicy(allowance_bytes=100, grace_days=30),
    )

    grace = service.evaluate(account.id, wallet_can_fund=False, observed_at=now)
    gate_during_grace = (
        service.can_create_world(account.id),
        service.can_create_manual_backup(account.id),
        service.can_wake(account.id),
    )
    gated_worlds = Worlds(worlds_repository, access=accounts, storage_gate=service)
    gated_data = WorldData(
        worlds_repository,
        access=accounts,
        archive_store=archive,
        storage_gate=service,
    )
    with pytest.raises(StorageBlockedError):
        gated_worlds.create_world(
            account.id,
            actor_user_id="owner",
            name="Segundo mundo",
            game_template_id="palworld:1",
            region="br-sao-paulo",
            runtime_profile_id="palworld-small",
        )
    with pytest.raises(StorageBlockedError):
        gated_data.create_manual_backup(
            account.id,
            current.id,
            actor_user_id="owner",
            idempotency_key="blocked-manual",
        )
    after_grace = service.evaluate(
        account.id,
        wallet_can_fund=False,
        observed_at=now + timedelta(days=30),
    )

    assert grace.used_bytes == 180
    assert grace.grace_ends_at == now + timedelta(days=30)
    assert grace.manual_backups_blocked is True
    assert grace.new_worlds_blocked is True
    assert grace.wake_blocked is False
    assert grace.pruned_backup_ids == ()
    assert gate_during_grace == (False, False, True)
    assert after_grace.used_bytes == 110
    assert after_grace.wake_blocked is True
    assert len(after_grace.pruned_backup_ids) == 2
    assert service.can_wake(account.id) is False
    with pytest.raises(StorageBlockedError):
        gated_worlds.request_wake(
            account.id,
            current.id,
            actor_user_id="owner",
            idempotency_key="blocked-wake",
        )
    remaining = archive.list_backups(account.id, current.id)
    assert [backup.kind for backup in remaining] == [BackupKind.MANUAL]
    assert remaining[0].state_id == "manual"
