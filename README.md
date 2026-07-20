# palworld-cloud-server

An on-demand Palworld dedicated server on AWS, controlled through Discord slash commands. The EC2
instance starts only when an authorized user requests it, publishes its dynamic public address when
the game is ready, and shuts down with a save and backup after remaining empty.

The project uses Terraform, EC2 On-Demand, Lambda Function URL, Systems Manager Parameter Store,
Session Manager, CloudWatch Logs, Python 3.12, Bash, systemd, SteamCMD, and GitHub Actions. There is
no permanently running bot, container, API Gateway, NAT Gateway, Elastic IP, Load Balancer, or open
SSH port by default.

> This repository creates billable infrastructure. It never runs `terraform apply` or
> `terraform destroy` automatically after a push. Always review the saved plan.

## What is implemented

- `/palworld ligar`, `/palworld status`, `/palworld desligar`, and `/palworld ajuda` commands in
  Portuguese;
- Ed25519 verification over the timestamp and raw HTTP body before parsing JSON;
- allowlists by Discord Guild ID and by user or role;
- Discord `PING` support and short initial Lambda responses;
- one-EC2 control with explicit handling for `pending`, `running`, `stopping`, `stopped`,
  `shutting-down`, and `terminated`;
- Ubuntu Server 24.04 LTS x86-64 obtained through Canonical's public parameter;
- configurable defaults of `m6a.xlarge`, 50 GiB `gp3`, and `us-east-1`;
- required IMDSv2, encrypted EBS, instance shutdown behavior `stop`, and an ephemeral public IP;
- automatic SteamCMD and Palworld App ID `2394010` installation without running the game as root;
- no inbound rule for the REST API or RCON; only UDP 8211 is open;
- health checks, webhook notifications, secret-free telemetry, fail-safe autostop, and backups;
- optional private, encrypted, versioned S3 storage with lifecycle rules, disabled by default;
- Session Manager administration without depending on SSH;
- an interactive `./palworld settings` assistant for server and gameplay configuration;
- Python tests, Ruff, ShellCheck, Terraform fmt/validate, and OIDC GitHub Actions workflows.

## Architecture

Command flow:

```text
Authorized player
        ↓
Discord Slash Command
        ↓ HTTPS + Ed25519 signature
Lambda Function URL (AuthType NONE)
        ↓
AWS Lambda Python 3.12
        ├── Describe/Start the single EC2 instance
        ├── read runtime status from Parameter Store
        └── SSM Run Command for safe shutdown
                ↓
EC2 Ubuntu 24.04 + systemd + Palworld
```

Boot flow:

```text
Discord /palworld ligar
        ↓
EC2 stopped → pending → running with a new public IP
        ↓
palworld.service reads configuration and SecureStrings from Parameter Store
        ↓
PalServer.sh -port=8211
        ↓
health check queries the REST API at 127.0.0.1:8212
        ↓
webhook publishes the formatted public address
```

Autostop flow:

```text
systemd timer
        ↓ every 5 minutes by default
GET /v1/api/players on localhost
        ├── players > 0 → reset idle counter
        ├── error/timeout/401 → keep counter unchanged and do not shut down
        └── zero players for 20 minutes
                    ↓
              announcement → save → backup → Palworld shutdown
                    ↓
              systemctl poweroff
                    ↓
              EC2 becomes stopped, never terminated
```

The snapshot stored at `/<project>/<environment>/runtime/status` contains no password, player IP,
or other personal data. Lambda only uses it to enrich `/status` and provide a quick warning. The
script running on EC2 always checks the connected players again immediately before shutdown.

## Security decisions

1. The Function URL must be public (`AuthType=NONE`) because Discord does not use AWS SigV4. The
   application authenticates every interaction with `X-Signature-Ed25519`,
   `X-Signature-Timestamp`, and the original body. Invalid requests receive HTTP 401.
2. The Security Group opens only the UDP game port. The REST API on 8212 is not exposed, RCON is
   disabled, and SSH is closed.
3. The server password, administrator password, and webhook are `SecureString` parameters.
   Terraform creates only write-only placeholders using `value_wo`. Neither the placeholder nor
   later CLI updates are persisted as values in Terraform state.
4. Lambda can start or stop only the instance created by this stack and can run only
   `AWS-RunShellScript` on it. `DescribeInstances` and `GetCommandInvocation` require
   `Resource: "*"` because those actions do not support resource-level permissions; the policy
   limits the Region through conditions.
