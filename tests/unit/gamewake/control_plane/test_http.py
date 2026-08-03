import base64
import json
from types import SimpleNamespace

from gamewake.auth import InvalidSession
from gamewake.billing import PaymentProviderError
from gamewake.control_plane import ApiResponse, GameWakeHttpHandler


class Sessions:
    def issue(self, subject, **kwargs):
        return f"token:{subject}"

    def verify(self, token):
        if not token.startswith("token:"):
            raise InvalidSession("invalid")
        return SimpleNamespace(subject=token.removeprefix("token:"))


class OAuth:
    def authorization_url(self, *, state, redirect_uri, install):
        return f"https://discord.invalid/oauth?state={state}&redirect_uri={redirect_uri}&install={int(install)}"

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
            query={"code": "discord-code", "state": "token:oauth:login"},
        )
    )

    assert started["statusCode"] == 302
    assert started["headers"]["location"].startswith("https://discord.invalid/oauth")
    assert started["headers"]["location"].endswith("&install=0")
    assert callback["statusCode"] == 302
    assert callback["headers"]["location"] == (
        "https://app.gamewake.example/auth/callback#session=token:user-123"
    )


def test_discord_oauth_preserves_the_installed_guild_for_onboarding():
    class GuildOAuth(OAuth):
        def authenticate(self, code, *, redirect_uri):
            identity = super().authenticate(code, redirect_uri=redirect_uri)
            identity.installed_guild_id = "123456789012345678"
            return identity

    transport = GameWakeHttpHandler(
        application=SimpleNamespace(
            accounts=Accounts(),
            list_accounts=lambda **kwargs: (),
        ),
        api=Api(),
        sessions=Sessions(),
        oauth=GuildOAuth(),
        console_url="https://app.gamewake.example",
        oauth_redirect_uri="https://api.gamewake.example/auth/discord/callback",
    )

    response = transport.handle(
        event(
            "GET",
            "/auth/discord/callback",
            query={"code": "discord-code", "state": "token:oauth:install"},
        )
    )

    assert response["headers"]["location"] == (
        "https://app.gamewake.example/auth/callback"
        "#session=token:user-123&discordGuildId=123456789012345678"
    )


def test_first_install_links_the_selected_server_when_the_user_already_has_one_account():
    configured = []

    class GuildOAuth(OAuth):
        def authenticate(self, code, *, redirect_uri):
            identity = super().authenticate(code, redirect_uri=redirect_uri)
            identity.installed_guild_id = "123456789012345678"
            return identity

    application = SimpleNamespace(
        accounts=Accounts(),
        list_accounts=lambda **kwargs: (
            SimpleNamespace(id="account-existing", discord_guild_id=None),
        ),
        configure_discord_guild=lambda account_id, **kwargs: configured.append(
            (account_id, kwargs)
        ),
    )
    transport = GameWakeHttpHandler(
        application=application,
        api=Api(),
        sessions=Sessions(),
        oauth=GuildOAuth(),
        console_url="https://app.gamewake.example",
        oauth_redirect_uri="https://api.gamewake.example/auth/discord/callback",
    )

    response = transport.handle(
        event(
            "GET",
            "/auth/discord/callback",
            query={"code": "discord-code", "state": "token:oauth:install"},
        )
    )

    assert configured == [
        (
            "account-existing",
            {
                "actor_user_id": "user-123",
                "discord_guild_id": "123456789012345678",
            },
        )
    ]
    assert response["headers"]["location"].endswith(
        "#session=token:user-123&accountId=account-existing"
    )


def test_switching_to_an_unlinked_server_starts_a_separate_account_onboarding():
    configured = []

    class GuildOAuth(OAuth):
        def authenticate(self, code, *, redirect_uri):
            identity = super().authenticate(code, redirect_uri=redirect_uri)
            identity.installed_guild_id = "987654321098765432"
            return identity

    application = SimpleNamespace(
        accounts=Accounts(),
        configure_discord_guild=lambda account_id, **kwargs: configured.append(
            (account_id, kwargs)
        ),
        list_accounts=lambda **kwargs: (
            SimpleNamespace(
                id="account-1",
                discord_guild_id="123456789012345678",
            ),
        ),
    )
    transport = GameWakeHttpHandler(
        application=application,
        api=Api(),
        sessions=Sessions(),
        oauth=GuildOAuth(),
        console_url="https://app.gamewake.example",
        oauth_redirect_uri="https://api.gamewake.example/auth/discord/callback",
    )

    callback = transport.handle(
        event(
            "GET",
            "/auth/discord/callback",
            query={
                "code": "discord-code",
                "state": "token:oauth:install:account-1",
            },
        )
    )

    assert configured == []
    assert callback["headers"]["location"].endswith(
        "#session=token:user-123&discordGuildId=987654321098765432"
    )


