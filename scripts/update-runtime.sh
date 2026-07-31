#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"

activate=false
case ${1:-} in
  "") ;;
  --activate) activate=true ;;
  *)
    printf 'Usage: %s [--activate]\n' "$0" >&2
    exit 64
    ;;
esac

ssm_bash_command() {
  local script=$1
  local payload

  payload=$(printf '%s' "$script" | base64 | tr -d '\n')
  printf "printf '%%s' '%s' | base64 --decode | sudo bash" "$payload"
}

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

region=${AWS_REGION:-$(terraform -chdir=terraform output -raw aws_region)}
instance_id=$(terraform -chdir=terraform output -raw instance_id)
original_state=$(aws ec2 describe-instances \
  --region "$region" \
  --instance-ids "$instance_id" \
  --query 'Reservations[0].Instances[0].State.Name' \
  --output text)

started_for_update=false
if [[ $original_state == stopped ]]; then
  printf 'Starting %s temporarily to update its runtime scripts...\n' "$instance_id"
  aws ec2 start-instances --region "$region" --instance-ids "$instance_id" >/dev/null
  aws ec2 wait instance-running --region "$region" --instance-ids "$instance_id"
  started_for_update=true
elif [[ $original_state != running ]]; then
  printf 'Instance %s is %s; wait for a stable state before updating.\n' \
    "$instance_id" "$original_state" >&2
  exit 1
fi

printf 'Waiting for Systems Manager...\n'
ssm_online=false
for _ in {1..60}; do
  ping_status=$(aws ssm describe-instance-information \
    --region "$region" \
    --filters "Key=InstanceIds,Values=$instance_id" \
    --query 'InstanceInformationList[0].PingStatus' \
    --output text 2>/dev/null || true)
  if [[ $ping_status == Online ]]; then
    ssm_online=true
    break
  fi
  sleep 3
done
if [[ $ssm_online != true ]]; then
  printf 'Systems Manager did not become available for %s.\n' "$instance_id" >&2
  exit 1
fi

