# Runbook: primeiro deploy

Objetivo: validar uma instalação nova sem colocar saves ou valores relevantes em risco.

## Antes da janela

- Conclua todos os itens de [DEPLOYMENT.md](../DEPLOYMENT.md).
- Use uma guild e uma conta AWS dedicadas à beta.
- Tenha dois usuários Discord, um e-mail verificado para o Owner e um produto AbacatePay de baixo valor.
- Defina quem observa CloudWatch, quem valida o jogo e quem pode interromper o teste.
- Guarde os outputs `gamewake_api`, `gamewake_control_plane` e o plano aplicado.

## Execução

1. Confirme a assinatura do tópico SNS e deixe o dashboard de operações aberto.
2. Confirme que API, worker, state machine, cluster Aurora, bucket de World data e schedules existem.
3. Procure erros na invocation de migrations; não continue com schema incompleto.
4. Abra a landing page, autentique pelo Discord e confira que a Console não entrou em modo demo.
5. No canal autorizado, execute `/gamewake comecar`. Registre a Account criada e guarde offline os recovery codes mostrados uma única vez.
6. Execute `/gamewake convidar @amigo1`; o segundo usuário executa `/gamewake aceitar`.
7. Faça uma contribuição real de menor valor. Confira checkout `Paid`, uma única entrada no Wallet Ledger e saldo exato.
8. Crie ou selecione o World, defina orçamento e auto-sleep de 10 minutos durante o teste.
9. Execute `/gamewake acordar`. Observe `Queued`, `Provisioning`, `StartingGame` e `Online` na Console.
10. Confira que o canal recebeu apenas a disponibilidade, sem IP ou senha. Cada usuário autorizado usa `/gamewake conectar` privadamente.
11. Entre no jogo, produza uma alteração identificável no World e saia.
12. Execute `/gamewake dormir`; confirme save, backup verificado, término do runtime e estado `Sleeping`.
13. Acorde novamente e valide a alteração. Depois faça um restore para cópia e um World Export.
14. Confira runtime usage, cobrança, saldo, activity events redigidos, dashboard, alarmes e DLQ.

## Aprovação

O smoke passa somente se:

- nenhum segredo apareceu em Discord, logs, checkout compartilhado ou activity;
- uma repetição de webhook, comando ou callback não duplicou saldo, runtime ou operação;
- wake e sleep terminaram com estado persistido coerente;
- o runtime foi encerrado depois do sono seguro;
- backup restaurado e export baixado contêm manifest, configuração e save;
- o ledger explica exatamente a variação da Wallet;
- alarmes e contato operacional funcionaram.

Se algum item falhar, não convide outros grupos. Preserve logs/IDs e siga o runbook específico.
