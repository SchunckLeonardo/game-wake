from __future__ import annotations

import base64
import json
from datetime import timedelta
from typing import Any

from gamewake.auth import InvalidSession

from .api import ApiRequest


class GameWakeHttpHandler:
    """AWS Lambda Function URL transport for OAuth, API, Discord and payments."""

    def __init__(
        self,
        *,
        application: Any,
        api: Any,
        sessions: Any,
        oauth: Any,
        console_url: str,
        oauth_redirect_uri: str | None,
        discord: Any | None = None,
        verify_discord: Any | None = None,
        abacatepay_webhook: Any | None = None,
    ) -> None:
        self._application = application
        self._api = api
        self._sessions = sessions
        self._oauth = oauth
        self._console_url = console_url.rstrip("/")
        self._oauth_redirect_uri = oauth_redirect_uri
        self._discord = discord
        self._verify_discord = verify_discord
        self._abacatepay_webhook = abacatepay_webhook

    def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        method = str(event.get("requestContext", {}).get("http", {}).get("method", ""))
        path = str(event.get("rawPath") or "/")
        headers = {
            str(key).casefold(): str(value) for key, value in (event.get("headers") or {}).items()
        }
        origin = headers.get("origin")
        cors = self._cors(origin)
        if method == "OPTIONS":
            return self._response(204, None, headers=cors)
        try:
            raw_body = self._raw_body(event)
            oauth_redirect_uri = self._oauth_redirect_uri or self._callback_uri(event)
            if method == "GET" and path == "/auth/discord/start":
                state = self._sessions.issue("oauth", ttl=timedelta(minutes=10))
                return self._redirect(
                    self._oauth.authorization_url(state=state, redirect_uri=oauth_redirect_uri)
                )
            if method == "GET" and path == "/auth/discord/callback":
                query = event.get("queryStringParameters") or {}
                code = query.get("code")
                state = query.get("state")
                if not isinstance(code, str) or not isinstance(state, str):
                    return self._error(400, "invalid_oauth", "OAuth callback is incomplete")
                if self._sessions.verify(state).subject != "oauth":
                    return self._error(401, "invalid_oauth", "OAuth state is invalid")
                identity = self._oauth.authenticate(code, redirect_uri=oauth_redirect_uri)
                user = self._application.accounts.sign_in_with_discord(
                    discord_user_id=identity.discord_user_id,
                    display_name=identity.display_name,
                )
                session = self._sessions.issue(user.id)
                return self._redirect(f"{self._console_url}/auth/callback#session={session}")
            if method == "POST" and path == "/discord/interactions":
                if self._discord is None or self._verify_discord is None:
                    return self._error(503, "not_configured", "Discord is not configured")
                self._verify_discord(headers, raw_body)
                return self._response(200, self._discord.handle(self._json(raw_body)))
            if method == "POST" and path == "/webhooks/abacatepay":
                if self._abacatepay_webhook is None:
                    return self._error(503, "not_configured", "AbacatePay is not configured")
                result = self._abacatepay_webhook.handle(
                    raw_body,
                    webhook_secret=headers.get("webhooksecret", ""),
                    signature=headers.get("x-webhook-signature", ""),
                )
                return self._response(200, {"processed": bool(result)})
            if method == "POST" and path == "/api/v1/auth/discord/activity/token":
                code = self._json(raw_body).get("code")
                if not isinstance(code, str) or not code:
                    return self._error(400, "invalid_oauth", "OAuth code is required", cors)
                grant = self._oauth.authenticate_activity(code)
                user = self._application.accounts.sign_in_with_discord(
                    discord_user_id=grant.identity.discord_user_id,
                    display_name=grant.identity.display_name,
                )
                session = self._sessions.issue(user.id)
                return self._response(
                    200,
                    {"accessToken": grant.access_token, "session": session},
                    headers=cors,
                )
            if path.startswith("/api/v1/"):
                authorization = headers.get("authorization", "")
                if not authorization.startswith("Bearer "):
                    return self._error(401, "unauthorized", "Authentication required", cors)
                claims = self._sessions.verify(authorization.removeprefix("Bearer "))
                body = self._json(raw_body) if raw_body else {}
                response = self._api.handle(
                    ApiRequest(
                        method=method,
                        path=path,
                        user_id=claims.subject,
                        body=body,
                    )
                )
                return self._response(response.status, response.body, headers=cors)
            return self._error(404, "not_found", "Not found", cors)
        except InvalidSession:
            return self._error(401, "invalid_session", "Session is invalid or expired", cors)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            code = "invalid_json" if raw_body else "invalid_request"
            return self._error(400, code, "Invalid request", cors)

    @staticmethod
    def _raw_body(event: dict[str, Any]) -> bytes:
        body = event.get("body") or ""
        if event.get("isBase64Encoded") is True:
            return base64.b64decode(body, validate=True)
        return str(body).encode()

    @staticmethod
    def _json(raw_body: bytes) -> dict[str, Any]:
        value = json.loads(raw_body)
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def _cors(self, origin: str | None) -> dict[str, str]:
        if origin != self._console_url:
            return {}
        return {
            "access-control-allow-origin": self._console_url,
            "access-control-allow-headers": "authorization,content-type,idempotency-key",
            "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS",
            "vary": "Origin",
        }

    @staticmethod
    def _callback_uri(event: dict[str, Any]) -> str:
        domain_name = event.get("requestContext", {}).get("domainName")
        if not isinstance(domain_name, str) or not domain_name:
            raise ValueError("request domain is unavailable")
        return f"https://{domain_name}/auth/discord/callback"

    @classmethod
    def _response(
        cls,
        status: int,
        body: dict[str, Any] | None,
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        response_headers = {"content-type": "application/json", **(headers or {})}
        return {
            "statusCode": status,
            "headers": response_headers,
            "body": "" if body is None else json.dumps(body, ensure_ascii=False),
            "isBase64Encoded": False,
        }

    @classmethod
    def _error(
        cls,
        status: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return cls._response(
            status,
            {"error": {"code": code, "message": message}},
            headers=headers,
        )

    @staticmethod
    def _redirect(location: str) -> dict[str, Any]:
        return {
            "statusCode": 302,
            "headers": {"location": location, "cache-control": "no-store"},
            "body": "",
            "isBase64Encoded": False,
        }
