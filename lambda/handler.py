"""Entrada da Lambda Function URL para Discord Interactions."""

import base64
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.config import Config
from config_service import DiscordConfig, EnvironmentConfigProvider
from discord_signature import SignatureValidationError, verify_discord_signature
from ec2_service import EC2Service, human_uptime
from response_service import message, plain_error, pong
from settings_interactions import SettingsInteractionController, is_settings_interaction
from settings_service import ParameterSettingsService

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

PING = 1
APPLICATION_COMMAND = 2
MESSAGE_COMPONENT = 3
MODAL_SUBMIT = 5
ADMINISTRATOR_PERMISSION = 1 << 3

_runtime: tuple[EnvironmentConfigProvider, EC2Service, ParameterSettingsService] | None = None


def _structured_log(event_name: str, **fields: Any) -> None:
    LOGGER.info(json.dumps({"event": event_name, **fields}, ensure_ascii=False, default=str))


def _raw_body(event: dict[str, Any]) -> bytes:
    body = event.get("body") or ""
    return base64.b64decode(body) if event.get("isBase64Encoded") else body.encode("utf-8")


def _runtime_services() -> tuple[EnvironmentConfigProvider, EC2Service, ParameterSettingsService]:
    global _runtime
    if _runtime is None:
        region = os.environ["AWS_REGION"]
        client_config = Config(
            connect_timeout=0.5,
            read_timeout=1.0,
            retries={"total_max_attempts": 1, "mode": "standard"},
        )
        ec2 = boto3.client("ec2", region_name=region, config=client_config)
        ssm_client = None

        def get_ssm_client():
            nonlocal ssm_client
            if ssm_client is None:
                ssm_client = boto3.client("ssm", region_name=region, config=client_config)
            return ssm_client

        _runtime = (
            EnvironmentConfigProvider(os.environ["DISCORD_CONFIG_JSON"]),
            EC2Service(
                ec2,
                None,
                os.environ["PALWORLD_INSTANCE_ID"],
                os.environ["PALWORLD_STATUS_PARAMETER_NAME"],
                ssm_client_factory=get_ssm_client,
            ),
            ParameterSettingsService(
                get_ssm_client,
                os.environ["PALWORLD_CONFIG_PARAMETER_NAME"],
                os.environ["PALWORLD_OVERRIDES_PARAMETER_NAME"],
            ),
        )
    return _runtime


def _member(interaction: dict[str, Any]) -> tuple[str, set[str]]:
    member = interaction.get("member") or {}
    user_id = str((member.get("user") or {}).get("id") or "")
    roles = {str(role) for role in member.get("roles", [])}
    return user_id, roles


def _authorized(interaction: dict[str, Any], config: DiscordConfig) -> bool:
    user_id, roles = _member(interaction)
    return bool(
        user_id
        and (
            user_id in config.allowed_user_ids or bool(roles.intersection(config.allowed_role_ids))
        )
    )


def _is_discord_admin(interaction: dict[str, Any]) -> bool:
    raw_permissions = str((interaction.get("member") or {}).get("permissions") or "0")
    try:
        return bool(int(raw_permissions) & ADMINISTRATOR_PERMISSION)
    except ValueError:
        return False


