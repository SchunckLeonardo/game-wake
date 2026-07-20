#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck source=server/palworld-common.sh
source /usr/local/lib/palworld/palworld-common.sh

load_palworld_config || palworld_log warning "Usando configuracao local durante parada; Parameter Store indisponivel"

force=false
shutdown_host=false
service_stop=false
main_pid=""

while (($#)); do
  case "$1" in
    --force) force=true ;;
    --shutdown) shutdown_host=true ;;
    --service-stop)
      service_stop=true
      if [[ ${2:-} =~ ^[0-9]+$ ]]; then
        main_pid=$2
        shift
      fi
      ;;
    *)
      palworld_log err "Argumento desconhecido: $1"
      exit 64
      ;;
  esac
  shift
done

if [[ $service_stop == true ]]; then
  palworld_api POST save '{}' >/dev/null 2>&1 || palworld_log warning "Save REST indisponivel durante ExecStop"
  if [[ -n "$main_pid" ]] && kill -0 "$main_pid" 2>/dev/null; then
    kill -INT "$main_pid"
    for _ in {1..60}; do
      kill -0 "$main_pid" 2>/dev/null || exit 0
      sleep 1
    done
  fi
  exit 0
fi

if ! systemctl is-active --quiet palworld.service; then
  palworld_log info "Servico Palworld ja esta parado"
  publish_status offline null "service inactive" || true
  [[ $shutdown_host == true ]] && systemctl poweroff
  exit 0
fi

if ! players=$(palworld_player_count); then
  if [[ $force == false ]]; then
    palworld_log err "Nao foi possivel confirmar jogadores; desligamento cancelado"
    publish_status api_error null "shutdown cancelled: player query failed" || true
    exit 1
  fi
  players=unknown
  palworld_log warning "Forcado por administrador apesar de falha na API de jogadores"
fi

if [[ "$players" =~ ^[0-9]+$ ]] && ((players > 0)) && [[ $force == false ]]; then
  palworld_log warning "Desligamento cancelado: $players jogador(es) conectado(s)"
  publish_status online "$players" "shutdown cancelled: players connected" || true
  exit 2
fi

message="Servidor sera salvo e desligado para economizar custos."
palworld_api POST announce "$(jq -cn --arg message "$message" '{message:$message}')" >/dev/null 2>&1 || true
sleep 5
palworld_api POST save '{}' >/dev/null 2>&1 || {
  if [[ $force == false ]]; then
    palworld_log err "Save REST falhou; desligamento seguro cancelado"
    exit 1
  fi
  palworld_log warning "Save REST falhou durante desligamento forcado; SIGINT ainda sera usado"
}

/usr/local/sbin/backup-palworld.sh --skip-save || {
  if [[ $force == false ]]; then
    palworld_log err "Backup falhou; desligamento seguro cancelado"
    exit 1
  fi
}

palworld_api POST shutdown '{"waittime":1,"message":"Servidor em desligamento seguro"}' >/dev/null 2>&1 || true
systemctl stop palworld.service
rm -f /run/palworld/ready
publish_status offline 0 "safe shutdown completed" || true
discord_webhook_send "⚫ Servidor Palworld salvo e desligado." || true

if [[ $shutdown_host == true ]]; then
  palworld_log info "Desligando o Linux; a EC2 deve entrar em stopped"
  systemctl poweroff
fi
