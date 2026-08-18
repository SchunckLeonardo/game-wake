# Context Map

## Contexts

- [GameWake](./CONTEXT.md) — define a linguagem compartilhada do produto
- [Accounts and Access](./docs/contexts/accounts/CONTEXT.md) — representa pessoas, grupos, propriedade e autorização
- [Worlds](./docs/contexts/worlds/CONTEXT.md) — preserva e executa mundos com segurança
- [Game Catalog](./docs/contexts/game-catalog/CONTEXT.md) — descreve como cada jogo é instalado, configurado e operado
- [Billing](./docs/contexts/billing/CONTEXT.md) — recebe contribuições, reserva saldo e mede uso
- [Experience](./docs/contexts/experience/CONTEXT.md) — apresenta o produto no Discord e na Web

## Relationships

- **Experience → Accounts and Access**: autentica o User e autoriza cada interação no Resource Scope solicitado
- **Accounts and Access → Worlds**: o GameWake Account possui Worlds e o Role Assignment único de cada Membership limita o acesso a eles
- **Worlds → Game Catalog**: cada World usa um Game Template imutável para executar operações específicas do jogo
- **Worlds → Billing**: um despertar solicita Usage Reservation e uma sessão produz Runtime Usage
- **Billing → Worlds**: Balance Guard e World Budget podem solicitar que um World durma com segurança
- **Worlds → Experience**: World Status, Operation Progress e Connection Details alimentam Discord e GameWake Console
- **Todos → Experience**: ações relevantes produzem Activity Events redigidos para exibição conforme a Role
