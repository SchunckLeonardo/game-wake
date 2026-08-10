import json
from datetime import UTC, datetime
from urllib.error import URLError

import pytest

from gamewake.accounts import Account
from gamewake.experience import DiscordChannelNotifier, DiscordInteractionWebhookClient
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
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


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
