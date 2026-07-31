from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .data_api import Database

_MIGRATIONS_DIRECTORY = Path(__file__).with_name("sql")
_STATEMENT_MARKER = "-- gamewake:statement"


@dataclass(frozen=True)
class Migration:
    id: str
    path: str
    statements: tuple[str, ...]


def load_migrations(directory: Path = _MIGRATIONS_DIRECTORY) -> tuple[Migration, ...]:
    migrations: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        statements = tuple(
            statement.strip()
            for statement in path.read_text(encoding="utf-8").split(_STATEMENT_MARKER)
            if statement.strip()
        )
        migrations.append(Migration(id=path.stem, path=str(path), statements=statements))
    return tuple(migrations)


class MigrationRunner:
    def __init__(self, database: Database) -> None:
        self._database = database

    def apply(self) -> tuple[str, ...]:
        with self._database.transaction() as transaction:
            transaction.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            applied = {
                str(row["id"])
                for row in transaction.fetch_all("SELECT id FROM schema_migrations ORDER BY id")
            }

        newly_applied: list[str] = []
        for migration in load_migrations():
            if migration.id in applied:
                continue
            with self._database.transaction() as transaction:
                for statement in migration.statements:
                    transaction.execute(statement)
                transaction.execute(
                    "INSERT INTO schema_migrations (id) VALUES (:id)", {"id": migration.id}
                )
            newly_applied.append(migration.id)
        return tuple(newly_applied)
