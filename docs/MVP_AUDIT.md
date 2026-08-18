# Auditoria do MVP GameWake

Data da auditoria de implementação: 31 de julho de 2026.

Esta matriz separa três coisas diferentes:

- **Implementado**: existe código, infraestrutura e teste automatizado no repositório.
- **Verificável no CI**: o contrato é exercitado sem credenciais de produção; integração usa PostgreSQL real no GitHub Actions.
- **Gate de lançamento**: exige deploy real, provedor, usuários, decisão comercial ou validação jurídica. Não é correto marcar como concluído só porque o código existe.

## Fundação e arquitetura

| Requisito | Estado | Evidência |
|---|---|---|
| GameWake Discord-first com Console compartilhada | Implementado | Landing, onboarding, Console Web, Activity e API única em `web/` e `gamewake/control_plane/`. |
| Account 1:1 com guild Discord | Implementado | Aggregate, persistência e `/gamewake comecar`. |
| Aurora PostgreSQL Serverless v2 | Implementado; deploy pendente | Data API, cluster Serverless v2, secrets gerenciados, migrations e integração PostgreSQL. Compatibilidade regional precisa ser confirmada no plan/apply. |
| Step Functions Standard | Implementado; deploy pendente | State machine Standard, execução estável por operação, projeção persistida, reconciliação e DLQ. |
| Runtimes descartáveis separados de Worlds | Implementado; deploy pendente | Launch Template, EC2 por wake, tags gerenciadas e término após sono seguro. |
| Dados duráveis e criptografados | Implementado; drill pendente | S3 privado/KMS, backups, restore/export e política de última cópia. |
| Observabilidade e alertas | Implementado; canal pendente | Logs, dashboard, alarmes, SNS criptografado e e-mail opcional. A assinatura precisa ser confirmada. |

## Accounts e acesso

| Requisito | Estado | Evidência |
|---|---|---|
| Users internos e identidades Discord ligadas | Implementado | OAuth Web/Activity, sessão KMS HMAC e repositórios. |
| Convite de até três amigos e aceite | Implementado | `/gamewake convidar`, `/gamewake aceitar`, Console e testes. |
| Owner, Manager, Player e Billing | Implementado | Roles predefinidas e matriz de permissões. |
| Custom Roles com escopo opcional por World | Implementado | Criação, substituição de Role única e autorização allow-only. |
| Revogação imediata de membership/role | Implementado | API/Console, step-up e activity auditável. |
| Impedir remoção do último Owner | Implementado | Invariante de domínio e testes. |
| Recuperação sem support root | Implementado; exercício pendente | E-mail Discord somente quando verificado, recovery codes de uso único e apenas hashes persistidos. |
| Activity imutável e redigida | Implementado | Eventos append-only, autorização e redaction testada. |

## Worlds e Palworld

| Requisito | Estado | Evidência |
|---|---|---|
| Criar/listar múltiplos Worlds | Implementado | API, persistência e seletor na Console. |
| Wake com reserva antes de compute | Implementado | Quote, Reservation, Balance Guard e Step Functions. |
| Progresso real de operação | Implementado | Fases persistidas; a Console não inventa progresso live. |
| Conexão privada | Implementado | `/gamewake conectar` e API autorizada; canal do grupo não recebe IP/senha. |
| Sono seguro | Implementado | Save, backup, verificação e término serializados. |
| Auto-sleep por World | Implementado | 10/20/30/60 minutos ou desligado, usado pelo monitor de sessão. |
| Recovery sem dupla cobrança | Implementado | Retoma dentro da sessão/reserva existente e reconcilia provider. |
| Configuração guiada | Implementado | Game Template Palworld versionado, tipos, limites, opções, help e revisões/diff. |
| Opções Palworld solicitadas | Implementado | Drops, `BaseCampWorkerMaxNum`, Palbox import/export, regen em sono, hatch, farm speed, stamina, fome e supply drops. |
| Backup, restore como cópia e export | Implementado; drill real pendente | Contratos, S3/in-memory, links privados e manifest. Falta executar restore/export em Palworld real fora do GameWake. |
| Allowance, grace e excedente de storage | Implementado | Medição, cobrança mensal idempotente, grace e poda limitada a backups automáticos elegíveis. |

## Wallet, billing e AbacatePay

