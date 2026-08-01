#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck source=server/palworld-common.sh
source /usr/local/lib/palworld/palworld-common.sh

main_pid=""

if [[ ${1:-} != --service-stop ]]; then
  palworld_log err "A parada deve ser coordenada pelo GameWake"
  exit 64
fi
if [[ ${2:-} =~ ^[0-9]+$ ]]; then
  main_pid=$2
fi

load_palworld_config || palworld_log warning "Configuracao indisponivel durante ExecStop"
palworld_api POST save '{}' >/dev/null 2>&1 || palworld_log warning "Save REST indisponivel durante ExecStop"
if [[ -n "$main_pid" ]] && kill -0 "$main_pid" 2>/dev/null; then
  kill -INT "$main_pid"
  for _ in {1..60}; do
    kill -0 "$main_pid" 2>/dev/null || exit 0
    sleep 1
  done
fi
