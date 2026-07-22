import json
from typing import Any

import handler
from palworld_settings_catalog import FIELDS, FIELDS_BY_KEY, OFFICIAL_CONFIGURATION_URL
from settings_service import SettingsSnapshot

from .conftest import FakeEC2Service, StaticConfigProvider, response_payload

BASE_SETTINGS: dict[str, str | int | float | bool] = {
    "server_name": "Palworld Friends Server",
    "server_description": "Private server started through Discord",
    "max_players": 16,
    "exp_rate": 1.0,
    "collection_drop_rate": 1.0,
    "enemy_drop_item_rate": 1.0,
    "base_camp_worker_max_num": 15,
    "allow_global_palbox_export": False,
    "allow_global_palbox_import": False,
    "pal_auto_hp_regen_rate_in_sleep": 1.0,
    "pal_egg_default_hatching_time": 72.0,
    "pal_spawn_rate": 1.0,
    "death_penalty": "Item",
    "pal_damage_attack_rate": 1.0,
    "pal_damage_defense_rate": 1.0,
    "player_damage_attack_rate": 1.0,
    "player_damage_defense_rate": 1.0,
    "pal_stamina_decrease_rate": 1.0,
    "player_stamina_decrease_rate": 1.0,
    "item_weight_rate": 1.0,
}


class FakeSettingsService:
    def __init__(self, overrides: dict[str, str | int | float | bool] | None = None):
        self.base = dict(BASE_SETTINGS)
        self.overrides = dict(overrides or {})
        self.updates: list[tuple[str, object]] = []

    def read(self) -> SettingsSnapshot:
        return SettingsSnapshot.from_values(self.base, self.overrides)

    def set_override(self, key: str, raw_value: object) -> SettingsSnapshot:
        self.updates.append((key, raw_value))
        if isinstance(raw_value, str) and raw_value.casefold() in {"padrao", "padrão", "default"}:
            self.overrides.pop(key, None)
        else:
            self.overrides[key] = FIELDS_BY_KEY[key].parse(raw_value)
        return self.read()


def _component(payload: dict[str, Any], custom_id: str) -> dict[str, Any]:
    for row in payload["data"].get("components", []):
        for component in row.get("components", []):
            if component.get("custom_id") == custom_id:
                return component
    raise AssertionError(f"component not found: {custom_id}")


def _modal_child(payload: dict[str, Any], custom_id: str) -> dict[str, Any]:
    for component in payload["data"]["components"]:
        child = component.get("component", component)
        if child.get("custom_id") == custom_id:
            return child
    raise AssertionError(f"modal child not found: {custom_id}")


def test_enemy_drop_rate_uses_the_official_key_and_explains_its_effect() -> None:
    field = FIELDS_BY_KEY["enemy_drop_item_rate"]

    assert field.ini_key == "EnemyDropItemRate"
    assert "Pals" in field.label_pt
    assert "derrotados" in field.official_description_pt
    assert "maior que 0" in field.allowed_values_pt


def test_new_fields_use_official_keys_and_document_their_constraints() -> None:
    assert FIELDS_BY_KEY["base_camp_worker_max_num"].ini_key == "BaseCampWorkerMaxNum"
    assert "50" in FIELDS_BY_KEY["base_camp_worker_max_num"].allowed_values_pt
    assert FIELDS_BY_KEY["allow_global_palbox_export"].ini_key == "bAllowGlobalPalboxExport"
    assert FIELDS_BY_KEY["allow_global_palbox_import"].ini_key == "bAllowGlobalPalboxImport"
    assert FIELDS_BY_KEY["pal_auto_hp_regen_rate_in_sleep"].ini_key == "PalAutoHpRegeneRateInSleep"
    assert FIELDS_BY_KEY["pal_egg_default_hatching_time"].ini_key == "PalEggDefaultHatchingTime"
    assert "0" in FIELDS_BY_KEY["pal_egg_default_hatching_time"].allowed_values_pt


