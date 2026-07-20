#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck source=server/palworld-common.sh
source /usr/local/lib/palworld/palworld-common.sh

load_palworld_config
/usr/local/sbin/configure-palworld.sh
install -d -o palworld -g palworld -m 0750 /run/palworld
rm -f /run/palworld/ready

palworld_log info "Iniciando Palworld em UDP $PALWORLD_PORT"
cd /opt/palworld
exec /opt/palworld/PalServer.sh \
  -port="$PALWORLD_PORT" \
  -useperfthreads \
  -NoAsyncLoadingThread \
  -UseMultithreadForDS
