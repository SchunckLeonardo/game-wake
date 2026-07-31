"""Authentication adapters shared by the Web Console and Discord Activity."""

from .discord_oauth import DiscordIdentity, DiscordOAuthClient
from .session import InvalidSession, KmsSessionCodec, SessionClaims

__all__ = [
    "DiscordIdentity",
    "DiscordOAuthClient",
    "InvalidSession",
    "KmsSessionCodec",
    "SessionClaims",
]
