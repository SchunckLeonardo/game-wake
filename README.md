# palworld-cloud-server

Servidor dedicado de Palworld sob demanda na AWS, controlado por comandos slash do Discord. A
instância EC2 inicia somente quando alguém autorizado pede, publica o IP público dinâmico quando o
jogo fica pronto e desliga com save e backup depois de permanecer vazia.

O projeto usa Terraform, EC2 On-Demand, Lambda Function URL, Systems Manager Parameter Store,
Session Manager, CloudWatch Logs, Python 3.12, Bash, systemd, SteamCMD e GitHub Actions. Não existe
bot permanente, container, API Gateway, NAT Gateway, Elastic IP, Load Balancer ou SSH aberto por
padrão. Não há módulo Java, portanto Gradle não é necessário.

> Este repositório cria infraestrutura cobrável. Ele nunca executa `terraform apply` ou
> `terraform destroy` automaticamente em push. Revise sempre o plano salvo.

## O que está implementado

- `/palworld ligar`, `/palworld status`, `/palworld desligar` e `/palworld ajuda`, em português;
- verificação Ed25519 sobre timestamp + corpo HTTP bruto antes de interpretar o JSON;
- allowlist por Guild ID e por usuário ou cargo do Discord;
- `PING` do Discord e respostas iniciais dentro do fluxo curto da Lambda;
- controle de uma única EC2, com tratamento de `pending`, `running`, `stopping`, `stopped`,
  `shutting-down` e `terminated`;
- Ubuntu Server 24.04 LTS x86-64 obtido pelo parâmetro público da Canonical;
- `m6a.xlarge`, EBS `gp3` de 50 GiB e `us-east-1` como defaults configuráveis;
- IMDSv2 obrigatório, EBS criptografado, shutdown behavior `stop` e IP público efêmero;
- instalação automática do SteamCMD e Palworld App ID `2394010` sem executar o jogo como root;
- REST API e RCON sem regra de entrada; somente UDP 8211 é aberto;
- healthcheck, notificação por webhook, telemetria sem segredos, autostop fail-safe e backup;
- S3 opcional, privado, criptografado, versionado e com lifecycle; desabilitado por padrão;
- Session Manager para administração, sem depender de SSH;
- 28 testes unitários, Ruff, ShellCheck, Terraform fmt/validate e workflows com OIDC.

## Arquitetura

Fluxo de comando:

```text
Jogador autorizado
        ↓
Discord Slash Command
        ↓ HTTPS + assinatura Ed25519
Lambda Function URL (AuthType NONE)
        ↓
AWS Lambda Python 3.12
        ├── Describe/Start da única EC2
        ├── leitura do status no Parameter Store
        └── Run Command SSM para shutdown seguro
                ↓
EC2 Ubuntu 24.04 + systemd + Palworld
```

Fluxo de boot:

```text
Discord /palworld ligar
        ↓
EC2 stopped → pending → running, com novo IP público
        ↓
palworld.service lê configuração e SecureStrings no Parameter Store
        ↓
PalServer.sh -port=8211
        ↓
healthcheck consulta a REST API em 127.0.0.1:8212
        ↓
webhook: 🟢 IP_PUBLICO:8211
```

Fluxo de autostop:

```text
timer systemd
        ↓ a cada 5 min por padrão
GET /v1/api/players em localhost
        ├── jogadores > 0 → zera o contador
        ├── erro/timeout/401 → não altera contador e não desliga
        └── zero jogadores por 20 min
                    ↓
              anúncio → save → backup → shutdown do Palworld
                    ↓
              systemctl poweroff
                    ↓
              EC2 fica stopped, nunca terminated
```

O snapshot gravado em `/<projeto>/<ambiente>/runtime/status` não contém senha, IP de jogador nem
outro dado pessoal. A Lambda usa esse snapshot somente para enriquecer `/status` e dar um aviso
rápido. O script executado na EC2 sempre verifica os jogadores novamente antes de desligar.

## Decisões de segurança

1. A Function URL precisa ser pública (`AuthType=NONE`), pois o Discord não usa AWS SigV4. Toda
   interação é autenticada na aplicação com `X-Signature-Ed25519`, `X-Signature-Timestamp` e o corpo
   original. Requisição inválida recebe HTTP 401.
2. O Security Group abre somente a porta UDP do jogo. A REST API em 8212 não é exposta, RCON fica
   desabilitado e SSH fica fechado.
