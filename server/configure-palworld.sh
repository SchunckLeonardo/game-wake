#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# shellcheck source=server/palworld-common.sh
source /usr/local/lib/palworld/palworld-common.sh

load_palworld_config
server_password=$(ssm_get_secret "$SERVER_PASSWORD_PARAMETER_NAME")
admin_password=$(ssm_get_secret "$ADMIN_PASSWORD_PARAMETER_NAME")
server_name=$PALWORLD_SERVER_NAME
server_description=$PALWORLD_SERVER_DESCRIPTION

config_dir=/var/lib/palworld/saved/Config/LinuxServer
config_file="$config_dir/PalWorldSettings.ini"
install -d -o palworld -g palworld -m 0750 "$config_dir"

updates=$(jq -cn \
  --arg server_password "$server_password" \
  --arg admin_password "$admin_password" \
  --arg server_name "$server_name" \
  --arg server_description "$server_description" \
  --argjson port "$PALWORLD_PORT" \
  --argjson max_players "$PALWORLD_MAX_PLAYERS" \
  --argjson exp_rate "$EXP_RATE" \
  --argjson collection_drop_rate "$COLLECTION_DROP_RATE" \
  --argjson enemy_drop_item_rate "$ENEMY_DROP_ITEM_RATE" \
  --argjson base_camp_worker_max_num "$BASE_CAMP_WORKER_MAX_NUM" \
  --argjson allow_global_palbox_export "$ALLOW_GLOBAL_PALBOX_EXPORT" \
  --argjson allow_global_palbox_import "$ALLOW_GLOBAL_PALBOX_IMPORT" \
  --argjson pal_auto_hp_regen_rate_in_sleep "$PAL_AUTO_HP_REGEN_RATE_IN_SLEEP" \
  --argjson pal_egg_default_hatching_time "$PAL_EGG_DEFAULT_HATCHING_TIME" \
  --argjson pal_spawn_rate "$PAL_SPAWN_RATE" \
  --arg death_penalty "$DEATH_PENALTY" \
  --argjson pal_damage_attack_rate "$PAL_DAMAGE_ATTACK_RATE" \
  --argjson pal_damage_defense_rate "$PAL_DAMAGE_DEFENSE_RATE" \
  --argjson player_damage_attack_rate "$PLAYER_DAMAGE_ATTACK_RATE" \
  --argjson player_damage_defense_rate "$PLAYER_DAMAGE_DEFENSE_RATE" \
  --argjson pal_stamina_decrease_rate "$PAL_STAMINA_DECREASE_RATE" \
  --argjson player_stamina_decrease_rate "$PLAYER_STAMINA_DECREASE_RATE" \
  --argjson item_weight_rate "$ITEM_WEIGHT_RATE" \
  --argjson rest_api_port "$REST_API_PORT" \
  '{
    ServerPassword:$server_password,
    AdminPassword:$admin_password,
    ServerName:$server_name,
    ServerDescription:$server_description,
    PublicPort:$port,
    ServerPlayerMaxNum:$max_players,
    ExpRate:$exp_rate,
    CollectionDropRate:$collection_drop_rate,
    EnemyDropItemRate:$enemy_drop_item_rate,
    BaseCampWorkerMaxNum:$base_camp_worker_max_num,
    bAllowGlobalPalboxExport:$allow_global_palbox_export,
    bAllowGlobalPalboxImport:$allow_global_palbox_import,
    PalAutoHpRegeneRateInSleep:$pal_auto_hp_regen_rate_in_sleep,
    PalEggDefaultHatchingTime:$pal_egg_default_hatching_time,
    PalSpawnNumRate:$pal_spawn_rate,
    DeathPenalty:$death_penalty,
    PalDamageRateAttack:$pal_damage_attack_rate,
    PalDamageRateDefense:$pal_damage_defense_rate,
    PlayerDamageRateAttack:$player_damage_attack_rate,
    PlayerDamageRateDefense:$player_damage_defense_rate,
    PalStaminaDecreaceRate:$pal_stamina_decrease_rate,
    PlayerStaminaDecreaceRate:$player_stamina_decrease_rate,
    ItemWeightRate:$item_weight_rate,
    bAllowEnhanceStat_Stamina:true,
    bAllowEnhanceStat_Weight:true,
    bIsUseBackupSaveData:true,
    RCONEnabled:false,
    RESTAPIEnabled:true,
    RESTAPIPort:$rest_api_port
  }')

printf '%s' "$updates" | /usr/local/lib/palworld/render_settings.py \
  --base /opt/palworld/DefaultPalWorldSettings.ini \
  --output "$config_file.tmp"

chown palworld:palworld "$config_file.tmp"
chmod 0600 "$config_file.tmp"
mv "$config_file.tmp" "$config_file"
palworld_log info "PalWorldSettings.ini atualizado sem registrar segredos"
