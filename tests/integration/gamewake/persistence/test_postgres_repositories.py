from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gamewake.accounts import (
    Account,
    ActivityAction,
    ActivityEvent,
    DiscordGuildAlreadyLinkedError,
    IdentityProvider,
    Invitation,
    InvitationStatus,
    LinkedIdentity,
    Membership,
    PredefinedRole,
    ResourceScope,
    RoleAssignment,
    User,
)
from gamewake.accounts.repository import AccountSnapshot
from gamewake.billing import (
    ContributionStatus,
    LedgerEntry,
    LedgerEntryType,
    WalletContribution,
)
from gamewake.billing.model import ConcurrentBillingUpdate, WalletSnapshot
from gamewake.persistence import (
    MigrationRunner,
    PostgresAccountRepository,
    PostgresBillingRepository,
    PostgresRecoverySecretStore,
    PostgresStoragePolicyRepository,
    PostgresWorldRepository,
    PsycopgDatabase,
)
from gamewake.worlds import (
    ConfigurationRevision,
    OperationPhase,
    OperationStatus,
    OperationType,
    StorageGraceState,
    StorageStatus,
    World,
    WorldOperation,
    WorldStatus,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database():
    database_url = os.environ.get("GAMEWAKE_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("GAMEWAKE_TEST_DATABASE_URL is not configured")
    if "gamewake_test" not in database_url:
        pytest.fail("integration tests require a disposable gamewake_test database")

    database = PsycopgDatabase(database_url)
    with database.transaction() as transaction:
        transaction.execute("DROP SCHEMA public CASCADE")
        transaction.execute("CREATE SCHEMA public")
    assert MigrationRunner(database).apply() == (
        "0001_initial",
        "0002_account_memberships",
        "0003_owner_recovery",
    )
    assert MigrationRunner(database).apply() == ()
    return database


def owner(account_id: str, user_id: str = "owner-1") -> Membership:
    return Membership(
        f"membership-{account_id}",
        account_id,
        user_id,
        (
            RoleAssignment(
                f"assignment-{account_id}",
                ResourceScope(account_id),
                predefined_role=PredefinedRole.OWNER,
            ),
        ),
    )


def create_account(database, account_id: str) -> PostgresAccountRepository:
    repository = PostgresAccountRepository(database)
    repository.create(Account(account_id, account_id), owner(account_id))
    return repository


def test_owner_recovery_hashes_are_persistent_and_single_use(database) -> None:
    accounts = PostgresAccountRepository(database)
    user = User("recovery-user", "Recovery Owner")
    accounts.create_user(
        user,
        LinkedIdentity(
            "recovery-identity",
            user.id,
            IdentityProvider.DISCORD,
            "recovery-discord",
        ),
    )
    recovery = PostgresRecoverySecretStore(database)
    recovery.put(user.id, "owner@example.com", frozenset({"hash-1", "hash-2"}))

    assert recovery.is_enabled(user.id) is True
    assert recovery.consume(user.id, "hash-1") is True
    assert recovery.consume(user.id, "hash-1") is False
    assert recovery.is_enabled(user.id) is True


def test_accounts_identities_activity_and_concurrency_are_transactional(database) -> None:
    repository = PostgresAccountRepository(database)
    account = Account("account-1", "Sexta", "guild-1")
    membership = owner(account.id)
    repository.create(account, membership)

    assert repository.get(account.id) == AccountSnapshot(
        account,
        (membership,),
        (),
        (),
        (),
        1,
    )
    assert repository.find_by_discord_guild("guild-1") == repository.get(account.id)
    assert repository.list_for_user(membership.user_id) == (repository.get(account.id),)

    user = User("user-1", "Leonardo")
    discord = LinkedIdentity("identity-1", user.id, IdentityProvider.DISCORD, "discord-1")
    repository.create_user(user, discord)
    assert repository.find_user_by_identity(IdentityProvider.DISCORD, "discord-1") == user
    assert repository.list_linked_identities(user.id) == (discord,)

    replacement = replace(discord, id="identity-2", provider_user_id="discord-2")
    repository.replace_identity(replacement)
    assert repository.find_user_by_identity(IdentityProvider.DISCORD, "discord-1") is None
    assert repository.list_linked_identities(user.id) == (replacement,)

    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    invitation = Invitation(
        "invitation-1",
        account.id,
        user.id,
        "friend-1",
        InvitationStatus.PENDING,
    )
    activity = ActivityEvent(
        "activity-1",
        account.id,
        user.id,
        ActivityAction.MEMBERSHIP_REVOKED,
        "friend-1",
        now,
    )
    repository.save(
        replace(repository.get(account.id), invitations=(invitation,), activity_events=(activity,)),
        expected_version=1,
    )
    saved = repository.get(account.id)
    assert saved.version == 2
    assert saved.invitations == (invitation,)
    assert saved.activity_events == (activity,)
    assert repository.list_for_user("friend-1") == ()

    with pytest.raises(RuntimeError, match="concurrently"):
        repository.save(saved, expected_version=1)
    with pytest.raises(ValueError, match="immutable Activity Event"):
        repository.save(
            replace(
                saved,
                activity_events=(replace(activity, subject_id="different-subject"),),
            ),
            expected_version=2,
        )
    assert repository.get(account.id).version == 2
    with pytest.raises(DiscordGuildAlreadyLinkedError):
        repository.create(
            Account("account-duplicate", "Outro", "guild-1"),
            owner("account-duplicate"),
        )
    with pytest.raises(Exception, match="immutable"), database.transaction() as transaction:
        transaction.execute(
            "UPDATE activity_events SET payload = payload WHERE id = :id",
            {"id": activity.id},
        )


def test_world_operations_and_configuration_revisions_are_idempotent(database) -> None:
    create_account(database, "world-account")
    repository = PostgresWorldRepository(database)
    now = datetime(2026, 7, 31, 13, 0, tzinfo=UTC)
    revision = ConfigurationRevision(
        "config-1",
        "world-account",
        "world-1",
        "palworld",
        1,
        (("DropItemRate", 3.0),),
        "config-create",
        now,
    )
    world = World(
        "world-1",
        "world-account",
        "Palpagos",
        "palworld",
        "sa-east-1",
        "friends-8",
        WorldStatus.SLEEPING,
        None,
        None,
        revision.id,
        None,
        "state-1",
        "sha256:one",
        1,
    )
    repository.create(world, revision)
    assert repository.get(world.account_id, world.id) == world
    assert repository.list_worlds(world.account_id) == (world,)

    waking = replace(world, status=WorldStatus.WAKING, version=2)
    operation = WorldOperation(
        "operation-1",
        world.account_id,
        world.id,
        OperationType.WAKE,
        OperationStatus.PENDING,
        OperationPhase.REQUESTED,
        "wake-1",
        now,
        1,
    )
    assert repository.begin_operation(waking, operation, expected_world_version=1) == operation
    assert repository.begin_operation(waking, operation, expected_world_version=1) == operation
    competing = replace(operation, id="operation-2", idempotency_key="wake-2")
    assert repository.begin_operation(waking, competing, expected_world_version=1) == operation

    online = replace(waking, status=WorldStatus.ONLINE, version=3)
    succeeded = replace(
        operation,
        status=OperationStatus.SUCCEEDED,
        phase=OperationPhase.COMPLETE,
        version=2,
    )
    repository.save_operation(
        succeeded,
        expected_operation_version=1,
        world=online,
        expected_world_version=2,
    )
    assert repository.get_operation(world.account_id, operation.id) == succeeded
    assert repository.get(world.account_id, world.id) == online

    revision_two = replace(
        revision,
        id="config-2",
        number=2,
        entries=(("DropItemRate", 4.0),),
        idempotency_key="config-update",
        created_at=now + timedelta(minutes=1),
    )
    configured = replace(online, pending_configuration_revision_id=revision_two.id, version=4)
    assert (
        repository.append_configuration(
            configured,
            revision_two,
            expected_world_version=3,
        )
        == revision_two
    )
    assert (
        repository.append_configuration(
            configured,
            revision_two,
            expected_world_version=3,
        )
        == revision_two
    )
    assert repository.get_configuration(world.account_id, world.id, revision_two.id) == revision_two


def test_wallet_keeps_ledger_immutable_and_contributions_queryable(database) -> None:
    create_account(database, "billing-account")
    repository = PostgresBillingRepository(database)
    assert repository.get("billing-account").version == 0
    now = datetime(2026, 7, 31, 14, 0, tzinfo=UTC)
    entry = LedgerEntry(
        "ledger-1",
        "billing-account",
        LedgerEntryType.CONTRIBUTION,
        Decimal("50.00"),
        "contribution-1",
        "payment-event-1",
        now,
    )
    contribution = WalletContribution(
        "contribution-1",
        "billing-account",
        "user-1",
        "credits-50",
        Decimal("50.00"),
        "product-50",
        "checkout-1",
        "https://pay.example/checkout-1",
        "https://gamewake.example/return",
        "https://gamewake.example/completed",
        ContributionStatus.COMPLETED,
        "contribution-key-1",
        now,
        None,
        None,
    )
    snapshot = WalletSnapshot(
        "billing-account",
        (entry,),
        (),
        (),
        (),
        (contribution,),
        (),
        (),
        (),
        (),
        0,
    )
    repository.save(snapshot, expected_version=0)
    saved = repository.get("billing-account")
    assert saved.version == 1
    assert saved.entries == (entry,)
    assert saved.contributions == (contribution,)
    assert repository.find_contribution(contribution.id) == contribution

    with pytest.raises(ConcurrentBillingUpdate):
        repository.save(snapshot, expected_version=0)
    with pytest.raises(ValueError, match="immutable Ledger Entry"):
        repository.save(
            replace(saved, entries=(replace(entry, amount=Decimal("49.00")),)),
            expected_version=1,
        )
    assert repository.get("billing-account").version == 1
    with pytest.raises(Exception, match="immutable"), database.transaction() as transaction:
        transaction.execute(
            "UPDATE wallet_ledger_entries SET amount = 0 WHERE id = :id", {"id": entry.id}
        )


def test_storage_policy_state_uses_optimistic_concurrency(database) -> None:
    create_account(database, "storage-account")
    repository = PostgresStoragePolicyRepository(database)
    now = datetime(2026, 7, 31, 15, 0, tzinfo=UTC)
    state = StorageGraceState("storage-account", now, 0)
    repository.save(state, expected_version=0)
    assert repository.get("storage-account") == replace(state, version=1)

    with pytest.raises(RuntimeError, match="concurrently"):
        repository.save(state, expected_version=0)

    status = StorageStatus(
        "storage-account",
        12,
        10,
        2,
        now,
        now + timedelta(days=30),
        True,
        True,
        False,
        ("backup-old",),
    )
    repository.save_status(status)
    assert repository.get_status("storage-account") == status
    repository.clear("storage-account", expected_version=1)
    assert repository.get("storage-account") is None
