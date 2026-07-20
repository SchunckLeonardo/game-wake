import base64
import json
from datetime import UTC, datetime
from typing import Any

import handler
import pytest
from config_service import DiscordConfig

from .conftest import FakeEC2Service, StaticConfigProvider, response_payload


def content(response: dict[str, Any]) -> str:
    return response_payload(response).get("data", {}).get("content", "")


def test_ping_returns_pong(make_event, deps) -> None:
    response = handler.process_event(make_event(interaction_type=1), deps.provider, deps.service)

    assert response["statusCode"] == 200
    assert response_payload(response) == {"type": 1}


def test_ping_preserves_base64_encoded_raw_body(make_event, deps) -> None:
    event = make_event(interaction_type=1)
    event["body"] = base64.b64encode(event["body"].encode()).decode()
    event["isBase64Encoded"] = True

    response = handler.process_event(event, deps.provider, deps.service)

    assert response_payload(response) == {"type": 1}


def test_ligar_starts_stopped_instance(make_event, deps) -> None:
    response = handler.process_event(make_event("ligar"), deps.provider, deps.service)

    assert deps.service.started is True
    assert "sendo iniciado" in content(response)
    assert "alguns minutos" in content(response)


def test_ligar_reports_already_running(make_event, config) -> None:
    service = FakeEC2Service(state="running", public_ip="203.0.113.10")

    response = handler.process_event(make_event("ligar"), StaticConfigProvider(config), service)

    assert service.started is False
    assert "203.0.113.10:8211" in content(response)
    assert "já está ligada" in content(response)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("pending", "já está iniciando"),
        ("stopping", "ainda está desligando"),
        ("shutting-down", "não pode ser iniciada"),
        ("terminated", "não pode ser iniciada"),
    ],
)
def test_ligar_handles_intermediate_states(make_event, config, state: str, expected: str) -> None:
    service = FakeEC2Service(state=state)

    response = handler.process_event(make_event("ligar"), StaticConfigProvider(config), service)

    assert expected in content(response)
    assert service.started is False


def test_status_includes_address_service_players_and_uptime(make_event, config) -> None:
    service = FakeEC2Service(
        state="running",
        public_ip="203.0.113.20",
        snapshot={
            "updated_at": datetime.now(UTC).isoformat(),
            "service_state": "online",
            "players": 2,
        },
    )

    response = handler.process_event(make_event("status"), StaticConfigProvider(config), service)

    text = content(response)
    assert "203.0.113.20:8211" in text
    assert "online" in text
    assert "Jogadores conectados: **2**" in text
    assert "Tempo desde a inicialização" in text


def test_status_reports_stopped(make_event, deps) -> None:
    response = handler.process_event(make_event("status"), deps.provider, deps.service)

    assert "está desligado" in content(response)


def test_desligar_dispatches_safe_command(make_event, config) -> None:
    service = FakeEC2Service(
        state="running",
        snapshot={"updated_at": datetime.now(UTC).isoformat(), "players": 0},
    )

    response = handler.process_event(make_event("desligar"), StaticConfigProvider(config), service)

    assert service.shutdown_force is False
    assert "salvará o mundo" in content(response)
    assert "12345678" in content(response)


def test_desligar_delegates_final_check_when_recent_snapshot_has_api_error(
    make_event, config
) -> None:
    service = FakeEC2Service(
        state="running",
        snapshot={"updated_at": datetime.now(UTC).isoformat(), "players": None},
    )

    response = handler.process_event(make_event("desligar"), StaticConfigProvider(config), service)

    assert service.shutdown_force is False
    assert "verificará os jogadores novamente" in content(response)


def test_desligar_refuses_when_players_are_connected(make_event, config) -> None:
    service = FakeEC2Service(
        state="running",
        snapshot={"updated_at": datetime.now(UTC).isoformat(), "players": 3},
    )

    response = handler.process_event(make_event("desligar"), StaticConfigProvider(config), service)

    assert service.shutdown_force is None
    assert "3" in content(response)
    assert "cancelado" in content(response)