3. Senha do servidor, senha administrativa e webhook são `SecureString`. O Terraform cria apenas
   placeholders com o atributo write-only `value_wo`; nem o placeholder nem mudanças posteriores
   feitas pela CLI são persistidos como valor no state.
4. A Lambda pode iniciar/parar somente a instância criada neste stack e executar apenas
   `AWS-RunShellScript` nela. `DescribeInstances` e `GetCommandInvocation` usam `Resource: "*"`
   porque essas APIs não oferecem resource-level permission; a região é limitada por condition.
5. `forcar:true` exige o bit Administrator do membro no Discord. Sem `forcar`, erro na REST API,
   save ou backup cancela o desligamento.
6. `allowed_user_ids` e `allowed_role_ids` vazios negam todos por padrão.
7. A EC2 usa Instance Profile; não existem access keys em disco.

## Estrutura do repositório

```text
.
├── README.md
├── Makefile
├── pyproject.toml
├── .env.example
├── terraform/
│   ├── versions.tf                 # Terraform/provider fixados e backend local
│   ├── provider.tf                 # provider, tags e payloads de configuração
│   ├── variables.tf                # tipos, defaults, descriptions e validações
│   ├── terraform.tfvars.example
│   ├── network.tf                  # VPC, subnet, IGW e rota pública
│   ├── security-group.tf           # UDP e SSH opcional/restrito
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
│   ├── render_settings.py          # preserva defaults oficiais instalados
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

## Pré-requisitos

- conta AWS com permissão para criar VPC, EC2, IAM Role/Instance Profile, Lambda, SSM Parameter,
  CloudWatch Log Group e opcionalmente S3;
- aplicativo e servidor (guild) Discord administrados por você;
- AWS CLI v2 autenticada, preferencialmente por IAM Identity Center/SSO;
- Terraform 1.11.x;
- Python 3.12, `pip`, `zip`, `jq`, `curl`, `shellcheck` e `make`;
- Git e uma máquina x86-64 ou arm64. O empacotador baixa wheels Linux x86-64 para a Lambda.

Verifique:

```bash
aws --version
terraform version
python3.12 --version
jq --version
shellcheck --version
aws sts get-caller-identity
```

### Instalar AWS CLI

Siga a [documentação oficial da AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
Depois, use SSO quando sua conta oferecer IAM Identity Center:

```bash
aws configure sso
aws sso login --profile SEU_PROFILE
export AWS_PROFILE=SEU_PROFILE
export AWS_REGION=us-east-1
aws sts get-caller-identity
```

Para uma conta pessoal sem SSO, `aws configure` funciona, mas use um usuário/role dedicado com MFA
e permissões mínimas. Não coloque access keys no repositório nem em GitHub Secrets quando OIDC for
possível.

### Instalar Terraform

Use o pacote oficial da HashiCorp. No macOS:

```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
terraform version
```

No Linux, siga [Install Terraform](https://developer.hashicorp.com/terraform/install). O provider
AWS está fixado em `6.53.0` e o lockfile deve permanecer versionado.

## AWS Free Plan, Paid Plan e créditos

`m6a.xlarge` tem 4 vCPU e 16 GiB, capacidade recomendada para este grupo pequeno, mas não está na
lista atual de tipos EC2 Free Tier eligible. Contas novas no AWS Free account plan podem não ter
acesso a esse recurso; nesse caso, faça upgrade manual para o Paid account plan em **Billing and
Cost Management → Account → AWS Free Tier plan**.

Segundo a documentação atual da AWS, um upgrade manual preserva os créditos restantes e os aplica
às faturas elegíveis até a expiração. Há exceções: entrada em AWS Organizations/Control Tower pode
fazer os créditos expirarem, e contas antigas seguem regras legadas. Confirme no Billing antes do
upgrade. Paid Plan significa que uso além dos créditos será cobrado.

Fontes: [Choosing an AWS Free Tier plan](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html),
[Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/) e
[EC2 Free Tier usage](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html).

## Criar e configurar o aplicativo Discord

### 1. Criar o aplicativo e obter Application ID/Public Key

1. Abra o [Discord Developer Portal](https://discord.com/developers/applications).
2. Clique em **New Application**, escolha um nome e confirme.
3. Em **General Information**, copie:
   - **Application ID** → `discord_application_id` e `DISCORD_APPLICATION_ID`;
   - **Public Key** → `discord_public_key`.
4. A Public Key não é segredo. O Bot Token e o webhook são segredos.

### 2. Criar o bot e obter o token

1. Abra **Bot** e clique em **Add Bot**, se necessário.
2. Em **Token**, gere/reset o token e copie uma única vez.
3. Guarde-o somente em `.env` local como `DISCORD_BOT_TOKEN`.
4. Não são necessários Message Content Intent nem um processo de bot online; o token serve apenas
   para registrar o comando pela API do Discord.

### 3. Instalar o aplicativo na guild

Em **Installation** ou **OAuth2 → URL Generator**:

1. selecione os scopes `applications.commands` e `bot`;
2. conceda ao bot apenas as permissões mínimas desejadas; os comandos HTTP não exigem Administrator;
3. abra a URL gerada e escolha sua guild.

### 4. Obter Guild ID, User IDs e Role IDs

No Discord, abra **User Settings → Advanced → Developer Mode**. Depois:

- clique com o botão direito no servidor → **Copy Server ID**;
- clique no usuário → **Copy User ID**;
- em Server Settings → Roles, clique no cargo → **Copy Role ID**.

Preencha ao menos um usuário ou cargo. A Lambda exige também que a interação venha exatamente da
guild configurada.

### 5. Criar o webhook

Na guild, vá ao canal onde os avisos devem aparecer:

1. **Edit Channel → Integrations → Webhooks → New Webhook**;
2. escolha o canal, nomeie o webhook e copie a URL;
3. guarde em `.env` como `DISCORD_WEBHOOK_URL`.

O webhook pertence a um canal fixo. Para que “o endereço será enviado neste canal” seja literal,
use os comandos nesse mesmo canal. O projeto não persiste interaction tokens de 15 minutos.

## Configuração local

Crie arquivos que são ignorados pelo Git:

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
cp .env.example .env
chmod 600 .env terraform/terraform.tfvars
```

