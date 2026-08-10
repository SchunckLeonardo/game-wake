---
name: GameWake
description: A mesa compartilhada onde amigos acordam um World protegido sem carregar a infraestrutura nas costas.
colors:
  night-ink: "#0b1020"
  night-ink-soft: "#11182b"
  mist-paper: "#f4f5ef"
  bright-paper: "#fbfcf7"
  quiet-line: "#dfe2d7"
  muted-sage: "#697064"
  wake-green: "#b8f43d"
  wake-green-deep: "#6d9f00"
  journey-indigo: "#606bf3"
  preparation-amber: "#ffb44a"
  attention-coral: "#ff7164"
  pure-white: "#ffffff"
  night-line: "#28334a"
  night-muted: "#a8b2c2"
typography:
  display:
    fontFamily: "Geist, Arial, sans-serif"
    fontSize: "clamp(42px, 4.2vw, 60px)"
    fontWeight: 820
    lineHeight: 0.98
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Geist, Arial, sans-serif"
    fontSize: "clamp(40px, 5vw, 68px)"
    fontWeight: 700
    lineHeight: 1.02
    letterSpacing: "-0.04em"
  title:
    fontFamily: "Geist, Arial, sans-serif"
    fontSize: "clamp(34px, 4vw, 52px)"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.04em"
  body:
    fontFamily: "Geist, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.65
  action:
    fontFamily: "Geist, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 720
  label:
    fontFamily: "Geist Mono, monospace"
    fontSize: "11px"
    fontWeight: 680
    letterSpacing: "0.08em"
rounded:
  brand: "11px 11px 11px 4px"
  compact: "8px"
  navigation: "9px"
  control: "10px"
  action: "12px"
  card: "14px"
  panel: "15px"
  feature: "16px"
  full: "999px"
spacing:
  micro: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "24px"
  2xl: "32px"
  section: "116px"
components:
  button-primary:
    backgroundColor: "{colors.wake-green}"
    textColor: "{colors.night-ink}"
    typography: "{typography.action}"
    rounded: "{rounded.action}"
    padding: "0 21px"
    height: "47px"
  button-outline:
    backgroundColor: transparent
    textColor: "{colors.night-ink}"
    typography: "{typography.action}"
    rounded: "{rounded.action}"
    padding: "0 21px"
    height: "47px"
  field-light:
    backgroundColor: "{colors.pure-white}"
    textColor: "{colors.night-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "0 13px"
    height: "48px"
  field-dark:
    backgroundColor: "#091321"
    textColor: "{colors.pure-white}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "45px"
  nav-active:
    backgroundColor: "{colors.wake-green}"
    textColor: "{colors.night-ink}"
    rounded: "{rounded.navigation}"
    padding: "0 11px"
    height: "42px"
  status-chip-online:
    backgroundColor: "#263b24"
    textColor: "#c9f37d"
    rounded: "{rounded.full}"
    padding: "7px 10px"
  card-console:
    backgroundColor: "#101a2b"
    textColor: "{colors.pure-white}"
    rounded: "{rounded.card}"
    padding: "20px"
  wallet-card:
    backgroundColor: "{colors.night-ink}"
    textColor: "{colors.pure-white}"
    rounded: "{rounded.feature}"
    padding: "34px"
---

# Design System: GameWake

## Overview

**Creative North Star: "A Mesa Central do World"**

GameWake transforma o World persistente na mesa onde o grupo se reúne. Papel quente, tinta quase preta, regras técnicas finas e um terreno circular ilustrado dão presença ao que continua existindo; Verde Despertar, Índigo de Jornada, Âmbar de Preparação e Coral de Atenção tornam ação, orientação, espera e proteção legíveis sem parecer um painel de nuvem.

A landing persuade com uma World Table clara e ampla. A Console traduz a mesma ideia para uma Command Table escura, densa e escaneável. Onboarding, autenticação e fluxos auxiliares preservam os mesmos materiais, tipografia, controles e sinais, mas não são forçados a repetir a composição radial: a topologia serve ao ciclo do World, não a toda página.

**Key Characteristics:**

