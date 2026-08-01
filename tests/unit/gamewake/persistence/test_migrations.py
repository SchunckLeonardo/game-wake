from pathlib import Path

from gamewake.persistence import load_migrations


def test_initial_postgres_migration_covers_durable_mvp_state() -> None:
    migrations = load_migrations()

    assert [migration.id for migration in migrations] == [
        "0001_initial",
        "0002_account_memberships",
        "0003_owner_recovery",
    ]
    sql = "\n".join(migrations[0].statements).lower()
    for table in (
        "accounts",
        "users",
        "linked_identities",
        "worlds",
        "world_operations",
        "configuration_revisions",
        "wallet_snapshots",
        "wallet_ledger_entries",
        "wallet_contributions",
        "activity_events",
        "storage_grace_states",
        "storage_statuses",
    ):
        assert f"create table {table}" in sql

    assert "unique (provider, provider_user_id)" in sql
    assert "world_operations_one_active_per_world" in sql
    assert "reject_immutable_row_mutation" in sql
    assert "wallet_ledger_entries_are_immutable" in sql
    assert "activity_events_are_immutable" in sql
    owner_recovery = "\n".join(migrations[2].statements).lower()
    assert "create table owner_recovery_profiles" in owner_recovery
    assert "create table owner_recovery_codes" in owner_recovery


def test_every_migration_statement_is_non_empty_and_source_is_versioned() -> None:
    migrations = load_migrations()

    assert all(statement.strip() for migration in migrations for statement in migration.statements)
    assert all(Path(migration.path).name.startswith(migration.id) for migration in migrations)