def _subcommand(interaction: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    data = interaction.get("data") or {}
    if data.get("name") != "palworld":
        return "", {}
    options = data.get("options") or []
    if not options:
        return "ajuda", {}
    selected = options[0]
    args = {str(option["name"]): option.get("value") for option in selected.get("options", [])}
    return str(selected.get("name") or ""), args


def _state_label(state: str) -> str:
    return {
        "pending": "iniciando",
        "running": "ligada",
        "stopping": "desligando",
        "stopped": "desligada",
        "shutting-down": "encerrando",
        "terminated": "removida",
    }.get(state, state)


def _snapshot_is_fresh(snapshot: dict[str, Any] | None, max_age_seconds: int = 600) -> bool:
    if not snapshot or not snapshot.get("updated_at"):
        return False
    try:
        updated_at = datetime.fromisoformat(str(snapshot["updated_at"]).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if updated_at.tzinfo is None:
        return False
    age_seconds = (datetime.now(UTC) - updated_at).total_seconds()
    return 0 <= age_seconds <= max_age_seconds


def _handle_start(service: EC2Service) -> dict[str, Any]:
    status = service.describe()
    if status.state == "stopped":
        service.start()
        return message(
            "🟡 O servidor Palworld está sendo iniciado.\n"
            "Assim que estiver disponível, o endereço será enviado no canal do webhook. "
            "O processo pode levar alguns minutos."
        )
    if status.state == "pending":
        return message("🟡 O servidor Palworld já está iniciando. Aguarde alguns minutos.")
    if status.state == "running":
        address = (
            f"{status.public_ip}:{os.getenv('PALWORLD_PORT', '8211')}"
            if status.public_ip
            else "IP sendo atribuído"
        )
        return message(f"🟢 A instância já está ligada. Endereço: `{address}`")
    if status.state == "stopping":
        return message(
            "🟠 A instância ainda está desligando. Tente novamente em alguns minutos.",
            ephemeral=True,
        )
    return message(
        "🔴 A instância não pode ser iniciada porque está encerrando ou foi removida. "
        "Verifique o Terraform.",
        ephemeral=True,
    )


def _handle_status(service: EC2Service) -> dict[str, Any]:
    status = service.describe()
    if status.state == "stopped":
        return message("⚫ O servidor Palworld está desligado.", ephemeral=True)
    if status.state != "running":
        return message(f"🟡 Estado da instância: **{_state_label(status.state)}**.", ephemeral=True)

    port = os.getenv("PALWORLD_PORT", "8211")
    address = f"{status.public_ip}:{port}" if status.public_ip else "IP público ainda indisponível"
    lines = [
        "🟢 **Servidor Palworld**",
        f"Estado da EC2: **{_state_label(status.state)}**",
        f"Endereço: `{address}`",
        f"Tempo desde a inicialização: **{human_uptime(status.launch_time)}**",
    ]
    snapshot = service.read_game_snapshot()
    if _snapshot_is_fresh(snapshot):
        lines.append(f"Serviço Palworld: **{snapshot.get('service_state', 'desconhecido')}**")
        if isinstance(snapshot.get("players"), int):
            lines.append(f"Jogadores conectados: **{snapshot['players']}**")
    else:
        lines.append("Serviço/jogadores: **sem telemetria recente**")
    return message("\n".join(lines), ephemeral=True)


def _handle_shutdown(
    interaction: dict[str, Any], service: EC2Service, args: dict[str, Any]
) -> dict[str, Any]:
    status = service.describe()
    if status.state in {"stopped", "stopping"}:
        return message(f"⚫ A instância já está {_state_label(status.state)}.", ephemeral=True)
    if status.state != "running":
        return message(
            f"🟠 Não é seguro desligar enquanto a instância está {_state_label(status.state)}.",
            ephemeral=True,
        )

    force = args.get("forcar") is True
    if force and not _is_discord_admin(interaction):
        return message(
            "⛔ Apenas administradores do Discord podem usar `forcar: true`.", ephemeral=True
        )

    snapshot = service.read_game_snapshot()
    snapshot_players = snapshot.get("players") if snapshot else None
    if (
        not force
        and _snapshot_is_fresh(snapshot)
        and isinstance(snapshot_players, int)
        and snapshot_players > 0
    ):
        players = snapshot_players
        return message(
            f"⚠️ Há **{players}** jogador(es) conectado(s). O desligamento foi cancelado.",
            ephemeral=True,
        )

    command_id = service.request_safe_shutdown(force=force)
    qualifier = "forçado" if force else "seguro"
    return message(
        f"🟠 Desligamento {qualifier} solicitado (`{command_id[:8]}`). "
        "A máquina verificará os jogadores novamente, salvará o mundo e só então será desligada."
    )


def _handle_help() -> dict[str, Any]:
    return message(
        "**Comandos Palworld**\n"
        "`/palworld ligar` — inicia a instância.\n"
        "`/palworld status` — mostra EC2, endereço e jogadores quando disponíveis.\n"
        "`/palworld desligar` — salva e desliga somente após uma verificação segura.\n"
        "`/palworld desligar forcar:true` — uso exclusivo de administradores.\n"
        "`/palworld configurar` — abre o painel guiado de configurações.\n"
        "`/palworld ajuda` — exibe esta ajuda.",
        ephemeral=True,
    )


def process_event(
    event: dict[str, Any],
    config_provider: EnvironmentConfigProvider,
    service: EC2Service,
    settings_service: ParameterSettingsService | None = None,
) -> dict[str, Any]:
    raw_body = _raw_body(event)
    config = config_provider.get()
    verify_discord_signature(event.get("headers") or {}, raw_body, config.public_key)

    try:
        interaction = json.loads(raw_body)
    except json.JSONDecodeError:
        return plain_error(400, "JSON invalido")

    if interaction.get("type") == PING:
        return pong()
    interaction_type = interaction.get("type")
    if interaction_type not in {APPLICATION_COMMAND, MESSAGE_COMPONENT, MODAL_SUBMIT}:
        return message("Tipo de interação não suportado.", ephemeral=True)
    if str(interaction.get("guild_id") or "") != config.guild_id:
        return message("⛔ Este servidor Discord não está autorizado.", ephemeral=True)
    if not _authorized(interaction, config):
        return message("⛔ Você não tem permissão para controlar o servidor.", ephemeral=True)

    if is_settings_interaction(interaction):
        if settings_service is None:
            return message("Configuração pelo Discord indisponível.", ephemeral=True)
        return SettingsInteractionController(settings_service, service).handle(interaction)
    if interaction_type != APPLICATION_COMMAND:
        return message("Interação desconhecida.", ephemeral=True)

    command, args = _subcommand(interaction)
    _structured_log("command_received", command=command, guild_id=interaction.get("guild_id"))
    if command == "ligar":
        return _handle_start(service)
    if command == "status":
        return _handle_status(service)
    if command == "desligar":
        return _handle_shutdown(interaction, service, args)
    if command == "ajuda":
        return _handle_help()
    if command == "configurar":
        if settings_service is None:
            return message("Configuração pelo Discord indisponível.", ephemeral=True)
        return SettingsInteractionController(settings_service, service).handle(interaction)
    return message("Comando desconhecido. Use `/palworld ajuda`.", ephemeral=True)


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    try:
        config_provider, service, settings_service = _runtime_services()
        return process_event(event, config_provider, service, settings_service)
    except SignatureValidationError as exc:
        _structured_log("invalid_signature", reason=str(exc))
        return plain_error(401, "assinatura invalida")
    except Exception as exc:
        _structured_log("unhandled_error", error_type=type(exc).__name__, message=str(exc))
        return plain_error(500, "falha interna ao processar a interacao")
