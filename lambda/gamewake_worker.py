from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3

from gamewake.accounts import Accounts
from gamewake.aws import (
    Ec2RuntimeProvider,
    S3WorldArchiveStore,
    S3WorldStateStore,
    SsmCommandRunner,
    SsmPalworldTemplate,
)
from gamewake.billing import Billing, BillingRuntimeUsageRecorder
from gamewake.orchestration import (
    StepFunctionsOperationOrchestrator,
    advance_operation,
)
from gamewake.persistence import (
    AuroraDataApi,
    MigrationRunner,
    PostgresAccountRepository,
    PostgresBillingRepository,
    PostgresStoragePolicyRepository,
    PostgresWorldRepository,
)
from gamewake.worlds import (
    StoragePolicy,
    StoragePolicyService,
    WorldData,
    WorldOperationWorker,
)


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
    world_data: WorldData
    storage: StoragePolicyService
    billing: Billing


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
    accounts = Accounts(PostgresAccountRepository(database))
    billing = Billing(PostgresBillingRepository(database))
    storage = StoragePolicyService(
        repository,
        archive_store=archive,
        repository=PostgresStoragePolicyRepository(database),
        policy=StoragePolicy(
            allowance_bytes=int(_required(environ, "STORAGE_ALLOWANCE_BYTES")),
            grace_days=int(_required(environ, "STORAGE_GRACE_DAYS")),
        ),
    )
    world_data = WorldData(
        repository,
        access=accounts,
        archive_store=archive,
        storage_gate=storage,
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
        game_templates=_PalworldTemplates(
            SsmPalworldTemplate(
                runner,
                repository=repository,
                parameter_prefix=_required(environ, "GAMEWAKE_WORLD_PARAMETER_PREFIX"),
                base_configuration=json.loads(_required(environ, "PALWORLD_BASE_CONFIG_JSON")),
                client=client_factory("ssm"),
            )
        ),
        backup_store=archive,
        usage_recorder=BillingRuntimeUsageRecorder(billing),
    )
    step_functions_client = client_factory("stepfunctions")
    return _Services(
        worker=worker,
        migrations=MigrationRunner(database),
        database=database,
        orchestrator_factory=lambda arn: StepFunctionsOperationOrchestrator(
            arn, client=step_functions_client
        ),
        world_data=world_data,
        storage=storage,
        billing=billing,
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
    if action == "monitor_sessions":
        state_machine_arn = event.get("state_machine_arn")
        if not isinstance(state_machine_arn, str) or not state_machine_arn:
            raise ValueError("state_machine_arn is required for session monitoring")
        idle_minutes = int(event.get("idle_minutes", 20))
        with services.database.transaction() as transaction:
            worlds = transaction.fetch_all(
                """
                SELECT account_id, id
                FROM worlds
                WHERE status = 'online'
                ORDER BY account_id, id
                """
            )
        orchestrator = services.orchestrator_factory(state_machine_arn)
        sleep_operations = 0
        for world in worlds:
            operation = services.worker.monitor_session(
                str(world["account_id"]),
                str(world["id"]),
                idle_minutes=idle_minutes,
            )
            if operation is not None:
                orchestrator.ensure_running(str(world["account_id"]), operation.id)
                sleep_operations += 1
        return {"monitored": len(worlds), "sleep_operations": sleep_operations}
    if action == "maintain_data":
        raw_observed_at = event.get("observed_at")
        observed_at = (
            datetime.fromisoformat(raw_observed_at.replace("Z", "+00:00"))
            if isinstance(raw_observed_at, str)
            else datetime.now(UTC)
        )
        with services.database.transaction() as transaction:
            pending_deletions = transaction.fetch_all(
                """
                SELECT account_id, id
                FROM worlds
                WHERE status = 'pending_deletion'
                ORDER BY account_id, id
                """
            )
            accounts = transaction.fetch_all("SELECT id FROM accounts ORDER BY id")
        purged = sum(
            services.world_data.purge_due_deletion(
                str(world["account_id"]),
                str(world["id"]),
                observed_at=observed_at,
            )
            for world in pending_deletions
        )
        for account in accounts:
            account_id = str(account["id"])
            services.storage.evaluate(
                account_id,
                wallet_can_fund=(
                    services.billing.get_wallet(account_id).available_balance > Decimal("0.00")
                ),
                observed_at=observed_at,
            )
        return {"purged": purged, "storage_accounts": len(accounts)}
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
