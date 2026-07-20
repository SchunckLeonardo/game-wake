import pytest
from discord_signature import SignatureValidationError, verify_discord_signature
from nacl.signing import SigningKey


def test_accepts_valid_signature(signing_key: SigningKey) -> None:
    body = b'{"type":1}'
    timestamp = "1784500000"
    signature = signing_key.sign(timestamp.encode() + body).signature.hex()

    verify_discord_signature(
        {
            "X-Signature-Ed25519": signature,
            "X-Signature-Timestamp": timestamp,
        },
        body,
        signing_key.verify_key.encode().hex(),
    )


def test_rejects_modified_body(signing_key: SigningKey) -> None:
    original = b'{"type":1}'
    timestamp = "1784500000"
    signature = signing_key.sign(timestamp.encode() + original).signature.hex()

    with pytest.raises(SignatureValidationError, match="assinatura invalida"):
        verify_discord_signature(
            {
                "X-Signature-Ed25519": signature,
                "X-Signature-Timestamp": timestamp,
            },
            b'{"type":2}',
            signing_key.verify_key.encode().hex(),
        )


def test_rejects_missing_headers(signing_key: SigningKey) -> None:
    with pytest.raises(SignatureValidationError, match="ausentes"):
        verify_discord_signature({}, b"{}", signing_key.verify_key.encode().hex())
