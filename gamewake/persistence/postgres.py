from __future__ import annotations

import json
from dataclasses import replace

from gamewake.accounts.model import (
    Account,
    DiscordGuildAlreadyLinkedError,
    IdentityProvider,
    LinkedIdentity,
    Membership,
    User,
)
from gamewake.accounts.repository import AccountSnapshot
from gamewake.accounts.security import ActivityEvent
from gamewake.billing.model import (
    ConcurrentBillingUpdate,
    LedgerEntry,
    WalletContribution,
    WalletSnapshot,
)
from gamewake.worlds.model import (
    ConfigurationRevision,
    World,
    WorldOperation,
)
from gamewake.worlds.storage import StorageGraceState, StorageStatus

from .codec import decode_domain, encode_domain
from .data_api import Database, Row, Transaction


def _payload(row: Row, key: str = "payload") -> str:
    value = row[key]
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _missing(identifier: str) -> KeyError:
    return KeyError(identifier)


class PostgresAccountRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, account: Account, owner: Membership) -> None:
        snapshot = AccountSnapshot(account, (owner,), (), (), (), 1)
        with self._database.transaction() as transaction:
            if account.discord_guild_id is not None:
                linked = transaction.fetch_one(
                    "SELECT id FROM accounts WHERE discord_guild_id = :guild_id",
                    {"guild_id": account.discord_guild_id},
                )
                if linked is not None:
                    raise DiscordGuildAlreadyLinkedError(
                        "the Discord Guild is already linked to a GameWake Account"
                    )
            transaction.execute(
                """
                INSERT INTO accounts (id, name, discord_guild_id, aggregate, version)
                VALUES (:id, :name, :discord_guild_id, CAST(:aggregate AS JSONB), 1)
                """,
                {
                    "id": account.id,
                    "name": account.name,
                    "discord_guild_id": account.discord_guild_id,
                    "aggregate": encode_domain(snapshot),
                },
            )
            self._sync_memberships(transaction, snapshot)

    def _snapshot(self, transaction: Transaction, row: Row) -> AccountSnapshot:
        snapshot = decode_domain(_payload(row, "aggregate"), AccountSnapshot)
        activity = tuple(
            decode_domain(_payload(event), ActivityEvent)
            for event in transaction.fetch_all(
                """
                SELECT payload FROM activity_events
                WHERE account_id = :account_id
                ORDER BY occurred_at, id
                """,
                {"account_id": snapshot.account.id},
            )
        )
        return replace(snapshot, activity_events=activity, version=int(row["version"]))

    def get(self, account_id: str) -> AccountSnapshot:
        with self._database.transaction() as transaction:
            row = transaction.fetch_one(
                "SELECT aggregate, version FROM accounts WHERE id = :account_id",
                {"account_id": account_id},
            )
            if row is None:
                raise _missing(account_id)
            return self._snapshot(transaction, row)

    def find_by_discord_guild(self, discord_guild_id: str) -> AccountSnapshot | None:
        with self._database.transaction() as transaction:
            row = transaction.fetch_one(
                "SELECT aggregate, version FROM accounts WHERE discord_guild_id = :guild_id",
                {"guild_id": discord_guild_id},
            )
            return self._snapshot(transaction, row) if row is not None else None

    def list_for_user(self, user_id: str) -> tuple[AccountSnapshot, ...]:
        with self._database.transaction() as transaction:
            return tuple(
                self._snapshot(transaction, row)
                for row in transaction.fetch_all(
                    """
                    SELECT accounts.aggregate, accounts.version
                    FROM account_memberships
                    JOIN accounts ON accounts.id = account_memberships.account_id
                    WHERE account_memberships.user_id = :user_id
                    ORDER BY accounts.name, accounts.id
                    """,
                    {"user_id": user_id},
                )
            )

    @staticmethod
    def _sync_memberships(transaction: Transaction, snapshot: AccountSnapshot) -> None:
        transaction.execute(
            "DELETE FROM account_memberships WHERE account_id = :account_id",
            {"account_id": snapshot.account.id},
        )
        for membership in snapshot.memberships:
            transaction.execute(
                """
                INSERT INTO account_memberships (account_id, user_id, membership_id)
                VALUES (:account_id, :user_id, :membership_id)
                """,
                {
                    "account_id": snapshot.account.id,
                    "user_id": membership.user_id,
                    "membership_id": membership.id,
                },
            )

    def save(self, snapshot: AccountSnapshot, expected_version: int) -> None:
        persisted = replace(snapshot, activity_events=(), version=expected_version + 1)
        with self._database.transaction() as transaction:
            updated = transaction.execute(
                """
                UPDATE accounts
                SET name = :name,
                    discord_guild_id = :discord_guild_id,
                    aggregate = CAST(:aggregate AS JSONB),
                    version = :new_version,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :account_id AND version = :expected_version
                """,
                {
                    "account_id": snapshot.account.id,
                    "name": snapshot.account.name,
                    "discord_guild_id": snapshot.account.discord_guild_id,
                    "aggregate": encode_domain(persisted),
                    "expected_version": expected_version,
                    "new_version": expected_version + 1,
                },
            )
            if updated != 1:
                raise RuntimeError("account was changed concurrently")
            self._sync_memberships(transaction, snapshot)
            for event in snapshot.activity_events:
                inserted = transaction.execute(
                    """
                    INSERT INTO activity_events (id, account_id, occurred_at, payload)
                    VALUES (:id, :account_id, :occurred_at, CAST(:payload AS JSONB))
                    ON CONFLICT (id) DO NOTHING
                    """,
                    {
                        "id": event.id,
                        "account_id": event.account_id,
                        "occurred_at": event.occurred_at,
                        "payload": encode_domain(event),
                    },
                )
                if inserted == 0:
                    existing = transaction.fetch_one(
                        "SELECT payload FROM activity_events WHERE id = :id",
                        {"id": event.id},
                    )
                    if (
                        existing is None
                        or decode_domain(_payload(existing), ActivityEvent) != event
                    ):
                        raise ValueError("immutable Activity Event conflicts with persisted data")

    def find_user_by_identity(
        self,
        provider: IdentityProvider,
        provider_user_id: str,
    ) -> User | None:
        with self._database.transaction() as transaction:
            row = transaction.fetch_one(
                """
                SELECT users.aggregate
                FROM linked_identities
                JOIN users ON users.id = linked_identities.user_id
                WHERE linked_identities.provider = :provider
                  AND linked_identities.provider_user_id = :provider_user_id
                """,
                {"provider": provider.value, "provider_user_id": provider_user_id},
            )
            return decode_domain(_payload(row, "aggregate"), User) if row is not None else None

    def create_user(self, user: User, identity: LinkedIdentity) -> None:
        with self._database.transaction() as transaction:
            transaction.execute(
                """
                INSERT INTO users (id, display_name, aggregate)
                VALUES (:id, :display_name, CAST(:aggregate AS JSONB))
                """,
                {
                    "id": user.id,
                    "display_name": user.display_name,
                    "aggregate": encode_domain(user),
                },
            )
            self._insert_identity(transaction, identity)

    def _insert_identity(self, transaction: Transaction, identity: LinkedIdentity) -> None:
        transaction.execute(
            """
            INSERT INTO linked_identities
                (id, user_id, provider, provider_user_id, aggregate)
            VALUES
                (:id, :user_id, :provider, :provider_user_id, CAST(:aggregate AS JSONB))
            """,
            {
                "id": identity.id,
                "user_id": identity.user_id,
                "provider": identity.provider.value,
                "provider_user_id": identity.provider_user_id,
                "aggregate": encode_domain(identity),
            },
        )

    def replace_identity(self, identity: LinkedIdentity) -> None:
        with self._database.transaction() as transaction:
            transaction.execute(
                "DELETE FROM linked_identities WHERE user_id = :user_id AND provider = :provider",
                {"user_id": identity.user_id, "provider": identity.provider.value},
            )
            self._insert_identity(transaction, identity)

    def list_linked_identities(self, user_id: str) -> tuple[LinkedIdentity, ...]:
        with self._database.transaction() as transaction:
            return tuple(
                decode_domain(_payload(row), LinkedIdentity)
                for row in transaction.fetch_all(
                    """
                    SELECT aggregate AS payload FROM linked_identities
                    WHERE user_id = :user_id
                    ORDER BY id
                    """,
                    {"user_id": user_id},
                )
            )


class PostgresWorldRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _world(row: Row) -> World:
        return decode_domain(_payload(row, "aggregate"), World)

    @staticmethod
    def _operation(row: Row) -> WorldOperation:
        return decode_domain(_payload(row), WorldOperation)

    @staticmethod
    def _configuration(row: Row) -> ConfigurationRevision:
        return decode_domain(_payload(row), ConfigurationRevision)

    def _insert_configuration(
        self, transaction: Transaction, revision: ConfigurationRevision
    ) -> None:
        transaction.execute(
            """
            INSERT INTO configuration_revisions
                (id, account_id, world_id, number, idempotency_key, created_at, payload)
            VALUES
                (:id, :account_id, :world_id, :number, :idempotency_key, :created_at,
                 CAST(:payload AS JSONB))
            """,
            {
                "id": revision.id,
                "account_id": revision.account_id,
                "world_id": revision.world_id,
                "number": revision.number,
                "idempotency_key": revision.idempotency_key,
                "created_at": revision.created_at,
                "payload": encode_domain(revision),
            },
        )

    def create(self, world: World, initial_configuration: ConfigurationRevision) -> None:
        with self._database.transaction() as transaction:
            transaction.execute(
                """
                INSERT INTO worlds (account_id, id, status, aggregate, version)
                VALUES (:account_id, :id, :status, CAST(:aggregate AS JSONB), :version)
                """,
                {
                    "account_id": world.account_id,
                    "id": world.id,
                    "status": world.status.value,
                    "aggregate": encode_domain(world),
                    "version": world.version,
                },
            )
            self._insert_configuration(transaction, initial_configuration)

    def get(self, account_id: str, world_id: str) -> World:
        with self._database.transaction() as transaction:
            row = transaction.fetch_one(
                """
                SELECT aggregate FROM worlds
                WHERE account_id = :account_id AND id = :world_id
                """,
                {"account_id": account_id, "world_id": world_id},
            )
            if row is None:
                raise _missing(world_id)
            return self._world(row)

    def list_worlds(self, account_id: str) -> tuple[World, ...]:
        with self._database.transaction() as transaction:
            return tuple(
                self._world(row)
                for row in transaction.fetch_all(
                    "SELECT aggregate FROM worlds WHERE account_id = :account_id ORDER BY id",
                    {"account_id": account_id},
                )
            )

    @staticmethod
    def _save_world(transaction: Transaction, world: World, expected_version: int) -> None:
        updated = transaction.execute(
            """
            UPDATE worlds
            SET status = :status,
                aggregate = CAST(:aggregate AS JSONB),
                version = :new_version,
                updated_at = CURRENT_TIMESTAMP
            WHERE account_id = :account_id AND id = :world_id AND version = :expected_version
            """,
            {
                "account_id": world.account_id,
                "world_id": world.id,
                "status": world.status.value,
                "aggregate": encode_domain(world),
                "new_version": world.version,
                "expected_version": expected_version,
            },
        )
        if updated != 1:
            raise RuntimeError("World was changed concurrently")

    def save(self, world: World, expected_version: int) -> None:
        with self._database.transaction() as transaction:
            self._save_world(transaction, world, expected_version)

    def delete(self, account_id: str, world_id: str) -> None:
        with self._database.transaction() as transaction:
            deleted = transaction.execute(
                "DELETE FROM worlds WHERE account_id = :account_id AND id = :world_id",
                {"account_id": account_id, "world_id": world_id},
            )
            if deleted != 1:
                raise _missing(world_id)

    def begin_operation(
        self,
        world: World,
        operation: WorldOperation,
        *,
        expected_world_version: int,
    ) -> WorldOperation:
        with self._database.transaction() as transaction:
            existing = transaction.fetch_one(
                """
                SELECT payload FROM world_operations
                WHERE account_id = :account_id AND idempotency_key = :idempotency_key
                """,
                {
                    "account_id": operation.account_id,
                    "idempotency_key": operation.idempotency_key,
                },
            )
            if existing is not None:
                return self._operation(existing)
            active = transaction.fetch_one(
                """
                SELECT payload FROM world_operations
                WHERE account_id = :account_id AND world_id = :world_id
                  AND status IN ('pending', 'running')
                ORDER BY created_at, id
                LIMIT 1
                """,
                {"account_id": operation.account_id, "world_id": operation.world_id},
            )
            if active is not None:
                return self._operation(active)
            self._save_world(transaction, world, expected_world_version)
            transaction.execute(
                """
                INSERT INTO world_operations
                    (id, account_id, world_id, operation_type, status, phase,
                     idempotency_key, created_at, payload, version)
                VALUES
                    (:id, :account_id, :world_id, :operation_type, :status, :phase,
                     :idempotency_key, :created_at, CAST(:payload AS JSONB), :version)
                """,
                {
                    "id": operation.id,
                    "account_id": operation.account_id,
                    "world_id": operation.world_id,
                    "operation_type": operation.operation_type.value,
                    "status": operation.status.value,
                    "phase": operation.phase.value,
                    "idempotency_key": operation.idempotency_key,
                    "created_at": operation.created_at,
                    "payload": encode_domain(operation),
                    "version": operation.version,
                },
            )
            return operation

    def list_operations(self, account_id: str, world_id: str) -> tuple[WorldOperation, ...]:
        with self._database.transaction() as transaction:
            return tuple(
                self._operation(row)
                for row in transaction.fetch_all(
                    """
                    SELECT payload FROM world_operations
                    WHERE account_id = :account_id AND world_id = :world_id
                    ORDER BY created_at, id
                    """,
                    {"account_id": account_id, "world_id": world_id},
                )
            )

    def get_operation(self, account_id: str, operation_id: str) -> WorldOperation:
        with self._database.transaction() as transaction:
            row = transaction.fetch_one(
                """
                SELECT payload FROM world_operations
                WHERE account_id = :account_id AND id = :operation_id
                """,
                {"account_id": account_id, "operation_id": operation_id},
            )
            if row is None:
                raise _missing(operation_id)
            return self._operation(row)

    def save_operation(
        self,
        operation: WorldOperation,
        *,
        expected_operation_version: int,
        world: World | None = None,
        expected_world_version: int | None = None,
    ) -> None:
        with self._database.transaction() as transaction:
            if world is not None:
                if expected_world_version is None:
                    raise ValueError("expected World version is required")
                self._save_world(transaction, world, expected_world_version)
            updated = transaction.execute(
                """
                UPDATE world_operations
                SET status = :status,
                    phase = :phase,
                    payload = CAST(:payload AS JSONB),
                    version = :new_version
                WHERE account_id = :account_id AND id = :operation_id
                  AND version = :expected_version
                """,
                {
                    "account_id": operation.account_id,
                    "operation_id": operation.id,
                    "status": operation.status.value,
                    "phase": operation.phase.value,
                    "payload": encode_domain(operation),
                    "new_version": operation.version,
                    "expected_version": expected_operation_version,
                },
            )
            if updated != 1:
                raise RuntimeError("World Operation was changed concurrently")

    def get_configuration(
        self,
        account_id: str,
        world_id: str,
        revision_id: str,
    ) -> ConfigurationRevision:
        with self._database.transaction() as transaction:
            row = transaction.fetch_one(
                """
                SELECT payload FROM configuration_revisions
                WHERE account_id = :account_id AND world_id = :world_id AND id = :revision_id
                """,
                {
                    "account_id": account_id,
                    "world_id": world_id,
                    "revision_id": revision_id,
                },
            )
            if row is None:
                raise _missing(revision_id)
            return self._configuration(row)

    def append_configuration(
        self,
        world: World,
        revision: ConfigurationRevision,
        *,
        expected_world_version: int,
    ) -> ConfigurationRevision:
        with self._database.transaction() as transaction:
            existing = transaction.fetch_one(
                """
                SELECT payload FROM configuration_revisions
                WHERE account_id = :account_id AND idempotency_key = :idempotency_key
                """,
                {
                    "account_id": revision.account_id,
                    "idempotency_key": revision.idempotency_key,
                },
            )
            if existing is not None:
                return self._configuration(existing)
            self._save_world(transaction, world, expected_world_version)
            self._insert_configuration(transaction, revision)
            return revision


class PostgresBillingRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _empty(account_id: str) -> WalletSnapshot:
        return WalletSnapshot(account_id, (), (), (), (), (), (), (), (), (), 0)

    def get(self, account_id: str) -> WalletSnapshot:
        with self._database.transaction() as transaction:
            row = transaction.fetch_one(
                "SELECT aggregate, version FROM wallet_snapshots WHERE account_id = :account_id",
                {"account_id": account_id},
            )
            if row is None:
                return self._empty(account_id)
            snapshot = decode_domain(_payload(row, "aggregate"), WalletSnapshot)
            entries = tuple(
                decode_domain(_payload(entry), LedgerEntry)
                for entry in transaction.fetch_all(
                    """
                    SELECT payload FROM wallet_ledger_entries
                    WHERE account_id = :account_id ORDER BY occurred_at, id
                    """,
                    {"account_id": account_id},
                )
            )
            contributions = tuple(
                decode_domain(_payload(contribution), WalletContribution)
                for contribution in transaction.fetch_all(
                    """
                    SELECT payload FROM wallet_contributions
                    WHERE account_id = :account_id ORDER BY id
                    """,
                    {"account_id": account_id},
                )
            )
            return replace(
                snapshot,
                entries=entries,
                contributions=contributions,
                version=int(row["version"]),
            )

    def save(self, snapshot: WalletSnapshot, *, expected_version: int) -> None:
        next_snapshot = replace(
            snapshot,
            entries=(),
            contributions=(),
            version=expected_version + 1,
        )
        parameters = {
            "account_id": snapshot.account_id,
            "aggregate": encode_domain(next_snapshot),
            "new_version": expected_version + 1,
            "expected_version": expected_version,
        }
        with self._database.transaction() as transaction:
            if expected_version == 0:
                updated = transaction.execute(
                    """
                    INSERT INTO wallet_snapshots (account_id, aggregate, version)
                    VALUES (:account_id, CAST(:aggregate AS JSONB), :new_version)
                    ON CONFLICT (account_id) DO NOTHING
                    """,
                    parameters,
                )
            else:
                updated = transaction.execute(
                    """
                    UPDATE wallet_snapshots
                    SET aggregate = CAST(:aggregate AS JSONB),
                        version = :new_version,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = :account_id AND version = :expected_version
                    """,
                    parameters,
                )
            if updated != 1:
                raise ConcurrentBillingUpdate("Wallet was changed concurrently")

            for entry in snapshot.entries:
                inserted = transaction.execute(
                    """
                    INSERT INTO wallet_ledger_entries
                        (id, account_id, entry_type, amount, reference,
                         idempotency_key, occurred_at, payload)
                    VALUES
                        (:id, :account_id, :entry_type, :amount, :reference,
                         :idempotency_key, :occurred_at, CAST(:payload AS JSONB))
                    ON CONFLICT DO NOTHING
                    """,
                    {
                        "id": entry.id,
                        "account_id": entry.account_id,
                        "entry_type": entry.entry_type.value,
                        "amount": entry.amount,
                        "reference": entry.reference,
                        "idempotency_key": entry.idempotency_key,
                        "occurred_at": entry.occurred_at,
                        "payload": encode_domain(entry),
                    },
                )
                if inserted == 0:
                    existing = transaction.fetch_one(
                        "SELECT payload FROM wallet_ledger_entries WHERE id = :id",
                        {"id": entry.id},
                    )
                    if existing is None or decode_domain(_payload(existing), LedgerEntry) != entry:
                        raise ValueError("immutable Ledger Entry conflicts with persisted data")
            for contribution in snapshot.contributions:
                transaction.execute(
                    """
                    INSERT INTO wallet_contributions
                        (id, account_id, status, idempotency_key, payload)
                    VALUES
                        (:id, :account_id, :status, :idempotency_key, CAST(:payload AS JSONB))
                    ON CONFLICT (id) DO UPDATE
                    SET status = EXCLUDED.status, payload = EXCLUDED.payload
                    """,
                    {
                        "id": contribution.id,
                        "account_id": contribution.account_id,
                        "status": contribution.status.value,
                        "idempotency_key": contribution.idempotency_key,
                        "payload": encode_domain(contribution),
                    },
                )

    def find_contribution(self, contribution_id: str) -> WalletContribution | None:
        with self._database.transaction() as transaction:
            row = transaction.fetch_one(
                "SELECT payload FROM wallet_contributions WHERE id = :contribution_id",
                {"contribution_id": contribution_id},
            )
            return decode_domain(_payload(row), WalletContribution) if row is not None else None


class PostgresStoragePolicyRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, account_id: str) -> StorageGraceState | None:
        with self._database.transaction() as transaction:
            row = transaction.fetch_one(
                "SELECT payload FROM storage_grace_states WHERE account_id = :account_id",
                {"account_id": account_id},
            )
            return decode_domain(_payload(row), StorageGraceState) if row is not None else None

    def save(self, state: StorageGraceState, *, expected_version: int) -> None:
        persisted = replace(state, version=expected_version + 1)
        parameters = {
            "account_id": state.account_id,
            "started_at": state.started_at,
            "version": expected_version + 1,
            "expected_version": expected_version,
            "payload": encode_domain(persisted),
        }
        with self._database.transaction() as transaction:
            if expected_version == 0:
                updated = transaction.execute(
                    """
                    INSERT INTO storage_grace_states (account_id, started_at, version, payload)
                    VALUES (:account_id, :started_at, :version, CAST(:payload AS JSONB))
                    ON CONFLICT (account_id) DO NOTHING
                    """,
                    parameters,
                )
            else:
                updated = transaction.execute(
                    """
                    UPDATE storage_grace_states
                    SET started_at = :started_at,
                        version = :version,
                        payload = CAST(:payload AS JSONB)
                    WHERE account_id = :account_id AND version = :expected_version
                    """,
                    parameters,
                )
            if updated != 1:
                raise RuntimeError("Storage Grace Period was changed concurrently")

    def clear(self, account_id: str, *, expected_version: int) -> None:
        with self._database.transaction() as transaction:
            deleted = transaction.execute(
                """
                DELETE FROM storage_grace_states
                WHERE account_id = :account_id AND version = :expected_version
                """,
                {"account_id": account_id, "expected_version": expected_version},
            )
            if deleted != 1:
                exists = transaction.fetch_one(
                    "SELECT version FROM storage_grace_states WHERE account_id = :account_id",
                    {"account_id": account_id},
                )
                if exists is not None or expected_version != 0:
                    raise RuntimeError("Storage Grace Period was changed concurrently")

    def get_status(self, account_id: str) -> StorageStatus | None:
        with self._database.transaction() as transaction:
            row = transaction.fetch_one(
                "SELECT payload FROM storage_statuses WHERE account_id = :account_id",
                {"account_id": account_id},
            )
            return decode_domain(_payload(row), StorageStatus) if row is not None else None

    def save_status(self, status: StorageStatus) -> None:
        with self._database.transaction() as transaction:
            transaction.execute(
                """
                INSERT INTO storage_statuses (account_id, payload)
                VALUES (:account_id, CAST(:payload AS JSONB))
                ON CONFLICT (account_id) DO UPDATE
                SET payload = EXCLUDED.payload, updated_at = CURRENT_TIMESTAMP
                """,
                {"account_id": status.account_id, "payload": encode_domain(status)},
            )