| Requisito | Estado | Evidência |
|---|---|---|
| Wallet pré-paga em BRL | Implementado | Ledger append-only, saldo derivado e compensações. |
| Checkout Pix/cartão AbacatePay API v2 | Implementado; credenciais pendentes | Pacotes mapeados a product IDs e checkout externo. Produtos reais precisam ser cadastrados. |
| Webhook autenticado e idempotente | Implementado; teste real pendente | URL secret, HMAC Base64 do corpo bruto, API version e provider event dedupe. |
| Valor pago deve coincidir com pacote | Implementado | Retorno e evento divergentes são rejeitados. |
| Reserva, release e Runtime Charge | Implementado | Preço/hora travado, usage metering, cobrança e wake refund. |
| Orçamento por World | Implementado | API/Console e enforcement no fluxo de consumo. |
| Proteção de saldo | Implementado | Não inicia sem reserva; monitor dorme antes de saldo insuficiente. |
| Service credit por indisponibilidade | Implementado | Crédito imutável para falha confirmada de wake/availability. |
| Refund/disputa/reconciliação | Implementado no domínio; operação real pendente | Compensação sem edição e `Needs Review` quando reversal causaria negativo. Semântica comercial final depende de termos e provedor. |
| Auto Recharge | Fora do MVP | Só entra quando o provedor documentar cobrança segura sob demanda. |

## Experiência

| Requisito | Estado | Evidência |
|---|---|---|
| Landing page e onboarding | Implementado | Rotas responsivas e jornadas E2E. |
| Console desktop/mobile | Implementado | Wallet, Worlds, membros, roles, settings, backup e activity. |
| Discord Activity | Implementado; portal pendente | Embedded App SDK, authorize/exchange e mesma Console. URL Mapping precisa ser configurado. |
| Comandos rápidos `/gamewake` | Implementado | Começar, convidar, aceitar, status, acordar, conectar, dormir, configurar, console e ajuda. |
| Notificações de lifecycle | Implementado; bot real pendente | Mensagens idempotentes por nonce para online/sleep/recovery/cancel/attention. |

## Qualidade e segurança

| Requisito | Estado | Evidência |
|---|---|---|
| Unit tests | Verificável | Suíte Python sem serviços externos. |
| Integração PostgreSQL real | Verificável no CI | Service `postgres:16-alpine` e `GAMEWAKE_TEST_DATABASE_URL`. Localmente é ignorada sem essa variável. |
| E2E desktop/mobile | Verificável | Playwright cobre onboarding, Wallet, convite, wake/connect/sleep, configuração e Activity. |
| Lint/build/infra | Verificável | Ruff, ESLint/build, ShellCheck, pacote reproduzível, Terraform fmt/validate. |
| Dependency review e CodeQL | Verificável no GitHub | Dependency review em PR e CodeQL Python/TypeScript. |
| Merge protegido | Verificação externa necessária | `main` deve exigir aprovação de Leonardo, checks e conversa resolvida; conferir live nas settings do GitHub. |
| Segredos fora do state/Git | Implementado por desenho | SSM SecureString e RDS managed secret; `.env`, `.tfvars`, state e planos ignorados. É preciso confirmar que nenhum segredo histórico foi publicado. |

## Requisitos externos antes da Closed Beta

Estes itens continuam abertos e não devem ser confundidos com defeitos escondidos:

1. Escolher domínio/origem definitiva e publicar a Console por HTTPS.
2. Criar aplicação Discord real, instalar bot, configurar OAuth callback, Interactions Endpoint e Activity URL Mapping.
3. Criar produtos, API key, public key e webhook reais na AbacatePay; executar contribuição, replay, refund e conciliação controlados.
4. Aplicar Terraform em conta AWS de beta, confirmar quotas/capacidade de `m6a.xlarge`, versão Aurora disponível, migrations, pausa/retomada e assinatura SNS.
5. Executar restore real e abrir um World Export em instalação Palworld independente do GameWake.
6. Validar preço, custo AWS, impostos, margem, allowance, grace, política de refund/disputa e orçamento de incidentes.
7. Revisar LGPD, termos de uso, privacidade, retenção/exclusão, responsabilidade por conteúdo e comunicações financeiras.
8. Exercitar runbooks com responsáveis reais, inclusive perda do Owner e operação travada.
9. Fazer auditoria de segurança e de histórico de segredos antes de usuários externos.

## Gates de saída da Closed Beta

O repositório não produz essas métricas sozinho. Elas exigem tráfego e grupos reais:

- taxa de wake bem-sucedido e tempo P95 até `Online` dentro da meta acordada;
- zero perda de World e restore/export comprovados;
- ledger conciliado com todos os pagamentos reais;
- nenhum runtime órfão ou cobrança sem explicação;
- alarmes acionáveis e incidentes dentro do SLA da beta;
- retenção, ativação e feedback suficientes para justificar lançamento público.

Até esses dados existirem, o status correto é: **MVP implementado e verificável localmente/CI; lançamento de Closed Beta condicionado aos gates externos acima**.
