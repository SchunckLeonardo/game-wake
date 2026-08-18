import json
import subprocess
import sys
from pathlib import Path

import pytest
from palworld_settings import (
    SettingsDocument,
    SettingsValidationError,
    run_settings_cli,
)

DEFAULT_DOCUMENT = {
    "schema_version": 1,
    "settings": {
        "server_name": "Palworld Friends Server",
        "server_description": "Private server started on demand through Discord",
        "max_players": 16,
        "exp_rate": 1.0,
        "collection_drop_rate": 1.0,
        "enemy_drop_item_rate": 1.0,
        "supply_drop_span": 180,
        "base_camp_worker_max_num": 15,
        "monster_farm_action_speed_rate": 1.0,
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
        "pal_stomach_decrease_rate": 1.0,
        "player_stamina_decrease_rate": 1.0,
        "item_weight_rate": 1.0,
    },
}


def write_json(path: Path, document: dict = DEFAULT_DOCUMENT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_load_bootstraps_local_document_from_repository_template(tmp_path: Path) -> None:
    template = tmp_path / "palworld-settings.json.example"
    settings = tmp_path / "palworld-settings.json"
    write_json(template)

    document = SettingsDocument.load(settings, template_path=template)

    assert settings.exists()
    assert document.values["server_name"] == "Palworld Friends Server"
    assert json.loads(settings.read_text(encoding="utf-8")) == DEFAULT_DOCUMENT


def test_update_validates_and_persists_a_canonical_document(tmp_path: Path) -> None:
    settings = tmp_path / "palworld-settings.json"
    write_json(settings)
    document = SettingsDocument.load(settings)

    changes = document.update(
        {
            "server_name": "Guild World",
            "max_players": "12",
            "exp_rate": "1.5",
            "death_penalty": "None",
        }
    )
    document.save()

    assert [change.key for change in changes] == [
        "server_name",
        "max_players",
        "exp_rate",
        "death_penalty",
    ]
    persisted = json.loads(settings.read_text(encoding="utf-8"))
    assert persisted["settings"]["server_name"] == "Guild World"
    assert persisted["settings"]["max_players"] == 12
    assert persisted["settings"]["exp_rate"] == 1.5
    assert persisted["settings"]["death_penalty"] == "None"
    assert settings.read_text(encoding="utf-8").endswith("\n")


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("max_players", 0, "must be at least 1"),
        ("exp_rate", 0, "must be greater than 0"),
        ("base_camp_worker_max_num", 51, "must be at most 50"),
        ("allow_global_palbox_export", "yes", "must be True or False"),
        ("pal_auto_hp_regen_rate_in_sleep", 0, "must be greater than 0"),
        ("monster_farm_action_speed_rate", 0, "must be greater than 0"),
        ("pal_stomach_decrease_rate", 0, "must be greater than 0"),
        ("supply_drop_span", 0, "must be at least 1"),
        ("pal_egg_default_hatching_time", -1, "must be at least 0"),
        ("death_penalty", "Inventory", "must be one of"),
        ("ServerPassword", "do-not-store-here", "unknown setting"),
        ("server_name", "x" * 101, "must be at most 100 characters"),
    ],
)
def test_update_rejects_invalid_or_secret_values(
    tmp_path: Path, key: str, value: object, message: str
) -> None:
    settings = tmp_path / "palworld-settings.json"
    write_json(settings)
    document = SettingsDocument.load(settings)

    with pytest.raises(SettingsValidationError, match=message):
        document.update({key: value})


def test_load_rejects_missing_or_extra_settings(tmp_path: Path) -> None:
    settings = tmp_path / "palworld-settings.json"
    invalid = json.loads(json.dumps(DEFAULT_DOCUMENT))
    invalid["settings"].pop("exp_rate")
    invalid["settings"]["InventedSetting"] = 2
    write_json(settings, invalid)

    with pytest.raises(SettingsValidationError, match="missing settings: exp_rate"):
        SettingsDocument.load(settings)


def test_show_command_is_non_interactive_and_uses_friendly_labels(tmp_path: Path) -> None:
    settings = tmp_path / "palworld-settings.json"
    write_json(settings)
    output: list[str] = []

    exit_code = run_settings_cli(
        ["--file", str(settings), "show"],
        input_fn=lambda _: pytest.fail("show must not prompt"),
        output_fn=output.append,
    )

    assert exit_code == 0
    rendered = "\n".join(output)
    assert "Server name: Palworld Friends Server" in rendered
    assert "Experience rate: 1" in rendered
    assert "Death penalty: Item" in rendered


def test_default_command_runs_wizard_and_saves_only_confirmed_changes(tmp_path: Path) -> None:
    settings = tmp_path / "palworld-settings.json"
    write_json(settings)
    answers = iter(
        [
            "3",  # Gameplay
            "1.5",  # Experience
            "",  # Collection drops
            "",  # Enemy/Pal drops
            "",  # Meteorite/supply interval
            "",  # Pal spawn
            "",  # Death penalty
            "",  # Pal HP regeneration while sleeping
            "",  # Egg hatching time
            "6",  # Review and save
            "y",
        ]
    )
    output: list[str] = []

    exit_code = run_settings_cli(
        ["--file", str(settings)],
        input_fn=lambda _: next(answers),
        output_fn=output.append,
    )

    assert exit_code == 0
    persisted = json.loads(settings.read_text(encoding="utf-8"))
    assert persisted["settings"]["exp_rate"] == 1.5
    assert persisted["settings"]["collection_drop_rate"] == 1.0
    assert "Experience rate: 1 -> 1.5" in "\n".join(output)


def test_cancelled_wizard_does_not_modify_the_file(tmp_path: Path) -> None:
    settings = tmp_path / "palworld-settings.json"
    write_json(settings)
    before = settings.read_text(encoding="utf-8")

    exit_code = run_settings_cli(
        ["--file", str(settings)],
        input_fn=lambda _: "0",
        output_fn=lambda _: None,
    )

    assert exit_code == 0
    assert settings.read_text(encoding="utf-8") == before


def test_root_command_exposes_settings_help() -> None:
    project_root = Path(__file__).resolve().parents[2]

    completed = subprocess.run(
        [sys.executable, str(project_root / "palworld"), "settings", "--help"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Interactively edit Palworld server settings" in completed.stdout
    assert "show" in completed.stdout
    assert "plan" in completed.stdout
    assert "apply" in completed.stdout


def test_discord_registration_exposes_guided_settings_panel() -> None:
    project_root = Path(__file__).resolve().parents[2]
    registration_script = (project_root / "scripts" / "register-discord-commands.sh").read_text(
        encoding="utf-8"
    )

    assert registration_script.count('name:"configurar"') == 1
    assert 'name:"palworld"' not in registration_script
    assert "painel guiado de configurações" in registration_script


def test_discord_registration_publishes_gamewake_globally_without_overwriting_activity() -> None:
    project_root = Path(__file__).resolve().parents[2]
    registration_script = (project_root / "scripts" / "register-discord-commands.sh").read_text(
        encoding="utf-8"
    )

    assert "${DISCORD_GUILD_ID:?" not in registration_script
    assert "applications/$DISCORD_APPLICATION_ID/commands" in registration_script
    assert "guilds/$DISCORD_GUILD_ID/commands" not in registration_script
    assert "--request POST" in registration_script
    assert "--request PUT" not in registration_script
    assert "integration_types:[0]" in registration_script
    assert "contexts:[0]" in registration_script
