# Deploy de produção do GameWake

Este guia instala o MVP com Aurora PostgreSQL Serverless v2 e Step Functions Standard. Execute primeiro em uma conta AWS de beta separada e mantenha `enable_legacy_single_server = false`.

## 1. Pré-requisitos

- conta AWS com billing, MFA no usuário root e acesso administrativo temporário para o bootstrap;
- quota e capacidade para `m6a.xlarge` na região escolhida; esse runtime não pertence ao Free Tier;
- AWS CLI autenticada, Terraform 1.11+, Python 3.12+, Node.js 22.13+, `jq` e ShellCheck;
- aplicativo Discord com bot, OAuth2 e Activity habilitados;
- conta AbacatePay com API v2, produtos avulsos em BRL e webhook;
- domínio HTTPS estável para a GameWake Console;
- bucket S3 de state e GitHub OIDC para automação de produção.

Confira identidade e região antes de criar recursos:

```bash
aws sts get-caller-identity
aws configure get region
terraform version
python3 --version
node --version
```

O Aurora precisa suportar Serverless v2 com `min_capacity = 0` na combinação região/versão escolhida. O exemplo usa Aurora PostgreSQL `16.3`, `0–4 ACUs` e pausa após 900 segundos. Se a região não aceitar essa combinação, escolha uma versão compatível antes do plan. A primeira chamada depois de uma pausa pode demorar mais enquanto o banco retoma.

## 2. Preparar e validar o repositório

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r lambda/requirements.txt -r lambda/requirements-dev.txt
npm --prefix web ci
cp .env.example .env
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
make validate
npm --prefix web run test:e2e
```

`make validate` inclui testes Python, Ruff, build/teste da Console, ShellCheck, pacote Lambda reproduzível e validação Terraform. A integração real de persistência requer PostgreSQL isolado:

```bash
GAMEWAKE_TEST_DATABASE_URL=postgresql://gamewake:gamewake@127.0.0.1:5432/gamewake_test \
  .venv/bin/python -m pytest -q -m integration
```

Nunca aponte essa variável para um banco com dados reais: a suíte cria e limpa seu próprio schema.

## 3. Criar a aplicação Discord

No [Discord Developer Portal](https://discord.com/developers/applications):

1. Crie a aplicação e anote Application ID e Public Key.
2. Na aba Bot, crie o bot, copie o token uma única vez e instale-o no servidor da beta com permissão de enviar mensagens no canal de operação.
3. Em OAuth2, adicione exatamente o callback retornado por `gamewake_api.discord_oauth_callback` após o deploy.
4. O login Web solicita `identify email`; o e-mail só é usado para recuperação do único Owner quando o Discord informa `verified=true`.
5. A Activity solicita `identify`, `email` e `guilds`. Em Activities, configure a URL Mapping para a origem HTTPS da Console e use `/activity` como entrada.
6. Depois do apply, configure `gamewake_api.discord_interactions` como Interactions Endpoint URL.

Use IDs da aplicação, guild, usuários e roles — nunca nomes visíveis. O bot não precisa anunciar IP ou senha em canal público; a mensagem de disponibilidade orienta o usuário a executar `/gamewake conectar`, que responde privadamente.

## 4. Configurar AbacatePay API v2

Crie produtos avulsos para cada pacote de crédito e preencha `abacatepay_packages` com:

- `id`: identificador estável do pacote no GameWake;
- `amount`: crédito exato em reais que entra na Wallet;
- `product_id`: ID real do produto avulso na AbacatePay.

O Control Plane rejeita um checkout ou pagamento cujo valor não coincida com o pacote. A Wallet deriva do ledger imutável interno; a AbacatePay apenas confirma a contribuição.

Após o apply, cadastre o output `gamewake_api.abacatepay_webhook` no painel da AbacatePay e informe o secret ao criar o webhook. A AbacatePay acrescenta esse valor como query parameter `webhookSecret`; configure exatamente o mesmo valor em `ABACATEPAY_WEBHOOK_SECRET`. O endpoint também valida o header `x-webhook-signature` como HMAC-SHA256 Base64 do corpo bruto usando `ABACATEPAY_PUBLIC_KEY`. Não coloque o secret manualmente no output Terraform e não passe o evento por um proxy que reserialize o JSON.

Auto Recharge não faz parte do MVP. Refund e disputa precisam seguir o runbook de conciliação.

## 5. Preencher Terraform e segredos locais

Edite `terraform/terraform.tfvars`. No mínimo, revise:

```hcl
project_name  = "gamewake"
environment   = "prod"
aws_region    = "us-east-1"
instance_type = "m6a.xlarge"

