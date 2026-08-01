# Runbook: conciliação AbacatePay e Wallet

Objetivo: provar que cada pagamento, refund ou disputa produziu exatamente as entradas esperadas no ledger.

## Coleta

Registre o ID do evento AbacatePay, checkout/contribution ID, Account ID, valor em BRL, status do provedor e horário UTC. Redija dados pessoais e nunca copie chave de API ou assinatura.

## Conciliação

1. Confirme que o webhook chegou ao endpoint correto e passou pelas duas autenticações: query parameter `webhookSecret` e header `x-webhook-signature` HMAC-SHA256 Base64 do corpo bruto.
2. Confirme API version, produto, pacote, valor exato e contribution existente.
3. Procure o provider event ID na tabela de idempotência. Um replay deve retornar o efeito anterior, não criar outro crédito.
4. Compare status da Contribution e entradas imutáveis do Wallet Ledger.
5. Recalcule saldo como soma das entradas, incluindo reservas, releases, Runtime Charges, storage charges, service credits e compensações.
6. Compare sessões efetivas com preço/hora travado no início e duração faturável.

## Casos

- `Paid`: uma contribuição confirmada e um único crédito do valor exato.
- `Refunded`: compensação integral somente quando o crédito contribuído ainda está disponível; não edite o crédito original.
- disputa/reversal com saldo insuficiente: marque funding como `Needs Review`; não permita saldo negativo silencioso.
- evento desconhecido ou valor divergente: rejeite/quarentene, sem creditar.
- webhook ausente: consulte a AbacatePay, valide a resposta e reprocesse o mesmo evento autenticado; nunca fabrique um event ID.

Uma correção de suporte sempre cria entrada compensatória, actor e motivo. Encerre quando a soma do ledger, status da Contribution e evidência do provedor coincidirem.