- Papel quente e tinta noturna alternam os modos persuasivo e operacional.
- Um World circular ilustrado é o foco memorável do ciclo de acordar, jogar e dormir.
- Verde elétrico marca a ação prioritária; pervinca orienta; âmbar prepara; coral protege e alerta.
- Hairlines, círculos, órbitas e ícones lineares compactos organizam informação sem decoração gratuita.
- Geist sustenta títulos compactos e corpo direto; Geist Mono fica restrito a metadados operacionais.
- Superfícies de trabalho são planas; profundidade tátil fica concentrada em ações e focos reais.

## Colors

A paleta alterna o Papel Neblina calmo da landing com o campo escuro da Console, mantendo os mesmos sinais elétricos em ambos os contextos.

### Primary

- **Verde Despertar** (`wake-green`, CSS `--wake`): ação prioritária, disponibilidade e medidores positivos; funciona como superfície com Tinta Noturna.
- **Verde Despertar Profundo** (`wake-green-deep`, CSS `--wake-deep`): pontos de presença, checks e sinais positivos pequenos que precisam de contraste adicional.

### Secondary

- **Índigo de Jornada** (`journey-indigo`, CSS `--blue`): orientação, seleção, progresso e momentos de encerramento; conduz sem competir com o CTA verde.

### Tertiary

- **Âmbar de Preparação** (`preparation-amber`, CSS `--amber`): espera, despertar e fases intermediárias.
- **Coral de Atenção** (`attention-coral`, CSS `--coral`): proteção, risco e consequências sensíveis.

### Neutral

- **Tinta Noturna** e **Tinta Noturna Suave** (`night-ink`, `night-ink-soft`): texto, marca, superfícies financeiras e a base da experiência operacional.
- **Papel Neblina** e **Papel Claro** (`mist-paper`, `bright-paper`): ambiente quente e camadas claras de trabalho.
- **Linha Silenciosa** e **Linha Noturna** (`quiet-line`, `night-line`): divisores técnicos de 1px nos modos claro e escuro.
- **Sálvia Suave** e **Névoa Noturna** (`muted-sage`, `night-muted`): texto secundário contextual em cada modo.
- **Branco Puro** (`pure-white`): contraste pontual em superfícies escuras e campos claros, nunca o ambiente dominante da landing.

**The Wake Signal Rule.** Verde Despertar identifica a ação mais importante ou um estado positivo; sua raridade preserva o significado.

**The Guidance, Not Action Rule.** Índigo de Jornada orienta seleção e progresso, mas não substitui Verde Despertar como chamada principal.

**The Contextual Neutral Rule.** Papel e sálvia sustentam superfícies claras; tinta e névoa noturna sustentam superfícies operacionais escuras sem trocar o vocabulário de sinais.

## Typography

**Display Font:** Geist, com Arial e sans-serif como fallback.  
**Body Font:** Geist, com Arial e sans-serif como fallback.  
**Label/Mono Font:** Geist Mono, com monospace como fallback.

**Character:** títulos grandes e compactos dão convicção sem estética eSports; corpo pequeno e respirado mantém custos, consequências e fases compreensíveis. Mono funciona como instrumento para chaves, regiões, valores e estados, não como voz decorativa.

### Hierarchy

- **Display** (peso 820, `clamp(42px, 4.2vw, 60px)`, line-height 0.98, tracking -0.04em): uma tese principal em superfícies persuasivas.
- **Headline** (peso 700, `clamp(40px, 5vw, 68px)`, line-height 1.02, tracking -0.04em): títulos de histórias amplas da landing.
- **Title** (peso 700, `clamp(34px, 4vw, 52px)`, line-height 1, tracking -0.04em): saudações, títulos de painel e decisões de alto nível na Console.
- **Body** (peso 400, 14px, line-height 1.65): instrução e explicação; variações observadas de 12 a 17px mudam com densidade e contexto.
- **Action** (peso 720, 14px): botões e links que representam decisões explícitas.
- **Label** (peso 680, 11px, tracking 0.08em): metadados operacionais curtos em Geist Mono.

**The Tracking Floor Rule.** Tracking negativo nunca passa de -0.04em; densidade vem de escala, peso e line-height, não de letras colidindo.

**The Metadata Is Instrumentation Rule.** Mono e caixa alta pertencem a dados realmente instrumentais; texto essencial e linguagem persuasiva permanecem em Geist sans.

