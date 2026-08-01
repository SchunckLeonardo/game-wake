from pathlib import Path


def test_membership_projection_migration_backfills_existing_account_aggregates():
    migration = (
        Path(__file__).parents[4]
        / "gamewake"
        / "persistence"
        / "sql"
        / "0002_account_memberships.sql"
    ).read_text()

    assert "CREATE TABLE account_memberships" in migration
    assert "jsonb_array_elements" in migration
    assert "ON CONFLICT" in migration
