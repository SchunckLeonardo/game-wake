import json
from typing import Any

import pytest
from palworld_settings_catalog import SettingsValidationError
from settings_service import ParameterSettingsService

from .test_settings_interactions import BASE_SETTINGS


class FakeSSM:
    def __init__(self, base: dict[str, Any], overrides: dict[str, Any]):
        self.parameters = {
            "/palworld/config": json.dumps({**base, "port": 8211}),
            "/palworld/settings-overrides": json.dumps(overrides),
        }
        self.puts: list[dict[str, Any]] = []

    def get_parameters(self, *, Names: list[str], WithDecryption: bool) -> dict[str, Any]:
        assert WithDecryption is False
        return {"Parameters": [{"Name": name, "Value": self.parameters[name]} for name in Names]}

    def put_parameter(self, **kwargs: Any) -> dict[str, Any]:
        self.puts.append(kwargs)
        self.parameters[kwargs["Name"]] = kwargs["Value"]
        return {"Version": 2}


def test_parameter_service_merges_only_valid_discord_overrides() -> None:
    ssm = FakeSSM(BASE_SETTINGS, {"exp_rate": 1.5, "death_penalty": "None"})
    service = ParameterSettingsService(
        lambda: ssm,
        "/palworld/config",
        "/palworld/settings-overrides",
    )

    snapshot = service.read()

    assert snapshot.base["exp_rate"] == 1.0
    assert snapshot.effective["exp_rate"] == 1.5
    assert snapshot.source("exp_rate") == "discord"
    assert snapshot.source("max_players") == "base"


def test_parameter_service_validates_and_persists_only_the_override_document() -> None:
    ssm = FakeSSM(BASE_SETTINGS, {})
    service = ParameterSettingsService(
        lambda: ssm,
        "/palworld/config",
        "/palworld/settings-overrides",
    )

    snapshot = service.set_override("max_players", "12")

    assert snapshot.effective["max_players"] == 12
    assert json.loads(ssm.puts[-1]["Value"]) == {"max_players": 12}
    assert ssm.puts[-1]["Name"] == "/palworld/settings-overrides"
    assert ssm.puts[-1]["Overwrite"] is True


def test_parameter_service_persists_enemy_drop_rate_override() -> None:
    ssm = FakeSSM(BASE_SETTINGS, {})
    service = ParameterSettingsService(
        lambda: ssm,
        "/palworld/config",
        "/palworld/settings-overrides",
    )

    snapshot = service.set_override("enemy_drop_item_rate", "2,5")

    assert snapshot.effective["enemy_drop_item_rate"] == 2.5
    assert json.loads(ssm.puts[-1]["Value"]) == {"enemy_drop_item_rate": 2.5}


def test_parameter_service_parses_and_persists_boolean_override() -> None:
    ssm = FakeSSM(BASE_SETTINGS, {})
    service = ParameterSettingsService(
        lambda: ssm,
        "/palworld/config",
        "/palworld/settings-overrides",
    )

    snapshot = service.set_override("allow_global_palbox_export", "true")

    assert snapshot.effective["allow_global_palbox_export"] is True
    assert json.loads(ssm.puts[-1]["Value"]) == {"allow_global_palbox_export": True}


def test_parameter_service_validates_new_numeric_limits() -> None:
    ssm = FakeSSM(BASE_SETTINGS, {})
    service = ParameterSettingsService(
        lambda: ssm,
        "/palworld/config",
        "/palworld/settings-overrides",
    )

    assert (
        service.set_override("base_camp_worker_max_num", "50").effective["base_camp_worker_max_num"]
        == 50
    )
    assert (
        service.set_override("pal_egg_default_hatching_time", "0").effective[
            "pal_egg_default_hatching_time"
        ]
        == 0.0
    )
    assert (
        service.set_override("monster_farm_action_speed_rate", "2,5").effective[
            "monster_farm_action_speed_rate"
        ]
        == 2.5
    )
    assert (
        service.set_override("pal_stomach_decrease_rate", "0,5").effective[
            "pal_stomach_decrease_rate"
        ]
        == 0.5
    )
    assert service.set_override("supply_drop_span", "60").effective["supply_drop_span"] == 60

    with pytest.raises(SettingsValidationError):
        service.set_override("base_camp_worker_max_num", 51)
    with pytest.raises(SettingsValidationError):
        service.set_override("pal_egg_default_hatching_time", -1)
    with pytest.raises(SettingsValidationError):
        service.set_override("supply_drop_span", 0)


def test_parameter_service_rejects_unknown_or_invalid_values() -> None:
    ssm = FakeSSM(BASE_SETTINGS, {})
    service = ParameterSettingsService(
        lambda: ssm,
        "/palworld/config",
        "/palworld/settings-overrides",
    )

    with pytest.raises(SettingsValidationError):
        service.set_override("ServerPassword", "secret")
    with pytest.raises(SettingsValidationError):
        service.set_override("exp_rate", 0)

    assert ssm.puts == []


def test_parameter_service_does_not_keep_redundant_base_value_as_override() -> None:
    ssm = FakeSSM(BASE_SETTINGS, {"exp_rate": 1.5})
    service = ParameterSettingsService(
        lambda: ssm,
        "/palworld/config",
        "/palworld/settings-overrides",
    )

    snapshot = service.set_override("exp_rate", "1.0")

    assert snapshot.source("exp_rate") == "base"
    assert json.loads(ssm.puts[-1]["Value"]) == {}
