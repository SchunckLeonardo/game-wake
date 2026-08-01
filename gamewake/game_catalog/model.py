from dataclasses import dataclass


class GameConfigurationError(ValueError):
    """Raised when configuration does not satisfy its Game Template schema."""


ConfigurationValue = str | int | float | bool


@dataclass(frozen=True)
class ConfigurationField:
    key: str
    ini_key: str
    label_pt: str
    section: str
    value_type: str
    default: ConfigurationValue
    recommended: ConfigurationValue
    allowed_values_pt: str
    impact_pt: str
    official_documentation_url: str
    restart_required: bool
    choices: tuple[str, ...]


@dataclass(frozen=True)
class GameTemplateDefinition:
    id: str
    game_key: str
    version: int
    display_name: str
    configuration_fields: tuple[ConfigurationField, ...]
