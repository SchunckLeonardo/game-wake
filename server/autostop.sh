#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck source=server/palworld-common.sh
source /usr/local/lib/palworld/palworld-common.sh

load_palworld_config

state_dir=/var/lib/palworld-monitor
idle_file="$state_dir/idle-seconds"
last_check_file="$state_dir/last-player-check-epoch"
install -d -o palworld -g palworld -m 0750 "$state_dir"

if ! systemctl is-active --quiet palworld.service; then
  printf '0\n' >"$idle_file"
  publish_status offline null "service inactive" || true
  exit 0
fi

if [[ ! -f /run/palworld/ready ]]; then
  palworld_log info "Servidor ainda esta iniciando; autostop adiado"
  publish_status starting null "healthcheck not ready" || true
  exit 0
fi

now_epoch=$(date +%s)
last_check_epoch=0
if [[ -r "$last_check_file" ]]; then
  read -r last_check_epoch <"$last_check_file" || last_check_epoch=0
fi
[[ "$last_check_epoch" =~ ^[0-9]+$ ]] || last_check_epoch=0
if ((now_epoch - last_check_epoch < AUTOSTOP_CHECK_MINUTES * 60)); then
  exit 0
fi
printf '%s\n' "$now_epoch" >"$last_check_file"

if ! players=$(palworld_player_count); then
  palworld_log err "Falha temporaria na API de jogadores; contador nao sera alterado"
  publish_status api_error null "player query failed; autostop skipped" || true
  exit 0
fi

if ((players > 0)); then
  printf '0\n' >"$idle_file"
  publish_status online "$players" "players connected" || true
  exit 0
fi

idle_seconds=0
if [[ -r "$idle_file" ]]; then
  read -r idle_seconds <"$idle_file" || idle_seconds=0
fi
[[ "$idle_seconds" =~ ^[0-9]+$ ]] || idle_seconds=0
idle_seconds=$((idle_seconds + AUTOSTOP_CHECK_MINUTES * 60))
printf '%s\n' "$idle_seconds" >"$idle_file"
publish_status online 0 "idle for $idle_seconds seconds" || true

if ((idle_seconds < AUTOSTOP_IDLE_MINUTES * 60)); then
  palworld_log info "Servidor vazio por ${idle_seconds}s; limite ainda nao atingido"
  exit 0
fi

discord_webhook_send "🟠 Servidor vazio por $AUTOSTOP_IDLE_MINUTES minutos. Salvando e desligando." || true
/usr/local/sbin/stop-palworld.sh --shutdown
