# Game Catalog

Este contexto encapsula tudo que varia entre jogos para que o restante do GameWake permaneça genérico.

## Language

**Game Template**:
A definição versionada de como o GameWake instala, configura, observa, salva, atualiza e protege um jogo.
_Avoid_: World, server image, installation script, scattered game conditionals

**World Access Strategy**:
O mecanismo definido pelo Game Template para autorizar entrada no servidor de jogo.
_Avoid_: Role, Discord authorization, public connection details

**Game Update**:
Uma versão validada do servidor de jogo disponível para aplicação em um World.
_Avoid_: Game Template version, unvalidated release, forced live update

**World Configuration**:
O conjunto validado de configurações de jogo desejadas para um World.
_Avoid_: live INI file, UI-specific settings, unvalidated text

**Configuration Revision**:
Um registro imutável de uma alteração confirmada na World Configuration.
_Avoid_: mutable settings history, World restore, Backup

**Runtime Profile**:
Uma opção de capacidade específica do jogo apresentada como `Essencial`, `Recomendado` ou `Desempenho`.
_Avoid_: instance type, machine size, provider SKU
