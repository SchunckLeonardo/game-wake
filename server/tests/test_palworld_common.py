import json
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMMON_SCRIPT = PROJECT_ROOT / "server" / "palworld-common.sh"
CONFIGURE_SCRIPT = PROJECT_ROOT / "server" / "configure-palworld.sh"

BASE_CONFIG = {
    "server_name": "Base Server",
    "server_description": "Base description",
    "port": 8211,
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
    "rest_api_port": 8212,
    "rest_api_username": "admin",
    "autostop_check_minutes": 5,
    "autostop_idle_minutes": 20,
    "healthcheck_timeout_minutes": 15,
    "local_backup_retention_days": 14,
    "s3_backup_uri": "",
}


def run_load(overrides: dict[str, object]) -> subprocess.CompletedProcess[str]:
    script = f"""
set -Eeuo pipefail
PALWORLD_ENV_FILE=/definitely/missing
source {COMMON_SCRIPT}
AWS_REGION=us-east-1
PALWORLD_CONFIG_PARAMETER_NAME=/project/prod/palworld/config
aws() {{
  if [[ \"$*\" == *settings-overrides* ]]; then
    printf '%s' \"$OVERRIDES_JSON\"
  else
    printf '%s' \"$BASE_JSON\"
  fi
}}
load_palworld_config
printf '%s|%s|%s|%s' \\
  \"$PALWORLD_SERVER_NAME\" \\
  \"$EXP_RATE\" \\
  \"$ENEMY_DROP_ITEM_RATE\" \\
  \"$DEATH_PENALTY\"
printf '|%s|%s|%s|%s|%s' \
  \"$BASE_CAMP_WORKER_MAX_NUM\" \
  \"$ALLOW_GLOBAL_PALBOX_EXPORT\" \
  \"$ALLOW_GLOBAL_PALBOX_IMPORT\" \
  \"$PAL_AUTO_HP_REGEN_RATE_IN_SLEEP\" \
  \"$PAL_EGG_DEFAULT_HATCHING_TIME\"
"""
    return subprocess.run(
        ["bash", "-c", script],
        cwd=PROJECT_ROOT,
        env={
            **os.environ,
            "BASE_JSON": json.dumps(BASE_CONFIG, separators=(",", ":")),
            "OVERRIDES_JSON": json.dumps(overrides, separators=(",", ":")),
        },
        text=True,
        capture_output=True,
        check=False,
    )


def test_load_palworld_config_merges_discord_overrides() -> None:
    completed = run_load(
        {
            "server_name": "Discord Server",
            "exp_rate": 1.5,
            "enemy_drop_item_rate": 2.5,
            "death_penalty": "None",
            "base_camp_worker_max_num": 50,
            "allow_global_palbox_export": True,
            "allow_global_palbox_import": True,
            "pal_auto_hp_regen_rate_in_sleep": 2.0,
            "pal_egg_default_hatching_time": 0,
        }
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "Discord Server|1.5|2.5|None|50|true|true|2.0|0"


def test_load_palworld_config_rejects_unknown_override_keys() -> None:
    completed = run_load({"ServerPassword": "must-not-be-overridden"})

    assert completed.returncode != 0
    assert "invalidas ou desconhecidas" in completed.stderr


def test_load_palworld_config_rejects_invalid_override_values() -> None:
    completed = run_load({"enemy_drop_item_rate": 0})

    assert completed.returncode != 0
    assert "invalidas ou desconhecidas" in completed.stderr


def test_load_palworld_config_rejects_invalid_new_override_values() -> None:
    for overrides in (
        {"base_camp_worker_max_num": 51},
        {"base_camp_worker_max_num": False},
        {"allow_global_palbox_export": "true"},
        {"pal_auto_hp_regen_rate_in_sleep": 0},
        {"pal_egg_default_hatching_time": -1},
        {"pal_egg_default_hatching_time": False},
    ):
        completed = run_load(overrides)
        assert completed.returncode != 0
        assert "invalidas ou desconhecidas" in completed.stderr


def test_configure_script_maps_supported_settings_to_official_ini_keys() -> None:
    script = CONFIGURE_SCRIPT.read_text(encoding="utf-8")

    assert '--argjson enemy_drop_item_rate "$ENEMY_DROP_ITEM_RATE"' in script
    assert "EnemyDropItemRate:$enemy_drop_item_rate" in script
    assert "BaseCampWorkerMaxNum:$base_camp_worker_max_num" in script
    assert "bAllowGlobalPalboxExport:$allow_global_palbox_export" in script
    assert "bAllowGlobalPalboxImport:$allow_global_palbox_import" in script
    assert "PalAutoHpRegeneRateInSleep:$pal_auto_hp_regen_rate_in_sleep" in script
    assert "PalEggDefaultHatchingTime:$pal_egg_default_hatching_time" in script
