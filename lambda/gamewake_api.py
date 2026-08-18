from __future__ import annotations

import base64
import json
import logging
import os
from decimal import Decimal
from typing import Any

import boto3
from discord_signature import SignatureValidationError, verify_discord_signature

from gamewake.accounts import Accounts
from gamewake.auth import DiscordOAuthClient, KmsSessionCodec
from gamewake.aws import (
    Ec2SsmConnectionDetailsProvider,
    S3WorldArchiveStore,
    SsmWorldPasswordManager,
)
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
from gamewake.experience import (
    DiscordCommandController,
    DiscordInteractionAdapter,
    DiscordInteractionWebhookClient,
    DiscordInvitationNotifier,
    DiscordRestMessageClient,
)
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

_LOGGER = logging.getLogger(__name__)
_DEFERRED_DISCORD_EVENT_TYPE = "gamewake.discord.interaction.v1"


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
        client_factory=client_factory,
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
        world_password_manager=SsmWorldPasswordManager(
            parameter_prefix=_required("GAMEWAKE_WORLD_PARAMETER_PREFIX"),
            client=ssm,
        ),
        runtime_profile_hourly_rates=_runtime_profile_rates(),
    )
    console_url = _required("GAMEWAKE_CONSOLE_URL")
    discord = DiscordInteractionAdapter(
        DiscordCommandController(
            application,
            console_url=console_url,
            invitation_notifier=DiscordInvitationNotifier(
                DiscordRestMessageClient(_secret(ssm, "DISCORD_BOT_TOKEN_PARAMETER_NAME")),
                console_url=console_url,
            ),
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
_async_lambda_client: Any | None = None
_discord_interaction_responder: DiscordInteractionWebhookClient | None = None


def _http_response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        "isBase64Encoded": False,
    }


def _raw_body(event: dict[str, Any]) -> bytes:
    body = event.get("body") or ""
    if event.get("isBase64Encoded") is True:
        return base64.b64decode(body, validate=True)
    return str(body).encode()


def _is_discord_http_event(event: dict[str, Any]) -> bool:
    return (
        event.get("rawPath") == "/discord/interactions"
        and event.get("requestContext", {}).get("http", {}).get("method") == "POST"
    )


def _dispatch_deferred_discord(payload: dict[str, Any], context: Any) -> None:
    global _async_lambda_client
    if _async_lambda_client is None:
        _async_lambda_client = boto3.client("lambda")
    function_name = getattr(context, "invoked_function_arn", None) or _required(
        "AWS_LAMBDA_FUNCTION_NAME"
    )
    _async_lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="Event",
        Payload=json.dumps(
            {"eventType": _DEFERRED_DISCORD_EVENT_TYPE, "payload": payload},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode(),
    )


def _lightweight_discord_response(
    event: dict[str, Any],
    context: Any,
) -> dict[str, Any] | None:
    raw = _raw_body(event)
    headers = {
        str(key).casefold(): str(value) for key, value in (event.get("headers") or {}).items()
    }
    try:
        verify_discord_signature(headers, raw, _required("DISCORD_PUBLIC_KEY"))
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Discord payload must be an object")
    except SignatureValidationError:
        return _http_response(
            401,
            {"error": {"code": "invalid_discord_signature", "message": "Invalid signature"}},
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return _http_response(
            400,
            {"error": {"code": "invalid_request", "message": "Invalid request"}},
        )
    response = DiscordInteractionAdapter.lightweight_response(payload)
    if response is None:
        return None
    if payload.get("type") != 1:
        if not payload.get("application_id") or not payload.get("token"):
            return _http_response(
                400,
                {"error": {"code": "invalid_request", "message": "Invalid request"}},
            )
        try:
            _dispatch_deferred_discord(payload, context)
        except Exception:
            _LOGGER.exception(
                "Could not dispatch deferred Discord interaction",
                extra={"interaction_id": str(payload.get("id") or "unknown")},
            )
            return _http_response(
                200,
                {
                    "type": 4,
                    "data": {
                        "content": "Não foi possível iniciar a ação. Tente novamente em instantes.",
                        "flags": 64,
                        "allowed_mentions": {"parse": []},
                    },
                },
            )
    return _http_response(200, response)


def _process_deferred_discord(event: dict[str, Any]) -> dict[str, Any]:
    global _handler, _discord_interaction_responder
    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("deferred Discord payload must be an object")
    if _handler is None:
        _handler = build_handler()
    try:
        response = _handler.handle_discord(payload)
    except Exception:
        _LOGGER.exception(
            "Deferred Discord interaction failed",
            extra={"interaction_id": str(payload.get("id") or "unknown")},
        )
        response = {
            "type": 4,
            "data": {
                "content": "Não foi possível concluir a ação. Tente novamente em instantes.",
                "allowed_mentions": {"parse": []},
            },
        }
    if _discord_interaction_responder is None:
        _discord_interaction_responder = DiscordInteractionWebhookClient()
    _discord_interaction_responder.update_original(payload, response)
    return {"processed": True}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    global _handler
    if event.get("eventType") == _DEFERRED_DISCORD_EVENT_TYPE:
        return _process_deferred_discord(event)
    if _is_discord_http_event(event):
        lightweight = _lightweight_discord_response(event, context)
        if lightweight is not None:
            return lightweight
    if _handler is None:
        _handler = build_handler()
    return _handler.handle(event)
