import pytest

from gamewake.game_catalog import GameCatalog, GameConfigurationError


def test_palworld_template_exposes_versioned_guided_configuration():
    catalog = GameCatalog.with_palworld()

    template = catalog.resolve("palworld:1")
    fields = {field.key: field for field in template.configuration_fields}

    assert template.id == "palworld:1"
    assert fields["enemy_drop_item_rate"].ini_key == "EnemyDropItemRate"
    assert fields["enemy_drop_item_rate"].default == 1.0
    assert fields["enemy_drop_item_rate"].recommended == 1.0
    assert "maior que 0" in fields["enemy_drop_item_rate"].allowed_values_pt
    assert fields["enemy_drop_item_rate"].impact_pt
    assert fields["enemy_drop_item_rate"].official_documentation_url.startswith("https://")
    assert fields["enemy_drop_item_rate"].restart_required
    assert {
        "base_camp_worker_max_num",
        "allow_global_palbox_export",
        "allow_global_palbox_import",
        "pal_auto_hp_regen_rate_in_sleep",
        "pal_egg_default_hatching_time",
        "monster_farm_action_speed_rate",
        "pal_stamina_decrease_rate",
        "pal_stomach_decrease_rate",
        "supply_drop_span",
    }.issubset(fields)


def test_palworld_configuration_uses_the_template_schema_for_validation():
    catalog = GameCatalog.with_palworld()

    normalized = catalog.validate_configuration(
        "palworld:1",
        {
            "enemy_drop_item_rate": "3,5",
            "base_camp_worker_max_num": "25",
            "allow_global_palbox_import": "true",
        },
        partial=True,
    )

    assert normalized == {
        "enemy_drop_item_rate": 3.5,
        "base_camp_worker_max_num": 25,
        "allow_global_palbox_import": True,
    }
    with pytest.raises(GameConfigurationError):
        catalog.validate_configuration(
            "palworld:1",
            {"enemy_drop_item_rate": 0},
            partial=True,
        )
