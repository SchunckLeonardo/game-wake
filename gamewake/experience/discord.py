from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from gamewake.control_plane import GameWakeApplication
from gamewake.worlds import World, WorldOperation

_OPERATION_PHASES = {
    "wake": (
        "requested",
        "provisioning_runtime",
        "restoring_world",
        "applying_configuration",
        "starting_game",
        "checking_game_health",
        "complete",
    ),
    "sleep": (
        "requested",
        "checking_players",
        "saving_game",
        "stopping_game",
        "persisting_world",
        "creating_backup",
        "releasing_runtime",
        "complete",
    ),
}

_OPERATION_PHASE_COPY = {
    "requested": (
        "Pedido recebido",
        "A GameWake está validando o despertar e protegendo a reserva.",
    ),
    "provisioning_runtime": (
        "Reservando a máquina do jogo",
        "Separando uma máquina temporária só para este World.",
    ),
    "restoring_world": (
        "Preparando a máquina do jogo",
        "Iniciando o ambiente e restaurando seu World protegido.",
    ),
    "applying_configuration": (
        "Aplicando suas configurações",
        "Carregando as regras salvas para esta sessão.",
    ),
    "starting_game": ("Iniciando Palworld", "Abrindo o servidor com o progresso restaurado."),
    "checking_game_health": (
        "Confirmando que está pronto",
        "Testando a conexão real antes de liberar o endereço.",
    ),
    "checking_players": (
        "Verificando jogadores",
        "Confirmando que ninguém será desconectado sem aviso.",
    ),
    "saving_game": ("Salvando o progresso", "Pedindo ao Palworld o save mais recente."),
    "stopping_game": ("Encerrando Palworld", "Fechando o jogo depois do save."),
    "persisting_world": (
        "Protegendo o World",
        "Enviando o progresso para o armazenamento durável.",
    ),
    "creating_backup": ("Validando o Backup", "Conferindo a cópia recuperável."),
    "releasing_runtime": (
        "Liberando a máquina",
        "Encerrando a cobrança da infraestrutura temporária.",
    ),
    "complete": ("Operação concluída", "A etapa final foi concluída com segurança."),
}


@dataclass(frozen=True)
class DiscordUser:
    id: str
    display_name: str


@dataclass(frozen=True)
class DiscordInteraction:
    id: str
    guild_id: str
    discord_user_id: str
    display_name: str
    command: str
    channel_id: str | None = None
    selected_users: tuple[DiscordUser, ...] = ()
    world_id: str | None = None


@dataclass(frozen=True)
class DiscordWorldOption:
    id: str
    label: str
    status: str


@dataclass(frozen=True)
class DiscordCommandResponse:
    content: str
    ephemeral: bool
    world_options: tuple[DiscordWorldOption, ...] = ()
    links: tuple[tuple[str, str], ...] = ()
    select_command: str | None = None


