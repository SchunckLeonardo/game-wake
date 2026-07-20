#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"

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

common_payload=$(base64 <server/palworld-common.sh | tr -d '\n')
install_command=$(printf '%s' \
  "printf '%s' '$common_payload' | base64 --decode | sudo tee /usr/local/lib/palworld/palworld-common.sh >/dev/null
sudo chown root:root /usr/local/lib/palworld/palworld-common.sh
sudo chmod 0644 /usr/local/lib/palworld/palworld-common.sh")
parameters=$(jq -cn --arg command "$install_command" \
  '{commands:[$command],executionTimeout:["120"]}')
command_id=$(aws ssm send-command \
  --region "$region" \
  --instance-ids "$instance_id" \
  --document-name AWS-RunShellScript \
  --comment 'Update Palworld runtime configuration loader' \
  --parameters "$parameters" \
  --query 'Command.CommandId' \
  --output text)
aws ssm wait command-executed \
  --region "$region" \
  --command-id "$command_id" \
  --instance-id "$instance_id"
printf 'Runtime configuration loader updated (%s).\n' "${command_id:0:8}"

if [[ $started_for_update == true ]]; then
  printf 'Returning the temporarily started server to stopped state through the safe flow...\n'
  shutdown_command='for _ in {1..150}; do
  sudo test -e /run/palworld/ready && break
  sudo systemctl is-active --quiet palworld.service || exit 1
  sleep 2
done
sudo test -e /run/palworld/ready
sudo /usr/local/sbin/stop-palworld.sh --shutdown'
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
