#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -f "$project_root/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$project_root/.env"
  set +a
fi

: "${DISCORD_APPLICATION_ID:?Defina DISCORD_APPLICATION_ID no ambiente ou .env}"
: "${DISCORD_GUILD_ID:?Defina DISCORD_GUILD_ID no ambiente ou .env}"
: "${DISCORD_BOT_TOKEN:?Defina DISCORD_BOT_TOKEN no ambiente ou .env}"

api_url="https://discord.com/api/v10/applications/$DISCORD_APPLICATION_ID/guilds/$DISCORD_GUILD_ID/commands"
payload=$(jq -cn '[
  {
    name:"gamewake",
    description:"Jogue com seus amigos sem manter um servidor ligado",
    type:1,
    default_member_permissions:null,
    dm_permission:false,
    options:[
      {type:1,name:"comecar",description:"Cria a conta GameWake deste servidor"},
      {
        type:1,
        name:"convidar",
        description:"Convida até três amigos para a conta GameWake",
        options:[
          {type:6,name:"amigo1",description:"Primeiro amigo",required:true},
          {type:6,name:"amigo2",description:"Segundo amigo",required:false},
          {type:6,name:"amigo3",description:"Terceiro amigo",required:false}
        ]
      },
      {type:1,name:"aceitar",description:"Aceita seu convite pendente para a conta GameWake"},
      {type:1,name:"status",description:"Mostra o estado do seu World"},
      {type:1,name:"acordar",description:"Acorda o World para jogar"},
      {type:1,name:"conectar",description:"Mostra conexão e senha somente para você"},
      {type:1,name:"dormir",description:"Salva o World e inicia o sono seguro"},
      {type:1,name:"configurar",description:"Abre o painel guiado de configurações do World"},
      {type:1,name:"console",description:"Abre a GameWake Console"},
      {type:1,name:"ajuda",description:"Explica os comandos GameWake"}
    ]
  }
]')

response_file=$(mktemp)
curl_config=$(mktemp)
trap 'rm -f "$response_file" "$curl_config"' EXIT
chmod 0600 "$curl_config"
printf 'header = "Authorization: Bot %s"\n' "$DISCORD_BOT_TOKEN" >"$curl_config"
http_status=$(curl --config "$curl_config" \
  --silent \
  --show-error \
  --output "$response_file" \
  --write-out '%{http_code}' \
  --request PUT \
  --header 'Content-Type: application/json' \
  --data "$payload" \
  --url "$api_url")

if [[ $http_status != 2* ]]; then
  printf 'Discord respondeu HTTP %s:\n' "$http_status" >&2
  jq . "$response_file" >&2 || sed -n '1,80p' "$response_file" >&2
  exit 1
fi

jq -r '.[] | "Registrado: /" + .name + " (id=" + .id + ")"' "$response_file"
