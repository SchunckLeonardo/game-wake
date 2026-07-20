#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -f "$project_root/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$project_root/.env"
  set +a
fi

parameter_path=${1:-/palworld-cloud-server/prod}
region=${AWS_REGION:-us-east-1}

: "${DISCORD_WEBHOOK_URL:?Defina DISCORD_WEBHOOK_URL no ambiente ou .env}"
: "${PALWORLD_SERVER_PASSWORD:?Defina PALWORLD_SERVER_PASSWORD no ambiente ou .env}"
: "${PALWORLD_ADMIN_PASSWORD:?Defina PALWORLD_ADMIN_PASSWORD no ambiente ou .env}"

if [[ $PALWORLD_SERVER_PASSWORD == "$PALWORLD_ADMIN_PASSWORD" ]]; then
  echo "As senhas de jogador e administrador devem ser diferentes." >&2
  exit 1
fi
if ((${#PALWORLD_ADMIN_PASSWORD} < 12)); then
  echo "PALWORLD_ADMIN_PASSWORD deve ter pelo menos 12 caracteres." >&2
  exit 1
fi
if [[ $DISCORD_WEBHOOK_URL != https://discord.com/api/webhooks/* && $DISCORD_WEBHOOK_URL != https://discordapp.com/api/webhooks/* ]]; then
  echo "DISCORD_WEBHOOK_URL nao parece um webhook oficial do Discord." >&2
  exit 1
fi

put_secret() {
  local name=$1
  local value=$2
  local request_file
  request_file=$(mktemp)
  chmod 0600 "$request_file"
  jq -n --arg name "$name" --arg value "$value" \
    '{Name:$name,Type:"SecureString",Overwrite:true,Value:$value}' >"$request_file"
  if ! aws ssm put-parameter \
    --region "$region" \
    --cli-input-json "file://$request_file" >/dev/null; then
    rm -f "$request_file"
    return 1
  fi
  rm -f "$request_file"
  printf 'Atualizado: %s\n' "$name"
}

put_secret "$parameter_path/discord/webhook-url" "$DISCORD_WEBHOOK_URL"
put_secret "$parameter_path/palworld/server-password" "$PALWORLD_SERVER_PASSWORD"
put_secret "$parameter_path/palworld/admin-password" "$PALWORLD_ADMIN_PASSWORD"

echo "Segredos atualizados sem exibir valores."
