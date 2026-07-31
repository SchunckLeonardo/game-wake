import json
from types import SimpleNamespace

from gamewake.auth import InvalidSession
from gamewake.control_plane import ApiResponse, GameWakeHttpHandler


class Sessions:
    def issue(self, subject, **kwargs):
        return f"token:{subject}"

    def verify(self, token):
        if not token.startswith("token:"):
            raise InvalidSession("invalid")
        return SimpleNamespace(subject=token.removeprefix("token:"))


class OAuth:
    def authorization_url(self, *, state, redirect_uri):
        return f"https://discord.invalid/oauth?state={state}&redirect_uri={redirect_uri}"

    def authenticate(self, code, *, redirect_uri):
        assert code == "discord-code"
        return SimpleNamespace(discord_user_id="discord-123", display_name="Leonardo")

    def authenticate_activity(self, code):
        assert code == "activity-code"
        return SimpleNamespace(
            access_token="discord-access",
            identity=SimpleNamespace(
                discord_user_id="discord-123",
                display_name="Leonardo",
            ),
        )


class Accounts:
    def sign_in_with_discord(self, *, discord_user_id, display_name):
        assert discord_user_id == "discord-123"
        assert display_name == "Leonardo"
        return SimpleNamespace(id="user-123")


class Api:
    def __init__(self):
        self.requests = []

    def handle(self, request):
        self.requests.append(request)
        return ApiResponse(200, {"ok": True, "userId": request.user_id})


def handler(api=None, **kwargs):
    return GameWakeHttpHandler(
        application=SimpleNamespace(accounts=Accounts()),
        api=api or Api(),
        sessions=Sessions(),
        oauth=OAuth(),
        console_url="https://app.gamewake.example",
        oauth_redirect_uri="https://api.gamewake.example/auth/discord/callback",
        **kwargs,
    )


def event(method, path, *, headers=None, body=None, query=None):
    return {
        "requestContext": {"http": {"method": method}},
        "rawPath": path,
        "headers": headers or {},
        "queryStringParameters": query or {},
        "body": body,
        "isBase64Encoded": False,
    }


def test_discord_oauth_issues_a_kms_session_only_after_code_exchange():
    started = handler().handle(event("GET", "/auth/discord/start"))
    callback = handler().handle(
        event(
            "GET",
            "/auth/discord/callback",
            query={"code": "discord-code", "state": "token:oauth"},
        )
    )

    assert started["statusCode"] == 302
    assert started["headers"]["location"].startswith("https://discord.invalid/oauth")
    assert callback["statusCode"] == 302
    assert callback["headers"]["location"] == (
        "https://app.gamewake.example/auth/callback#session=token:user-123"
    )


def test_api_requires_a_bearer_session_and_applies_exact_origin_cors():
    api = Api()
    transport = handler(api)

    unauthorized = transport.handle(event("GET", "/api/v1/accounts/a/worlds"))
    accepted = transport.handle(
        event(
            "GET",
            "/api/v1/accounts/a/worlds",
            headers={
                "authorization": "Bearer token:user-123",
                "origin": "https://app.gamewake.example",
            },
        )
    )

    assert unauthorized["statusCode"] == 401
    assert accepted["statusCode"] == 200
    assert accepted["headers"]["access-control-allow-origin"] == ("https://app.gamewake.example")
    assert api.requests[0].user_id == "user-123"


def test_discord_and_abacatepay_receive_the_unmodified_raw_body():
    calls = []
    discord = SimpleNamespace(handle=lambda payload: {"type": 4, "data": payload})
    webhook = SimpleNamespace(
        handle=lambda raw, **auth: calls.append((raw, auth)) or {"processed": True}
    )
    transport = handler(
        discord=discord,
        verify_discord=lambda headers, raw: calls.append((headers, raw)),
        abacatepay_webhook=webhook,
    )
    raw = b'{"type":1}'

    discord_response = transport.handle(
        event("POST", "/discord/interactions", headers={"sig": "x"}, body=raw.decode())
    )
    webhook_response = transport.handle(
        event(
            "POST",
            "/webhooks/abacatepay",
            headers={"webhooksecret": "url-secret", "x-webhook-signature": "signature"},
            body=raw.decode(),
        )
    )

    assert discord_response["statusCode"] == 200
    assert webhook_response["statusCode"] == 200
    assert calls[0][1] == raw
    assert calls[1] == (
        raw,
        {"webhook_secret": "url-secret", "signature": "signature"},
    )


def test_discord_activity_exchange_returns_discord_and_gamewake_sessions():
    response = handler().handle(
        event(
            "POST",
            "/api/v1/auth/discord/activity/token",
            headers={"origin": "https://app.gamewake.example"},
            body='{"code":"activity-code"}',
        )
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "accessToken": "discord-access",
        "session": "token:user-123",
    }


def test_invalid_json_is_a_safe_client_error_without_internal_details():
    response = handler().handle(
        event(
            "POST",
            "/api/v1/accounts",
            headers={"authorization": "Bearer token:user-123"},
            body="not-json",
        )
    )

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"]["code"] == "invalid_json"


def test_invalid_or_expired_session_is_an_unauthorized_response():
    response = handler().handle(
        event(
            "GET",
            "/api/v1/accounts/a/worlds",
            headers={"authorization": "Bearer invalid-token"},
        )
    )

    assert response["statusCode"] == 401
    assert json.loads(response["body"])["error"]["code"] == "invalid_session"


def test_oauth_callback_uri_can_be_derived_from_the_function_url_event():
    transport = GameWakeHttpHandler(
        application=SimpleNamespace(accounts=Accounts()),
        api=Api(),
        sessions=Sessions(),
        oauth=OAuth(),
        console_url="https://app.gamewake.example",
        oauth_redirect_uri=None,
    )
    request = event("GET", "/auth/discord/start")
    request["requestContext"]["domainName"] = "abc.lambda-url.us-east-1.on.aws"

    response = transport.handle(request)

    assert response["statusCode"] == 302
    assert (
        "redirect_uri=https://abc.lambda-url.us-east-1.on.aws/auth/discord/callback"
        in response["headers"]["location"]
    )