5. `forcar:true` requires the Discord Administrator permission bit. Without `forcar`, an error from
   the REST API, save, or backup cancels shutdown.
6. Empty `allowed_user_ids` and `allowed_role_ids` deny everyone by default.
7. EC2 uses an Instance Profile. No AWS access key is stored on disk.
8. Gameplay settings contain no secrets and live in a local, Git-ignored JSON document. Secrets
   remain separate in Parameter Store.

## Repository layout

```text
.
├── README.md
├── Makefile
├── pyproject.toml
├── palworld                       # repository command-line interface
├── .env.example
├── config/
│   └── palworld-settings.json.example
├── terraform/
│   ├── versions.tf               # pinned Terraform/provider and local backend
│   ├── provider.tf               # provider, tags, and configuration payloads
│   ├── variables.tf              # infrastructure types, defaults, and validations
│   ├── terraform.tfvars.example
│   ├── network.tf
│   ├── security-group.tf
│   ├── parameter-store.tf
│   ├── iam.tf
│   ├── ec2.tf
│   ├── lambda.tf
│   ├── cloudwatch.tf
│   ├── backup.tf
│   ├── outputs.tf
│   └── user-data.sh.tpl
├── lambda/
│   ├── handler.py
│   ├── discord_signature.py
│   ├── config_service.py
│   ├── ec2_service.py
│   ├── response_service.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── tests/
├── server/
│   ├── palworld-common.sh
│   ├── render_settings.py        # preserves installed official defaults
│   ├── install-palworld.sh
│   ├── configure-palworld.sh
│   ├── start-palworld.sh
│   ├── stop-palworld.sh
│   ├── backup-palworld.sh
│   ├── autostop.sh
│   ├── notify-discord.sh
│   ├── healthcheck.sh
│   └── *.service / *.timer
├── scripts/
│   ├── palworld_settings.py
│   ├── package-lambda.sh
│   ├── register-discord-commands.sh
│   ├── configure-secrets.sh
│   ├── deploy.sh
│   ├── destroy.sh
│   └── validate.sh
├── docs/research/official-platform-facts.md
└── .github/workflows/
    ├── tests.yml
    ├── terraform-plan.yml
    └── terraform-apply.yml
```

## Prerequisites

- an AWS account allowed to create VPC, EC2, IAM Role/Instance Profile, Lambda, SSM Parameters,
  CloudWatch Log Groups, and optionally S3;
- a Discord application and guild that you administer;
- an authenticated AWS CLI v2, preferably through IAM Identity Center/SSO;
- Terraform 1.11.x;
- Python 3.12, `pip`, `zip`, `jq`, `curl`, `shellcheck`, and `make`;
- Git and an x86-64 or arm64 development machine. The packager downloads Linux x86-64 wheels for
  Lambda.

Check your environment:

```bash
aws --version
terraform version
python3.12 --version
jq --version
shellcheck --version
aws sts get-caller-identity
```

### Install the AWS CLI

