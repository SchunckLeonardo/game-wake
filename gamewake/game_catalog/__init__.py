"""Versioned Game Template catalog used by every GameWake interface."""

from .catalog import GameCatalog
from .model import ConfigurationField, GameConfigurationError, GameTemplateDefinition

__all__ = [
    "ConfigurationField",
    "GameCatalog",
    "GameConfigurationError",
    "GameTemplateDefinition",
]
