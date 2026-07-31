from __future__ import annotations

import base64
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any


class InvalidSession(ValueError):
    pass


@dataclass(frozen=True)
class SessionClaims:
    subject: str
    issued_at: datetime
    expires_at: datetime


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class KmsSessionCodec:
    """Issues opaque-to-clients session claims authenticated by an AWS KMS HMAC key."""

    def __init__(
        self,
        key_id: str,
        *,
        client: Any | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not key_id:
            raise ValueError("KMS session key ID is required")
        if client is None:
            import boto3

            client = boto3.client("kms")
        self._key_id = key_id
        self._client = client
        self._clock = clock or (lambda: datetime.now(UTC))

    def issue(self, subject: str, *, ttl: timedelta = timedelta(hours=12)) -> str:
        if not subject or ttl <= timedelta(0):
            raise ValueError("session subject and positive TTL are required")
        now = self._clock()
        payload = json.dumps(
            {
                "iss": "gamewake",
                "sub": subject,
                "iat": int(now.timestamp()),
                "exp": int((now + ttl).timestamp()),
                "jti": token_urlsafe(16),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        mac = self._client.generate_mac(
            KeyId=self._key_id,
            MacAlgorithm="HMAC_SHA_256",
            Message=payload,
        )["Mac"]
        return f"{_encode(payload)}.{_encode(mac)}"

    def verify(self, token: str) -> SessionClaims:
        try:
            payload_part, mac_part = token.split(".", 1)
            payload = _decode(payload_part)
            mac = _decode(mac_part)
            verified = self._client.verify_mac(
                KeyId=self._key_id,
                MacAlgorithm="HMAC_SHA_256",
                Message=payload,
                Mac=mac,
            )["MacValid"]
            claims = json.loads(payload)
            subject = claims["sub"]
            issued_at = datetime.fromtimestamp(int(claims["iat"]), tz=UTC)
            expires_at = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise InvalidSession("invalid GameWake session") from error
        if verified is not True or claims.get("iss") != "gamewake" or not subject:
            raise InvalidSession("invalid GameWake session")
        if self._clock() >= expires_at:
            raise InvalidSession("GameWake session expired")
        return SessionClaims(
            subject=str(subject),
            issued_at=issued_at,
            expires_at=expires_at,
        )
