# Runbook: operação de World travada

Use quando um wake, sleep, restore ou recovery não avança, termina em `NeedsAttention` ou dispara alarme.

## Diagnóstico seguro

1. Anote Account ID, World ID, Operation ID, horário UTC e ação pedida. Não cole senha ou URL assinada em ticket.
2. Abra o dashboard indicado por `gamewake_control_plane.operations_dashboard`.
3. Consulte a execução Step Functions cujo nome deriva da operação e os logs `/aws/vendedlogs/states/...`.
4. Consulte `/aws/lambda/<projeto>-<ambiente>-operation-worker` pelo Operation ID.
5. Verifique a projeção persistida na Console: fase, última atualização e mensagem redigida.
6. Compare o runtime provider: instância com tag `GameWakeManaged=true`, estado EC2 e disponibilidade SSM.
7. Verifique a DLQ e os schedules de reconciliação e monitoramento.

## Recuperação

- Aguarde um ciclo de reconciliação quando a execução existe e o provider ainda converge.
- Se a execução falhou com erro transitório e está apta a redrive, use o redrive da própria execução; o worker e efeitos externos são idempotentes.
- Se o runtime sumiu durante wake, deixe a operação entrar em recovery; não crie uma EC2 manual fora do Launch Template.
- Se o jogo não responde mas a sessão ainda tem garantia, preserve a reserva e execute recovery dentro da sessão existente.
- Se um wake nunca ficou Online, confirme a liberação/refund da reserva e que não houve Runtime Charge indevida.
- Se o sleep não verificou save, não termine a última cópia recuperável. Marque para atenção e preserve runtime/backup conforme a evidência disponível.

## Não fazer

- não edite a fase diretamente no banco;
- não repita `RunInstances` manualmente;
- não termine uma instância antes de confirmar a cópia durável;
- não reenvie uma notificação com IP/senha para o canal;
- não apague a DLQ sem registrar e reprocessar cada mensagem.

Encerre o incidente apenas quando provider, operação, World, reserva/ledger e notificação concordarem. Registre a causa sem dados sensíveis.