class DiscordCommandController:
    def __init__(self, application: GameWakeApplication, *, console_url: str) -> None:
        self._application = application
        self._console_url = console_url.rstrip("/")

    def handle(self, interaction: DiscordInteraction) -> DiscordCommandResponse:
        try:
            if interaction.command == "comecar":
                account, _ = self._application.start_discord_account(
                    discord_guild_id=interaction.guild_id,
                    discord_user_id=interaction.discord_user_id,
                    display_name=interaction.display_name,
                    discord_channel_id=interaction.channel_id,
                )
                return DiscordCommandResponse(
                    content=(
                        "✅ **Conta do servidor pronta. Próximos passos:**\n"
                        "1. Abra a Console e crie o primeiro World.\n"
                        "2. Use `/gamewake convidar` para chamar os amigos; "
                        "cada um aceita com `/gamewake aceitar`.\n"
                        "3. Adicione créditos via Pix e use `/gamewake acordar` quando forem jogar."
                    ),
                    ephemeral=True,
                    links=(
                        ("Abrir GameWake Console", f"{self._console_url}/accounts/{account.id}"),
                    ),
                )
            account, actor = self._application.resolve_discord_principal(
                discord_guild_id=interaction.guild_id,
                discord_user_id=interaction.discord_user_id,
                display_name=interaction.display_name,
            )
            if interaction.command == "aceitar":
                self._application.accept_pending_invitation(
                    account.id,
                    invited_user_id=actor.id,
                )
                return DiscordCommandResponse(
                    content="✅ Convite aceito. Você agora tem a Role Player.",
                    ephemeral=True,
                )
            if interaction.command == "convidar":
                invitations = self._application.invite_discord_friends(
                    account.id,
                    actor_user_id=actor.id,
                    friends=[
                        (friend.id, friend.display_name) for friend in interaction.selected_users
                    ],
                )
                return DiscordCommandResponse(
                    content=(
                        f"✅ {len(invitations)} convites enviados separadamente. "
                        "Agora cada amigo precisa usar `/gamewake aceitar` neste servidor."
                    ),
                    ephemeral=True,
                )
            if interaction.command in {"status", "acordar"}:
                world_or_response = self._resolve_world(
                    account.id,
                    actor_user_id=actor.id,
                    selected_world_id=interaction.world_id,
                    command=interaction.command,
                )
                if isinstance(world_or_response, DiscordCommandResponse):
                    return world_or_response
                world = world_or_response
                if interaction.command == "status":
                    operations = self._application.worlds.list_operations(
                        account.id,
                        world.id,
                        viewer_user_id=actor.id,
                    )
                    active_operation = next(
                        (
                            operation
                            for operation in reversed(operations)
                            if operation.status.value in {"pending", "running"}
                        ),
                        None,
                    )
                    progress = (
                        f"\n{self._operation_progress(active_operation)}"
                        if active_operation is not None
                        else ""
                    )
                    return DiscordCommandResponse(
                        content=(
                            f"{self._status_icon(world.status.value)} **{world.name}**\n"
                            f"Estado: **{self._status_label(world.status.value)}**"
                            f"{progress}"
                        ),
                        ephemeral=False,
                    )
                operation = self._application.request_wake(
                    account.id,
                    world.id,
                    actor_user_id=actor.id,
                    idempotency_key=f"discord:{interaction.id}:wake",
                )
                return DiscordCommandResponse(
                    content=(
                        f"🟡 **{world.name}** está acordando. "
                        f"Operação `{operation.id[:8]}` iniciada.\n"
                        f"{self._operation_progress(operation)}\n"
                        "Acompanhe a etapa atual com `/gamewake status`."
                    ),
                    ephemeral=False,
                )
            if interaction.command in {"conectar", "dormir", "configurar"}:
                world_or_response = self._resolve_world(
                    account.id,
                    actor_user_id=actor.id,
                    selected_world_id=interaction.world_id,
                    command=interaction.command,
                )
                if isinstance(world_or_response, DiscordCommandResponse):
                    return world_or_response
                world = world_or_response
                if interaction.command == "conectar":
                    details = self._application.connection_details(
                        account.id,
                        world.id,
                        viewer_user_id=actor.id,
                    )
                    password = (
                        f"\nSenha: `{details.password}`" if details.password is not None else ""
                    )
                    return DiscordCommandResponse(
                        content=(
                            f"🔐 **Conexão privada — {world.name}**\n"
                            f"Endereço: `{details.host}:{details.port}`{password}"
                        ),
                        ephemeral=True,
                    )
                if interaction.command == "configurar":
                    return DiscordCommandResponse(
                        content=f"Configure **{world.name}** na GameWake Console.",
                        ephemeral=True,
                        links=(
                            (
                                "Abrir configurações",
                                (
                                    f"{self._console_url}/accounts/{account.id}/worlds/"
                                    f"{world.id}/configuration"
                                ),
                            ),
                        ),
                    )
                operation = self._application.request_sleep(
                    account.id,
                    world.id,
                    actor_user_id=actor.id,
                    idempotency_key=f"discord:{interaction.id}:sleep",
                )
                return DiscordCommandResponse(
                    content=(
                        f"🟠 O sono seguro de **{world.name}** foi iniciado. "
                        f"Operação `{operation.id[:8]}`."
                    ),
                    ephemeral=False,
                )
            if interaction.command == "console":
                return DiscordCommandResponse(
                    content="Abra a GameWake Console para gerenciar o grupo.",
                    ephemeral=True,
                    links=(
                        (
                            "Abrir GameWake Console",
                            f"{self._console_url}/accounts/{account.id}",
                        ),
                    ),
                )
            if interaction.command == "ajuda":
                return DiscordCommandResponse(
                    content=(
                        "**COMECE AQUI**\n"
                        "1. `/gamewake comecar` — cria a conta deste servidor.\n"
                        "2. Abra a Console e crie o primeiro World.\n"
                        "3. Adicione créditos e use `/gamewake acordar`.\n\n"
                        "**Comandos GameWake**\n"
                        "`/gamewake convidar` — convida até três amigos de uma vez.\n"
                        "`/gamewake aceitar` — cada amigo aceita seu convite pendente.\n"
                        "`/gamewake status` — mostra o estado do World.\n"
                        "`/gamewake acordar` — prepara o World para jogar.\n"
                        "`/gamewake conectar` — entrega conexão e senha em privado.\n"
                        "`/gamewake dormir` — salva e inicia o sono seguro.\n"
                        "`/gamewake configurar` — abre a configuração guiada.\n"
                        "`/gamewake console` — abre a GameWake Console."
                    ),
                    ephemeral=True,
                )
            return DiscordCommandResponse(
                content="Comando desconhecido. Use `/gamewake ajuda`.",
                ephemeral=True,
            )
        except PermissionError:
            return DiscordCommandResponse(
                content="⛔ Você não tem permissão para esta ação.",
                ephemeral=True,
            )
        except KeyError:
            return DiscordCommandResponse(
                content="Este servidor Discord ainda não está conectado ao GameWake.",
                ephemeral=True,
            )
        except ValueError as error:
            return DiscordCommandResponse(
                content=f"Não foi possível concluir: {error}",
                ephemeral=True,
            )

    def _resolve_world(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        selected_world_id: str | None,
        command: str,
    ) -> World | DiscordCommandResponse:
        worlds = self._application.list_worlds(
            account_id,
            viewer_user_id=actor_user_id,
        )
        if selected_world_id is not None:
            selected = next(
                (world for world in worlds if world.id == selected_world_id),
                None,
            )
            if selected is None:
                return DiscordCommandResponse(
                    content="O World solicitado não está disponível para você.",
                    ephemeral=True,
                )
            return selected
        if len(worlds) == 1:
            return worlds[0]
        if not worlds:
            return DiscordCommandResponse(
                content=(
                    "Nenhum World foi criado ainda. Abra a GameWake Console, "
                    "crie o primeiro World e depois use `/gamewake acordar`."
                ),
                ephemeral=True,
                links=(("Criar primeiro World", f"{self._console_url}/accounts/{account_id}"),),
            )
        return DiscordCommandResponse(
            content="Escolha um World para continuar:",
            ephemeral=True,
            select_command=command,
            world_options=tuple(
                DiscordWorldOption(
                    id=world.id,
                    label=world.name,
                    status=world.status.value,
                )
                for world in worlds
            ),
        )

    @staticmethod
    def _status_label(status: str) -> str:
        return {
            "sleeping": "dormindo",
            "waking": "acordando",
            "online": "online",
            "going_to_sleep": "indo dormir",
            "needs_attention": "precisa de atenção",
            "pending_deletion": "exclusão pendente",
        }.get(status, status)

    @staticmethod
    def _status_icon(status: str) -> str:
        return {
            "sleeping": "⚫",
            "waking": "🟡",
            "online": "🟢",
            "going_to_sleep": "🟠",
            "needs_attention": "🔴",
            "pending_deletion": "⚪",
        }.get(status, "⚪")

    @staticmethod
    def _operation_progress(operation: WorldOperation) -> str:
        operation_type = operation.operation_type.value
        phase = operation.phase.value
        phases = _OPERATION_PHASES.get(operation_type, (phase,))
        current = phases.index(phase) + 1 if phase in phases else 1
        label, detail = _OPERATION_PHASE_COPY.get(
            phase,
            (phase.replace("_", " ").capitalize(), "Acompanhando a operação persistida."),
        )
        return f"Etapa {current} de {len(phases)}: **{label}**\n{detail}"


