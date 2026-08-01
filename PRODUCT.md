# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

O público principal são grupos brasileiros de amigos que querem jogar juntos em um mundo privado e persistente sem aprender infraestrutura, escolher um provedor de nuvem ou manter uma máquina ligada. O primeiro recorte são grupos de Palworld convidados para a Closed Beta.

O grupo precisa criar e financiar sua conta, convidar amigos, acordar o World, entrar no jogo, ajustar configurações e encerrar a sessão com segurança. Participantes comuns devem conseguir jogar sem compreender recursos de nuvem, cobrança técnica ou administração avançada.

## Product Purpose

GameWake torna mundos persistentes de jogos simples de possuir e operar em grupo. O World continua existindo enquanto a infraestrutura descartável acorda somente quando os amigos querem jogar e volta a dormir com segurança quando a sessão termina.

O produto é bem-sucedido quando um grupo consegue concluir onboarding, primeira contribuição, primeiro despertar, conexão e sono sem ajuda humana; quando não há perda irrecuperável de progresso nem saldo negativo; e quando os grupos retornam para novas sessões.

## Positioning

GameWake não é um painel de hospedagem nem um bot específico de Palworld. Ele combina uma experiência Discord-first, uma Console Web para fluxos ricos, Wallet pré-paga, operação sob demanda e separação entre World e Runtime.

O mecanismo distintivo é preservar saves, configurações e Backups como recursos duráveis e portáteis do grupo, enquanto a infraestrutura paga é temporária. O cliente escolhe o que importa para jogar; provedor, instâncias e orquestração permanecem responsabilidade do GameWake.

## Operating Context

- A entrada principal do grupo acontece pelo Discord, com autenticação, comandos rápidos, convites e uma Activity que abre a mesma Console.
- A Console Web responsiva atende onboarding, Wallet, membros, Roles, configurações, Backups, atividade e operações sensíveis.
- Slash commands resolvem ações rápidas como convidar, consultar status, acordar, conectar e dormir. Fluxos complexos abrem a Console na tela apropriada.
- A conexão com o jogo é entregue de forma privada e efêmera a usuários autorizados. IP, senha, tokens e meios de pagamento não aparecem em mensagens públicas do grupo.
- O grupo compartilha um GameWake Account, uma Wallet e um ou mais Worlds. Cada pessoa mantém sua própria User identity e Membership.
- O ciclo habitual é contribuir com créditos, acordar o World, acompanhar o progresso, conectar, jogar e deixar o Auto Sleep persistir o estado antes de liberar o Runtime.

## Capabilities and Constraints

- O MVP opera no Brasil, em `pt-BR`, com Wallet em `BRL` e Palworld como único Game Template.
- A Console deve funcionar no navegador e como Discord Activity usando a mesma API, autorização e modelo de produto.
- Player, Manager e Owner cobrem o caso comum. Custom Roles e permissões com escopo ficam disponíveis como recurso avançado.
- A Wallet é pré-paga, compartilhada pelo grupo e nunca pode ficar negativa. Contribuições avulsas usam Pix ou cartão via AbacatePay.
- Pós-pago e Auto Recharge não fazem parte do MVP.
- Cada sessão apresenta e preserva seu preço antes do despertar. Usage Reservation, World Budget, Balance Guard e Auto Sleep evitam cobranças inesperadas.
- World e Runtime são recursos diferentes. O World preserva identidade, progresso, configuração e Backups; o Runtime é descartável.
- Um World não troca de jogo. Novos jogos entram por Game Templates versionados depois que a Closed Beta validar confiabilidade, demanda e margem.
- Sono seguro, Recovery Guarantee, Backups verificáveis, restauração que preserva o estado atual e World Export portátil são requisitos do produto.
- O produto nunca deve destruir automaticamente a última cópia recuperável de um World.
- Administração avançada não deve aumentar a complexidade do fluxo comum de um grupo de amigos.
- Segredos, dados de conexão e informações financeiras devem permanecer privados, efêmeros ou redigidos na origem.
- A Closed Beta prevista envolve 10 a 20 grupos brasileiros convidados. Expansão do catálogo, internacionalização, mods, indicações e outros provedores dependem da evidência obtida nessa fase.
- Preço público definitivo, política jurídica e fiscal, marca registrada, regiões futuras e SLA público continuam decisões abertas. Interfaces futuras não devem apresentá-los como fatos confirmados.

## Brand Commitments

- O nome do produto é **GameWake**.
- A promessa central é: **“Seu mundo continua existindo. A infraestrutura só acorda quando seus amigos querem jogar.”**
- A voz é amigável, direta, confiável e livre de linguagem de provedor de nuvem sempre que o usuário não precisar dela.
- A comunicação deve enfatizar jogar junto, continuidade do World, proteção do progresso, controle de custos e simplicidade.
- O vocabulário canônico inclui GameWake Account, User, Membership, Role, Wallet, World, Runtime, Backup, Game Template e Console.
- Evitar descrever o produto como “hosting panel”, “cloud wrapper”, “Discord Account”, “Discord-owned server” ou “Palworld bot”.

## Evidence on Hand

- O repositório contém uma implementação funcional da landing page, onboarding, Console Web responsiva e Discord Activity.
- Existem fluxos implementados para Accounts, Memberships, Roles, Wallet, Worlds, configurações, Backups, operações e integração com Discord e AbacatePay.
- A suíte automatizada cobre domínio, infraestrutura, renderização e jornadas E2E em desktop e mobile.
- A GameWake Foundation, o Context Map, os ADRs, o roadmap, a auditoria do MVP e os runbooks registram decisões e comportamento esperado.
- Ainda não existem depoimentos públicos, logotipos de clientes, estudos de caso, imprensa ou métricas reais da Closed Beta. Nenhuma interface deve inventar essas evidências.
- Metas da Closed Beta são objetivos, não resultados comprovados: 95% dos despertares válidos online, P95 inferior a cinco minutos, 80% dos grupos sem ajuda na primeira sessão, 50% retornando na quarta semana e 30% contribuindo novamente.

## Product Principles

1. **O caso simples permanece simples.** O grupo comum joga, convida e controla seus Worlds sem atravessar administração avançada.
2. **Seu mundo continua; a máquina não precisa continuar.** Progresso e configuração são duráveis, enquanto infraestrutura é temporária.
3. **Nenhuma conta-surpresa.** Preço antecipado, Wallet pré-paga e proteções automáticas impedem dívida e consumo silencioso.
4. **Discord primeiro, Discord apenas quando ajuda.** Ações rápidas ficam próximas da conversa; tarefas ricas usam a mesma Console no navegador ou na Activity.
5. **Os dados pertencem ao grupo.** Backup, recuperação e exportação evitam perda e aprisionamento.

## Accessibility & Inclusion

Todas as superfícies Web devem atender **WCAG 2.2 nível AA**. Fluxos essenciais precisam funcionar por teclado, com leitores de tela, contraste adequado, foco visível, alvos de interação confortáveis e suporte a preferência por movimento reduzido.

Textos devem permanecer compreensíveis para pessoas sem experiência em nuvem, hospedagem de servidores ou administração de sistemas. Estados, custos, consequências e ações destrutivas devem ser explicados em português claro, sem depender apenas de cor, ícones ou jargão.
