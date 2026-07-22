#!/usr/bin/env bash
set -Eeuo pipefail

exec > >(tee -a /var/log/palworld-user-data.log | systemd-cat -t palworld-user-data) 2>&1
trap 'echo "Bootstrap falhou na linha $LINENO"' ERR

export DEBIAN_FRONTEND=noninteractive

install_payload() {
  local payload=$1
  local destination=$2
  local mode=$3
  install -d -m 0755 "$(dirname "$destination")"
  printf '%s' "$payload" | base64 --decode >"$destination"
  chown root:root "$destination"
  chmod "$mode" "$destination"
}

install -d -m 0755 /usr/local/lib/palworld /usr/local/sbin /etc/palworld

install_payload '${common_script_b64}' /usr/local/lib/palworld/palworld-common.sh 0644
install_payload '${render_settings_script_b64}' /usr/local/lib/palworld/render_settings.py 0755
install_payload '${install_script_b64}' /usr/local/sbin/install-palworld.sh 0755
install_payload '${configure_script_b64}' /usr/local/sbin/configure-palworld.sh 0755
install_payload '${start_script_b64}' /usr/local/sbin/start-palworld.sh 0755
install_payload '${stop_script_b64}' /usr/local/sbin/stop-palworld.sh 0755
install_payload '${backup_script_b64}' /usr/local/sbin/backup-palworld.sh 0755
install_payload '${autostop_script_b64}' /usr/local/sbin/autostop.sh 0755
install_payload '${notify_script_b64}' /usr/local/sbin/notify-discord.sh 0755
install_payload '${healthcheck_script_b64}' /usr/local/sbin/healthcheck.sh 0755
install_payload '${palworld_service_b64}' /etc/systemd/system/palworld.service 0644
install_payload '${notify_service_b64}' /etc/systemd/system/palworld-notify.service 0644
install_payload '${autostop_service_b64}' /etc/systemd/system/palworld-autostop.service 0644
install_payload '${autostop_timer_b64}' /etc/systemd/system/palworld-autostop.timer 0644
install_payload '${backup_service_b64}' /etc/systemd/system/palworld-backup.service 0644
install_payload '${backup_timer_b64}' /etc/systemd/system/palworld-backup.timer 0644

cat >/etc/palworld/palworld.env <<'ENVIRONMENT'
AWS_REGION=${aws_region}
PALWORLD_PORT=${palworld_port}
REST_API_PORT=${palworld_rest_api_port}
REST_API_USERNAME=${palworld_rest_api_username}
PALWORLD_SERVER_NAME_B64=${palworld_server_name_b64}
PALWORLD_SERVER_DESCRIPTION_B64=${palworld_server_description_b64}
PALWORLD_MAX_PLAYERS=${palworld_max_players}
EXP_RATE=${palworld_exp_rate}
COLLECTION_DROP_RATE=${palworld_collection_drop_rate}
ENEMY_DROP_ITEM_RATE=${palworld_enemy_drop_item_rate}
SUPPLY_DROP_SPAN=${palworld_supply_drop_span}
BASE_CAMP_WORKER_MAX_NUM=${palworld_base_camp_worker_max_num}
MONSTER_FARM_ACTION_SPEED_RATE=${palworld_monster_farm_action_speed_rate}
ALLOW_GLOBAL_PALBOX_EXPORT=${palworld_allow_global_palbox_export}
ALLOW_GLOBAL_PALBOX_IMPORT=${palworld_allow_global_palbox_import}
PAL_AUTO_HP_REGEN_RATE_IN_SLEEP=${palworld_pal_auto_hp_regen_rate_in_sleep}
PAL_EGG_DEFAULT_HATCHING_TIME=${palworld_pal_egg_default_hatching_time}
PAL_SPAWN_RATE=${palworld_spawn_rate}
DEATH_PENALTY=${palworld_death_penalty}
PAL_DAMAGE_ATTACK_RATE=${palworld_pal_damage_attack_rate}
PAL_DAMAGE_DEFENSE_RATE=${palworld_pal_damage_defense_rate}
PLAYER_DAMAGE_ATTACK_RATE=${palworld_player_damage_attack_rate}
PLAYER_DAMAGE_DEFENSE_RATE=${palworld_player_damage_defense_rate}
PAL_STAMINA_DECREASE_RATE=${palworld_pal_stamina_decrease_rate}
PAL_STOMACH_DECREASE_RATE=${palworld_pal_stomach_decrease_rate}
PLAYER_STAMINA_DECREASE_RATE=${palworld_player_stamina_decrease_rate}
ITEM_WEIGHT_RATE=${palworld_item_weight_rate}
AUTOSTOP_CHECK_MINUTES=${autostop_check_minutes}
AUTOSTOP_IDLE_MINUTES=${autostop_idle_minutes}
HEALTHCHECK_TIMEOUT_MINUTES=${healthcheck_timeout_minutes}
LOCAL_BACKUP_RETENTION_DAYS=${local_backup_retention_days}
SERVER_PASSWORD_PARAMETER_NAME=${server_password_parameter_name}
ADMIN_PASSWORD_PARAMETER_NAME=${admin_password_parameter_name}
PALWORLD_CONFIG_PARAMETER_NAME=${palworld_config_parameter_name}
PALWORLD_OVERRIDES_PARAMETER_NAME=${palworld_overrides_parameter_name}
DISCORD_WEBHOOK_PARAMETER_NAME=${discord_webhook_parameter_name}
STATUS_PARAMETER_NAME=${server_status_parameter_name}
S3_BACKUP_URI=${s3_backup_uri}
ENVIRONMENT
chmod 0640 /etc/palworld/palworld.env

/usr/local/sbin/install-palworld.sh

chown root:palworld /etc/palworld/palworld.env
if ! snap list amazon-ssm-agent >/dev/null 2>&1; then
  snap install amazon-ssm-agent --classic
fi
systemctl enable --now snap.amazon-ssm-agent.amazon-ssm-agent.service || \
  systemctl enable --now amazon-ssm-agent.service

systemctl daemon-reload
systemctl enable palworld.service palworld-notify.service palworld-autostop.timer palworld-backup.timer
systemctl start --no-block palworld.service || true
systemctl start --no-block palworld-notify.service || true
systemctl start palworld-autostop.timer palworld-backup.timer

if [[ '${stop_after_initial_bootstrap}' == 'true' ]]; then
  systemd-run \
    --unit=palworld-initial-bootstrap-stop \
    --description='Stop initial Palworld bootstrap EC2' \
    --on-active=15m \
    /usr/local/sbin/stop-palworld.sh --shutdown
fi

echo "Bootstrap Palworld concluido"
