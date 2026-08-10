# GameWake

[![Continuous integration](https://github.com/SchunckLeonardo/palworld-server/actions/workflows/tests.yml/badge.svg)](https://github.com/SchunckLeonardo/palworld-server/actions/workflows/tests.yml)
[![CodeQL](https://github.com/SchunckLeonardo/palworld-server/actions/workflows/codeql.yml/badge.svg)](https://github.com/SchunckLeonardo/palworld-server/actions/workflows/codeql.yml)

GameWake deixa um grupo de amigos criar, pagar, configurar, acordar e dormir um servidor de jogo sem administrar infraestrutura. A experiência principal vive no Discord e na mesma Console responsiva, que também funciona no navegador.

O MVP suporta Palworld e foi desenhado para ampliar o catálogo por meio de Game Templates versionados. A infraestrutura de cada World é descartável; o mundo salvo, sua configuração e seus backups permanecem duráveis e exportáveis.

## O que já existe

- Accounts ligadas a um servidor Discord, convite em lote e papéis Owner, Manager, Player, Billing e Custom Role.
- Permissões aditivas e com escopo, revogação imediata, proteção do último Owner e recuperação com e-mail verificado pelo Discord.
- Wallet pré-paga em BRL, checkout avulso pela AbacatePay API v2, reserva antes do wake, cobrança por uso e orçamento por World.
- Worlds Palworld com wake, progresso persistido, conexão privada, sono seguro, recuperação, auto-sleep configurável, backup, restore e export.
- Runtime Palworld pré-preparado em AMI privada e versionada; o wake restaura o World e inicia o jogo sem baixar SteamCMD ou reinstalar o servidor.
- Editor guiado e versionado de `PalWorldSettings.ini`, incluindo valores válidos e documentação de cada campo.
- Landing page, onboarding, Console Web e Discord Activity com a mesma API e autorização.
- Aurora PostgreSQL Serverless v2 via Data API, Step Functions Standard, runtimes EC2 descartáveis, S3/KMS, SSM, CloudWatch e alertas SNS.
- Mensagens operacionais no canal do grupo sem expor IP ou senha; `/gamewake conectar` entrega credenciais somente ao usuário autorizado.
- Testes unitários, integração PostgreSQL real, E2E desktop/mobile, lint, Terraform, dependency review e CodeQL em GitHub Actions.

## Arquitetura

```mermaid
flowchart LR
    Friends["Grupo de amigos"] --> Discord["Discord commands + Activity"]
    Friends --> Web["GameWake Console"]
    Discord --> API["Lambda Control Plane"]
    Web --> API
    API --> DB["Aurora PostgreSQL Serverless v2"]
    API --> Billing["AbacatePay v2"]
    API --> SFN["Step Functions Standard"]
    SFN --> Worker["Idempotent worker"]
    Worker --> EC2["Disposable EC2 runtime"]
    Worker --> S3["Encrypted World data"]
    Worker --> Notify["Discord notifications"]
```

Aurora guarda metadados transacionais, autorização, ledger, idempotência e projeções. O S3 guarda os dados nativos dos Worlds. Step Functions serializa e retoma operações duráveis; cada efeito externo ainda recebe uma chave idempotente. A origem da verdade da Wallet é o ledger interno, nunca o saldo da AbacatePay.

As decisões de produto e arquitetura estão na [GameWake Foundation](docs/GAMEWAKE_FOUNDATION.md), no [Context Map](CONTEXT-MAP.md) e nos [ADRs](docs/adr/).

## Desenvolvimento local

Requisitos: Python 3.12+, Node.js 22.13+, Terraform 1.11+, AWS CLI, `jq` e ShellCheck.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r lambda/requirements.txt -r lambda/requirements-dev.txt
npm --prefix web ci
cp .env.example .env
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Validação principal:

```bash
make validate
npm --prefix web run test:e2e
```

Os testes de repositório PostgreSQL exigem uma instância isolada:

```bash
GAMEWAKE_TEST_DATABASE_URL=postgresql://gamewake:gamewake@127.0.0.1:5432/gamewake_test \
  .venv/bin/python -m pytest -q -m integration
```

A Console local fica em `http://localhost:3000`:

```bash
npm --prefix web run dev
```

Use `?demo=1` somente para as jornadas locais de demonstração. Contas reais nunca caem silenciosamente nesse modo.

## Deploy

O caminho de produção, variáveis, configuração do Discord, AbacatePay, AWS e smoke test estão em [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). O resumo é:

```bash
./scripts/deploy.sh plan
./scripts/deploy.sh apply
./scripts/configure-secrets.sh "$(terraform -chdir=terraform output -raw parameter_path)"
./scripts/register-discord-commands.sh
```

Use os comandos e outputs exatos descritos no guia; o trecho acima não substitui a revisão do plano, a configuração da Console nem os callbacks no Discord Developer Portal.

Antes de abrir a beta, consulte a [auditoria do MVP](docs/MVP_AUDIT.md) e execute os [runbooks operacionais](docs/runbooks/). Ela separa implementação verificada de gates que dependem de credenciais reais, deploy AWS, validação financeira, jurídica e dados da Closed Beta.

## Operação e segurança

- Não coloque tokens, senhas, chave HMAC ou `.tfvars` reais no Git.
- Segredos entram no SSM Parameter Store com `./scripts/configure-secrets.sh`.
- SSH permanece fechado por padrão; administração de runtime usa Systems Manager.
- Backups e exports usam objetos privados, criptografados e links temporários.
- Destruir compute não deve apagar a última cópia recuperável do World. Leia o runbook de restore/export antes de qualquer teardown.
- Alarmes do control plane chegam ao tópico SNS exposto pelo Terraform; confirme a assinatura de e-mail quando configurada.

## Guias

- [Deploy de produção](docs/DEPLOYMENT.md)
- [Auditoria requisito por requisito](docs/MVP_AUDIT.md)
- [Roadmap e gates da Closed Beta](docs/ROADMAP.md)
- [Primeiro deploy](docs/runbooks/first-deploy.md)
- [Operação travada](docs/runbooks/stuck-operation.md)
- [Conciliação de pagamento](docs/runbooks/payment-reconciliation.md)
- [Restore e export de World](docs/runbooks/world-restore-export.md)
- [Recuperação do Owner](docs/runbooks/owner-recovery.md)
- [Resposta a incidentes](docs/runbooks/incident-response.md)

## Licença

Distribuído sob a [MIT License](LICENSE).
