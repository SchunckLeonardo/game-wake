#!/usr/bin/env bash
set -Eeuo pipefail

export DEBIAN_FRONTEND=noninteractive
update_only=false
if [[ ${1:-} == "--update-only" ]]; then
  update_only=true
fi

install_server_files() {
  if ! id palworld >/dev/null 2>&1; then
    useradd --system --create-home --home-dir /var/lib/palworld --shell /usr/sbin/nologin palworld
  fi

  install -d -o palworld -g palworld -m 0750 /opt/palworld
  install -d -o palworld -g palworld -m 0750 /var/lib/palworld/saved
  install -d -o palworld -g palworld -m 0750 /var/lib/palworld-monitor
  install -d -o palworld -g palworld -m 0750 /var/backups/palworld
  install -d -o root -g root -m 0700 /var/lib/gamewake-operations
  install -d -o palworld -g palworld -m 0750 /run/palworld
}

install_aws_cli() {
  local aws_path
  local installer_dir
  local -a install_args

  aws_path=$(command -v aws || true)
  if [[ -n "$aws_path" && "$aws_path" != /snap/* ]]; then
    return
  fi

  installer_dir=$(mktemp -d)
  curl --fail --location --silent --show-error \
    https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip \
    --output "$installer_dir/awscliv2.zip"
  unzip -q "$installer_dir/awscliv2.zip" -d "$installer_dir"

  install_args=(--bin-dir /usr/local/bin --install-dir /usr/local/aws-cli)
  [[ -d /usr/local/aws-cli ]] && install_args+=(--update)
  "$installer_dir/aws/install" "${install_args[@]}"
  rm -rf "$installer_dir"
}

install_dependencies() {
  apt-get update
  apt-get install -y --no-install-recommends software-properties-common
  add-apt-repository -y multiverse
  dpkg --add-architecture i386
  apt-get update
  apt-get upgrade -y
  echo steam steam/question select "I AGREE" | debconf-set-selections
  echo steam steam/license note '' | debconf-set-selections
  apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    jq \
    lib32gcc-s1 \
    netcat-openbsd \
    steamcmd \
    tar \
    unzip \
    util-linux \
    zstd

  install_aws_cli
}

update_palworld() {
  local steamcmd=/usr/games/steamcmd
  [[ -x "$steamcmd" ]] || steamcmd=$(command -v steamcmd)
  runuser -u palworld -- "$steamcmd" \
    +force_install_dir /opt/palworld \
    +login anonymous \
    +app_update 2394010 validate \
    +quit
}

migrate_saved_directory() {
  local game_saved=/opt/palworld/Pal/Saved
  local migrated

  install -d -o palworld -g palworld -m 0750 /opt/palworld/Pal
  if [[ -L "$game_saved" ]]; then
    return
  fi
  if [[ -d "$game_saved" ]]; then
    cp -a "$game_saved"/. /var/lib/palworld/saved/
    migrated="${game_saved}.migrated.$(date +%s)"
    mv "$game_saved" "$migrated"
  fi
  ln -s /var/lib/palworld/saved "$game_saved"
  chown -h palworld:palworld "$game_saved"
}

if [[ $update_only == false ]]; then
  install_dependencies
  install_server_files
else
  systemctl is-active --quiet palworld.service && {
    echo "Pare palworld.service com seguranca antes de atualizar." >&2
    exit 1
  }
fi

update_palworld
migrate_saved_directory
chown -R palworld:palworld /opt/palworld /var/lib/palworld /var/lib/palworld-monitor /var/backups/palworld