Edite `terraform/terraform.tfvars` e preencha pelo menos:

```hcl
discord_application_id = "SEU_APPLICATION_ID"
discord_public_key      = "SUA_PUBLIC_KEY_HEX_DE_64_CARACTERES"
discord_guild_id        = "SUA_GUILD_ID"

discord_allowed_user_ids = ["SEU_USER_ID"]
discord_allowed_role_ids = ["ROLE_ID_OPCIONAL"]
```

Edite `.env`:

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

As senhas devem ser diferentes; a administrativa precisa de pelo menos 12 caracteres no script.
Nenhuma delas entra em `terraform.tfvars`.

### Variáveis principais

| Variável | Default | Efeito |
|---|---:|---|
| `aws_region` | `us-east-1` | região de todos os recursos |
| `instance_type` | `m6a.xlarge` | tipo On-Demand x86-64 |
| `root_volume_size_gib` | `50` | volume raiz gp3 criptografado |
| `root_volume_delete_on_termination` | `true` | apaga o volume ao destruir a EC2 |
| `enable_termination_protection` | `false` | proteção opcional contra terminate |
| `palworld_port` | `8211` | listener real passado a `PalServer.sh -port` |
| `palworld_allowed_cidr` | `0.0.0.0/0` | origem da conexão UDP; restrinja se puder |
| `autostop_check_minutes` | `5` | frequência real da consulta a jogadores |
| `autostop_idle_minutes` | `20` | vazio antes de desligar |
| `enable_s3_backup` | `false` | cria bucket privado opcional |
| `cloudwatch_log_retention_days` | `7` | retenção da Lambda |
| `lambda_reserved_concurrent_executions` | `-1` | usa a concorrência não reservada; aumente a quota antes de reservar |
| `stop_after_initial_bootstrap` | `true` | agenda stop 15 min após o primeiro bootstrap |

O timer acorda a cada minuto, mas o script respeita `autostop_check_minutes` antes de consultar a
API. Isso permite mudar o intervalo no Parameter Store via Terraform sem reescrever a unit.

### Configurações oficiais de gameplay incluídas

- `ServerName`, `ServerDescription`, `ServerPassword`, `AdminPassword`;
- `ServerPlayerMaxNum`, `ExpRate`, `CollectionDropRate`, `PalSpawnNumRate`;
- `DeathPenalty`: `None`, `Item`, `ItemAndEquipment` ou `All`;
- `PalDamageRateAttack`, `PalDamageRateDefense`;
- `PlayerDamageRateAttack`, `PlayerDamageRateDefense`;
- `PalStaminaDecreaceRate`, `PlayerStaminaDecreaceRate` — a grafia oficial é `Decreace`;
- `ItemWeightRate`, `bAllowEnhanceStat_Stamina`, `bAllowEnhanceStat_Weight`;
- `bIsUseBackupSaveData=True`, `RESTAPIEnabled=True`, `RESTAPIPort=8212`;
- `RCONEnabled=False`.

