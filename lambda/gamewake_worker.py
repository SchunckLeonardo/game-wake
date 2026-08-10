from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
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
from gamewake.billing import Billing, BillingRuntimeUsageRecorder, InsufficientFundsError
from gamewake.experience import DiscordChannelNotifier, DiscordRestMessageClient
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
    OperationStatus,
    OperationType,
    StoragePolicy,
    StoragePolicyService,
    WorldData,
    WorldOperationWorker,
    WorldStatus,
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
    storage_rate_per_gib_month: Decimal
    world_repository: PostgresWorldRepository
    account_repository: PostgresAccountRepository
    notifier: DiscordChannelNotifier


def _required(environ: dict[str, str], name: str) -> str:
    value = environ.get(name)
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def _secret(ssm: Any, environ: dict[str, str], parameter_environment_name: str) -> str:
    return str(
        ssm.get_parameter(
            Name=_required(environ, parameter_environment_name),
            WithDecryption=True,
        )["Parameter"]["Value"]
    )


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
    account_repository = PostgresAccountRepository(database)
    ssm = client_factory("ssm")
    runner = SsmCommandRunner(client=ssm)
    archive = S3WorldArchiveStore(
        _required(environ, "WORLD_DATA_BUCKET"),
        client=client_factory("s3"),
    )
    accounts = Accounts(account_repository)
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
                client=ssm,
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
        storage_rate_per_gib_month=Decimal(_required(environ, "STORAGE_RATE_PER_GIB_MONTH_BRL")),
        world_repository=repository,
        account_repository=account_repository,
        notifier=DiscordChannelNotifier(
            DiscordRestMessageClient(_secret(ssm, environ, "DISCORD_BOT_TOKEN_PARAMETER_NAME"))
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
    if action == "monitor_session":
        state_machine_arn = event.get("state_machine_arn")
        if not isinstance(state_machine_arn, str) or not state_machine_arn:
            raise ValueError("state_machine_arn is required for session monitoring")
        account_id = event.get("account_id")
        world_id = event.get("world_id")
        if not isinstance(account_id, str) or not isinstance(world_id, str):
            raise ValueError("account_id and world_id are required for session monitoring")
        raw_idle_minutes = event.get("idle_minutes")
        idle_minutes = int(raw_idle_minutes) if raw_idle_minutes is not None else None
        monitor_checks = int(event.get("monitor_checks", 0))
        if monitor_checks < 0:
            raise ValueError("monitor_checks must be non-negative")
        world = services.world_repository.get(account_id, world_id)
        orchestrator = services.orchestrator_factory(state_machine_arn)
        operation = None
        if world.status is WorldStatus.ONLINE:
            operation = services.worker.monitor_session(
                account_id,
                world_id,
                idle_minutes=idle_minutes,
            )
        elif world.status is WorldStatus.GOING_TO_SLEEP:
            operation = next(
                (
                    candidate
                    for candidate in reversed(
                        services.world_repository.list_operations(account_id, world_id)
                    )
                    if candidate.operation_type is OperationType.SLEEP
                    and candidate.status in {OperationStatus.PENDING, OperationStatus.RUNNING}
                ),
                None,
            )
        if operation is not None:
            orchestrator.ensure_running(account_id, operation.id)
        return {
            "account_id": account_id,
            "world_id": world_id,
            "session_monitor": True,
            "monitor_checks": monitor_checks + 1,
            "continue_monitoring": world.status is WorldStatus.ONLINE and operation is None,
            "sleep_operation_id": operation.id if operation is not None else None,
        }
    if action == "apply_support_credit":
        account_id = event.get("account_id")
        reference = event.get("reference")
        actor_user_id = event.get("actor_user_id")
        reason = event.get("reason")
        idempotency_key = event.get("idempotency_key")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (account_id, reference, actor_user_id, reason, idempotency_key)
        ):
            raise ValueError(
                "account_id, reference, actor_user_id, reason and idempotency_key are required"
            )
        credit = services.billing.apply_support_credit(
            account_id,
            amount=Decimal(str(event.get("amount_brl"))),
            reference=reference,
            actor_user_id=actor_user_id,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        return {
            "ledger_entry_id": credit.id,
            "entry_type": credit.entry_type.value,
            "amount_brl": str(credit.amount),
            "reference": credit.reference,
        }
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
        storage_charges = 0
        billing_month = f"{observed_at.year:04d}-{observed_at.month:02d}"
        for account in accounts:
            account_id = str(account["id"])
            status = services.storage.evaluate(
                account_id,
                wallet_can_fund=False,
                observed_at=observed_at,
            )
            if status.excess_bytes <= 0:
                continue
            estimated_charge = (
                services.storage_rate_per_gib_month
                * Decimal(status.excess_bytes)
                / Decimal(1024**3)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            funded = estimated_charge == Decimal("0.00")
            if not funded:
                try:
                    services.billing.charge_monthly_storage(
                        account_id,
                        excess_bytes=status.excess_bytes,
                        rate_per_gib_month=services.storage_rate_per_gib_month,
                        billing_month=billing_month,
                        idempotency_key=f"storage:{account_id}:{billing_month}",
                    )
                    funded = True
                    storage_charges += 1
                except InsufficientFundsError:
                    funded = False
            if funded:
                services.storage.evaluate(
                    account_id,
                    wallet_can_fund=True,
                    observed_at=observed_at,
                )
        return {
            "purged": purged,
            "storage_accounts": len(accounts),
            "storage_charges": storage_charges,
        }
    if action not in {"advance", "record_failure"}:
        raise ValueError(f"unsupported operation worker action: {action}")
    result = advance_operation(event, worker=services.worker)
    if result["terminal"] is True:
        account_id = str(result["account_id"])
        operation_id = str(result["operation_id"])
        operation = services.world_repository.get_operation(account_id, operation_id)
        world = services.world_repository.get(account_id, operation.world_id)
        account = services.account_repository.get(account_id).account
        try:
            result["notified"] = services.notifier.notify(account, world, operation)
        except Exception:
            logging.exception(
                "terminal Discord notification failed",
                extra={"account_id": account_id, "operation_id": operation_id},
            )
            result["notified"] = False
    return result


_services: _Services | None = None


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    del context
    global _services
    if _services is None:
        _services = build_services()
    return handle_event(event, services=_services)
