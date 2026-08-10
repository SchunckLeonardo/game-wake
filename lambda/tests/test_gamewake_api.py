import json
from types import SimpleNamespace

import gamewake_api


class RecordingLambdaClient:
    def __init__(self):
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return {"StatusCode": 202}


class RecordingDiscordResponder:
    def __init__(self):
        self.calls = []

    def update_original(self, payload, response):
        self.calls.append((payload, response))


def discord_event(signing_key, payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    timestamp = "1786372335"
    signature = signing_key.sign(timestamp.encode() + raw).signature.hex()
    return {
        "rawPath": "/discord/interactions",
        "headers": {
            "x-signature-ed25519": signature,
            "x-signature-timestamp": timestamp,
        },
        "requestContext": {"http": {"method": "POST"}},
        "body": raw.decode(),
        "isBase64Encoded": False,
    }


def wake_payload():
    return {
        "id": "interaction-wake-1",
        "application_id": "application-1",
        "token": "private-interaction-token",
        "type": 2,
        "guild_id": "guild-1",
        "member": {"user": {"id": "discord-owner", "username": "Leonardo"}},
        "data": {
            "name": "gamewake",
            "options": [{"type": 1, "name": "acordar"}],
        },
    }


def test_wake_interaction_is_acknowledged_before_building_database_dependencies(
    monkeypatch, signing_key
):
    lambda_client = RecordingLambdaClient()
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", signing_key.verify_key.encode().hex())
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "gamewake-prod-api")
    monkeypatch.setattr(gamewake_api, "_handler", None)
    monkeypatch.setattr(gamewake_api, "_async_lambda_client", lambda_client, raising=False)
    monkeypatch.setattr(
        gamewake_api,
        "build_handler",
        lambda: (_ for _ in ()).throw(AssertionError("the ACK must not build the control plane")),
    )

    response = gamewake_api.lambda_handler(
        discord_event(signing_key, wake_payload()),
        SimpleNamespace(
            invoked_function_arn="arn:aws:lambda:us-east-1:123:function:gamewake-prod-api"
        ),
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"type": 5}
    [invocation] = lambda_client.calls
    assert invocation["InvocationType"] == "Event"
    deferred = json.loads(invocation["Payload"])
    assert deferred["eventType"] == "gamewake.discord.interaction.v1"
    assert deferred["payload"] == wake_payload()


def test_deferred_wake_updates_the_original_discord_interaction(monkeypatch):
    payload = wake_payload()
    rendered = {
        "type": 4,
        "data": {
            "content": "🟡 Palpagos está acordando.",
            "allowed_mentions": {"parse": []},
        },
    }
    handler = SimpleNamespace(handle_discord=lambda received: rendered)
    responder = RecordingDiscordResponder()
    monkeypatch.setattr(gamewake_api, "_handler", handler)
    monkeypatch.setattr(gamewake_api, "_discord_interaction_responder", responder, raising=False)

    result = gamewake_api.lambda_handler(
        {"eventType": "gamewake.discord.interaction.v1", "payload": payload},
        None,
    )

    assert result == {"processed": True}
    assert responder.calls == [(payload, rendered)]


def test_discord_ping_stays_synchronous_and_does_not_build_the_control_plane(
    monkeypatch, signing_key
):
    lambda_client = RecordingLambdaClient()
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", signing_key.verify_key.encode().hex())
    monkeypatch.setattr(gamewake_api, "_handler", None)
    monkeypatch.setattr(gamewake_api, "_async_lambda_client", lambda_client, raising=False)
    monkeypatch.setattr(
        gamewake_api,
        "build_handler",
        lambda: (_ for _ in ()).throw(AssertionError("PING must stay on the lightweight edge")),
    )

    response = gamewake_api.lambda_handler(
        discord_event(signing_key, {"id": "ping-1", "type": 1}),
        SimpleNamespace(
            invoked_function_arn="arn:aws:lambda:us-east-1:123:function:gamewake-prod-api"
        ),
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"type": 1}
    assert lambda_client.calls == []
