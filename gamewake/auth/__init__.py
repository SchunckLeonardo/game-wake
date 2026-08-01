"""Authentication adapters shared by the Web Console and Discord Activity."""

from .discord_oauth import DiscordIdentity, DiscordOAuthClient, DiscordOAuthGrant
from .session import InvalidSession, KmsSessionCodec, SessionClaims

__all__ = [
    "DiscordIdentity",
    "DiscordOAuthClient",
    "DiscordOAuthGrant",
    "InvalidSession",
    "KmsSessionCodec",
    "SessionClaims",
]
