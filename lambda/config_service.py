"""Leitura cacheada da configuracao nao secreta mantida no Parameter Store."""

import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DiscordConfig:
    public_key: str
    guild_id: str
    allowed_user_ids: frozenset[str]
    allowed_role_ids: frozenset[str]


class ParameterConfigProvider:
    def __init__(self, ssm_client: Any, parameter_name: str, cache_seconds: int = 300):
        self._ssm = ssm_client
        self._parameter_name = parameter_name
        self._cache_seconds = cache_seconds
        self._cached_config: DiscordConfig | None = None
        self._cached_at = 0.0

    def get(self) -> DiscordConfig:
        now = time.monotonic()
        if self._cached_config and now - self._cached_at < self._cache_seconds:
            return self._cached_config

        response = self._ssm.get_parameter(Name=self._parameter_name, WithDecryption=False)
        raw = json.loads(response["Parameter"]["Value"])
        config = DiscordConfig(
            public_key=str(raw["public_key"]),
            guild_id=str(raw["guild_id"]),
            allowed_user_ids=frozenset(map(str, raw.get("allowed_user_ids", []))),
            allowed_role_ids=frozenset(map(str, raw.get("allowed_role_ids", []))),
        )
        if not config.public_key or not config.guild_id:
            raise ValueError("configuracao Discord incompleta")

        self._cached_config = config
        self._cached_at = now
        return config
