# Billing

Este contexto mantém o saldo pré-pago do grupo, reconcilia pagamentos e transforma uso de infraestrutura em cobranças previsíveis.

## Money and payments

**Billing Currency**:
A única moeda usada pelo Wallet Ledger de um GameWake Account.
_Avoid_: display locale, provider currency, exchange rate

**Payment Provider**:
O adaptador externo que cria e reconcilia pagamentos reais sem possuir o saldo da Wallet.
_Avoid_: Wallet Ledger, provider-owned balance

**Wallet**:
O saldo pré-pago compartilhado por um GameWake Account.
_Avoid_: account balance field, billing account, postpaid invoice

**Wallet Ledger**:
O histórico financeiro imutável do qual o saldo da Wallet é derivado.
_Avoid_: mutable balance field, deleted transaction, overwritten charge

**Wallet Contribution**:
Uma compra pontual de créditos feita por uma Membership para a Wallet compartilhada.
_Avoid_: transfer, shared card, reimbursement

**Auto Recharge**:
Uma capacidade planejada de criar Wallet Contributions automaticamente sob limites definidos por um Owner.
_Avoid_: postpaid billing, unlimited charge, shared payment method

## Usage and price

**Usage Reservation**:
Um bloqueio temporário de créditos criado antes de alocar infraestrutura paga.
_Avoid_: Runtime Charge, security deposit, prepaid session package

**Runtime Usage**:
O intervalo faturável entre o início da alocação paga e a liberação confirmada de um Runtime.
_Avoid_: online time, player time, uptime estimate

**Runtime Charge**:
O débito calculado para uma sessão bem-sucedida a partir de seu Runtime Usage.
_Avoid_: hourly block, per-sample rounding, failed-wake charge

**Session Quote**:
O preço final por hora fixado para uma tentativa de despertar e preservado na sessão resultante.
_Avoid_: mutable active-session rate, provider spot price, hidden markup

**Wake Guarantee**:
A garantia de estorno quando uma tentativa de despertar nunca leva o World a `Online`.
_Avoid_: free Runtime Usage, manual refund request, successful short session

**Availability Credit**:
O lançamento compensatório pelo período em que um World anteriormente `Online` fica comprovadamente indisponível.
_Avoid_: manual service credit, failed-wake refund, monitoring blip

## Cost protection

**Storage Allowance**:
A quantidade de armazenamento incluída sem custo para Worlds e Backups de um GameWake Account.
_Avoid_: unlimited storage, Runtime Usage, hidden storage fee

**Storage Grace Period**:
O prazo para resolver armazenamento excedente que a Wallet não pode financiar.
_Avoid_: immediate deletion, silent data loss, indefinite paid overage

**World Budget**:
Um limite mensal opcional que restringe quanto um World pode consumir da Wallet compartilhada.
_Avoid_: separate Wallet, prepaid package, hidden spending limit

**Balance Guard**:
A proteção que alerta sobre saldo baixo e inicia o sono seguro antes de a Wallet ficar negativa.
_Avoid_: overdraft, abrupt termination, silent low balance