enable_legacy_single_server = false

discord_application_id = "..."
discord_public_key     = "..."
discord_guild_id       = "..."
gamewake_console_url   = "https://app.seu-dominio.com"

aurora_engine_version      = "16.3"
aurora_min_acu             = 0
aurora_max_acu             = 4
aurora_auto_pause_seconds  = 900
aurora_deletion_protection = true
aurora_skip_final_snapshot = false

operations_alarm_email = "operacoes@seu-dominio.com"
```

Também defina os produtos AbacatePay, preço final por hora, allowance e preço de armazenamento, CIDR UDP e pelo menos um `discord_allowed_user_ids` ou `discord_allowed_role_ids`. Os valores de preço no exemplo são ilustrativos e não devem ser publicados sem custos, impostos e margem validados.

Preencha `.env` somente na máquina operacional:

```dotenv
DISCORD_APPLICATION_ID=...
DISCORD_GUILD_ID=...
DISCORD_BOT_TOKEN=...
DISCORD_CLIENT_SECRET=...
ABACATEPAY_API_KEY=...
ABACATEPAY_WEBHOOK_SECRET=...
ABACATEPAY_PUBLIC_KEY=...
PALWORLD_SERVER_PASSWORD=...
PALWORLD_ADMIN_PASSWORD=...
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
AWS_REGION=us-east-1
```

`.env`, `.tfvars`, planos, states e pacotes são ignorados pelo Git. Não os force para o histórico.

## 6. Plan e apply local

O script gera o pacote Lambda, inicializa Terraform, valida e mostra o plano:

```bash
./scripts/deploy.sh plan
```

Leia substituições, recursos públicos, IAM, proteção do banco e política de retenção. Para aplicar exatamente o plano mostrado:

```bash
./scripts/deploy.sh apply
```

Digite `APLICAR` apenas depois da revisão. O apply também executa migrations idempotentes pelo worker depois de o Aurora ficar disponível.

Grave os segredos nos parâmetros criados. O caminho deriva de `/<project_name>/<environment>`:

```bash
./scripts/configure-secrets.sh /gamewake/prod
```

O script grava SecureStrings sem imprimir valores. O bot token é lido apenas pelo worker para notificações; o client secret, API key e chaves de webhook são lidos apenas pelo Control Plane.

## 7. Configurar endpoints e comandos

Veja os outputs sem revelar segredos:

```bash
terraform -chdir=terraform output gamewake_api
terraform -chdir=terraform output gamewake_control_plane
terraform -chdir=terraform output post_deploy_instructions
```

No Discord Developer Portal:

- Interactions Endpoint URL = `gamewake_api.discord_interactions`;
- OAuth2 Redirect URL = `gamewake_api.discord_oauth_callback`;
- Activity URL Mapping = origem da Console;
- Activity launch path = `/activity`.

Registre os comandos de guild para feedback imediato durante a beta:

```bash
./scripts/register-discord-commands.sh
```

O script registra `/gamewake` e mantém `/palworld` apenas para compatibilidade do protótipo legado. A jornada nova começa em `/gamewake comecar`.

## 8. Publicar a Console

Faça o deploy do diretório `web/` em um host HTTPS estável. O build de produção exige:

```dotenv
NEXT_PUBLIC_GAMEWAKE_API_URL=https://ID.lambda-url.REGION.on.aws
NEXT_PUBLIC_DISCORD_APPLICATION_ID=123456789012345678
NEXT_PUBLIC_SITE_URL=https://app.seu-dominio.com
```

`NEXT_PUBLIC_GAMEWAKE_API_URL` é o `gamewake_api.base_url`, sem necessidade de barra final. `NEXT_PUBLIC_SITE_URL` e `gamewake_console_url` precisam apontar para a mesma origem exata. Se a URL mudar, atualize Terraform para corrigir OAuth e CORS antes de aceitar usuários.

O hosting é estático/server-rendered na borda e não recebe outra base de dados: dados reais continuam no Control Plane/Aurora.

## 9. GitHub Actions e state remoto

Crie um GitHub Environment protegido chamado `production`, com aprovação obrigatória do Owner. Configure:

- `AWS_ROLE_TO_ASSUME`: role confiando no OIDC do repositório;
- `AWS_REGION`;
- `TF_STATE_BUCKET` e `TF_STATE_KEY`;
- `DISCORD_APPLICATION_ID`, `DISCORD_PUBLIC_KEY`, `DISCORD_GUILD_ID`;
- `DISCORD_ALLOWED_USER_IDS_JSON` e `DISCORD_ALLOWED_ROLE_IDS_JSON`;
- `GAMEWAKE_CONSOLE_URL`;
- `ABACATEPAY_PACKAGES_JSON`;
- `RUNTIME_PROFILE_HOURLY_RATES_JSON`;
- `PROJECT_NAME`, `DEPLOYMENT_ENVIRONMENT` e `INSTANCE_TYPE` quando diferentes dos defaults;
- `STORAGE_ALLOWANCE_BYTES`, `STORAGE_GRACE_DAYS` e `STORAGE_RATE_PER_GIB_MONTH_BRL`;
- `AURORA_ENGINE_VERSION`, `AURORA_MIN_ACU`, `AURORA_MAX_ACU` e `AURORA_AUTO_PAUSE_SECONDS`;
- `PALWORLD_ALLOWED_CIDR` e `OPERATIONS_ALARM_EMAIL` quando usados.

O backend S3 usa criptografia e lockfile. `terraform-plan.yml` só planeja; `terraform-apply.yml` recria e mostra um plano antes de aplicar, exige `APPLY`, ou `DESTROY` para destruição. Nenhum secret de runtime deve entrar em GitHub Variables; eles são gravados diretamente no SSM.

A branch `main` deve exigir o check agregado `Required quality gate`, CodeQL e aprovação do Owner antes do merge.

## 10. Smoke test após o deploy

Siga [runbooks/first-deploy.md](runbooks/first-deploy.md). O mínimo é:

1. confirmar a assinatura SNS recebida por e-mail;
2. verificar migrations e alarmes sem erro;
3. executar `/gamewake comecar` no canal escolhido;
4. guardar os recovery codes exibidos uma única vez;
5. convidar e aceitar um segundo usuário;
6. criar/contribuir para a Wallet em checkout real de valor mínimo;
7. acordar um World e observar as fases persistidas;
8. conectar, salvar, dormir, restaurar uma cópia e exportar;
9. reconciliar ledger, runtime e cobrança;
10. verificar dashboard, DLQ e logs redigidos.

Não use o primeiro pagamento real para descobrir preço ou política de reembolso. Esses itens são gates de lançamento listados na auditoria.

## 11. Destruição e retenção

Produção usa proteção de exclusão do Aurora e snapshot final. O bucket durável de Worlds não deve ser esvaziado automaticamente. Antes de um destroy:

1. coloque todos os Worlds para dormir com save verificado;
2. gere backup e World Export;
3. baixe e teste o export fora do GameWake;
4. guarde o objeto em local independente da conta AWS;
5. só então remova a proteção do Aurora, caso a intenção seja realmente apagar o control plane.

O fluxo manual exige confirmação explícita:

```bash
./scripts/destroy.sh
```

Leia o plano e digite `DESTRUIR`. Essa confirmação autoriza a infraestrutura descrita no plan, não autoriza apagar cópias externas nem significa que a portabilidade foi testada.

## Referências oficiais

- [Aurora Serverless v2 — funcionamento](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.how-it-works.html)
- [Aurora Serverless v2 — pausa automática em zero ACUs](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2-auto-pause.html)
- [Discord Activities — funcionamento](https://docs.discord.com/developers/activities/how-activities-work)
- [Discord Activities — construção e URL Mapping](https://docs.discord.com/developers/activities/building-an-activity)
- [Discord API — criação de mensagens](https://docs.discord.com/developers/resources/message#create-message)
- [AbacatePay — criação de Checkout v2](https://docs.abacatepay.com/pages/payment/create)
- [AbacatePay — segurança de webhooks](https://docs.abacatepay.com/pages/webhooks/security)
- [Pocketpair — parâmetros do servidor](https://docs.palworldgame.com/settings-and-operation/configuration/)
