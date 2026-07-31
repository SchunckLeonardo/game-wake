from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_DISCORD_API = "https://discord.com/api/v10"


class OAuthHttpClient(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        form: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]: ...


class UrllibOAuthHttpClient:
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        form: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        request = Request(
            url,
            data=urlencode(form).encode() if form is not None else None,
            headers=dict(headers),
            method=method,
        )
        try:
            with urlopen(request, timeout=15) as response:
                result = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RuntimeError("Discord OAuth request failed") from error
        if not isinstance(result, dict):
            raise RuntimeError("Discord OAuth returned an invalid response")
        return result


@dataclass(frozen=True)
class DiscordIdentity:
    discord_user_id: str
    display_name: str
    verified_email: str | None = None


@dataclass(frozen=True)
class DiscordOAuthGrant:
    identity: DiscordIdentity
    access_token: str


class DiscordOAuthClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        http_client: OAuthHttpClient | None = None,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("Discord OAuth credentials are required")
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http_client or UrllibOAuthHttpClient()

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "client_id": self._client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": "identify email",
                "state": state,
            }
        )
        return f"{_DISCORD_API}/oauth2/authorize?{query}"

    def authenticate(self, code: str, *, redirect_uri: str) -> DiscordIdentity:
        return self._exchange(code, redirect_uri=redirect_uri).identity

    def authenticate_activity(self, code: str) -> DiscordOAuthGrant:
        return self._exchange(code)

    def _exchange(self, code: str, *, redirect_uri: str | None = None) -> DiscordOAuthGrant:
        form = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "authorization_code",
            "code": code,
        }
        if redirect_uri is not None:
            form["redirect_uri"] = redirect_uri
        token = self._http.request(
            "POST",
            f"{_DISCORD_API}/oauth2/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            form=form,
        )
        access_token = token.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise RuntimeError("Discord OAuth returned no access token")
        user = self._http.request(
            "GET",
            f"{_DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_id = user.get("id")
        display_name = user.get("global_name") or user.get("username")
        if not isinstance(user_id, str) or not isinstance(display_name, str):
            raise RuntimeError("Discord OAuth returned an invalid User")
        raw_email = user.get("email")
        verified_email = (
            raw_email
            if user.get("verified") is True and isinstance(raw_email, str) and "@" in raw_email
            else None
        )
        return DiscordOAuthGrant(
            identity=DiscordIdentity(user_id, display_name, verified_email),
            access_token=access_token,
        )
