#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck source=server/palworld-common.sh
source /usr/local/lib/palworld/palworld-common.sh

load_palworld_config

deadline=$((SECONDS + HEALTHCHECK_TIMEOUT_MINUTES * 60))
rm -f /run/palworld/ready
publish_status starting null "waiting for REST API" || true

while ((SECONDS < deadline)); do
  if palworld_api GET info >/dev/null 2>&1 && players=$(palworld_player_count); then
    touch /run/palworld/ready
    chown palworld:palworld /run/palworld/ready
    publish_status online "$players" "REST API ready" || true
    public_ip=$(current_public_ipv4 || printf 'IP_PUBLICO_INDISPONIVEL')
    printf -v ready_message \
      "🟢 **Servidor Palworld disponível!**\n\n🎮 **Endereço para conectar**\n\`%s:%s\`\n\n_Desligamento automático após %s minutos sem jogadores._" \
      "$public_ip" "$PALWORLD_PORT" "$AUTOSTOP_IDLE_MINUTES"
    discord_webhook_send "$ready_message" || true
    palworld_log info "Healthcheck concluido; endereco ${public_ip}:${PALWORLD_PORT}"
    exit 0
  fi
  sleep 10
done

publish_status starting null "healthcheck timed out; systemd will retry" || true
palworld_log err "REST API nao ficou pronta dentro do timeout"
exit 1
