# Worlds

Este contexto preserva o progresso de um grupo e coordena a infraestrutura temporária necessária para jogar.

## Resources and lifecycle

**World**:
O recurso persistente de um jogo que conserva progresso e configurações de um grupo.
_Avoid_: server, instance, machine, save

**World Status**:
O estado público de um World: `Dormindo`, `Acordando`, `Online`, `Indo dormir` ou `Precisa de atenção`.
_Avoid_: raw provider status, instance state, deployment status

**World Operation**:
Uma execução exclusiva, durável e idempotente que altera o ciclo de vida de um World.
_Avoid_: duplicate job, UI-local progress, parallel lifecycle mutation

**Operation Progress**:
A projeção compartilhada das fases e da estimativa de uma World Operation.
_Avoid_: fake countdown, blocking interaction, Discord-only status

**Runtime**:
A infraestrutura temporária que executa um World sem possuir seu progresso.
_Avoid_: World, game server, save

**Runtime Provider**:
O adaptador interno que cria, conecta, observa, recupera e destrói Runtimes.
_Avoid_: customer cloud account, BYOC, provider picker

**Game Region**:
A localização geográfica estável de um World.
_Avoid_: availability zone, provider region code, Runtime location

## Protection and recovery

**Backup**:
Um ponto recuperável do progresso e da configuração de um World.
_Avoid_: World, live save, Runtime snapshot

**World Export**:
Um pacote portátil com os arquivos e metadados necessários para hospedar um World fora do GameWake.
_Avoid_: proprietary archive, Backup, account deletion

**Pending Deletion**:
O período reversível entre a solicitação de exclusão de um World e a remoção definitiva de seus dados.
_Avoid_: Dormindo, immediate deletion, indefinite archive

**Recovery Guarantee**:
A garantia de que o GameWake nunca destrói a última cópia recuperável de um World.
_Avoid_: best-effort backup, unverified shutdown

**Automatic Recovery**:
A tentativa limitada de restaurar a saúde de um World dentro da sessão existente.
_Avoid_: new wake session, unbounded restart loop, manual-only recovery

**Auto Sleep**:
A política que coloca um World para dormir após um período contínuo sem jogadores.
_Avoid_: scheduled shutdown, forced shutdown with players, idle Runtime termination
