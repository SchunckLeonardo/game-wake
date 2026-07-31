from datetime import UTC, datetime

from gamewake.accounts import Account
from gamewake.experience import DiscordChannelNotifier
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