def test_switching_discord_server_routes_to_its_account_without_rebinding_worlds():
    configured = []

    class GuildOAuth(OAuth):
        def authenticate(self, code, *, redirect_uri):
            identity = super().authenticate(code, redirect_uri=redirect_uri)
            identity.installed_guild_id = "987654321098765432"
            return identity

    application = SimpleNamespace(
        accounts=Accounts(),
        configure_discord_guild=lambda account_id, **kwargs: configured.append(
            (account_id, kwargs)
        ),
        list_accounts=lambda **kwargs: (
            SimpleNamespace(
                id="account-1",
                discord_guild_id="123456789012345678",
            ),
            SimpleNamespace(
                id="account-2",
                discord_guild_id="987654321098765432",
            ),
        ),
    )
    transport = GameWakeHttpHandler(
        application=application,
        api=Api(),
        sessions=Sessions(),
        oauth=GuildOAuth(),
        console_url="https://app.gamewake.example",
        oauth_redirect_uri="https://api.gamewake.example/auth/discord/callback",
    )

    started = transport.handle(
        event(
            "GET",
            "/auth/discord/start",
            query={"accountId": "account-1"},
        )
    )
    callback = transport.handle(
        event(
            "GET",
            "/auth/discord/callback",
            query={
                "code": "discord-code",
                "state": "token:oauth:install:account-1",
            },
        )
    )

    assert started["headers"]["location"].endswith("&install=1")
    assert configured == []
    assert callback["headers"]["location"].endswith("#session=token:user-123&accountId=account-2")


def test_server_picker_routes_to_the_account_already_linked_to_the_selected_guild():
    configured = []

    class GuildOAuth(OAuth):
        def authenticate(self, code, *, redirect_uri):
            identity = super().authenticate(code, redirect_uri=redirect_uri)
            identity.installed_guild_id = "987654321098765432"
            return identity

    application = SimpleNamespace(
        accounts=Accounts(),
        configure_discord_guild=lambda account_id, **kwargs: configured.append(
            (account_id, kwargs)
        ),
        list_accounts=lambda **kwargs: (
            SimpleNamespace(
                id="account-1",
                discord_guild_id="123456789012345678",
            ),
            SimpleNamespace(
                id="account-2",
                discord_guild_id="987654321098765432",
            ),
        ),
    )
    transport = GameWakeHttpHandler(
        application=application,
        api=Api(),
        sessions=Sessions(),
        oauth=GuildOAuth(),
        console_url="https://app.gamewake.example",
        oauth_redirect_uri="https://api.gamewake.example/auth/discord/callback",
    )

    callback = transport.handle(
        event(
            "GET",
            "/auth/discord/callback",
            query={"code": "discord-code", "state": "token:oauth:install"},
        )
    )

    assert configured == []
    assert callback["headers"]["location"].endswith("#session=token:user-123&accountId=account-2")


def test_oauth_bootstraps_owner_recovery_from_verified_discord_email_once():
    class VerifiedOAuth(OAuth):
        def authenticate(self, code, *, redirect_uri):
            identity = super().authenticate(code, redirect_uri=redirect_uri)
            identity.verified_email = "owner@example.com"
            return identity

    class RecoveryAccounts(Accounts):
        def owner_recovery_ready(self, account_id):
            assert account_id == "account-1"
            return False

    application = SimpleNamespace(
        accounts=RecoveryAccounts(),
        list_accounts=lambda **kwargs: (SimpleNamespace(id="account-1"),),
        enable_owner_recovery=lambda account_id, **kwargs: ("code-one", "code-two"),
    )
    transport = GameWakeHttpHandler(
        application=application,
        api=Api(),
        sessions=Sessions(),
        oauth=VerifiedOAuth(),
        console_url="https://app.gamewake.example",
        oauth_redirect_uri="https://api.gamewake.example/auth/discord/callback",
    )

    callback = transport.handle(
        event(
            "GET",
            "/auth/discord/callback",
            query={"code": "discord-code", "state": "token:oauth:login"},
        )
    )
    fragment = callback["headers"]["location"].split("#", 1)[1]
    encoded = dict(item.split("=", 1) for item in fragment.split("&"))["ownerRecovery"]
    recovery = json.loads(base64.urlsafe_b64decode(encoded + "=="))

    assert recovery == [
        {
            "accountId": "account-1",
            "verifiedEmail": "owner@example.com",
            "codes": ["code-one", "code-two"],
        }
    ]


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
            headers={"x-webhook-signature": "signature"},
            query={"webhookSecret": "url-secret"},
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


def test_unexpected_api_failure_is_a_safe_cors_response():
    class FailingApi:
        def handle(self, request):
            del request
            raise RuntimeError("database secret detail")

    response = handler(FailingApi()).handle(
        event(
            "GET",
            "/api/v1/me/accounts",
            headers={
                "authorization": "Bearer token:user-123",
                "origin": "https://app.gamewake.example",
            },
        )
    )

    assert response["statusCode"] == 500
    assert response["headers"]["access-control-allow-origin"] == ("https://app.gamewake.example")
    assert json.loads(response["body"]) == {
        "error": {
            "code": "internal_error",
            "message": "Não foi possível concluir a ação.",
        }
    }
    assert "database secret detail" not in response["body"]


def test_payment_provider_failure_returns_a_safe_actionable_checkout_error():
    class FailingCheckoutApi:
        def handle(self, request):
            del request
            raise PaymentProviderError("private provider diagnostic")

    response = handler(FailingCheckoutApi()).handle(
        event(
            "POST",
            "/api/v1/accounts/account-1/wallet/contributions",
            headers={
                "authorization": "Bearer token:user-123",
                "origin": "https://app.gamewake.example",
            },
            body='{"packageId":"credits-25"}',
        )
    )

    assert response["statusCode"] == 502
    assert json.loads(response["body"]) == {
        "error": {
            "code": "payment_unavailable",
            "message": "Não foi possível abrir o checkout Pix. Tente novamente em instantes.",
        }
    }
    assert "private provider diagnostic" not in response["body"]


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
