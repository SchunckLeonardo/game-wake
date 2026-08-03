#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

marker=${1:-}
action=${2:-}
shift "$(( $# >= 2 ? 2 : $# ))"

if [[ ! $marker =~ ^[a-f0-9]{64}$ ]]; then
  echo "invalid operation marker" >&2
  exit 64
fi

runtime_state_dir=/var/lib/gamewake
if [[ -f $runtime_state_dir/bootstrap-failed ]]; then
  echo "GameWake runtime bootstrap failed" >&2
  exit 70
fi
if [[ ! -f $runtime_state_dir/bootstrap-ready ]]; then
  echo "GameWake runtime bootstrap is still running" >&2
  exit 75
fi

operation_dir=/var/lib/gamewake-operations
install -d -o root -g root -m 0700 "$operation_dir"

observe() {
  case "$action" in
    health)
      if systemctl is-active --quiet palworld.service; then
        # shellcheck source=server/palworld-common.sh
        source /usr/local/lib/palworld/palworld-common.sh
        load_palworld_config
        if palworld_api GET info >/dev/null 2>&1; then
          echo healthy
        else
          echo unhealthy
        fi
      else
        echo unhealthy
      fi
      ;;
    player-count)
      # shellcheck source=server/palworld-common.sh
      source /usr/local/lib/palworld/palworld-common.sh
      load_palworld_config
      palworld_player_count
      ;;
    *) return 1 ;;
  esac
}

if [[ $action == health || $action == player-count ]]; then
  observe
  exit 0
fi

result_file="$operation_dir/$marker.result"
exec 9>"$operation_dir/$marker.lock"
flock 9
if [[ -f $result_file ]]; then
  cat "$result_file"
  exit 0
fi

run_mutation() {
  local archive bucket checksum checksum_hex expected_checksum key parameter world_env prefix remote_checksum state_id
  case "$action" in
    apply-configuration)
      [[ $# -eq 3 ]] || return 64
      for parameter in "$1" "$2" "$3"; do
        [[ $parameter =~ ^/[A-Za-z0-9_.\/-]+$ ]] || return 65
      done
      world_env=/etc/palworld/world.env
      {
        printf 'PALWORLD_CONFIG_PARAMETER_NAME=%q\n' "$1"
        printf 'PALWORLD_OVERRIDES_PARAMETER_NAME=%q\n' "${1%/config}/settings-overrides"
        printf 'SERVER_PASSWORD_PARAMETER_NAME=%q\n' "$2"
        printf 'ADMIN_PASSWORD_PARAMETER_NAME=%q\n' "$3"
      } >"$world_env.tmp"
      chown root:palworld "$world_env.tmp"
      chmod 0640 "$world_env.tmp"
      mv "$world_env.tmp" "$world_env"
      /usr/local/sbin/configure-palworld.sh
      ;;
    start)
      [[ $# -eq 0 ]] || return 64
      systemctl start palworld.service
      ;;
    save)
      [[ $# -eq 0 ]] || return 64
      # shellcheck source=server/palworld-common.sh
      source /usr/local/lib/palworld/palworld-common.sh
      load_palworld_config
      palworld_api POST save '{}' >/dev/null
      ;;
    stop)
      [[ $# -eq 0 ]] || return 64
      systemctl stop palworld.service
      ;;
    initialize-state)
      [[ $# -eq 0 ]] || return 64
      install -d -o palworld -g palworld -m 0750 /var/lib/palworld/saved
      ;;
    restore-state)
      [[ $# -eq 3 ]] || return 64
      bucket=$1
      key=$2
      checksum=$3
      [[ $checksum =~ ^sha256:([a-f0-9]{64})$ ]] || return 66
      expected_checksum=${BASH_REMATCH[1]}
      archive=$(mktemp --suffix=.tar.zst)
      trap 'rm -f "${archive:-}"' RETURN
      aws s3 cp --only-show-errors "s3://$bucket/$key" "$archive"
      checksum_hex=$(sha256sum "$archive" | cut -d' ' -f1)
      [[ $checksum_hex == "$expected_checksum" ]] || {
        echo "world state checksum mismatch" >&2
        return 67
      }
      tar --zstd --list --file "$archive" | awk '
        $0 !~ /^saved\// || $0 ~ /(^|\/)\.\.($|\/)/ { exit 1 }
      '
      rm -rf /var/lib/palworld/saved
      install -d -o palworld -g palworld -m 0750 /var/lib/palworld
      tar --zstd --extract --file "$archive" --directory /var/lib/palworld
      chown -R palworld:palworld /var/lib/palworld/saved
      ;;
    persist-state)
      [[ $# -eq 2 ]] || return 64
      bucket=$1
      prefix=$2
      archive=$(mktemp --suffix=.tar.zst)
      trap 'rm -f "${archive:-}"' RETURN
      tar --zstd --create --file "$archive" --directory /var/lib/palworld saved
      checksum_hex=$(sha256sum "$archive" | cut -d' ' -f1)
      state_id=$checksum_hex
      key="${prefix}${state_id}.tar.zst"
      remote_checksum=$(aws s3api put-object \
        --bucket "$bucket" \
        --key "$key" \
        --body "$archive" \
        --checksum-algorithm SHA256 \
        --metadata "sha256=$checksum_hex" \
        --query ChecksumSHA256 \
        --output text)
      [[ -n $remote_checksum && $remote_checksum != None ]] || return 68
      [[ $(aws s3api head-object \
        --bucket "$bucket" \
        --key "$key" \
        --checksum-mode ENABLED \
        --query ChecksumSHA256 \
        --output text) == "$remote_checksum" ]] || return 69
      jq -cn \
        --arg state_id "$state_id" \
        --arg checksum "sha256:$checksum_hex" \
        '{state_id:$state_id,checksum:$checksum,validated:true}'
      ;;
    *)
      echo "unsupported GameWake host action: $action" >&2
      return 64
      ;;
  esac
}

run_mutation "$@" >"$result_file.tmp"
mv "$result_file.tmp" "$result_file"
cat "$result_file"