`PublicPort` é gravado no INI, mas, oficialmente, não altera o listener. A porta real é o argumento
`-port`. Não adicione nomes não confirmados sem consultar a documentação da versão instalada.

## Primeiro deploy: sequência exata

Nenhum comando abaixo contém segredo real.

### 1. Preparar Python e validar tudo

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r lambda/requirements.txt -r lambda/requirements-dev.txt
make validate
```

`make validate` executa testes, Ruff, `bash -n`, ShellCheck, empacota wheels Linux para a Lambda,
executa `terraform fmt -check`, `terraform init -backend=false` e `terraform validate`.

### 2. Gerar e revisar o plano

```bash
export AWS_PROFILE=SEU_PROFILE
export AWS_REGION=us-east-1
aws sts get-caller-identity
./scripts/deploy.sh plan
terraform -chdir=terraform show -no-color tfplan
```

Até aqui nenhum recurso foi alterado.

### 3. Aplicar somente após revisar

```bash
./scripts/deploy.sh apply
```

O script gera um novo saved plan, mostra o conteúdo e exige digitar `APLICAR`. Não use
`terraform apply -auto-approve` localmente.

### 4. Gravar os SecureStrings reais

```bash
set -a
source .env
set +a
./scripts/configure-secrets.sh /palworld-cloud-server/prod
```

O Terraform cria esses parâmetros com placeholder. O script substitui os três valores sem
imprimi-los. Se você alterou `project_name` ou `environment`, obtenha o path correto:

```bash
terraform -chdir=terraform output parameter_store_names
```

### 5. Aguardar o bootstrap e confirmar que ficou stopped

O primeiro apply inicia a EC2 para instalar SteamCMD/Palworld. Por padrão, um transient timer faz
`poweroff` após 15 minutos do término do user-data, evitando deixá-la ociosa. Não use o comando do
Discord antes de confirmar o primeiro stop.

```bash
INSTANCE_ID=$(terraform -chdir=terraform output -raw instance_id)
aws ec2 wait instance-status-ok --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
aws ssm start-session --region "$AWS_REGION" --target "$INSTANCE_ID"
```

Dentro da sessão, acompanhe:

```bash
sudo cloud-init status --wait
sudo journalctl -t palworld-user-data --no-pager
exit
```

Depois aguarde:

```bash
aws ec2 wait instance-stopped --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
```

### 6. Configurar Interactions Endpoint URL

Obtenha a URL:

```bash
terraform -chdir=terraform output -raw lambda_function_url
```

No Discord Developer Portal:

1. abra **General Information**;
2. cole em **Interactions Endpoint URL**;
3. salve.

O Discord envia um PING assinado. A Lambda valida e retorna `{"type":1}`. Se a URL não for aceita,
consulte o troubleshooting de assinatura/logs.

### 7. Registrar comandos na guild

```bash
set -a
source .env
set +a
./scripts/register-discord-commands.sh
```

Comandos de guild normalmente aparecem rapidamente. O Bot Token não é enviado à AWS.

### 8. Primeiro teste funcional

No canal do Discord:

```text
/palworld status
/palworld ligar
```

Espere a mensagem do webhook e conecte no endereço `IP_PUBLICO:8211`.

## Operação diária

### `/palworld ligar`

- `stopped`: chama `StartInstances` e responde imediatamente;
- `pending`: informa que já está iniciando;
- `running`: informa que já está ligada e mostra o IP, se disponível;
- `stopping`: pede para aguardar;
- `shutting-down`/`terminated`: não tenta recriar nada.

O IP público muda normalmente a cada start porque não existe Elastic IP.

### `/palworld status`

Mostra estado EC2, IP/porta e uptime. Quando o snapshot da EC2 foi atualizado nos últimos dez
minutos, mostra estado do serviço e jogadores. Snapshot ausente/desatualizado é exibido como tal,
sem inferir zero jogadores.

### `/palworld desligar`

A Lambda consulta o snapshot para resposta rápida e envia um Run Command. Na EC2, o script:

1. consulta `/players` novamente;
2. cancela se houver jogadores ou a consulta falhar;
3. envia anúncio;
4. chama `/save`;
5. cria backup;
6. pede `/shutdown` e para a unit systemd com SIGINT;
7. espera a unit parar;
8. executa `poweroff`, que vira estado EC2 `stopped`.

`forcar:true` exige Administrator do Discord. Ele continua tentando save/backup, mas permite
prosseguir diante de falhas; use apenas em emergência.

### `/palworld ajuda`

Mostra os comandos sem divulgar configuração sensível.

## Conectar ao Palworld

No jogo, use o endereço informado pelo webhook ou `/palworld status`:

```text
203.0.113.10:8211
```

Se o CIDR foi restrito, o IP público do jogador precisa estar incluído em
`palworld_allowed_cidr`. Não confunda TCP com UDP ao testar regras de rede.

## Administração com Systems Manager

Não há porta SSH por padrão. Inicie uma sessão:

```bash
INSTANCE_ID=$(terraform -chdir=terraform output -raw instance_id)
aws ssm start-session --region us-east-1 --target "$INSTANCE_ID"
```

Se a instância estiver stopped, ligue pelo Discord e espere `running`/SSM online. Comandos úteis:

```bash
sudo systemctl status palworld.service palworld-notify.service
sudo systemctl list-timers 'palworld-*'
sudo journalctl -u palworld.service -n 200 --no-pager
sudo journalctl -u palworld-autostop.service -n 200 --no-pager
sudo journalctl -t palworld-automation -n 200 --no-pager
sudo cloud-init status --long
```

SSH temporário existe apenas como escape hatch. Configure `enable_ssh=true`, um `/32` em
`ssh_allowed_cidr` e `ssh_key_name`, revise o plan e remova logo depois. `0.0.0.0/0` é rejeitado.

## Logs

Lambda:

```bash
aws logs tail /aws/lambda/palworld-cloud-server-prod-discord \
  --region us-east-1 \
  --since 1h \
  --follow
