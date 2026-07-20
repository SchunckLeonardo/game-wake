import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from config_service import DiscordConfig
from ec2_service import InstanceStatus
from nacl.signing import SigningKey


class StaticConfigProvider:
    def __init__(self, config: DiscordConfig):
        self.config = config

    def get(self) -> DiscordConfig:
        return self.config


class FakeEC2Service:
    def __init__(
        self,
        state: str = "stopped",
        public_ip: str | None = None,
        snapshot: dict[str, Any] | None = None,
    ):
        self.status = InstanceStatus(
            state=state,
            public_ip=public_ip,
            launch_time=datetime.now(UTC) - timedelta(minutes=17),
        )
        self.snapshot = snapshot
        self.started = False
        self.shutdown_force: bool | None = None
        self.settings_activation_requested = False

    def describe(self) -> InstanceStatus:
        return self.status

    def start(self) -> None:
        self.started = True

    def request_safe_shutdown(self, *, force: bool = False) -> str:
        self.shutdown_force = force
        return "12345678-aaaa-bbbb-cccc-123456789012"

    def request_settings_activation(self) -> str:
        if self.status.state != "running":
            raise RuntimeError("instance is not running")
        self.settings_activation_requested = True
        return "87654321-aaaa-bbbb-cccc-123456789012"

    def read_game_snapshot(self) -> dict[str, Any] | None:
        return self.snapshot


@pytest.fixture
def signing_key() -> SigningKey:
    return SigningKey.generate()


@pytest.fixture
def config(signing_key: SigningKey) -> DiscordConfig:
    return DiscordConfig(
        public_key=signing_key.verify_key.encode().hex(),
        guild_id="guild-1",
        allowed_user_ids=frozenset({"user-1"}),
        allowed_role_ids=frozenset({"role-1"}),
    )


@pytest.fixture
def make_event(signing_key: SigningKey):
    def factory(
        command: str | None = None,
        *,
        interaction_type: int = 2,
        guild_id: str = "guild-1",
        user_id: str = "user-1",
        roles: list[str] | None = None,
        permissions: str = "0",
        options: list[dict[str, Any]] | None = None,
        interaction_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        interaction: dict[str, Any] = {"type": interaction_type}
        if interaction_type == 2:
            subcommand = {"type": 1, "name": command or "ajuda"}
            if options:
                subcommand["options"] = options
            interaction.update(
                {
                    "guild_id": guild_id,
                    "member": {
                        "user": {"id": user_id},
                        "roles": roles or [],
                        "permissions": permissions,
                    },
                    "data": {"name": "palworld", "options": [subcommand]},
                }
            )
        elif interaction_type in {3, 5}:
            interaction.update(
                {
                    "guild_id": guild_id,
                    "member": {
                        "user": {"id": user_id},
                        "roles": roles or [],
                        "permissions": permissions,
                    },
                    "data": interaction_data or {},
                }
            )
        body = json.dumps(interaction, separators=(",", ":")).encode()
        timestamp = "1784500000"
        signature = signing_key.sign(timestamp.encode() + body).signature.hex()
        return {
            "headers": {
                "x-signature-ed25519": signature,
                "x-signature-timestamp": timestamp,
            },
            "body": body.decode(),
            "isBase64Encoded": False,
        }

    return factory


@pytest.fixture
def deps(config: DiscordConfig):
    return SimpleNamespace(provider=StaticConfigProvider(config), service=FakeEC2Service())


def response_payload(response: dict[str, Any]) -> dict[str, Any]:
    return json.loads(response["body"])