Follow the official
[AWS CLI v2 installation guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
Use SSO when your account provides IAM Identity Center:

```bash
aws configure sso
aws sso login --profile YOUR_PROFILE
export AWS_PROFILE=YOUR_PROFILE
export AWS_REGION=us-east-1
aws sts get-caller-identity
```

For a personal account without SSO, `aws configure` works, but use a dedicated user or role with MFA
and least privilege. Do not place access keys in the repository or GitHub Secrets when OIDC is
available.

### Install Terraform

Use the official HashiCorp package. On macOS:

```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
terraform version
```

On Linux, follow [Install Terraform](https://developer.hashicorp.com/terraform/install). The AWS
provider is pinned to `6.53.0` and the lockfile should remain versioned.

## AWS Free Plan, Paid Plan, and credits

`m6a.xlarge` provides 4 vCPUs and 16 GiB, a reasonable baseline for this small group, but it is not
currently listed as an EC2 Free Tier eligible type. New AWS Free account plan accounts might not
have access to it. If necessary, manually upgrade to the Paid account plan under **Billing and Cost
Management → Account → AWS Free Tier plan**.

According to the current AWS documentation, a manual upgrade preserves remaining credits and
applies them to eligible bills until expiration. Exceptions exist: joining AWS Organizations or
Control Tower can cause credits to expire, and older accounts follow legacy rules. Confirm the
conditions in Billing before upgrading. A Paid Plan means usage beyond credits is billable.

Sources: [Choosing an AWS Free Tier plan](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html),
[Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/), and
[EC2 Free Tier usage](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html).

## Create and configure the Discord application

### 1. Create the application and obtain its Application ID and Public Key

1. Open the [Discord Developer Portal](https://discord.com/developers/applications).
2. Select **New Application**, choose a name, and confirm.
3. Under **General Information**, copy:
   - **Application ID** → `discord_application_id` and `DISCORD_APPLICATION_ID`;
   - **Public Key** → `discord_public_key`.
4. The Public Key is not a secret. The Bot Token and webhook URL are secrets.

### 2. Create the bot and obtain its token

1. Open **Bot** and select **Add Bot**, if necessary.
2. Under **Token**, generate or reset the token and copy it once.
3. Store it only in the local `.env` file as `DISCORD_BOT_TOKEN`.
4. Message Content Intent and a permanently online bot process are not required. The token is used
   only to register commands through the Discord API.

### 3. Install the application in the guild

Under **Installation** or **OAuth2 → URL Generator**:

1. select the `applications.commands` and `bot` scopes;
2. grant only the minimum bot permissions you want; HTTP commands do not require Administrator;
3. open the generated URL and select your guild.

### 4. Obtain Guild, User, and Role IDs

In Discord, open **User Settings → Advanced → Developer Mode**. Then:

- right-click the server and select **Copy Server ID**;
- right-click a user and select **Copy User ID**;
- under Server Settings → Roles, right-click the role and select **Copy Role ID**.

Configure at least one user or role. Lambda also requires the interaction to originate from exactly
the configured guild.

### 5. Create the webhook

In the guild, open the channel that should receive notifications:

1. **Edit Channel → Integrations → Webhooks → New Webhook**;
2. choose the channel, name the webhook, and copy the URL;
3. store it in `.env` as `DISCORD_WEBHOOK_URL`.

A webhook belongs to one fixed channel. To make “the address will be sent in this channel” literal,
use the commands in that same channel. The project does not persist 15-minute interaction tokens.

## Local configuration

Create the local files ignored by Git:

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
cp .env.example .env
./palworld settings
chmod 600 .env terraform/terraform.tfvars config/palworld-settings.json
```

The first `./palworld settings` invocation copies
`config/palworld-settings.json.example` to `config/palworld-settings.json` and opens the interactive
assistant. Existing clones are upgraded automatically: supported gameplay values still present in
`terraform/terraform.tfvars` are imported only when the local JSON file is first created.

Edit `terraform/terraform.tfvars` and configure at least:

```hcl
discord_application_id = "YOUR_APPLICATION_ID"
discord_public_key      = "YOUR_64_CHARACTER_HEX_PUBLIC_KEY"
discord_guild_id        = "YOUR_GUILD_ID"

discord_allowed_user_ids = ["YOUR_USER_ID"]
discord_allowed_role_ids = ["OPTIONAL_ROLE_ID"]
```

Edit `.env`:

```dotenv
DISCORD_APPLICATION_ID=...
DISCORD_GUILD_ID=...
DISCORD_BOT_TOKEN=...
AWS_PROFILE=...
AWS_REGION=us-east-1
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
PALWORLD_SERVER_PASSWORD=...
PALWORLD_ADMIN_PASSWORD=...
```

The two passwords must differ. The configuration script requires at least 12 characters for the
administrator password. Neither password belongs in `terraform.tfvars` or
`config/palworld-settings.json`.

### Main infrastructure variables

| Variable | Default | Effect |
|---|---:|---|
| `aws_region` | `us-east-1` | Region for every resource |
| `instance_type` | `m6a.xlarge` | On-Demand x86-64 instance type |
| `root_volume_size_gib` | `50` | Encrypted gp3 root volume |
| `root_volume_delete_on_termination` | `true` | Delete the volume when EC2 is destroyed |
| `enable_termination_protection` | `false` | Optional terminate protection |
| `palworld_port` | `8211` | Real listener passed to `PalServer.sh -port` |
| `palworld_allowed_cidr` | `0.0.0.0/0` | Allowed UDP source; restrict it when possible |
| `autostop_check_minutes` | `5` | Effective player-query frequency |
| `autostop_idle_minutes` | `20` | Empty time before shutdown |
| `enable_s3_backup` | `false` | Create the optional private bucket |
| `cloudwatch_log_retention_days` | `7` | Lambda log retention |
| `lambda_memory_size_mb` | `512` | Memory and CPU for the Discord response deadline |
| `lambda_reserved_concurrent_executions` | `-1` | Use unreserved concurrency |
| `stop_after_initial_bootstrap` | `true` | Schedule a stop after the first bootstrap |

The timer wakes every minute, but the script honors `autostop_check_minutes` before querying the
API. This allows the interval to change through Terraform without rewriting the systemd unit.

## Configure `PalWorldSettings.ini` with the assistant

Run:

```bash
./palworld settings
```

The assistant groups the supported settings into **Server**, **Gameplay**, **Damage**, and
**Stamina and inventory**. Press Enter to keep a value, review the diff, and confirm before saving.

Useful non-interactive commands:

```bash
./palworld settings show
./palworld settings validate
./palworld settings plan
./palworld settings apply
```

- `show` prints the current values with friendly labels.
- `validate` checks the schema, required keys, numeric values, and `DeathPenalty`.
- `plan` validates the document and generates the normal saved Terraform plan.
- `apply` runs the reviewed Terraform flow and then:
  - if EC2 is stopped, leaves the configuration ready for the next start;
  - if EC2 is running, sends a safe SSM activation command;
  - if players are connected or the player query fails, does not stop the game and leaves the
    change pending for the next safe start.

To publish a change without restarting a running server:

```bash
./palworld settings apply --activate next-start
```

The local file is the single editing interface for gameplay values. Terraform converts it to the
non-secret `/<project>/<environment>/palworld/config` parameter. Every service start regenerates the
effective `PalWorldSettings.ini` from the installed official default.

Do not place `ServerPassword` or `AdminPassword` in the JSON document. The assistant rejects unknown
fields, while the passwords continue to be read independently from `SecureString` parameters.

### Official gameplay settings currently exposed

| Assistant label | Official INI key |
|---|---|
| Server name | `ServerName` |
| Server description | `ServerDescription` |
| Maximum players | `ServerPlayerMaxNum` |
| Experience rate | `ExpRate` |
| Collection drop rate | `CollectionDropRate` |
| Pal spawn rate | `PalSpawnNumRate` |
| Death penalty | `DeathPenalty` |
| Pal attack/received damage | `PalDamageRateAttack` / `PalDamageRateDefense` |
| Player attack/received damage | `PlayerDamageRateAttack` / `PlayerDamageRateDefense` |
| Pal/player stamina depletion | `PalStaminaDecreaceRate` / `PlayerStaminaDecreaceRate` |
| Item weight rate | `ItemWeightRate` |

`DeathPenalty` accepts `None`, `Item`, `ItemAndEquipment`, or `All`. The official spelling really is
`Decreace`. High `PalSpawnNumRate` values can affect performance.

The project also enforces `bAllowEnhanceStat_Stamina=True`,
`bAllowEnhanceStat_Weight=True`, `bIsUseBackupSaveData=True`, `RESTAPIEnabled=True`,
`RCONEnabled=False`, and the private REST API port. `PublicPort` is written to the INI but does not
change the listener; the real port is the `-port` process argument.

## First deployment: exact sequence

No command below contains a real secret.

### 1. Prepare Python and validate everything

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r lambda/requirements.txt -r lambda/requirements-dev.txt
make validate
```

`make validate` runs tests, Ruff, `bash -n`, ShellCheck, deterministic Linux Lambda packaging,
`terraform fmt -check`, `terraform init -backend=false` when needed, and `terraform validate`.

### 2. Generate and review the plan

```bash
export AWS_PROFILE=YOUR_PROFILE
export AWS_REGION=us-east-1
aws sts get-caller-identity
./scripts/deploy.sh plan
terraform -chdir=terraform show -no-color tfplan
```

No resource has changed yet.

### 3. Apply only after review

```bash
./scripts/deploy.sh apply
```

The script creates a new saved plan, displays it, and requires the literal confirmation `APLICAR`.
Do not use local `terraform apply -auto-approve`.

### 4. Store the real SecureStrings

```bash
set -a
source .env
set +a
./scripts/configure-secrets.sh /palworld-cloud-server/prod
```

Terraform creates placeholder parameters. The script replaces the three values without printing
them. If you changed `project_name` or `environment`, get the correct path with:

```bash
terraform -chdir=terraform output parameter_store_names
```

### 5. Wait for bootstrap and confirm that EC2 stopped

The first apply starts EC2 to install SteamCMD and Palworld. By default, a transient timer powers it
off 15 minutes after user-data finishes, preventing an idle instance. Do not use the Discord start
command before confirming this first stop.

```bash
INSTANCE_ID=$(terraform -chdir=terraform output -raw instance_id)
aws ec2 wait instance-status-ok --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
aws ssm start-session --region "$AWS_REGION" --target "$INSTANCE_ID"
```

Inside the session:

```bash
sudo cloud-init status --wait
sudo journalctl -t palworld-user-data --no-pager
exit
```

Then wait for the instance to stop:

```bash
aws ec2 wait instance-stopped --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
```

### 6. Configure the Interactions Endpoint URL

Get the URL:

```bash
terraform -chdir=terraform output -raw lambda_function_url
```

In the Discord Developer Portal:

1. open **General Information**;
2. paste it into **Interactions Endpoint URL**;
3. save.

Discord sends a signed PING. Lambda validates it and returns `{"type":1}`. If Discord rejects the
URL, see the signature and logging troubleshooting section.

### 7. Register guild commands

```bash
set -a
source .env
set +a
./scripts/register-discord-commands.sh
```

Guild commands usually appear quickly. The Bot Token is never sent to AWS.

### 8. Run the first functional test

In the Discord channel:

```text
/palworld status
/palworld ligar
```

Wait for the webhook message and connect to `PUBLIC_IP:8211`.

## Daily operation

### `/palworld ligar`

- `stopped`: calls `StartInstances` and responds immediately;
- `pending`: reports that startup is already in progress;
- `running`: reports that it is already running and includes the IP when available;
- `stopping`: asks the user to wait;
- `shutting-down` or `terminated`: does not attempt to recreate anything.

The public IP normally changes after every start because there is no Elastic IP.

### `/palworld status`

Displays EC2 state, IP and port, and uptime. When the EC2 snapshot was updated within the last ten
minutes, it also displays game state and player count. A missing or stale snapshot is shown as such,
never interpreted as zero players.

### `/palworld desligar`

Lambda reads the snapshot for a quick response and sends a Run Command. On EC2, the script:

1. queries `/players` again;
2. cancels if players are connected or the query fails;
3. sends an announcement;
4. calls `/save`;
5. creates a backup;
6. requests `/shutdown` and stops the systemd unit with SIGINT;
7. waits for the unit to stop;
8. runs `poweroff`, which becomes EC2 state `stopped`.

`forcar:true` requires the Discord Administrator permission. It still attempts save and backup but
can continue after failures. Use it only in an emergency.

### `/palworld ajuda`

Lists the commands without exposing sensitive configuration.

## Connect to Palworld

Use the address reported by the webhook or `/palworld status`:

```text
203.0.113.10:8211
```

If you restricted the CIDR, the player's public IP must be allowed by `palworld_allowed_cidr`. Do
not confuse TCP with UDP when testing network rules.

## Administration through Systems Manager

SSH is closed by default. Start a session with:

```bash
INSTANCE_ID=$(terraform -chdir=terraform output -raw instance_id)
aws ssm start-session --region us-east-1 --target "$INSTANCE_ID"
```

If the instance is stopped, start it through Discord and wait until it is running and SSM is online.
Useful commands:

```bash
sudo systemctl status palworld.service palworld-notify.service
sudo systemctl list-timers 'palworld-*'
sudo journalctl -u palworld.service -n 200 --no-pager
sudo journalctl -u palworld-autostop.service -n 200 --no-pager
sudo journalctl -t palworld-automation -n 200 --no-pager
sudo cloud-init status --long
```

Temporary SSH exists only as an escape hatch. Set `enable_ssh=true`, use a `/32`
`ssh_allowed_cidr` and `ssh_key_name`, review the plan, and remove them immediately afterward.
`0.0.0.0/0` is rejected for SSH.

## Logs

Lambda:

```bash
aws logs tail /aws/lambda/palworld-cloud-server-prod-discord \
  --region us-east-1 \
  --since 1h \
  --follow
```

EC2 through Session Manager:

```bash
sudo journalctl -u palworld.service --since '1 hour ago'
sudo journalctl -u palworld-notify.service --since '1 hour ago'
sudo journalctl -u palworld-autostop.service --since '1 hour ago'
sudo journalctl -t palworld-user-data --no-pager
```

CloudWatch retains Lambda logs for seven days by default. Palworld logs stay in journald and EBS to
avoid an extra agent and continuous log-ingestion cost.

## Update Palworld

Perform maintenance only when players are disconnected:

```bash
INSTANCE_ID=$(terraform -chdir=terraform output -raw instance_id)
aws ssm start-session --region us-east-1 --target "$INSTANCE_ID"
```

Inside the session:

```bash
sudo /usr/local/sbin/stop-palworld.sh
sudo /usr/local/sbin/install-palworld.sh --update-only
sudo systemctl start palworld.service
sudo systemctl restart palworld-notify.service
```

`--update-only` refuses to update while the unit is active. Save data lives under
`/var/lib/palworld/saved`, outside the updated `/opt/palworld` installation tree.

## Backups

`PalWorldSettings.ini` is generated by copying the defaults from the installed version and replacing
only the supported official keys. The renderer rejects a key that is absent instead of inventing a
parameter or silently deleting new Pocketpair defaults.

Palworld keeps its internal backup when `bIsUseBackupSaveData=True`. The project also creates a daily
`tar.gz` archive and another archive before shutdown:

```text
/var/backups/palworld/palworld-save-YYYYMMDDTHHMMSSZ.tar.gz
```

Default local retention is 14 days. Create and inspect a manual backup with:

```bash
sudo /usr/local/sbin/backup-palworld.sh
sudo ls -lh /var/backups/palworld
```

### Enable S3

In `terraform.tfvars`:

```hcl
enable_s3_backup         = true
s3_backup_versioning     = true
s3_backup_retention_days = 30
# s3_backup_bucket_name  = "optional-globally-unique-name"
```

Review and apply. The bucket has Block Public Access, SSE-S3, optional versioning, lifecycle rules,
and write/list IAM limited to the `saves/` prefix. `force_destroy=false` prevents Terraform from
accidentally deleting stored objects.

### Restore a local backup

With EC2 running and no connected players:

```bash
sudo /usr/local/sbin/stop-palworld.sh
BACKUP=/var/backups/palworld/palworld-save-YYYYMMDDTHHMMSSZ.tar.gz
sudo mv /var/lib/palworld/saved /var/lib/palworld/saved.before-restore
sudo tar -xzf "$BACKUP" -C /var/lib/palworld
sudo chown -R palworld:palworld /var/lib/palworld/saved
sudo systemctl start palworld.service
sudo systemctl restart palworld-notify.service
```

Validate the world before deleting `saved.before-restore`.

### Restore from S3

```bash
aws s3 ls s3://YOUR_BUCKET/saves/
aws s3 cp s3://YOUR_BUCKET/saves/palworld-save-FILE.tar.gz /tmp/restore.tar.gz
```

Then repeat the local restore procedure with `/tmp/restore.tar.gz`.

## Tests and validation

Run the complete gate:

```bash
make validate
```

Run individual gates:

```bash
make test
make lint
make shellcheck
make lambda-package
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
```

Covered behavior includes valid and invalid signatures, missing headers, PING, start from stopped or
running, intermediate EC2 states, status, shutdown, connected players, forced administrator
shutdown, user/role/guild authorization, AWS errors, single-instance targeting, webhook formatting,
settings bootstrapping and validation, canonical persistence, and the interactive assistant.

A real `terraform plan` requires AWS credentials and valid Discord values. `terraform validate`
creates no resources.

## GitHub Actions and OIDC

Workflows:

- `tests.yml`: pull requests and `main`; Python, Ruff, ShellCheck, Terraform fmt/validate;
- `terraform-plan.yml`: manual `workflow_dispatch` only; assumes an OIDC role and publishes a saved
  plan for three days;
- `terraform-apply.yml`: manual `workflow_dispatch` only, protected GitHub Environment, requires
  `APPLY` or `DESTROY`, displays a saved plan, and applies exactly that file.

The plan and apply workflows refuse to run while the S3 backend remains disabled. An ephemeral
runner with local state would lose the source of truth and could duplicate resources. Continue
using `scripts/deploy.sh` for local-only operation, or migrate the backend first.

### Create the OIDC role

1. In IAM → **Identity providers**, add `https://token.actions.githubusercontent.com` with audience
   `sts.amazonaws.com` by following
   [Configuring OpenID Connect in AWS](https://docs.github.com/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services).
2. Create a Web Identity role with trust restricted to your repository and Environment:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:OWNER/REPOSITORY:environment:production"
      }
    }
  }]
}
```

3. Attach a dedicated provisioning policy limited to the resource types used by this stack: VPC and
   EC2, project IAM roles, Lambda and Function URL, SSM Parameters, CloudWatch Logs, and optional S3.
   Limit Region, `palworld-cloud-server-*` prefixes, the `/palworld-cloud-server/*` path, and
   `iam:PassedToService` for EC2 and Lambda wherever the action supports it. Do not use
   `AdministratorAccess`.
4. Under Settings → Environments, create `production`, enable required reviewers, and reject
   unauthorized branches.
5. Configure these **Environment variables**, not access keys:

| GitHub variable | Example |
|---|---|
| `AWS_ROLE_TO_ASSUME` | `arn:aws:iam::123456789012:role/palworld-github-oidc` |
| `AWS_REGION` | `us-east-1` |
| `DISCORD_APPLICATION_ID` | numeric ID |
| `DISCORD_PUBLIC_KEY` | 64 hex characters |
| `DISCORD_GUILD_ID` | numeric ID |
| `DISCORD_ALLOWED_USER_IDS_JSON` | `["123..."]` |
| `DISCORD_ALLOWED_ROLE_IDS_JSON` | `["234..."]` |

Palworld passwords and the webhook remain in Parameter Store and are not needed by the workflow.

## Optional remote Terraform backend

The backend is local by default. This is simple for one operator, but `terraform.tfstate` contains
IDs and sensitive metadata and must not be committed. For collaboration:

1. manually create a separate private, encrypted, and versioned S3 bucket;
2. uncomment the `backend "s3"` block in `terraform/versions.tf`;
3. set its bucket, key, and Region;
4. run:

```bash
terraform -chdir=terraform init -migrate-state
```

Terraform 1.11 supports `use_lockfile=true` in the S3 backend. Restrict the bucket to the deployment
role.

## Estimated costs and billing risks

Approximate orders of magnitude in `us-east-1` before taxes and data transfer, last reviewed in July
2026:

| Item | Order of magnitude |
|---|---:|
| EC2 `m6a.xlarge` Linux On-Demand while running | about USD 0.1728/hour |
| Public IPv4 while running | USD 0.005/hour |
| 50 GiB gp3 EBS | about USD 4/month in a USD 0.08/GiB-month Region |
| Lambda, SSM, and CloudWatch | usually cents for a small group, depending on usage |
| S3 | depends on stored GB, versions, requests, and data transfer |

Examples without credits:

- 20 game hours/month: EC2 plus IPv4 ≈ USD 3.56, plus EBS ≈ USD 4 and other usage;
- 80 game hours/month: EC2 plus IPv4 ≈ USD 14.22, plus EBS ≈ USD 4;
- running 24×7 for 730 hours: EC2 plus IPv4 ≈ USD 129.79, plus EBS and data.

Prices change. Recalculate them with the [AWS Pricing Calculator](https://calculator.aws/) and check
[EC2 On-Demand](https://aws.amazon.com/ec2/pricing/on-demand/),
[EBS](https://aws.amazon.com/ebs/pricing/), and
[VPC IPv4](https://aws.amazon.com/vpc/pricing/). EBS remains billable while EC2 is stopped.
Outbound data transfer, snapshots, S3, and logs can also incur charges.

### Configure AWS Budgets

In the console:

1. Billing and Cost Management → **Budgets → Create budget**;
2. select a monthly **Cost budget**;
3. set, for example, USD 10 or USD 20;
4. create email alerts at 50%, 80%, and 100%;
5. optionally create a Cost Anomaly Monitor.

Budgets send alerts but do not immediately stop resources. Test `/palworld desligar`, monitor EC2,
and keep MFA on the root account. Do not confuse credits with a hard billing limit.

## Destroy resources

Before destruction:

1. stop the server with a save;
2. verify backups and the restore procedure;
3. empty the S3 bucket and its versions when S3 is enabled (`force_destroy=false`);
4. verify whether the root volume is configured for deletion.

Generate, display, and confirm the destroy plan:

```bash
./scripts/destroy.sh
```

The script requires the literal confirmation `DESTRUIR`. Never run it automatically. The OIDC role,
remote backend bucket, and AWS Budget created outside this stack are not removed.

## Troubleshooting

### Discord rejects the Interactions Endpoint URL

```bash
aws logs tail /aws/lambda/palworld-cloud-server-prod-discord \
  --region us-east-1 --since 15m
```

- confirm the 64-character hex Public Key and the correct Guild/Application;
- confirm both Function URL resource-policy permissions (`InvokeFunctionUrl` and `InvokeFunction`);
- republish the ZIP after changing Lambda;
- Lambda must return 401 for invalid signatures; never disable that verification.

### `/palworld ligar` returns AccessDenied

- inspect the Lambda role policy and the Instance ID in its environment;
- run `aws lambda get-function-configuration --function-name ...`;
- use `aws iam simulate-principal-policy` for `ec2:StartInstances` on the exact ARN.

### EC2 is running but does not appear in Session Manager

- wait for boot and confirm Internet Gateway, route, and egress;
- open EC2 → Connect → Session Manager;
- when the EC2 serial console is enabled, inspect
  `snap.amazon-ssm-agent.amazon-ssm-agent.service`;
- user-data installs and starts the Snap as a fallback, but AMIs can change over time.

### Palworld service is restarting in a loop

```bash
sudo systemctl status palworld.service
sudo journalctl -u palworld.service -n 200 --no-pager
sudo /usr/local/sbin/configure-palworld.sh
```

Common causes are SecureStrings that still contain placeholders, SSM access failure, a REST
username incompatible with the installed version, or an incomplete SteamCMD installation.

### Health check receives 401

Pocketpair documents Basic Auth but does not define the username or unambiguously tie the credential
to `AdminPassword`. The project uses `admin` as the operational
`palworld_rest_api_username` default. Validate it against the installed version and change it when
necessary. The REST API is never exposed just to troubleshoot this problem.

### The settings assistant rejects the file

```bash
./palworld settings validate
```

The local JSON must use `schema_version: 1` and contain exactly the supported non-secret settings.
If the file was damaged, compare it with `config/palworld-settings.json.example`. Do not copy
passwords into it.

### A settings change remains pending

`./palworld settings apply` refuses an immediate restart when players are connected or the REST
player query is inconclusive. This is fail-safe behavior. Run `./palworld settings apply` again when
the server is empty, or let the next normal start activate the already published configuration.

### The server is not reachable

- confirm `running`, the current IP, and `palworld_port`;
- confirm the client uses UDP and its address is allowed by the CIDR;
- inspect `sudo ss -lunp | grep 8211` and service logs;
- do not reuse an old IP after stop/start;
- `PublicPort` does not change the listener; this project uses `PalServer.sh -port=...`.

### Autostop does not shut down

This is intentional while the service is still starting, `/run/palworld/ready` is absent, the API
failed, or the player count is unreliable:

```bash
sudo systemctl start palworld-autostop.service
sudo journalctl -u palworld-autostop.service -n 100 --no-pager
sudo cat /var/lib/palworld-monitor/idle-seconds
```

Never convert a query error into zero connected players.

### Terraform wants to replace EC2

Stop and inspect the attribute forcing replacement. Gameplay changes update Parameter Store and
must not recreate the instance. AMI and bootstrap-only user-data are ignored after creation.
Subnet, architecture, and some fundamental attributes can still require replacement; create a
backup first.

### The S3 bucket prevents destroy

This is expected protection. Download anything you need, explicitly remove objects and versions,
and only then create another destroy plan. Do not set `force_destroy` merely to bypass review.

## Known limitations

- Pocketpair documents Linux and Ubuntu in general but does not specifically certify Ubuntu 24.04.
  The SteamCMD package is available in Ubuntu Noble multiverse/i386.
- The REST Basic Auth username and its exact relationship with `AdminPassword` remain unclear in the
  current official documentation. The value is configurable and must be validated against the
  installed version.
- The `waittime` unit for the `/shutdown` endpoint is not documented consistently. The project does
  not rely on it: it saves, calls the endpoint, and confirms shutdown through systemd and SIGINT.
- The “online” notification goes to the fixed webhook channel, not necessarily the channel where a
  command was issued.
- `/status` uses eventual telemetry and never treats a stale snapshot as evidence of zero players.
- The first instance boot must remain online long enough to download the server. The 15-minute timer
  starts after bootstrap, not before.
- Local validation cannot prove account quotas, `m6a.xlarge` availability, permissions in another
  AWS account, or behavior of a future Palworld version.

## Official references

- [Pocketpair: requirements](https://docs.palworldgame.com/getting-started/requirements/)
- [Pocketpair: SteamCMD deployment](https://docs.palworldgame.com/getting-started/deploy-dedicated-server/)
- [Pocketpair: configuration parameters](https://docs.palworldgame.com/settings-and-operation/configuration/)
- [Pocketpair: server arguments](https://docs.palworldgame.com/settings-and-operation/arguments/)
- [Pocketpair: REST API](https://docs.palworldgame.com/api/rest-api/palwold-rest-api/)
- [Discord Interactions](https://docs.discord.com/developers/interactions/overview)
- [AWS Lambda Function URL access](https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html)
- [AWS Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
- [Documented decisions and open gaps](docs/research/official-platform-facts.md)
