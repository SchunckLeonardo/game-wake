#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck source=server/palworld-common.sh
source /usr/local/lib/palworld/palworld-common.sh

load_palworld_config

skip_save=false
if [[ ${1:-} == "--skip-save" ]]; then
  skip_save=true
fi

exec 9>/var/lib/palworld-monitor/backup.lock
flock -n 9 || {
  palworld_log warning "Backup ja esta em execucao"
  exit 0
}

if [[ $skip_save == false ]] && systemctl is-active --quiet palworld.service; then
  palworld_api POST save '{}' >/dev/null
  sleep 3
fi

timestamp=$(date -u +'%Y%m%dT%H%M%SZ')
archive="/var/backups/palworld/palworld-save-$timestamp.tar.gz"
tar --create --gzip --file "$archive.tmp" --directory /var/lib/palworld saved
mv "$archive.tmp" "$archive"
chown palworld:palworld "$archive"
chmod 0640 "$archive"
find /var/backups/palworld -type f -name 'palworld-save-*.tar.gz' -mtime "+$LOCAL_BACKUP_RETENTION_DAYS" -delete

if [[ -n ${S3_BACKUP_URI:-} ]]; then
  aws s3 cp --only-show-errors "$archive" "$S3_BACKUP_URI/$(basename "$archive")"
fi
palworld_log info "Backup concluido: $archive"