def test_configurar_opens_ephemeral_panel_with_every_setting_and_official_docs(
    make_event, config
) -> None:
    settings = FakeSettingsService({"exp_rate": 1.5})

    response = handler.process_event(
        make_event("configurar"),
        StaticConfigProvider(config),
        FakeEC2Service(),
        settings,
    )

    payload = response_payload(response)
    assert payload["type"] == 4
    assert payload["data"]["flags"] == 64
    assert payload["data"]["embeds"][0]["url"] == OFFICIAL_CONFIGURATION_URL
    assert OFFICIAL_CONFIGURATION_URL in payload["data"]["content"]
    select = _component(payload, "pwcfg:setting")
    assert {option["value"] for option in select["options"]} == {field.key for field in FIELDS}
    assert all(option.get("description") for option in select["options"])
    assert "1.5" in json.dumps(payload["data"]["embeds"], ensure_ascii=False)
    assert "Discord" in json.dumps(payload["data"]["embeds"], ensure_ascii=False)


def test_selecting_numeric_setting_opens_guided_modal(make_event, config) -> None:
    settings = FakeSettingsService()
    event = make_event(
        interaction_type=3,
        interaction_data={
            "component_type": 3,
            "custom_id": "pwcfg:setting",
            "values": ["exp_rate"],
        },
    )

    response = handler.process_event(
        event,
        StaticConfigProvider(config),
        FakeEC2Service(),
        settings,
    )

    payload = response_payload(response)
    assert payload["type"] == 9
    assert payload["data"]["custom_id"] == "pwcfg:edit:exp_rate"
    modal_text = json.dumps(payload["data"]["components"], ensure_ascii=False)
    assert OFFICIAL_CONFIGURATION_URL in modal_text
    assert "maior que 0" in modal_text
    value_input = _modal_child(payload, "pwcfg:value")
    assert value_input["type"] == 4
    assert value_input["value"] == "1"


def test_death_penalty_modal_uses_the_four_official_choices(make_event, config) -> None:
    event = make_event(
        interaction_type=3,
        interaction_data={
            "component_type": 3,
            "custom_id": "pwcfg:setting",
            "values": ["death_penalty"],
        },
    )

    response = handler.process_event(
        event,
        StaticConfigProvider(config),
        FakeEC2Service(),
        FakeSettingsService(),
    )

    payload = response_payload(response)
    value_select = _modal_child(payload, "pwcfg:value")
    assert value_select["type"] == 3
    assert [choice["value"] for choice in value_select["options"]] == [
        "None",
        "Item",
        "ItemAndEquipment",
        "All",
        "__default__",
    ]
    assert all(choice.get("description") for choice in value_select["options"])


def test_boolean_setting_modal_uses_true_false_dropdown(make_event, config) -> None:
    event = make_event(
        interaction_type=3,
        interaction_data={
            "component_type": 3,
            "custom_id": "pwcfg:setting",
            "values": ["allow_global_palbox_export"],
        },
    )

    response = handler.process_event(
        event,
        StaticConfigProvider(config),
        FakeEC2Service(),
        FakeSettingsService(),
    )

    value_select = _modal_child(response_payload(response), "pwcfg:value")
    assert value_select["type"] == 3
    assert [choice["value"] for choice in value_select["options"]] == [
        "True",
        "False",
        "__default__",
    ]
    assert (
        next(choice for choice in value_select["options"] if choice["value"] == "False")["default"]
        is True
    )


def test_modal_submit_persists_valid_value_and_requests_safe_activation(make_event, config) -> None:
    settings = FakeSettingsService()
    game = FakeEC2Service(state="running")
    event = make_event(
        interaction_type=5,
        interaction_data={
            "custom_id": "pwcfg:edit:exp_rate",
            "components": [
                {
                    "type": 18,
                    "component": {
                        "type": 4,
                        "custom_id": "pwcfg:value",
                        "value": "1,5",
                    },
                }
            ],
        },
    )

    response = handler.process_event(
        event,
        StaticConfigProvider(config),
        game,
        settings,
    )

    assert settings.updates == [("exp_rate", "1,5")]
    assert settings.read().effective["exp_rate"] == 1.5
    assert game.settings_activation_requested is True
    text = response_payload(response)["data"]["content"]
    assert "1.5" in text
    assert "ativação segura" in text
    assert "jogadores" in text


