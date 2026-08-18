import json
from datetime import UTC, datetime
from urllib.error import URLError

import pytest

from gamewake.accounts import Account, Invitation, InvitationStatus
from gamewake.experience import (
    DiscordChannelNotifier,
    DiscordInteractionWebhookClient,
    DiscordInvitationNotifier,
    DiscordRestMessageClient,
)
from gamewake.worlds import (
    OperationPhase,
    OperationStatus,
    OperationType,
    World,
    WorldOperation,
    WorldStatus,
)


class Messages:
    def __init__(self):
        self.calls = []

    def create(self, channel_id, *, content, nonce, enforce_nonce):
        self.calls.append((channel_id, content, nonce, enforce_nonce))


class HttpResponse:
    def __init__(self, payload: bytes = b""):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.payload


class DirectMessages:
    def __init__(self):
        self.calls = []

    def create_direct(self, recipient_user_id, *, content, nonce, enforce_nonce):
        self.calls.append((recipient_user_id, content, nonce, enforce_nonce))


def test_terminal_world_notification_is_non_sensitive_and_idempotent_by_nonce():
    messages = Messages()
    notifier = DiscordChannelNotifier(messages)
    account = Account("account-1", "Grupo", "guild-1", "channel-1")
    world = World(
        "world-1",
        account.id,
        "Palpagos",
        "palworld:1",
        "sa-east-1",
        "palworld-small",
        WorldStatus.ONLINE,
        "runtime-1",
        "i-123",
        "revision-1",
        None,
        "state-1",
        "sha256:state",
        2,
    )
    operation = WorldOperation(
        "operation-12345678901234567890",
        account.id,
        world.id,
        OperationType.WAKE,
        OperationStatus.SUCCEEDED,
        OperationPhase.COMPLETE,
        "wake-1",
        datetime(2026, 7, 31, tzinfo=UTC),
        5,
    )

    assert notifier.notify(account, world, operation) is True
    channel_id, content, nonce, enforce_nonce = messages.calls[0]
    assert channel_id == "channel-1"
    assert "Palpagos" in content
    assert "/gamewake conectar" in content
    assert "password" not in content.casefold()
    assert "segredo-do-grupo" not in content
    assert len(nonce) <= 25
    assert enforce_nonce is True


def test_invited_friend_receives_a_private_acceptance_link_without_mentions():
    messages = DirectMessages()
    notifier = DiscordInvitationNotifier(
        messages,
        console_url="https://app.gamewake.example",
    )
    account = Account("account-1", "Sexta com os amigos", "guild-1")
    invitation = Invitation(
        "invitation-1",
        account.id,
        "owner-1",
        "friend-1",
        InvitationStatus.PENDING,
    )

    assert (
        notifier.notify(
            account,
            invitation,
            inviter_name="Leonardo",
            recipient_discord_user_id="discord-friend-1",
        )
        is True
    )

    [(recipient_id, content, nonce, enforce_nonce)] = messages.calls
    assert recipient_id == "discord-friend-1"
    assert "Leonardo" in content
    assert "Sexta com os amigos" in content
    assert "https://app.gamewake.example/convites/account-1/invitation-1" in content
    assert "/gamewake aceitar" in content
    assert "@" not in content
    assert len(nonce) <= 25
    assert enforce_nonce is True


def test_discord_rest_client_opens_a_dm_and_sends_the_invitation_safely():
    calls = []

    def open_request(request, timeout):
        calls.append((request, timeout))
        if request.full_url.endswith("/users/@me/channels"):
            return HttpResponse(b'{"id":"direct-channel-1"}')
        return HttpResponse()

    DiscordRestMessageClient("bot-token", opener=open_request).create_direct(
        "discord-friend-1",
        content="Convite privado",
        nonce="invitation-nonce",
        enforce_nonce=True,
    )

    [(open_dm, first_timeout), (send_message, second_timeout)] = calls
    assert open_dm.method == "POST"
    assert json.loads(open_dm.data) == {"recipient_id": "discord-friend-1"}
    assert send_message.method == "POST"
    assert send_message.full_url.endswith("/channels/direct-channel-1/messages")
    assert json.loads(send_message.data) == {
        "content": "Convite privado",
        "nonce": "invitation-nonce",
        "enforce_nonce": True,
        "allowed_mentions": {"parse": []},
    }
    assert first_timeout == second_timeout == 15


def test_deferred_interaction_edits_the_original_message_without_the_bot_token():
    calls = []

    def open_request(request, timeout):
        calls.append((request, timeout))
        return HttpResponse()

    DiscordInteractionWebhookClient(opener=open_request).update_original(
        {
            "application_id": "application-1",
            "token": "temporary-interaction-token",
        },
        {
            "type": 4,
            "data": {
                "content": "🟡 Palpagos está acordando.",
                "flags": 64,
                "allowed_mentions": {"parse": []},
            },
        },
    )

    [(request, timeout)] = calls
    assert request.method == "PATCH"
    assert request.full_url.endswith(
        "/webhooks/application-1/temporary-interaction-token/messages/@original"
    )
    assert request.get_header("Authorization") is None
    assert json.loads(request.data) == {
        "content": "🟡 Palpagos está acordando.",
        "allowed_mentions": {"parse": []},
    }
    assert timeout == 15


def test_deferred_interaction_failure_never_exposes_its_temporary_token():
    def fail_request(request, timeout):
        del request, timeout
        raise URLError("offline")

    with pytest.raises(RuntimeError) as error:
        DiscordInteractionWebhookClient(opener=fail_request).update_original(
            {
                "application_id": "application-1",
                "token": "temporary-interaction-token",
            },
            {"type": 4, "data": {"content": "mensagem"}},
        )

    assert "temporary-interaction-token" not in str(error.value)
