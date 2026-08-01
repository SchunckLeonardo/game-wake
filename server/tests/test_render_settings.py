import pytest
from render_settings import render_settings

DEFAULT = (
    "[/Script/Pal.PalGameWorldSettings]\n"
    "OptionSettings=(ExpRate=1.000000,"
    "EnemyDropItemRate=1.000000,"
    "SupplyDropSpan=180,"
    "BaseCampWorkerMaxNum=15,"
    "MonsterFarmActionSpeedRate=1.000000,"
    "bAllowGlobalPalboxExport=False,"
    "bAllowGlobalPalboxImport=False,"
    "PalAutoHpRegeneRateInSleep=1.000000,"
    "PalEggDefaultHatchingTime=72.000000,"
    "PalStaminaDecreaceRate=1.000000,"
    "PalStomachDecreaceRate=1.000000,"
    "CrossplayPlatforms=(Steam,Xbox,PS5),"
    "DeathPenalty=All,"
    'ServerName="Default Palworld Server",'
    'AdminPassword="",'
    "RESTAPIEnabled=False,"
    "RESTAPIPort=8212)\n"
)


def test_updates_selected_values_and_preserves_nested_defaults() -> None:
    rendered = render_settings(
        DEFAULT,
        {
            "ExpRate": 1.5,
            "EnemyDropItemRate": 2.5,
            "SupplyDropSpan": 60,
            "BaseCampWorkerMaxNum": 50,
            "MonsterFarmActionSpeedRate": 2.0,
            "bAllowGlobalPalboxExport": True,
            "bAllowGlobalPalboxImport": True,
            "PalAutoHpRegeneRateInSleep": 2.0,
            "PalEggDefaultHatchingTime": 0.0,
            "PalStaminaDecreaceRate": 0.5,
            "PalStomachDecreaceRate": 0.25,
            "DeathPenalty": "Item",
            "ServerName": "Amigos, São Paulo",
            "RESTAPIEnabled": True,
        },
    )

    assert "ExpRate=1.5" in rendered
    assert "EnemyDropItemRate=2.5" in rendered
    assert "SupplyDropSpan=60" in rendered
    assert "BaseCampWorkerMaxNum=50" in rendered
    assert "MonsterFarmActionSpeedRate=2" in rendered
    assert "bAllowGlobalPalboxExport=True" in rendered
    assert "bAllowGlobalPalboxImport=True" in rendered
    assert "PalAutoHpRegeneRateInSleep=2" in rendered
    assert "PalEggDefaultHatchingTime=0" in rendered
    assert "PalStaminaDecreaceRate=0.5" in rendered
    assert "PalStomachDecreaceRate=0.25" in rendered
    assert "DeathPenalty=Item" in rendered
    assert 'ServerName="Amigos, São Paulo"' in rendered
    assert "RESTAPIEnabled=True" in rendered
    assert "CrossplayPlatforms=(Steam,Xbox,PS5)" in rendered
    assert "RESTAPIPort=8212" in rendered


def test_escapes_quotes_in_string_values() -> None:
    rendered = render_settings(DEFAULT, {"ServerName": 'Mundo "Seguro"'})

    assert r'ServerName="Mundo \"Seguro\""' in rendered


def test_refuses_unknown_or_removed_setting() -> None:
    with pytest.raises(ValueError, match="not found exactly once"):
        render_settings(DEFAULT, {"InventedSetting": 1})
