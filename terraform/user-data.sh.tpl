#!/usr/bin/env bash
set -Eeuo pipefail

exec > >(tee -a /var/log/palworld-user-data.log | systemd-cat -t palworld-user-data) 2>&1

runtime_state_dir=/var/lib/gamewake
install -d -o root -g root -m 0755 "$runtime_state_dir"
rm -f \
  "$runtime_state_dir/bootstrap-ready" \
  "$runtime_state_dir/bootstrap-failed" \
  "$runtime_state_dir/bootstrap-error"

bootstrap_failed() {
  local exit_code=$?
  local line=$1
  trap - ERR
  printf 'Bootstrap failed at user-data line %s (exit %s)\n' \
    "$line" "$exit_code" >"$runtime_state_dir/bootstrap-error.tmp"
  chmod 0644 "$runtime_state_dir/bootstrap-error.tmp"
  mv "$runtime_state_dir/bootstrap-error.tmp" "$runtime_state_dir/bootstrap-error"
  touch "$runtime_state_dir/bootstrap-failed"
  echo "Bootstrap falhou na linha $line"
  exit "$exit_code"
}
trap 'bootstrap_failed "$LINENO"' ERR

export DEBIAN_FRONTEND=noninteractive

install_payload() {
  local payload=$1
  local destination=$2
  local mode=$3
  install -d -m 0755 "$(dirname "$destination")"
  printf '%s' "$payload" | base64 --decode >"$destination"
  chown root:root "$destination"
  chmod "$mode" "$destination"
}

install -d -m 0755 /usr/local/lib/palworld /usr/local/sbin /etc/palworld /opt/gamewake/bin

install_payload '${common_script_b64}' /usr/local/lib/palworld/palworld-common.sh 0644
install_payload '${render_settings_script_b64}' /usr/local/lib/palworld/render_settings.py 0755
install_payload '${install_script_b64}' /usr/local/sbin/install-palworld.sh 0755
install_payload '${configure_script_b64}' /usr/local/sbin/configure-palworld.sh 0755
install_payload '${start_script_b64}' /usr/local/sbin/start-palworld.sh 0755
install_payload '${stop_script_b64}' /usr/local/sbin/stop-palworld.sh 0755
install_payload '${palworld_service_b64}' /etc/systemd/system/palworld.service 0644
install_payload '${gamewake_operation_script_b64}' /opt/gamewake/bin/gamewake-operation 0755

cat >/etc/palworld/palworld.env <<'ENVIRONMENT'
AWS_REGION=${aws_region}
ENVIRONMENT
chmod 0640 /etc/palworld/palworld.env

/usr/local/sbin/install-palworld.sh

chown root:palworld /etc/palworld/palworld.env
if ! snap list amazon-ssm-agent >/dev/null 2>&1; then
  snap install amazon-ssm-agent --classic
fi
systemctl enable --now snap.amazon-ssm-agent.amazon-ssm-agent.service || \
  systemctl enable --now amazon-ssm-agent.service

systemctl daemon-reload
systemctl enable palworld.service

touch "$runtime_state_dir/bootstrap-ready.tmp"
mv "$runtime_state_dir/bootstrap-ready.tmp" "$runtime_state_dir/bootstrap-ready"
rm -f "$runtime_state_dir/bootstrap-failed" "$runtime_state_dir/bootstrap-error"
echo "Bootstrap Palworld concluido"
