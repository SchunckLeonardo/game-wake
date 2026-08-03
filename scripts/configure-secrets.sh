#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -f "$project_root/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$project_root/.env"
  set +a
fi

parameter_path=${1:-/gamewake/prod}
region=${AWS_REGION:-us-east-1}

: "${DISCORD_CLIENT_SECRET:?Defina DISCORD_CLIENT_SECRET no ambiente ou .env}"
: "${DISCORD_BOT_TOKEN:?Defina DISCORD_BOT_TOKEN no ambiente ou .env}"
: "${ABACATEPAY_API_KEY:?Defina ABACATEPAY_API_KEY no ambiente ou .env}"
: "${ABACATEPAY_WEBHOOK_SECRET:?Defina ABACATEPAY_WEBHOOK_SECRET no ambiente ou .env}"
: "${ABACATEPAY_PUBLIC_KEY:?Defina ABACATEPAY_PUBLIC_KEY no ambiente ou .env}"

if (( ${#ABACATEPAY_PUBLIC_KEY} < 200 )); then
  printf '%s\n' \
    "ABACATEPAY_PUBLIC_KEY invalida: use a chave HMAC publica longa da documentacao de webhooks, nao a chave publica curta da loja." >&2
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

put_secret "$parameter_path/gamewake/discord-client-secret" "$DISCORD_CLIENT_SECRET"
put_secret "$parameter_path/gamewake/discord-bot-token" "$DISCORD_BOT_TOKEN"
put_secret "$parameter_path/gamewake/abacatepay-api-key" "$ABACATEPAY_API_KEY"
put_secret "$parameter_path/gamewake/abacatepay-webhook-secret" "$ABACATEPAY_WEBHOOK_SECRET"
put_secret "$parameter_path/gamewake/abacatepay-public-key" "$ABACATEPAY_PUBLIC_KEY"

echo "Segredos atualizados sem exibir valores."
