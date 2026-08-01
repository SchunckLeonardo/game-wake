from .model import ConfigurationValue, GameConfigurationError, GameTemplateDefinition
from .palworld import PALWORLD_TEMPLATE, validate_palworld_configuration


class GameCatalog:
    def __init__(self, templates: tuple[GameTemplateDefinition, ...]) -> None:
        self._templates = {template.id: template for template in templates}

    @classmethod
    def with_palworld(cls) -> "GameCatalog":
        return cls((PALWORLD_TEMPLATE,))

    def resolve(self, game_template_id: str) -> GameTemplateDefinition:
        try:
            return self._templates[game_template_id]
        except KeyError as error:
            raise KeyError(f"unknown Game Template: {game_template_id}") from error

    def validate_configuration(
        self,
        game_template_id: str,
        values: object,
        *,
        partial: bool = False,
    ) -> dict[str, ConfigurationValue]:
        template = self.resolve(game_template_id)
        if template.game_key == "palworld":
            return validate_palworld_configuration(values, partial=partial)
        raise GameConfigurationError(
            f"Game Template has no configuration validator: {game_template_id}"
        )
