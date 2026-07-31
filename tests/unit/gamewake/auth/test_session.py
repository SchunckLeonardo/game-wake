from datetime import UTC, datetime, timedelta

import pytest

from gamewake.auth import InvalidSession, KmsSessionCodec


class FakeKmsClient:
    def generate_mac(self, **kwargs):
        return {"Mac": b"signed:" + kwargs["Message"][:16]}

    def verify_mac(self, **kwargs):
        return {"MacValid": kwargs["Mac"] == b"signed:" + kwargs["Message"][:16]}


def test_kms_session_round_trip_is_short_lived_and_contains_no_secret_key():
    now = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)
    codec = KmsSessionCodec("kms-key-123", client=FakeKmsClient(), clock=lambda: now)

    token = codec.issue("user-123", ttl=timedelta(hours=12))
    claims = codec.verify(token)

    assert claims.subject == "user-123"
    assert claims.expires_at == now + timedelta(hours=12)
    assert "kms-key-123" not in token


def test_tampered_or_expired_sessions_are_rejected():
    now = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)
    codec = KmsSessionCodec("kms-key-123", client=FakeKmsClient(), clock=lambda: now)
    token = codec.issue("user-123", ttl=timedelta(minutes=1))

    with pytest.raises(InvalidSession):
        codec.verify(token + "tampered")

    expired = KmsSessionCodec(
        "kms-key-123",
        client=FakeKmsClient(),
        clock=lambda: now + timedelta(minutes=2),
    )
    with pytest.raises(InvalidSession, match="expired"):
        expired.verify(token)