runtime_sources=(
  server/palworld-common.sh
  server/render_settings.py
  server/install-palworld.sh
  server/configure-palworld.sh
  server/start-palworld.sh
  server/stop-palworld.sh
  server/backup-palworld.sh
  server/autostop.sh
  server/notify-discord.sh
  server/healthcheck.sh
  server/gamewake-operation.sh
  server/palworld.service
  server/palworld-notify.service
  server/palworld-autostop.service
  server/palworld-autostop.timer
  server/palworld-backup.service
  server/palworld-backup.timer
)
runtime_archive=$(mktemp)
trap 'rm -f "$runtime_archive"' EXIT
tar -czf "$runtime_archive" "${runtime_sources[@]}"
runtime_payload=$(base64 <"$runtime_archive" | tr -d '\n')
# shellcheck disable=SC2016 # $runtime_dir expands on the remote host.
install_script=$(printf '%s\n' \
  'set -Eeuo pipefail' \
  'runtime_dir=$(mktemp -d)' \
  'trap '\''rm -rf "$runtime_dir"'\'' EXIT' \
  "printf '%s' '$runtime_payload' | base64 --decode | tar -xz -C \"\$runtime_dir\"" \
  'install -d -m 0755 /usr/local/lib/palworld /usr/local/sbin /opt/gamewake/bin' \
  'install -m 0644 "$runtime_dir/server/palworld-common.sh" /usr/local/lib/palworld/palworld-common.sh' \
  'install -m 0755 "$runtime_dir/server/render_settings.py" /usr/local/lib/palworld/render_settings.py' \
  'install -m 0755 "$runtime_dir/server/install-palworld.sh" /usr/local/sbin/install-palworld.sh' \
  'install -m 0755 "$runtime_dir/server/configure-palworld.sh" /usr/local/sbin/configure-palworld.sh' \
  'install -m 0755 "$runtime_dir/server/start-palworld.sh" /usr/local/sbin/start-palworld.sh' \
  'install -m 0755 "$runtime_dir/server/stop-palworld.sh" /usr/local/sbin/stop-palworld.sh' \
  'install -m 0755 "$runtime_dir/server/backup-palworld.sh" /usr/local/sbin/backup-palworld.sh' \
  'install -m 0755 "$runtime_dir/server/autostop.sh" /usr/local/sbin/autostop.sh' \
  'install -m 0755 "$runtime_dir/server/notify-discord.sh" /usr/local/sbin/notify-discord.sh' \
  'install -m 0755 "$runtime_dir/server/healthcheck.sh" /usr/local/sbin/healthcheck.sh' \
  'install -m 0755 "$runtime_dir/server/gamewake-operation.sh" /opt/gamewake/bin/gamewake-operation' \
  'install -m 0644 "$runtime_dir/server/palworld.service" /etc/systemd/system/palworld.service' \
  'install -m 0644 "$runtime_dir/server/palworld-notify.service" /etc/systemd/system/palworld-notify.service' \
  'install -m 0644 "$runtime_dir/server/palworld-autostop.service" /etc/systemd/system/palworld-autostop.service' \
  'install -m 0644 "$runtime_dir/server/palworld-autostop.timer" /etc/systemd/system/palworld-autostop.timer' \
  'install -m 0644 "$runtime_dir/server/palworld-backup.service" /etc/systemd/system/palworld-backup.service' \
  'install -m 0644 "$runtime_dir/server/palworld-backup.timer" /etc/systemd/system/palworld-backup.timer' \
  'chown root:root /usr/local/lib/palworld/palworld-common.sh /usr/local/lib/palworld/render_settings.py' \
  'chown root:root /usr/local/sbin/{install,configure,start,stop,backup}-palworld.sh' \
  'chown root:root /usr/local/sbin/{autostop,notify-discord,healthcheck}.sh' \
  'chown root:root /opt/gamewake/bin/gamewake-operation' \
  'chown root:root /etc/systemd/system/palworld*.service /etc/systemd/system/palworld*.timer' \
  'systemctl daemon-reload')
install_command=$(ssm_bash_command "$install_script")
parameters=$(jq -cn --arg command "$install_command" \
  '{commands:[$command],executionTimeout:["120"]}')
command_id=$(aws ssm send-command \
  --region "$region" \
  --instance-ids "$instance_id" \
  --document-name AWS-RunShellScript \
  --comment 'Update Palworld runtime files' \
  --parameters "$parameters" \
  --query 'Command.CommandId' \
  --output text)
if ! aws ssm wait command-executed \
  --region "$region" \
  --command-id "$command_id" \
  --instance-id "$instance_id"; then
  aws ssm get-command-invocation \
    --region "$region" \
    --command-id "$command_id" \
    --instance-id "$instance_id" \
    --query '{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}' \
    --output json >&2 || true
  exit 2
fi
printf 'Palworld runtime files updated (%s).\n' "${command_id:0:8}"

if [[ $started_for_update == false && $activate == true ]]; then
  activation_script='set -Eeuo pipefail
/usr/local/sbin/stop-palworld.sh
systemctl start palworld.service
systemctl restart palworld-notify.service'
  activation_command=$(ssm_bash_command "$activation_script")
  activation_parameters=$(jq -cn --arg command "$activation_command" \
    '{commands:[$command],executionTimeout:["360"]}')
  activation_id=$(aws ssm send-command \
    --region "$region" \
    --instance-ids "$instance_id" \
    --document-name AWS-RunShellScript \
    --comment 'Activate updated Palworld runtime and settings' \
    --parameters "$activation_parameters" \
    --query 'Command.CommandId' \
    --output text)
  if ! aws ssm wait command-executed \
    --region "$region" \
    --command-id "$activation_id" \
    --instance-id "$instance_id"; then
    aws ssm get-command-invocation \
      --region "$region" \
      --command-id "$activation_id" \
      --instance-id "$instance_id" \
      --query '{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}' \
      --output json >&2 || true
    exit 2
  fi
  printf 'Updated runtime and settings activated safely (%s).\n' "${activation_id:0:8}"
elif [[ $started_for_update == false ]]; then
  printf 'Runtime updated. Use --activate to restart safely now, or wait for the next start.\n'
fi

if [[ $started_for_update == true ]]; then
  printf 'Returning the temporarily started server to stopped state through the safe flow...\n'
  shutdown_script='set -Eeuo pipefail
for _ in {1..150}; do
  sudo test -e /run/palworld/ready && break
  sudo systemctl is-active --quiet palworld.service || exit 1
  sleep 2
done
sudo test -e /run/palworld/ready
sudo /usr/local/sbin/stop-palworld.sh --shutdown'
  shutdown_command=$(ssm_bash_command "$shutdown_script")
  shutdown_parameters=$(jq -cn --arg command "$shutdown_command" \
    '{commands:[$command],executionTimeout:["360"]}')
  shutdown_id=$(aws ssm send-command \
    --region "$region" \
    --instance-ids "$instance_id" \
    --document-name AWS-RunShellScript \
    --comment 'Return Palworld instance to its original stopped state' \
    --parameters "$shutdown_parameters" \
    --query 'Command.CommandId' \
    --output text)
  shutdown_complete=false
  terminal_failure=false
  for _ in {1..120}; do
    current_state=$(aws ec2 describe-instances \
      --region "$region" \
      --instance-ids "$instance_id" \
      --query 'Reservations[0].Instances[0].State.Name' \
      --output text)
    if [[ $current_state == stopped ]]; then
      shutdown_complete=true
      break
    fi
    invocation_status=$(aws ssm get-command-invocation \
      --region "$region" \
      --command-id "$shutdown_id" \
      --instance-id "$instance_id" \
      --query Status \
      --output text 2>/dev/null || true)
    if [[ $invocation_status =~ ^(Cancelled|Failed|TimedOut)$ ]]; then
      if [[ $terminal_failure == true ]]; then
        break
      fi
      terminal_failure=true
      sleep 10
      continue
    fi
    if [[ $terminal_failure == true ]]; then
      break
    fi
    sleep 3
  done
  if [[ $shutdown_complete != true ]]; then
    aws ssm get-command-invocation \
      --region "$region" \
      --command-id "$shutdown_id" \
      --instance-id "$instance_id" \
      --query '{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}' \
      --output json >&2 || true
    printf 'Safe shutdown did not complete. The instance was left running; check players and logs.\n' >&2
    exit 2
  fi
fi
