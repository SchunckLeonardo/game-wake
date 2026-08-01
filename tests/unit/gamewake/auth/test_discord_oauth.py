from gamewake.auth import DiscordOAuthClient


class FakeHttpClient:
    def __init__(self):
        self.calls = []

    def request(self, method, url, *, headers, form=None):
        self.calls.append((method, url, headers, form))
        if url.endswith("/oauth2/token"):
            return {"access_token": "discord-access"}
        return {
            "id": "discord-user-123",
            "global_name": "Leonardo",
            "email": "leo@example.com",
            "verified": True,
        }


def test_oauth_url_and_code_exchange_use_verified_discord_email_for_owner_recovery():
    http = FakeHttpClient()
    client = DiscordOAuthClient(
        client_id="app-123",
        client_secret="secret",
        http_client=http,
    )

    url = client.authorization_url(
        state="signed-state", redirect_uri="https://api.example/auth/discord/callback"
    )
    identity = client.authenticate(
        "one-time-code", redirect_uri="https://api.example/auth/discord/callback"
    )

    assert "scope=identify+email" in url
    assert "state=signed-state" in url
    assert identity.discord_user_id == "discord-user-123"
    assert identity.display_name == "Leonardo"
    assert identity.verified_email == "leo@example.com"
    assert http.calls[0][3]["grant_type"] == "authorization_code"
    assert http.calls[1][2] == {"Authorization": "Bearer discord-access"}


def test_activity_code_exchange_returns_the_discord_token_without_a_redirect_uri():
    http = FakeHttpClient()
    client = DiscordOAuthClient(
        client_id="app-123",
        client_secret="secret",
        http_client=http,
    )

    grant = client.authenticate_activity("activity-code")

    assert grant.identity.discord_user_id == "discord-user-123"
    assert grant.access_token == "discord-access"
    assert "redirect_uri" not in http.calls[0][3]
