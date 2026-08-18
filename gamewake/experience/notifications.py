from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from gamewake.accounts import Account, Invitation
from gamewake.worlds import OperationStatus, OperationType, World, WorldOperation


class DiscordMessageClient(Protocol):
    def create(
        self,
        channel_id: str,
        *,
        content: str,
        nonce: str,
        enforce_nonce: bool,
    ) -> None: ...


class DiscordDirectMessageClient(Protocol):
    def create_direct(
        self,
        recipient_user_id: str,
        *,
        content: str,
        nonce: str,
        enforce_nonce: bool,
    ) -> None: ...


class DiscordRestMessageClient:
    def __init__(self, bot_token: str, *, opener: Any = urlopen) -> None:
        if not bot_token:
            raise ValueError("Discord Bot Token is required")
        self._bot_token = bot_token
        self._opener = opener

    def create(
        self,
        channel_id: str,
        *,
        content: str,
        nonce: str,
        enforce_nonce: bool,
    ) -> None:
        payload = json.dumps(
            {
                "content": content,
                "nonce": nonce,
                "enforce_nonce": enforce_nonce,
                "allowed_mentions": {"parse": []},
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        request = Request(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            data=payload,
            headers={
                "Authorization": f"Bot {self._bot_token}",
                "Content-Type": "application/json",
                "User-Agent": "GameWake (https://gamewake.example, 1.0)",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=15):
                return
        except (HTTPError, URLError, TimeoutError) as error:
            raise RuntimeError("Discord notification failed") from error

    def create_direct(
        self,
        recipient_user_id: str,
        *,
        content: str,
        nonce: str,
        enforce_nonce: bool,
    ) -> None:
        payload = json.dumps(
            {"recipient_id": recipient_user_id},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        request = Request(
            "https://discord.com/api/v10/users/@me/channels",
            data=payload,
            headers={
                "Authorization": f"Bot {self._bot_token}",
                "Content-Type": "application/json",
                "User-Agent": "GameWake (https://gamewake.example, 1.0)",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=15) as response:
                direct_channel_id = str(json.loads(response.read())["id"])
            if not direct_channel_id:
                raise ValueError("Discord returned an empty direct channel")
        except (HTTPError, URLError, TimeoutError, KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Discord direct message channel failed") from error
        self.create(
            direct_channel_id,
            content=content,
            nonce=nonce,
            enforce_nonce=enforce_nonce,
        )


class DiscordInvitationNotifier:
    """Sends a targeted, non-sensitive acceptance path to an invited Discord user."""

    def __init__(
        self,
        messages: DiscordDirectMessageClient,
        *,
        console_url: str,
    ) -> None:
        self._messages = messages
        self._console_url = console_url.rstrip("/")

    def notify(
        self,
        account: Account,
        invitation: Invitation,
        *,
        inviter_name: str,
        recipient_discord_user_id: str,
    ) -> bool:
        acceptance_url = f"{self._console_url}/convites/{account.id}/{invitation.id}"
        content = (
            f"🎮 **{inviter_name} convidou você para {account.name} no GameWake.**\n"
            "Você entrará como **Player** depois de aceitar.\n"
            f"Aceitar convite: {acceptance_url}\n"
            "Se preferir, use `/gamewake aceitar` no servidor do grupo."
        )
        nonce = sha256(f"invitation:{invitation.id}".encode()).hexdigest()[:25]
        self._messages.create_direct(
            recipient_discord_user_id,
            content=content,
            nonce=nonce,
            enforce_nonce=True,
        )
        return True


class DiscordChannelNotifier:
    """Publishes terminal operation status without connection secrets or mentions."""

    def __init__(self, messages: DiscordMessageClient) -> None:
        self._messages = messages

    def notify(
        self,
        account: Account,
        world: World,
        operation: WorldOperation,
    ) -> bool:
        if account.discord_channel_id is None:
            return False
        content = self._content(world, operation)
        nonce = sha256(operation.id.encode()).hexdigest()[:25]
        self._messages.create(
            account.discord_channel_id,
            content=content,
            nonce=nonce,
            enforce_nonce=True,
        )
        return True

    @staticmethod
    def _content(world: World, operation: WorldOperation) -> str:
        if operation.status in {OperationStatus.FAILED, OperationStatus.NEEDS_ATTENTION}:
            return (
                f"🔴 **{world.name}** precisa de atenção. "
                "Abra a GameWake Console para revisar a operação."
            )
        if operation.status is OperationStatus.CANCELLED:
            return f"🟠 A operação de **{world.name}** foi cancelada com segurança."
        if operation.operation_type is OperationType.WAKE:
            return (
                f"🟢 **{world.name}** está Online. "
                "Use `/gamewake conectar` para receber o endereço e a senha em privado."
            )
        if operation.operation_type is OperationType.SLEEP:
            return f"⚫ **{world.name}** foi salvo, verificado e está dormindo."
        return f"🟢 **{world.name}** foi recuperado e está Online."
