from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import boto3

from gamewake.aws import (
    Ec2RuntimeProvider,
    S3WorldArchiveStore,
    S3WorldStateStore,
    SsmCommandRunner,
    SsmPalworldTemplate,
)
from gamewake.orchestration import (
    StepFunctionsOperationOrchestrator,
    advance_operation,
)
from gamewake.persistence import (
    AuroraDataApi,
    MigrationRunner,
    PostgresWorldRepository,
)
from gamewake.worlds import WorldOperationWorker


class _PalworldTemplates:
    def __init__(self, template: SsmPalworldTemplate) -> None:
        self._template = template

    def resolve(self, game_template_id: str) -> SsmPalworldTemplate:
        if game_template_id != "palworld:1":
            raise KeyError(game_template_id)
        return self._template


@dataclass(frozen=True)
class _Services:
    worker: WorldOperationWorker
    migrations: MigrationRunner
    database: AuroraDataApi
    orchestrator_factory: Any


def _required(environ: dict[str, str], name: str) -> str:
    value = environ.get(name)
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def build_services(
    environ: dict[str, str] | None = None,
    *,
    client_factory: Any = boto3.client,
) -> _Services:
    environ = environ or os.environ
    database = AuroraDataApi(
        _required(environ, "AURORA_CLUSTER_ARN"),
        _required(environ, "AURORA_SECRET_ARN"),
        _required(environ, "AURORA_DATABASE_NAME"),
        client=client_factory("rds-data"),
    )
    repository = PostgresWorldRepository(database)
    runner = SsmCommandRunner(client=client_factory("ssm"))
    archive = S3WorldArchiveStore(
        _required(environ, "WORLD_DATA_BUCKET"),
        client=client_factory("s3"),
    )
    worker = WorldOperationWorker(
        repository,
        runtime_provider=Ec2RuntimeProvider(
            _required(environ, "RUNTIME_LAUNCH_TEMPLATE_ID"),
            client=client_factory("ec2"),
        ),
        state_store=S3WorldStateStore(
            _required(environ, "WORLD_DATA_BUCKET"),
            runner=runner,
        ),
        game_templates=_PalworldTemplates(SsmPalworldTemplate(runner)),
        backup_store=archive,
    )
    step_functions_client = client_factory("stepfunctions")
    return _Services(
        worker=worker,
        migrations=MigrationRunner(database),
        database=database,
        orchestrator_factory=lambda arn: StepFunctionsOperationOrchestrator(
            arn, client=step_functions_client
        ),
    )


def handle_event(event: dict[str, Any], *, services: Any) -> dict[str, Any]:
    action = event.get("action", "advance")
    if action == "migrate":
        return {"applied_migrations": list(services.migrations.apply())}
    if action == "reconcile":
        state_machine_arn = event.get("state_machine_arn")
        if not isinstance(state_machine_arn, str) or not state_machine_arn:
            raise ValueError("state_machine_arn is required for reconciliation")
        with services.database.transaction() as transaction:
            operations = transaction.fetch_all(
                """
                SELECT account_id, id
                FROM world_operations
                WHERE status IN ('pending', 'running')
                ORDER BY created_at, id
                """
            )
        orchestrator = services.orchestrator_factory(state_machine_arn)
        for operation in operations:
            orchestrator.ensure_running(str(operation["account_id"]), str(operation["id"]))
        return {"reconciled": len(operations)}
    if action not in {"advance", "record_failure"}:
        raise ValueError(f"unsupported operation worker action: {action}")
    return advance_operation(event, worker=services.worker)


_services: _Services | None = None


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    del context
    global _services
    if _services is None:
        _services = build_services()
    return handle_event(event, services=_services)
