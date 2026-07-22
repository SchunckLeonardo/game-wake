#!/usr/bin/env bash

PALWORLD_ENV_FILE="${PALWORLD_ENV_FILE:-/etc/palworld/palworld.env}"

if [[ -r "$PALWORLD_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$PALWORLD_ENV_FILE"
fi

palworld_log() {
  local level=$1
  shift
  logger -t palworld-automation -p "user.$level" -- "$*"
  printf '%s [%s] %s\n' "$(date --iso-8601=seconds)" "$level" "$*" >&2
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    palworld_log err "Comando obrigatorio ausente: $1"
    return 1
  }
}

ssm_get_secret() {
  local parameter_name=$1
  local value

  value=$(aws ssm get-parameter \
    --region "$AWS_REGION" \
    --name "$parameter_name" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text)

  if [[ -z "$value" || "$value" == "CHANGE_ME_BEFORE_FIRST_START" ]]; then
    palworld_log err "Parametro seguro ainda nao foi configurado: $parameter_name"
    return 1
  fi
  printf '%s' "$value"
}

load_palworld_config() {
  local config
  local overrides
  local overrides_parameter_name

  config=$(aws ssm get-parameter \
    --region "$AWS_REGION" \
    --name "$PALWORLD_CONFIG_PARAMETER_NAME" \
    --query 'Parameter.Value' \
    --output text)
  jq -e 'type == "object"' >/dev/null <<<"$config"

  overrides_parameter_name=${PALWORLD_OVERRIDES_PARAMETER_NAME:-"${PALWORLD_CONFIG_PARAMETER_NAME%/config}/settings-overrides"}
  if overrides=$(aws ssm get-parameter \
    --region "$AWS_REGION" \
    --name "$overrides_parameter_name" \
    --query 'Parameter.Value' \
    --output text 2>/dev/null); then
    jq -e '
      type == "object" and
      ((keys - [
        "server_name",
        "server_description",
        "max_players",
        "exp_rate",
        "collection_drop_rate",
        "enemy_drop_item_rate",
        "base_camp_worker_max_num",
        "allow_global_palbox_export",
        "allow_global_palbox_import",
        "pal_auto_hp_regen_rate_in_sleep",
        "pal_egg_default_hatching_time",
        "pal_spawn_rate",
        "death_penalty",
        "pal_damage_attack_rate",
        "pal_damage_defense_rate",
        "player_damage_attack_rate",
        "player_damage_defense_rate",
        "pal_stamina_decrease_rate",
        "player_stamina_decrease_rate",
        "item_weight_rate"
      ]) | length) == 0 and
      ((.server_name // "valid") | type == "string" and length > 0 and length <= 100) and
      ((.server_description // "") | type == "string" and length <= 500) and
      ((.max_players // 1) | type == "number" and . >= 1 and floor == .) and
      ([.base_camp_worker_max_num?] |
        all(. == null or (type == "number" and . >= 1 and . <= 50 and floor == .))) and
      ([
        .allow_global_palbox_export?,
        .allow_global_palbox_import?
      ] | all(. == null or type == "boolean")) and
      ([
        .exp_rate?,
        .collection_drop_rate?,
        .enemy_drop_item_rate?,
        .pal_auto_hp_regen_rate_in_sleep?,
        .pal_spawn_rate?,
        .pal_damage_attack_rate?,
        .pal_damage_defense_rate?,
        .player_damage_attack_rate?,
        .player_damage_defense_rate?,
        .pal_stamina_decrease_rate?,
        .player_stamina_decrease_rate?,
        .item_weight_rate?
      ] | all(. == null or (type == "number" and . > 0))) and
      ([.pal_egg_default_hatching_time?] |
        all(. == null or (type == "number" and . >= 0))) and
      ((.death_penalty // "Item") as $death |
        ["None", "Item", "ItemAndEquipment", "All"] | index($death) != null)
    ' >/dev/null <<<"$overrides" || {
      palworld_log err "Overrides do Discord contem configuracoes invalidas ou desconhecidas"
      return 1
    }
    config=$(jq -ce --argjson overrides "$overrides" '. * $overrides' <<<"$config")
  else
    palworld_log warning "Overrides do Discord indisponiveis; usando configuracao base"
  fi

  PALWORLD_SERVER_NAME=$(jq -er '.server_name | strings' <<<"$config")
  PALWORLD_SERVER_DESCRIPTION=$(jq -er '.server_description | strings' <<<"$config")
  PALWORLD_PORT=$(jq -er '.port | numbers' <<<"$config")
  PALWORLD_MAX_PLAYERS=$(jq -er '.max_players | numbers' <<<"$config")
  EXP_RATE=$(jq -er '.exp_rate | numbers' <<<"$config")
  COLLECTION_DROP_RATE=$(jq -er '.collection_drop_rate | numbers' <<<"$config")
  ENEMY_DROP_ITEM_RATE=$(jq -er '.enemy_drop_item_rate | numbers' <<<"$config")
  BASE_CAMP_WORKER_MAX_NUM=$(jq -er '.base_camp_worker_max_num | numbers' <<<"$config")
  ALLOW_GLOBAL_PALBOX_EXPORT=$(jq -r '
    .allow_global_palbox_export |
    if type == "boolean" then . else error("expected boolean") end
  ' <<<"$config")
  ALLOW_GLOBAL_PALBOX_IMPORT=$(jq -r '
    .allow_global_palbox_import |
    if type == "boolean" then . else error("expected boolean") end
  ' <<<"$config")
  PAL_AUTO_HP_REGEN_RATE_IN_SLEEP=$(jq -er \
    '.pal_auto_hp_regen_rate_in_sleep | numbers' <<<"$config")
  PAL_EGG_DEFAULT_HATCHING_TIME=$(jq -er \
    '.pal_egg_default_hatching_time | numbers' <<<"$config")
  PAL_SPAWN_RATE=$(jq -er '.pal_spawn_rate | numbers' <<<"$config")
  DEATH_PENALTY=$(jq -er '.death_penalty | strings' <<<"$config")
  PAL_DAMAGE_ATTACK_RATE=$(jq -er '.pal_damage_attack_rate | numbers' <<<"$config")
  PAL_DAMAGE_DEFENSE_RATE=$(jq -er '.pal_damage_defense_rate | numbers' <<<"$config")
  PLAYER_DAMAGE_ATTACK_RATE=$(jq -er '.player_damage_attack_rate | numbers' <<<"$config")
  PLAYER_DAMAGE_DEFENSE_RATE=$(jq -er '.player_damage_defense_rate | numbers' <<<"$config")
  PAL_STAMINA_DECREASE_RATE=$(jq -er '.pal_stamina_decrease_rate | numbers' <<<"$config")
  PLAYER_STAMINA_DECREASE_RATE=$(jq -er '.player_stamina_decrease_rate | numbers' <<<"$config")
  ITEM_WEIGHT_RATE=$(jq -er '.item_weight_rate | numbers' <<<"$config")
  REST_API_PORT=$(jq -er '.rest_api_port | numbers' <<<"$config")
  REST_API_USERNAME=$(jq -er '.rest_api_username | strings' <<<"$config")
  AUTOSTOP_CHECK_MINUTES=$(jq -er '.autostop_check_minutes | numbers' <<<"$config")
  AUTOSTOP_IDLE_MINUTES=$(jq -er '.autostop_idle_minutes | numbers' <<<"$config")
  HEALTHCHECK_TIMEOUT_MINUTES=$(jq -er '.healthcheck_timeout_minutes | numbers' <<<"$config")
  LOCAL_BACKUP_RETENTION_DAYS=$(jq -er '.local_backup_retention_days | numbers' <<<"$config")
  S3_BACKUP_URI=$(jq -er '.s3_backup_uri | strings' <<<"$config")

  export PALWORLD_SERVER_NAME PALWORLD_SERVER_DESCRIPTION PALWORLD_PORT
  export PALWORLD_MAX_PLAYERS EXP_RATE COLLECTION_DROP_RATE ENEMY_DROP_ITEM_RATE
  export BASE_CAMP_WORKER_MAX_NUM ALLOW_GLOBAL_PALBOX_EXPORT ALLOW_GLOBAL_PALBOX_IMPORT
  export PAL_AUTO_HP_REGEN_RATE_IN_SLEEP PAL_EGG_DEFAULT_HATCHING_TIME
  export PAL_SPAWN_RATE DEATH_PENALTY
  export PAL_DAMAGE_ATTACK_RATE PAL_DAMAGE_DEFENSE_RATE PLAYER_DAMAGE_ATTACK_RATE
  export PLAYER_DAMAGE_DEFENSE_RATE PAL_STAMINA_DECREASE_RATE
  export PLAYER_STAMINA_DECREASE_RATE ITEM_WEIGHT_RATE REST_API_PORT REST_API_USERNAME
  export AUTOSTOP_CHECK_MINUTES AUTOSTOP_IDLE_MINUTES HEALTHCHECK_TIMEOUT_MINUTES
  export LOCAL_BACKUP_RETENTION_DAYS S3_BACKUP_URI
}

palworld_api() {
  local method=$1
  local endpoint=$2
  local body=${3:-}
  local admin_password
  local basic_auth
  local -a curl_args

  admin_password=$(ssm_get_secret "$ADMIN_PASSWORD_PARAMETER_NAME") || return 1
  basic_auth=$(printf '%s:%s' "$REST_API_USERNAME" "$admin_password" | base64 --wrap=0)
  curl_args=(
    --silent
    --show-error
    --fail-with-body
    --connect-timeout 2
    --max-time 8
    --request "$method"
    --header "Accept: application/json"
  )
  if [[ -n "$body" ]]; then
    curl_args+=(--header "Content-Type: application/json" --data "$body")
  fi
  printf 'header = "Authorization: Basic %s"\nurl = "http://127.0.0.1:%s/v1/api/%s"\n' \
    "$basic_auth" "$REST_API_PORT" "$endpoint" | curl --config - "${curl_args[@]}"
}

palworld_player_count() {
  local response
  local count

  response=$(palworld_api GET players) || return 1
  count=$(jq -er '.players | if type == "array" then length else error("players is not an array") end' <<<"$response") || return 1
  [[ "$count" =~ ^[0-9]+$ ]] || return 1
  printf '%s' "$count"
}

publish_status() {
  local service_state=$1
  local players=${2:-null}
  local detail=${3:-}
  local payload

  if [[ ! "$players" =~ ^[0-9]+$ ]]; then
    players=null
  fi
  payload=$(jq -cn \
    --arg service_state "$service_state" \
    --argjson players "$players" \
    --arg detail "$detail" \
    --arg updated_at "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    '{service_state:$service_state,players:$players,detail:$detail,updated_at:$updated_at}')

  aws ssm put-parameter \
    --region "$AWS_REGION" \
    --name "$STATUS_PARAMETER_NAME" \
    --type String \
    --overwrite \
    --value "$payload" >/dev/null
}

discord_webhook_send() {
  local message=$1
  local webhook_url
  local payload

  webhook_url=$(ssm_get_secret "$DISCORD_WEBHOOK_PARAMETER_NAME") || return 1
  payload=$(jq -cn --arg content "$message" '{content:$content,allowed_mentions:{parse:[]}}')
  printf 'url = "%s"\n' "$webhook_url" | curl --config - \
    --silent \
    --show-error \
    --fail-with-body \
    --connect-timeout 3 \
    --max-time 10 \
    --header "Content-Type: application/json" \
    --data "$payload" >/dev/null
}

current_public_ipv4() {
  local token
  token=$(curl \
    --silent \
    --show-error \
    --fail \
    --connect-timeout 1 \
    --max-time 2 \
    --request PUT \
    --header "X-aws-ec2-metadata-token-ttl-seconds: 60" \
    --url "http://169.254.169.254/latest/api/token") || return 1
  curl \
    --silent \
    --show-error \
    --fail \
    --connect-timeout 1 \
    --max-time 2 \
    --header "X-aws-ec2-metadata-token: $token" \
    --url "http://169.254.169.254/latest/meta-data/public-ipv4"
}