def test_invalid_modal_value_returns_allowed_values_without_writing(make_event, config) -> None:
    settings = FakeSettingsService()
    event = make_event(
        interaction_type=5,
        interaction_data={
            "custom_id": "pwcfg:edit:exp_rate",
            "components": [
                {
                    "type": 18,
                    "component": {
                        "type": 4,
                        "custom_id": "pwcfg:value",
                        "value": "0",
                    },
                }
            ],
        },
    )

    response = handler.process_event(
        event,
        StaticConfigProvider(config),
        FakeEC2Service(state="running"),
        settings,
    )

    payload = response_payload(response)
    assert payload["type"] == 4
    assert settings.updates == [("exp_rate", "0")]
    assert settings.read().effective["exp_rate"] == 1.0
    assert "maior que 0" in payload["data"]["content"]
    assert OFFICIAL_CONFIGURATION_URL in payload["data"]["content"]


def test_default_keyword_removes_discord_override(make_event, config) -> None:
    settings = FakeSettingsService({"exp_rate": 2.0})
    event = make_event(
        interaction_type=5,
        interaction_data={
            "custom_id": "pwcfg:edit:exp_rate",
            "components": [
                {
                    "type": 18,
                    "component": {
                        "type": 4,
                        "custom_id": "pwcfg:value",
                        "value": "PADRAO",
                    },
                }
            ],
        },
    )

    response = handler.process_event(
        event,
        StaticConfigProvider(config),
        FakeEC2Service(),
        settings,
    )

    assert settings.read().effective["exp_rate"] == 1.0
    assert "base do repositório" in response_payload(response)["data"]["content"]


def test_unauthorized_component_cannot_read_or_change_settings(make_event, config) -> None:
    settings = FakeSettingsService()
    event = make_event(
        interaction_type=3,
        user_id="intruder",
        interaction_data={
            "component_type": 3,
            "custom_id": "pwcfg:setting",
            "values": ["exp_rate"],
        },
    )

    response = handler.process_event(
        event,
        StaticConfigProvider(config),
        FakeEC2Service(),
        settings,
    )

    assert "não tem permissão" in response_payload(response)["data"]["content"]
    assert settings.updates == []


def test_catalog_and_generated_components_fit_discord_limits(make_event, config) -> None:
    assert len(FIELDS) <= 25
    for field in FIELDS:
        assert field.allowed_values_pt
        assert field.official_description_pt
        assert len(field.label_pt) <= 45
        assert len(field.menu_description_pt) <= 100

    panel = response_payload(
        handler.process_event(
            make_event("configurar"),
            StaticConfigProvider(config),
            FakeEC2Service(),
            FakeSettingsService(),
        )
    )
    select = _component(panel, "pwcfg:setting")
    assert len(select["options"]) <= 25
    assert all(len(option["label"]) <= 100 for option in select["options"])
    assert all(len(option["value"]) <= 100 for option in select["options"])
    assert all(len(option["description"]) <= 100 for option in select["options"])

    modal_payload = response_payload(
        handler.process_event(
            make_event(
                interaction_type=3,
                interaction_data={
                    "component_type": 3,
                    "custom_id": "pwcfg:setting",
                    "values": ["pal_stamina_decrease_rate"],
                },
            ),
            StaticConfigProvider(config),
            FakeEC2Service(),
            FakeSettingsService(),
        )
    )
    assert len(modal_payload["data"]["custom_id"]) <= 100
    assert len(modal_payload["data"]["title"]) <= 45
    assert 1 <= len(modal_payload["data"]["components"]) <= 5
    label = next(
        component for component in modal_payload["data"]["components"] if component["type"] == 18
    )
    assert len(label["label"]) <= 45
    assert len(label["description"]) <= 100
