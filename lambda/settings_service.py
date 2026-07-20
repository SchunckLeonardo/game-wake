"""Read and update non-secret Discord overrides for Palworld settings."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from palworld_settings_catalog import (
    FIELDS_BY_KEY,
    SettingsValidationError,
    normalize_settings,
)

SettingValue = str | int | float
DEFAULT_KEYWORDS = frozenset({"padrao", "padrão", "default", "__default__"})
STANDARD_PARAMETER_MAX_BYTES = 4096


@dataclass(frozen=True)
class SettingsSnapshot:
    base: Mapping[str, SettingValue]
    overrides: Mapping[str, SettingValue]
    effective: Mapping[str, SettingValue]

    @classmethod
    def from_values(
        cls,
        base: object,
        overrides: object,
    ) -> SettingsSnapshot:
        normalized_base = normalize_settings(base, allow_extra=True)
        normalized_overrides = normalize_settings(overrides, require_all=False)
        return cls(
            base=normalized_base,
            overrides=normalized_overrides,
            effective={**normalized_base, **normalized_overrides},
        )

    def source(self, key: str) -> str:
        if key not in FIELDS_BY_KEY:
            raise SettingsValidationError(f"unknown setting: {key}")
        return "discord" if key in self.overrides else "base"


class ParameterSettingsService:
    """Deep module for the base + Discord override Parameter Store seam."""

    def __init__(
        self,
        ssm_client_factory: Callable[[], Any],
        base_parameter_name: str,
        overrides_parameter_name: str,
    ):
        self._ssm_client_factory = ssm_client_factory
        self._ssm: Any | None = None
        self._base_parameter_name = base_parameter_name
        self._overrides_parameter_name = overrides_parameter_name

    def _client(self) -> Any:
        if self._ssm is None:
            self._ssm = self._ssm_client_factory()
        return self._ssm

    def read(self) -> SettingsSnapshot:
        names = [self._base_parameter_name, self._overrides_parameter_name]
        response = self._client().get_parameters(Names=names, WithDecryption=False)
        parameters = {
            str(parameter.get("Name")): parameter.get("Value")
            for parameter in response.get("Parameters", [])
        }
        missing = [name for name in names if name not in parameters]
        if missing:
            raise SettingsValidationError(f"missing Parameter Store settings: {', '.join(missing)}")
        try:
            base = json.loads(parameters[self._base_parameter_name])
            overrides = json.loads(parameters[self._overrides_parameter_name])
        except (TypeError, json.JSONDecodeError) as error:
            raise SettingsValidationError("invalid settings JSON in Parameter Store") from error
        return SettingsSnapshot.from_values(base, overrides)

    def set_override(self, key: str, raw_value: object) -> SettingsSnapshot:
        try:
            field = FIELDS_BY_KEY[key]
        except KeyError as error:
            raise SettingsValidationError(f"unknown setting: {key}") from error

        snapshot = self.read()
        overrides = dict(snapshot.overrides)
        is_default = isinstance(raw_value, str) and raw_value.strip().casefold() in DEFAULT_KEYWORDS
        if is_default:
            overrides.pop(key, None)
        else:
            parsed = field.parse(raw_value)
            if parsed == snapshot.base[key]:
                overrides.pop(key, None)
            else:
                overrides[key] = parsed

        serialized = json.dumps(overrides, ensure_ascii=False, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > STANDARD_PARAMETER_MAX_BYTES:
            raise SettingsValidationError("Discord settings overrides exceed 4096 bytes")

        self._client().put_parameter(
            Name=self._overrides_parameter_name,
            Description="Non-secret Palworld settings changed through Discord",
            Type="String",
            Overwrite=True,
            Value=serialized,
        )
        return SettingsSnapshot.from_values(snapshot.base, overrides)
