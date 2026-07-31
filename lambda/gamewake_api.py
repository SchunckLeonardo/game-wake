from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any

import boto3
from discord_signature import verify_discord_signature

from gamewake.accounts import Accounts
from gamewake.auth import DiscordOAuthClient, KmsSessionCodec
from gamewake.aws import Ec2SsmConnectionDetailsProvider, S3WorldArchiveStore
from gamewake.billing import (
    AbacatePayPaymentProvider,
    AbacatePayWebhookHandler,
    Billing,
    ContributionPackage,
)
from gamewake.control_plane import (
    GameWakeApi,
    GameWakeApplication,
    GameWakeHttpHandler,
)
from gamewake.experience import DiscordCommandController, DiscordInteractionAdapter
from gamewake.game_catalog import GameCatalog
from gamewake.orchestration import StepFunctionsOperationOrchestrator
from gamewake.persistence import (
    AuroraDataApi,
    PostgresAccountRepository,
    PostgresBillingRepository,
    PostgresRecoverySecretStore,
    PostgresStoragePolicyRepository,
    PostgresWorldRepository,
)
from gamewake.worlds import StoragePolicy, StoragePolicyService, WorldData, Worlds


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def _secret(ssm: Any, environment_name: str) -> str:
    return str(
        ssm.get_parameter(
            Name=_required(environment_name),
            WithDecryption=True,
        )["Parameter"]["Value"]
    )


def _packages() -> tuple[ContributionPackage, ...]:
    raw = json.loads(_required("ABACATEPAY_PACKAGES_JSON"))
    if not isinstance(raw, list):
        raise RuntimeError("ABACATEPAY_PACKAGES_JSON must be a list")
    return tuple(
        ContributionPackage(
            id=str(item["id"]),
            amount=Decimal(str(item["amount"])),
            provider_product_id=str(item["productId"]),
        )
        for item in raw
    )


def _runtime_profile_rates() -> dict[str, Decimal]:
    raw = json.loads(_required("RUNTIME_PROFILE_HOURLY_RATES_JSON"))
    if not isinstance(raw, dict) or not raw:
        raise RuntimeError("RUNTIME_PROFILE_HOURLY_RATES_JSON must be an object")
    return {str(profile): Decimal(str(rate)) for profile, rate in raw.items()}


def build_handler(*, client_factory: Any = boto3.client) -> GameWakeHttpHandler:
    ssm = client_factory("ssm")
    database = AuroraDataApi(
        _required("AURORA_CLUSTER_ARN"),
        _required("AURORA_SECRET_ARN"),
        _required("AURORA_DATABASE_NAME"),
        client=client_factory("rds-data"),
    )
    account_repository = PostgresAccountRepository(database)
    accounts = Accounts(
        account_repository,
        recovery_secret_store=PostgresRecoverySecretStore(database),
    )
    billing = Billing(
        PostgresBillingRepository(database),
        payment_provider=AbacatePayPaymentProvider(
            api_key=_secret(ssm, "ABACATEPAY_API_KEY_PARAMETER_NAME")
        ),
        contribution_packages=_packages(),
    )
    catalog = GameCatalog.with_palworld()
    world_repository = PostgresWorldRepository(database)
    archive = S3WorldArchiveStore(
        _required("WORLD_DATA_BUCKET"),
        client=client_factory("s3"),
    )
    storage = StoragePolicyService(
        world_repository,
        archive_store=archive,
        repository=PostgresStoragePolicyRepository(database),
        policy=StoragePolicy(
            allowance_bytes=int(_required("STORAGE_ALLOWANCE_BYTES")),
            grace_days=int(_required("STORAGE_GRACE_DAYS")),
        ),
    )
    worlds = Worlds(
        world_repository,
        access=accounts,
        game_catalog=catalog,
        storage_gate=storage,
    )
    world_data = WorldData(
        world_repository,
        access=accounts,
        archive_store=archive,
        storage_gate=storage,
    )
    application = GameWakeApplication(
        accounts=accounts,
        worlds=worlds,
        world_data=world_data,
        billing=billing,
        game_catalog=catalog,
        operation_dispatcher=StepFunctionsOperationOrchestrator(
            _required("WORLD_OPERATION_STATE_MACHINE_ARN"),
            client=client_factory("stepfunctions"),
        ),
        connection_details_provider=Ec2SsmConnectionDetailsProvider(
            parameter_prefix=_required("GAMEWAKE_WORLD_PARAMETER_PREFIX"),
            ec2_client=client_factory("ec2"),
            ssm_client=ssm,
            port=int(_required("PALWORLD_PORT")),
        ),
        runtime_profile_hourly_rates=_runtime_profile_rates(),
    )
    discord = DiscordInteractionAdapter(
        DiscordCommandController(
            application,
            console_url=_required("GAMEWAKE_CONSOLE_URL"),
        )
    )
    webhook = AbacatePayWebhookHandler(
        webhook_secret=_secret(ssm, "ABACATEPAY_WEBHOOK_SECRET_PARAMETER_NAME"),
        public_hmac_key=_secret(ssm, "ABACATEPAY_PUBLIC_KEY_PARAMETER_NAME"),
        event_processor=billing.process_payment_event,
    )
    public_key = _required("DISCORD_PUBLIC_KEY")
    return GameWakeHttpHandler(
        application=application,
        api=GameWakeApi(application),
        sessions=KmsSessionCodec(_required("SESSION_KMS_KEY_ID"), client=client_factory("kms")),
        oauth=DiscordOAuthClient(
            client_id=_required("DISCORD_APPLICATION_ID"),
            client_secret=_secret(ssm, "DISCORD_CLIENT_SECRET_PARAMETER_NAME"),
        ),
        console_url=_required("GAMEWAKE_CONSOLE_URL"),
        oauth_redirect_uri=(
            f"{os.environ['GAMEWAKE_API_BASE_URL'].rstrip('/')}/auth/discord/callback"
            if os.environ.get("GAMEWAKE_API_BASE_URL")
            else None
        ),
        discord=discord,
        verify_discord=lambda headers, raw: verify_discord_signature(headers, raw, public_key),
        abacatepay_webhook=webhook,
    )


_handler: GameWakeHttpHandler | None = None


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    del context
    global _handler
    if _handler is None:
        _handler = build_handler()
    return _handler.handle(event)