## Layout

A landing usa navegação e hero em contêineres de até 1320px com gutters de 32px; seções narrativas usam até 1260px e 116px de respiro vertical. A World Table distribui estações laterais em torno de um centro dominante com colunas proporcionais de 0.8 / 1.7 / 0.8 e altura mínima de 600px. O ritmo recorrente segue 4, 8, 12, 16, 20, 24 e 32px.

A Console fixa uma sidebar de 224px, uma topbar sticky de 68px e conteúdo de até 1280px. A Command Table usa um centro de World dominante entre painéis laterais de amigos e Discord, precedido por uma faixa de status e seguido por Auto Sleep e um dock de ações. Cards de apoio entram depois desse núcleo, nunca como um mural de KPIs concorrentes.

Em 1120px as colunas reduzem; em 980px o World assume a primeira linha e estações ou painéis passam para baixo; em 760px as composições viram sequências lineares. A Console remove a sidebar, adota navegação inferior fixa de seis destinos, coloca o World primeiro e permite rolagem horizontal apenas onde a semântica tabular precisa ser preservada.

**The Scoped World Table Rule.** Use Mesa Central ou Command Table quando amigos, Discord, custo, proteção e ações pertencem ao mesmo ciclo de um World; onboarding, autenticação, configurações e tabelas podem usar composições próprias sem orbitar um centro artificial.

**The Collapse, Don't Squeeze Rule.** No mobile, grades viram pilhas e navegação muda de forma; conteúdo essencial não é apenas comprimido.

## Elevation & Depth

O sistema é plano por padrão e usa profundidade como sinal. Hairlines e mudança de tom separam o trabalho cotidiano; sombras rígidas criam tato em marca e ações; sombras ambientes pertencem ao terreno focal, onboarding e diálogos.

### Shadow Vocabulary

- **Marca tátil compacta** (`3px 3px 0 var(--ink)`): marca e símbolos guiados.
- **Ação tátil** (`4px 4px 0 var(--ink)`; hover `6px 6px 0 var(--ink)`): decisão prioritária em superfícies claras.
- **Destaque deslocado** (`12px 12px 0 var(--wake)`): um card escuro protagonista, como a Wallet demonstrativa.
- **Terreno ambiente** (`drop-shadow(0 24px 24px rgba(11, 16, 32, 0.14))`): separa o World circular do papel sem fazê-lo parecer um card.
- **Ambiente de onboarding** (`0 24px 65px rgba(11, 16, 32, 0.09)`): concentra a tarefa guiada.
- **Ambiente modal** (`0 35px 80px rgba(0, 0, 0, 0.45)`): fixa o diálogo sobre o backdrop escuro.

**The Flat-at-Work Rule.** Superfícies operacionais são planas em repouso; sombra não substitui borda, hierarquia ou espaçamento.

**The One Tactile Protagonist Rule.** Uma composição pode ter um protagonista com sombra deslocada; repetir o efeito em todo card destrói sua força.

## Shapes

Controles usam cantos de 8 a 12px; cards de trabalho usam 14 a 16px. Pills e círculos ficam reservados a status, presença, identidade e órbitas. A marca usa um quadrado assimétrico de 11px 11px 11px 4px; linhas de 1px, anéis e conectores sustentam a linguagem de mesa técnica.

O World circular pintado, recortado em transparência, é a silhueta focal. Ícones funcionais são SVGs lineares compactos com stroke de 1.8, terminais e junções arredondados; eles acompanham texto e nunca substituem rótulos essenciais.

**The Hairline Geometry Rule.** Bordas, órbitas e conectores usam linhas de 1px para estruturar relações; peso visual maior fica com o World, o título ou a ação.

**The Pill Means State Rule.** Formas totalmente arredondadas pertencem a status, Roles, badges e escolhas compactas, não a todo botão.

## Components

### Buttons

- **Shape:** cantos de 12px, altura mínima de 47px e padding horizontal de 21px.
- **Primary:** Verde Despertar com Tinta Noturna e sombra rígida de 4px; representa a decisão prioritária da superfície.
- **Hover / Focus:** sobe 2px e amplia a sombra para 6px em 150ms; foco visível usa outline índigo de 3px com offset de 3px.
- **Outline / Quiet:** outline inverte para tinta ou branco conforme o modo; quiet permanece transparente e mantém rótulo textual.
- **Disabled:** preserva a forma, reduz opacidade para 0.52 e remove a affordance de clique.