def test_force_shutdown_requires_discord_administrator(make_event, config) -> None:
    service = FakeEC2Service(state="running")
    options = [{"type": 5, "name": "forcar", "value": True}]

    denied = handler.process_event(
        make_event("desligar", options=options), StaticConfigProvider(config), service
    )
    allowed = handler.process_event(
        make_event("desligar", options=options, permissions="8"),
        StaticConfigProvider(config),
        service,
    )

    assert "Apenas administradores" in content(denied)
    assert service.shutdown_force is True
    assert "forçado" in content(allowed)


def test_rejects_unauthorized_user(make_event, deps) -> None:
    response = handler.process_event(
        make_event("ligar", user_id="intruder"), deps.provider, deps.service
    )

    assert "não tem permissão" in content(response)
    assert deps.service.started is False


def test_allows_authorized_role(make_event, config) -> None:
    service = FakeEC2Service()

    response = handler.process_event(
        make_event("ligar", user_id="other", roles=["role-1"]),
        StaticConfigProvider(config),
        service,
    )

    assert service.started is True
    assert "sendo iniciado" in content(response)


def test_rejects_wrong_guild(make_event, deps) -> None:
    response = handler.process_event(
        make_event("ligar", guild_id="other-guild"), deps.provider, deps.service
    )

    assert "não está autorizado" in content(response)
    assert deps.service.started is False


def test_lambda_handler_returns_controlled_aws_error(make_event, config, monkeypatch) -> None:
    class FailingService(FakeEC2Service):
        def describe(self):
            raise RuntimeError("AWS unavailable")

    monkeypatch.setattr(
        handler,
        "_runtime_services",
        lambda: (StaticConfigProvider(config), FailingService()),
    )

    response = handler.lambda_handler(make_event("status"), None)

    assert response["statusCode"] == 500
    assert json.loads(response["body"]) == {"error": "falha interna ao processar a interacao"}


def test_runtime_config_does_not_fetch_parameter_store(monkeypatch) -> None:
    created_services: list[str] = []

    class UnexpectedSSMClient:
        def get_parameter(self, **_kwargs):
            raise AssertionError("Discord config must not be fetched from SSM on the request path")

    def fake_client(service_name, **_kwargs):
        created_services.append(service_name)
        return UnexpectedSSMClient() if service_name == "ssm" else object()

    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("PALWORLD_INSTANCE_ID", "i-123")
    monkeypatch.setenv("PALWORLD_STATUS_PARAMETER_NAME", "/palworld/status")
    monkeypatch.setenv("DISCORD_CONFIG_PARAMETER_NAME", "/palworld/discord/config")
    monkeypatch.setenv(
        "DISCORD_CONFIG_JSON",
        json.dumps(
            {
                "public_key": "ab" * 32,
                "guild_id": "guild-1",
                "allowed_user_ids": ["user-1"],
                "allowed_role_ids": ["role-1"],
            }
        ),
    )
    monkeypatch.setattr(handler.boto3, "client", fake_client)
    monkeypatch.setattr(handler, "_runtime", None)

    provider, _service = handler._runtime_services()
    config = provider.get()

    assert config.guild_id == "guild-1"
    assert config.allowed_user_ids == frozenset({"user-1"})
    assert created_services == ["ec2"]


def test_empty_authorization_lists_deny_by_default(make_event, config) -> None:
    locked_config = DiscordConfig(
        public_key=config.public_key,
        guild_id=config.guild_id,
        allowed_user_ids=frozenset(),
        allowed_role_ids=frozenset(),
    )
    service = FakeEC2Service()

    response = handler.process_event(
        make_event("ligar"), StaticConfigProvider(locked_config), service
    )

    assert "não tem permissão" in content(response)
    assert service.started is False