```

EC2, via Session Manager:

```bash
sudo journalctl -u palworld.service --since '1 hour ago'
sudo journalctl -u palworld-notify.service --since '1 hour ago'
sudo journalctl -u palworld-autostop.service --since '1 hour ago'
sudo journalctl -t palworld-user-data --no-pager
```

CloudWatch retém logs da Lambda por sete dias por padrão. O Palworld fica no journald/EBS para não
adicionar agente e ingestão contínua desnecessários.

## Alterar `PalWorldSettings.ini`

Altere as variáveis documentadas em `terraform/terraform.tfvars`, por exemplo:

```hcl
palworld_exp_rate             = 1.5
palworld_collection_drop_rate = 1.5
palworld_spawn_rate           = 1.0
palworld_death_penalty        = "Item"
palworld_item_weight_rate     = 0.8
```

Depois:

```bash
./scripts/deploy.sh plan
./scripts/deploy.sh apply
```

Isso atualiza `/<projeto>/<ambiente>/palworld/config` sem recriar a EC2. A próxima inicialização do
serviço gera um novo `PalWorldSettings.ini`. Para aplicar imediatamente numa instância ligada:

```bash
INSTANCE_ID=$(terraform -chdir=terraform output -raw instance_id)
aws ssm send-command \
  --region us-east-1 \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --parameters 'commands=["sudo /usr/local/sbin/stop-palworld.sh","sudo systemctl start palworld.service","sudo systemctl restart palworld-notify.service"]'
