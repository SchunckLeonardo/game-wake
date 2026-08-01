"""Validacao criptografica das interacoes HTTP do Discord."""

from collections.abc import Mapping

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey


class SignatureValidationError(ValueError):
    """A requisicao nao contem uma assinatura Discord valida."""


def _case_insensitive_header(headers: Mapping[str, str], name: str) -> str | None:
    expected = name.lower()
    return next((value for key, value in headers.items() if key.lower() == expected), None)


def verify_discord_signature(
    headers: Mapping[str, str], raw_body: bytes, public_key_hex: str
) -> None:
    """Valida timestamp + corpo bruto usando Ed25519.

    A funcao nao normaliza nem reserializa o JSON: o corpo deve ser exatamente o
    recebido pela Lambda Function URL.
    """

    signature_hex = _case_insensitive_header(headers, "X-Signature-Ed25519")
    timestamp = _case_insensitive_header(headers, "X-Signature-Timestamp")
    if not signature_hex or not timestamp:
        raise SignatureValidationError("cabecalhos de assinatura ausentes")

    try:
        public_key = bytes.fromhex(public_key_hex.strip())
        signature = bytes.fromhex(signature_hex.strip())
    except ValueError as exc:
        raise SignatureValidationError("assinatura ou chave publica malformada") from exc

    if len(public_key) != 32 or len(signature) != 64:
        raise SignatureValidationError("assinatura ou chave publica com tamanho invalido")

    try:
        VerifyKey(public_key).verify(timestamp.encode("utf-8") + raw_body, signature)
    except BadSignatureError as exc:
        raise SignatureValidationError("assinatura invalida") from exc
