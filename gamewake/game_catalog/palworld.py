from shared.palworld_settings_catalog import (
    FIELDS,
    OFFICIAL_CONFIGURATION_URL,
    SettingsValidationError,
    normalize_settings,
)

from .model import (
    ConfigurationField,
    ConfigurationValue,
    GameConfigurationError,
    GameTemplateDefinition,
)

PALWORLD_DEFAULTS: dict[str, ConfigurationValue] = {
    "server_name": "GameWake Palworld",
    "server_description": "Persistent World powered by GameWake",
    "max_players": 16,
    "base_camp_worker_max_num": 15,
    "monster_farm_action_speed_rate": 1.0,
    "allow_global_palbox_export": False,
    "allow_global_palbox_import": False,
    "exp_rate": 1.0,
    "collection_drop_rate": 1.0,
    "enemy_drop_item_rate": 1.0,
    "supply_drop_span": 180,
    "pal_spawn_rate": 1.0,
    "death_penalty": "Item",
    "pal_auto_hp_regen_rate_in_sleep": 1.0,
    "pal_egg_default_hatching_time": 72.0,
    "pal_damage_attack_rate": 1.0,
    "pal_damage_defense_rate": 1.0,
    "player_damage_attack_rate": 1.0,
    "player_damage_defense_rate": 1.0,
    "pal_stamina_decrease_rate": 1.0,
    "pal_stomach_decrease_rate": 1.0,
    "player_stamina_decrease_rate": 1.0,
    "item_weight_rate": 1.0,
}


PALWORLD_TEMPLATE = GameTemplateDefinition(
    id="palworld:1",
    game_key="palworld",
    version=1,
    display_name="Palworld",
    configuration_fields=tuple(
        ConfigurationField(
            key=field.key,
            ini_key=field.ini_key,
            label_pt=field.label_pt,
            section=field.section,
            value_type=field.value_type,
            default=PALWORLD_DEFAULTS[field.key],
            recommended=PALWORLD_DEFAULTS[field.key],
            allowed_values_pt=field.allowed_values_pt,
            impact_pt=field.official_description_pt,
            official_documentation_url=OFFICIAL_CONFIGURATION_URL,
            restart_required=True,
            choices=field.choices,
        )
        for field in FIELDS
    ),
)


def validate_palworld_configuration(
    values: object,
    *,
    partial: bool,
) -> dict[str, ConfigurationValue]:
    try:
        return normalize_settings(values, require_all=not partial)
    except SettingsValidationError as error:
        raise GameConfigurationError(str(error)) from error