```

Esse comando para com verificação de jogadores; se houver alguém online, ele falha sem reiniciar.
Não edite `DefaultPalWorldSettings.ini`: o arquivo efetivo é
`/var/lib/palworld/saved/Config/LinuxServer/PalWorldSettings.ini`.

## Atualizar o Palworld

Faça manutenção com jogadores desconectados:

```bash
INSTANCE_ID=$(terraform -chdir=terraform output -raw instance_id)
aws ssm start-session --region us-east-1 --target "$INSTANCE_ID"
```

Na sessão:

```bash
sudo /usr/local/sbin/stop-palworld.sh
sudo /usr/local/sbin/install-palworld.sh --update-only
sudo systemctl start palworld.service
sudo systemctl restart palworld-notify.service
```

`--update-only` recusa atualização com a unit ativa. O save fica em `/var/lib/palworld/saved`, fora
da árvore atualizada em `/opt/palworld`.

## Backups

O `PalWorldSettings.ini` é gerado copiando os defaults da versão instalada e substituindo somente
as chaves oficiais listadas acima. O renderizador recusa qualquer chave ausente, em vez de inventar
um parâmetro ou apagar silenciosamente defaults novos da Pocketpair.

O Palworld mantém seu backup interno (`bIsUseBackupSaveData=True`). Além disso, o projeto cria um
`tar.gz` diário e antes de desligar:

```text
/var/backups/palworld/palworld-save-YYYYMMDDTHHMMSSZ.tar.gz
```

Retenção local default: 14 dias. Backup manual:

```bash
sudo /usr/local/sbin/backup-palworld.sh
sudo ls -lh /var/backups/palworld
```

### Habilitar S3

Em `terraform.tfvars`:

```hcl
enable_s3_backup        = true
s3_backup_versioning    = true
s3_backup_retention_days = 30
# s3_backup_bucket_name = "nome-global-opcional"
```

Revise e aplique. O bucket tem Block Public Access, SSE-S3, versionamento opcional, lifecycle e IAM
de escrita/listagem limitado ao prefixo `saves/`. `force_destroy=false` impede remoção acidental de
objetos pelo Terraform.

### Restaurar backup local

Com a EC2 ligada e sem jogadores:

```bash
sudo /usr/local/sbin/stop-palworld.sh
BACKUP=/var/backups/palworld/palworld-save-YYYYMMDDTHHMMSSZ.tar.gz
sudo mv /var/lib/palworld/saved /var/lib/palworld/saved.before-restore
sudo tar -xzf "$BACKUP" -C /var/lib/palworld
sudo chown -R palworld:palworld /var/lib/palworld/saved
sudo systemctl start palworld.service
sudo systemctl restart palworld-notify.service
```

Valide o mundo antes de apagar `saved.before-restore`.

### Restaurar do S3

```bash
aws s3 ls s3://SEU_BUCKET/saves/
aws s3 cp s3://SEU_BUCKET/saves/palworld-save-ARQUIVO.tar.gz /tmp/restore.tar.gz
```

Depois repita o procedimento local usando `/tmp/restore.tar.gz`.

## Testes e validação

Gate completo:

```bash
make validate
```

Gates isolados:

```bash
make test
make lint
make shellcheck
make lambda-package
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
```

Casos cobertos: assinatura válida/inválida, headers ausentes, PING, ligar stopped/running,
intermediários EC2, status, desligamento, jogadores conectados, force admin, usuário/cargo/guild,
erro AWS, targeting da única instância e mensagens principais.

Um `terraform plan` real requer credenciais AWS e valores Discord válidos; `terraform validate` não
cria recursos.

## GitHub Actions e OIDC

Workflows:

- `tests.yml`: PR/main; Python, Ruff, ShellCheck, Terraform fmt/validate;
- `terraform-plan.yml`: somente `workflow_dispatch`; assume role OIDC e publica saved plan por três dias;
- `terraform-apply.yml`: somente `workflow_dispatch`, GitHub Environment protegido, exige `APPLY` ou
  `DESTROY`, mostra um saved plan e aplica exatamente esse arquivo.

Os workflows de plan/apply recusam execução enquanto o backend S3 não estiver habilitado. Runner
efêmero com state local perderia a fonte de verdade e poderia duplicar recursos. Para operação
somente local, continue usando `scripts/deploy.sh`; para Actions, migre primeiro conforme a seção de
backend remoto.

### Criar a role OIDC

1. Em IAM → **Identity providers**, adicione `https://token.actions.githubusercontent.com` com
   audience `sts.amazonaws.com`, seguindo
   [Configuring OpenID Connect in AWS](https://docs.github.com/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services).
2. Crie uma role para Web Identity com trust restrito ao seu repositório e Environment:

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

3. Anexe uma policy de provisionamento dedicada somente aos tipos usados por este stack: VPC/EC2,
   IAM roles do projeto, Lambda/Function URL, SSM Parameters, CloudWatch Logs e S3 opcional. Restrinja
   região, prefixos `palworld-cloud-server-*`, path `/palworld-cloud-server/*` e `iam:PassedToService`
   a EC2/Lambda onde a API permitir. Não use `AdministratorAccess`.
4. Em Settings → Environments, crie `production`, habilite required reviewers e impeça branches não
   autorizadas.
5. Cadastre estas **Environment variables**, não access keys:

| GitHub variable | Exemplo |
|---|---|
| `AWS_ROLE_TO_ASSUME` | `arn:aws:iam::123456789012:role/palworld-github-oidc` |
| `AWS_REGION` | `us-east-1` |
| `DISCORD_APPLICATION_ID` | ID numérico |
| `DISCORD_PUBLIC_KEY` | 64 hex |
| `DISCORD_GUILD_ID` | ID numérico |
| `DISCORD_ALLOWED_USER_IDS_JSON` | `["123..."]` |
| `DISCORD_ALLOWED_ROLE_IDS_JSON` | `["234..."]` |

Os segredos do Palworld/webhook continuam no Parameter Store e não são necessários no workflow.

## Backend Terraform remoto opcional

O backend é local por padrão. Isso é simples para um operador, mas `terraform.tfstate` contém IDs e
metadados sensíveis e não deve ir para o Git. Para colaboração:

1. crie manualmente um bucket S3 separado, privado, criptografado e versionado;
2. descomente o bloco `backend "s3"` em `terraform/versions.tf`;
3. ajuste bucket/key/region;
4. execute:

```bash
terraform -chdir=terraform init -migrate-state
```

Terraform 1.11 suporta `use_lockfile=true` no backend S3. Restrinja o bucket à role de deploy.

## Custos estimados e riscos de cobrança

Estimativa orientativa em `us-east-1`, antes de impostos e data transfer, verificada em julho de
2026:

| Componente | Ordem de grandeza |
|---|---:|
| EC2 `m6a.xlarge` Linux On-Demand ligada | cerca de USD 0,1728/h |
| IPv4 público enquanto ligado | USD 0,005/h |
| EBS gp3 50 GiB | cerca de USD 4/mês em região a USD 0,08/GiB-mês |
| Lambda/SSM/CloudWatch | normalmente centavos para um grupo pequeno, conforme uso |
| S3 | conforme GB armazenados, versões, requests e data transfer |

Exemplos, sem créditos:

- 20 horas de jogo/mês: EC2 + IPv4 ≈ USD 3,56, mais EBS ≈ USD 4 e demais usos;
- 80 horas de jogo/mês: EC2 + IPv4 ≈ USD 14,22, mais EBS ≈ USD 4;
- ligada 24x7 por 730 h: EC2 + IPv4 ≈ USD 129,79, mais EBS e dados.

Preços mudam. Refaça no [AWS Pricing Calculator](https://calculator.aws/) e confira
[EC2 On-Demand](https://aws.amazon.com/ec2/pricing/on-demand/),
[EBS](https://aws.amazon.com/ebs/pricing/) e [VPC IPv4](https://aws.amazon.com/vpc/pricing/).
O EBS continua cobrado com a EC2 stopped. Data transfer de saída, snapshots, S3 e logs podem cobrar.

### Configurar AWS Budgets

No console:

1. Billing and Cost Management → **Budgets → Create budget**;
2. escolha **Cost budget** mensal;
3. defina, por exemplo, USD 10 ou USD 20;
4. crie alertas em 50%, 80% e 100% para seu e-mail;
5. opcionalmente crie também um Cost Anomaly Monitor.

Budgets alerta, mas não desliga recursos imediatamente. Teste `/palworld desligar`, acompanhe a EC2
e mantenha MFA na conta root. Não confunda créditos com limite rígido de cobrança.

## Destruir recursos

Antes:

1. pare o servidor com save;
2. confirme backups/restauração;
3. esvazie o bucket S3 e versões se S3 estiver habilitado (`force_destroy=false`);
4. revise se o volume raiz está configurado para ser apagado.

Gere, mostre e confirme o plano de destruição:

```bash
./scripts/destroy.sh
```

O script exige digitar `DESTRUIR`. Nunca rode isso automaticamente. A role OIDC, backend S3 e AWS
Budget criados fora deste stack não são removidos.

## Troubleshooting

### Discord rejeita a Interactions Endpoint URL

```bash
aws logs tail /aws/lambda/palworld-cloud-server-prod-discord \
  --region us-east-1 --since 15m
```

- confirme Public Key de 64 hex e Guild/Application corretos;
- confirme as duas resource policies da Function URL (`InvokeFunctionUrl` e `InvokeFunction`);
- republique o ZIP se mudou a Lambda;
- a Lambda deve devolver 401 para assinaturas inválidas; não desabilite essa verificação.

### `/palworld ligar` responde AccessDenied

- confira a policy da role Lambda e o Instance ID no environment;
- execute `aws lambda get-function-configuration --function-name ...`;
- execute `aws iam simulate-principal-policy` para `ec2:StartInstances` no ARN exato.

### EC2 running, mas não aparece no Session Manager

- aguarde o boot e confirme Internet Gateway/rota/egress;
- veja o Console EC2 → Connect → Session Manager;
- pelo EC2 serial console, se habilitado, confirme
  `snap.amazon-ssm-agent.amazon-ssm-agent.service`;
- o user-data instala/inicia o Snap como fallback, mas AMIs podem variar com o tempo.

### Palworld service em loop de restart

```bash
sudo systemctl status palworld.service
sudo journalctl -u palworld.service -n 200 --no-pager
sudo /usr/local/sbin/configure-palworld.sh
```

As causas mais comuns são SecureStrings ainda com placeholder, falha de acesso SSM, username REST
incompatível com a versão instalada ou instalação SteamCMD incompleta.

### Healthcheck recebe 401

A documentação oficial da Pocketpair afirma Basic Auth, mas não define o username nem vincula de
forma inequívoca a credencial a `AdminPassword`. O projeto usa `admin` como default operacional em
`palworld_rest_api_username`; valide na versão instalada e altere se necessário. A REST API nunca é
exposta para testar esse problema.

### Servidor não é acessível

- confirme `running`, IP atual e `palworld_port`;
- confirme que o cliente usa UDP e o CIDR está autorizado;
- verifique `sudo ss -lunp | grep 8211` e logs do serviço;
- não use o IP antigo após um stop/start;
- `PublicPort` não muda o listener; o projeto usa `PalServer.sh -port=...`.

### Autostop não desliga

Isso é intencional se o serviço ainda inicia, não existe `/run/palworld/ready`, a API falhou ou o
contador não é confiável:

```bash
sudo systemctl start palworld-autostop.service
sudo journalctl -u palworld-autostop.service -n 100 --no-pager
sudo cat /var/lib/palworld-monitor/idle-seconds
```

Nunca transforme erro de consulta em zero jogadores.

### Terraform quer substituir a EC2

Pare e examine o atributo que força replacement. Mudanças de gameplay atualizam Parameter Store e
não devem recriar a instância. AMI é ignorada no lifecycle após criação. Alterações como subnet,
arquitetura ou certos atributos fundamentais podem exigir replacement; faça backup antes.

### Bucket S3 impede destroy

É proteção esperada. Baixe o que precisa, remova objetos e versões explicitamente e só depois gere
novo destroy plan. Não altere `force_destroy` apenas para contornar uma revisão.

## Limitações conhecidas

- A Pocketpair documenta Linux/Ubuntu genericamente, não certifica especificamente Ubuntu 24.04;
  o pacote SteamCMD existe no Ubuntu Noble multiverse/i386.
- O username da REST Basic Auth e a relação exata com `AdminPassword` não estão claros na
  documentação oficial atual. O valor é configurável e precisa ser validado com a versão instalada.
- A unidade de `waittime` do endpoint `/shutdown` não é declarada de forma coerente. O projeto não
  depende dela: salva, chama o endpoint e confirma a parada via systemd/SIGINT.
- A notificação “online” vai ao canal fixo do webhook, não necessariamente ao canal de qualquer
  comando emitido em outra sala.
- `/status` usa telemetria eventual; nunca trata snapshot antigo como prova de zero jogadores.
- A instância inicial precisa ficar ligada tempo suficiente para baixar o servidor. O timer de 15
  minutos começa depois do bootstrap, não antes.
- Não houve deploy real neste repositório. `terraform validate` prova schema/sintaxe, não quota,
  disponibilidade de `m6a.xlarge`, permissões da sua conta nem comportamento da versão futura do
  Palworld.

## Referências oficiais

- [Pocketpair: requisitos](https://docs.palworldgame.com/getting-started/requirements/)
- [Pocketpair: deploy com SteamCMD](https://docs.palworldgame.com/getting-started/deploy-dedicated-server/)
- [Pocketpair: parâmetros](https://docs.palworldgame.com/settings-and-operation/configuration/)
- [Pocketpair: argumentos](https://docs.palworldgame.com/settings-and-operation/arguments/)
- [Pocketpair: REST API](https://docs.palworldgame.com/api/rest-api/palwold-rest-api/)
- [Discord Interactions](https://docs.discord.com/developers/interactions/overview)
- [AWS Lambda Function URL access](https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html)
- [AWS Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
- [Pesquisa de decisões e lacunas](docs/research/official-platform-facts.md)
