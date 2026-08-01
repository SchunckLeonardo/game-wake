# Runbook: resposta a incidentes

## 1. Conter

- Nomeie um responsável e registre início em UTC, impacto, Accounts/Worlds afetados e sinais.
- Para risco financeiro, suspenda novos checkouts/wakes pelo controle mais estreito disponível; não destrua Worlds.
- Para segredo exposto, revogue e rotacione no provedor e no SSM. Um novo deploy não invalida segredo vazado.
- Para runtime comprometido, bloqueie novas conexões, preserve evidência e confirme backup durável antes de terminar a instância.
- Para incidente de dados, preserve logs e consulte obrigações LGPD/jurídicas antes de comunicar.

## 2. Investigar

Correlacione Request ID, Operation ID, Account ID, World ID, provider event ID e horários entre API, worker, Step Functions, CloudWatch, SQS DLQ, Aurora, S3, EC2/SSM, Discord e AbacatePay. Não copie payloads sensíveis para documentos públicos.

Classifique pelo menos:

- confidencialidade: segredo, IP/senha, e-mail ou dados de pagamento expostos;
- integridade: ledger, save, role, configuração ou idempotência incorretos;
- disponibilidade: wake/sleep/API/banco indisponível;
- custo: runtimes órfãos, cobrança divergente ou Aurora sem pausa.

## 3. Recuperar

- Restaure de uma cópia verificada e mantenha o original para análise.
- Reprocesse eventos com a mesma chave idempotente.
- Corrija ledger com entrada compensatória; nunca edite histórico.
- Use service credit quando indisponibilidade confirmada violar a garantia.
- Valide todos os invariantes do primeiro deploy antes de reabrir.

## 4. Encerrar

Documente causa raiz, linha do tempo, blast radius, impacto financeiro/dados, ações, testes e responsável por prevenção. Abra mudança de código com regressão automatizada. Confirme que alarmes voltaram a `OK`, DLQ está explicada, runtimes órfãos são zero e usuários afetados receberam comunicação apropriada.