class DiscordInteractionAdapter:
    """Maps Discord's wire payload to the transport-neutral command controller."""

    def __init__(self, controller: DiscordCommandController) -> None:
        self._controller = controller

    def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        interaction_type = payload.get("type")
        if interaction_type == 1:
            return {"type": 1}
        if interaction_type not in {2, 3}:
            return self._render(
                DiscordCommandResponse(
                    content="Interação do Discord não suportada.",
                    ephemeral=True,
                )
            )

        member_user = (payload.get("member") or {}).get("user") or {}
        data = payload.get("data") or {}
        command, option_values = self._command(data, interaction_type)
        resolved_users = (data.get("resolved") or {}).get("users") or {}
        selected_users = tuple(
            self._resolved_user(resolved_users, str(option["value"]))
            for option in option_values
            if option.get("type") == 6 and option.get("value") is not None
        )
        world_id = next(
            (
                str(option["value"])
                for option in option_values
                if option.get("name") in {"world", "mundo"} and option.get("value") is not None
            ),
            None,
        )
        response = self._controller.handle(
            DiscordInteraction(
                id=str(payload.get("id") or "unknown"),
                guild_id=str(payload.get("guild_id") or ""),
                channel_id=str(payload.get("channel_id") or "") or None,
                discord_user_id=str(member_user.get("id") or ""),
                display_name=str(
                    member_user.get("global_name") or member_user.get("username") or "Discord User"
                ),
                command=command,
                selected_users=selected_users,
                world_id=world_id,
            )
        )
        return self._render(response)

    @classmethod
    def lightweight_response(cls, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Returns responses that must not wait for control-plane dependencies."""
        interaction_type = payload.get("type")
        if interaction_type == 1:
            return {"type": 1}
        if interaction_type not in {2, 3}:
            return None
        command, _ = cls._command(payload.get("data") or {}, interaction_type)
        if command != "acordar":
            return None
        return {"type": 6} if interaction_type == 3 else {"type": 5}

    @staticmethod
    def _command(
        data: dict[str, Any],
        interaction_type: object,
    ) -> tuple[str, list[dict[str, Any]]]:
        if interaction_type == 3:
            custom_id = str(data.get("custom_id") or "")
            prefix = "gamewake:world:"
            if not custom_id.startswith(prefix):
                return "unknown", []
            values = data.get("values") or []
            return custom_id.removeprefix(prefix), [
                {"name": "world", "value": values[0]} if values else {}
            ]
        if data.get("name") != "gamewake":
            return "unknown", []
        root_options = data.get("options") or []
        if not root_options:
            return "ajuda", []
        selected = root_options[0]
        return str(selected.get("name") or "unknown"), list(selected.get("options") or [])

    @staticmethod
    def _resolved_user(users: dict[str, Any], user_id: str) -> DiscordUser:
        user = users.get(user_id) or {}
        return DiscordUser(
            id=user_id,
            display_name=str(user.get("global_name") or user.get("username") or user_id),
        )

    @staticmethod
    def _render(response: DiscordCommandResponse) -> dict[str, Any]:
        data: dict[str, Any] = {
            "content": response.content,
            "allowed_mentions": {"parse": []},
        }
        if response.ephemeral:
            data["flags"] = 64
        components: list[dict[str, Any]] = []
        if response.world_options:
            components.append(
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 3,
                            "custom_id": f"gamewake:world:{response.select_command}",
                            "placeholder": "Selecione um World",
                            "options": [
                                {
                                    "label": option.label[:100],
                                    "value": option.id,
                                    "description": f"Estado: {option.status}"[:100],
                                }
                                for option in response.world_options[:25]
                            ],
                        }
                    ],
                }
            )
        if response.links:
            components.append(
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 2,
                            "style": 5,
                            "label": label[:80],
                            "url": url,
                        }
                        for label, url in response.links[:5]
                    ],
                }
            )
        if components:
            data["components"] = components
        return {"type": 4, "data": data}


class DiscordInteractionWebhookClient:
    """Edits a deferred Discord interaction without requiring the Bot token."""

    def __init__(self, *, opener: Any = urlopen) -> None:
        self._opener = opener

    def update_original(self, payload: dict[str, Any], response: dict[str, Any]) -> None:
        application_id = str(payload.get("application_id") or "")
        interaction_token = str(payload.get("token") or "")
        data = response.get("data")
        if not application_id or not interaction_token or not isinstance(data, dict):
            raise ValueError("deferred Discord interaction is incomplete")
        message = {key: value for key, value in data.items() if key != "flags"}
        encoded = json.dumps(
            message,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        request = Request(
            (
                "https://discord.com/api/v10/webhooks/"
                f"{quote(application_id, safe='')}/{quote(interaction_token, safe='')}"
                "/messages/@original"
            ),
            data=encoded,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "GameWake (https://gamewake.example, 1.0)",
            },
            method="PATCH",
        )
        try:
            with self._opener(request, timeout=15):
                return
        except (HTTPError, URLError, TimeoutError):
            raise RuntimeError("Discord interaction response failed") from None