### Chips

- **Style:** pills compactas com padding de 7px por 10px e tipografia forte; superfície, texto e ponto mudam juntos.
- **State:** verde escuro para online, marrom âmbar para transições, azul-noturno para dormindo e coral escuro para atenção.

### Cards / Containers

- **Corner Style:** 14 a 16px para cards e painéis; superfícies de console usam fundos noturnos e borda de 1px.
- **Background:** Papel Claro em tarefas guiadas; Tinta Noturna ou camadas próximas em Wallet e Console.
- **Shadow Strategy:** planos por padrão; somente protagonistas e overlays recebem profundidade.
- **Internal Padding:** 20 a 34px, reduzido conforme aumenta a densidade operacional.

### Inputs / Fields

- **Light:** Branco Puro, borda neutra de 1px, raio de 10px, altura de 48px e padding horizontal de 13px.
- **Dark:** fundo azul-noturno profundo, borda de 1px, raio de 10px, altura de 45px e padding horizontal de 12px.
- **Focus / Error:** outline índigo de 3px com offset de 3px; erros trazem mensagem explícita e `role="alert"`.

### Navigation

A landing usa links discretos e entrada escura compacta. A Console usa sidebar de Tinta Noturna com item ativo em Verde Despertar; no mobile, os destinos permitidos migram para uma barra inferior fixa e o ativo combina cor, ícone e posição estável. A Role efetiva fica visível junto da identidade no desktop e abaixo do título da área no mobile. Áreas sem permissão não aparecem como controles desabilitados.

### Access and Invitation Choice

Convites separam duas decisões em opções grandes e mutuamente exclusivas: **Só jogar** entrega Player; **Gerenciar Console** revela uma segunda escolha de Role, limitada a Moderador ou Role personalizada. A opção escolhida usa hairline Verde Despertar e outline Índigo de Jornada, enquanto apenas o botão que cria o link recebe a superfície verde prioritária. No mobile, as escolhas e o campo de Role viram uma única pilha antes da ação.

**The Permission Is Visible Rule.** Mostre a Role efetiva e somente as áreas permitidas; não faça o usuário descobrir sua permissão por tentativa, erro ou botões mortos.

### World Table / Command Table

A World Table persuasiva ancora amigos, Discord, preço e backup ao redor de um grande terreno circular, com a ação Discord sobre o próprio World. A Command Table operacional conserva o World no centro, mas move estado para uma faixa superior e ações para um dock inferior; painéis laterais mostram presença e entrada pelo Discord. Ambas refluem com o World primeiro no mobile. Use essa assinatura somente quando as informações compartilham o ciclo do World.

## Do's and Don'ts

### Do:

- **Do** alternar Papel Neblina e Tinta Noturna conforme o modo sem trocar os sinais semânticos.
- **Do** reservar Verde Despertar para a ação prioritária, sucesso e presença online.
- **Do** aplicar Mesa Central e Command Table ao ciclo compartilhado de um World, mantendo outras jornadas livres para a composição adequada.
- **Do** combinar ícone linear, texto e estado para que informação não dependa apenas de cor.
- **Do** preservar foco visível, navegação por teclado, redução de movimento e contraste WCAG 2.2 AA.
- **Do** manter tracking negativo em -0.04em ou mais aberto.
- **Do** tornar a Role atual visível e esconder áreas que ela não pode usar.

### Don't:

- **Don't** transformar a narrativa principal da landing em um hero SaaS genérico seguido por uma grade de feature cards.
- **Don't** transformar a Console em um painel corporativo de nuvem ou um mural de KPIs.
- **Don't** obrigar onboarding, autenticação, configurações ou tabelas a imitar a composição orbital do World.
- **Don't** cobrir a interface com glassmorphism; blur pertence a camadas funcionais como topbar e backdrop.
- **Don't** adicionar sombra a todo card ou usar Verde Despertar e Índigo de Jornada como CTAs concorrentes.
- **Don't** inventar provas sociais, métricas, clientes ou imagens de jogo apresentadas como evidência real.
