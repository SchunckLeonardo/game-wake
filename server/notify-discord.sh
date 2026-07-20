#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck source=server/palworld-common.sh
source /usr/local/lib/palworld/palworld-common.sh

if (($# == 0)); then
  echo "Uso: notify-discord.sh MENSAGEM" >&2
  exit 64
fi
discord_webhook_send "$*"
