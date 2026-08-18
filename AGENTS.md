# AGENTS.md — GameWake

Este arquivo define como agentes devem trabalhar neste repositório. Ele vale para todo o projeto, salvo quando um `AGENTS.md` mais específico em um subdiretório trouxer regras adicionais.

## Como colaborar com Leonardo

- Responda e envie atualizações em português do Brasil.
- Comece pelo resultado ou pela evidência mais importante; explique detalhes técnicos somente quando ajudarem a decidir ou verificar.
- Trabalhe com autonomia. Não pare para perguntar algo que possa ser descoberto com segurança no repositório, nos testes, nos logs ou nos outputs da infraestrutura.
- Quando uma decisão realmente mudar produto, custo, segurança ou escopo, apresente a evidência, a suposição e o impacto antes de prosseguir.
- Mantenha atualizações curtas durante trabalhos longos. Não deixe uma execução sem contexto por mais de aproximadamente 60 segundos.
- Não declare um erro corrigido apenas porque o código parece correto. Reproduza o sintoma exato, aplique a correção e execute novamente a mesma jornada.
- Quando Leonardo relatar um erro de produção, investigue os IDs, horários, logs e estados reais antes de formular a correção.
- Para bugs, crie primeiro um sinal pass/fail pequeno e determinístico. Escreva o teste de regressão antes do fix quando existir um seam correto.
- Para mudanças de UX, não esconda pré-requisitos em documentação ou comandos. A própria tela deve explicar o estado atual, a próxima ação e por que uma ação está indisponível.
- Preserve alterações que já estavam no worktree. `.idea/palworld-server.iml` é um arquivo pessoal e não deve ser staged, alterado ou incluído em commits.
- Não crie commits, branches, PRs, deploys ou mudanças externas quando o pedido for apenas análise. Quando o pedido incluir implementação completa, prossiga até validação e publicação conforme as regras abaixo.

## Política atual de entrega

- Durante a construção ativa do MVP, a preferência vigente do Owner é publicar lotes concluídos e validados diretamente na `main`.
- Só crie branch ou Pull Request se Leonardo pedir novamente de forma explícita.
- Nunca force push, reescreva histórico ou use comandos destrutivos de Git.
- Faça stage somente dos arquivos pertencentes ao ajuste. Revise `git diff --cached` antes do commit.
- Use Conventional Commits, com assunto curto que registre a causa ou intenção real.
- Depois do push, acompanhe Continuous Integration e CodeQL até ambos terminarem. Uma publicação não está concluída com checks pendentes ou falhando.
- A política de proteção do GitHub continua sendo uma defesa importante. Um bypass administrativo deve acontecer somente dentro da instrução explícita vigente do Owner, nunca por conveniência do agente.

## Verdade do produto

Leia `CONTEXT.md`, `CONTEXT-MAP.md`, `docs/GAMEWAKE_FOUNDATION.md` e o contexto da área alterada antes de mudar regras de domínio.

- GameWake permite que grupos de amigos mantenham Worlds persistentes e paguem apenas pela infraestrutura temporária usada para jogar.
- Evite descrever o produto como painel de hospedagem, wrapper de nuvem ou bot de Palworld.
- `World` é o recurso persistente com progresso, configuração e Backups.
- `Runtime` é a infraestrutura temporária e descartável que executa um World.
- Discord é uma superfície de interação e integração; não é o dono da Account nem a fonte de autorização.
- A GameWake Console é uma única experiência responsiva usada na Web e como Discord Activity.
- O caso simples deve continuar simples para um grupo de amigos. Recursos avançados não podem poluir o onboarding comum.
- Palworld é o único Game Template do MVP, mas novas implementações devem respeitar os contratos multi-game existentes.

## Accounts, acesso e roles

- Uma `GameWake Account` é o perímetro de propriedade, acesso e responsabilidade financeira de um grupo.
- Um `User` pode ter várias `Linked Identities` e várias `Memberships`.
- Convite não cria acesso silenciosamente: o usuário precisa aceitar antes de a Membership ser criada.
- Cada Membership possui no máximo uma Role por vez. Trocar a Role substitui a anterior; remover a Role deixa a Membership sem permissões. Policies continuam allow-only: tudo que a Role não concede é negado e não existe `DENY` explícito.
- Roles predefinidas internas: `Owner`, `Manager` e `Player`. Na interface pt-BR, `Manager` pode ser apresentado como **Moderador** para corresponder ao vocabulário esperado pelos usuários.
- `Owner`: propriedade, membros, roles, integrações, Wallet, budgets e ações sensíveis.
- `Manager`/Moderador: opera e configura os Worlds permitidos, sem controlar propriedade, membros ou finanças.
- `Player`: vê o necessário para jogar e executa ações cotidianas seguras nos Worlds permitidos.
- Custom Roles continuam disponíveis em uma área avançada e combinam permissões existentes com Resource Scopes.
- Toda Account deve conservar pelo menos um Owner.
- Revogar acesso deve invalidar imediatamente autorização do Console e acesso correspondente no jogo.
- A interface deve ser derivada das permissões efetivas, não apenas do nome da role. O backend continua sendo a autoridade final.
- Acesso “somente jogar” deve levar a pessoa diretamente às Connection Details e ações permitidas, sem exigir que ela aprenda a administrar a Console.
- Acesso “gerenciar” deve autenticar o usuário, aceitar o convite e mostrar as ferramentas autorizadas pela role e pelo scope concedidos.

## Experiência obrigatória

- Estados públicos de World: `Dormindo`, `Acordando`, `Online`, `Indo dormir` e `Precisa de atenção`.
- Nunca use um countdown inventado. Operation Progress deve refletir fases persistidas da World Operation.
- Ao iniciar um World, a Console deve continuar acompanhando a operação iniciada no backend mesmo após reload, troca de aba ou nova consulta.
- Se o Runtime foi criado mas o fluxo ainda não terminou, a UI deve mostrar a fase real, última atualização e uma mensagem acionável; não deve voltar silenciosamente a “Dormindo”.
- Botões indisponíveis precisam explicar o pré-requisito. Erros de API devem aparecer em linguagem humana e manter detalhes técnicos redigidos nos logs.
- Selecionar outra Discord Guild ou Account deve invalidar dados dependentes anteriores; nunca misture Worlds entre contas.
- Inputs, selects e botões não podem se sobrepor em desktop ou mobile.
- Owner, Moderador e Player devem ver experiências proporcionais às permissões:
  - Player: status, entrada no jogo, contribuição permitida e ações seguras, sem controles administrativos decorativos.
  - Moderador: operação, configuração, logs e Backups dentro do scope, sem membros, roles ou finanças.
  - Owner: visão completa, incluindo acesso, roles, Wallet, budgets, integrações e ações sensíveis.
- Não renderize uma ação proibida apenas para deixá-la falhar depois. Quando for útil ensinar a capacidade, mostre-a bloqueada com explicação e caminho para pedir acesso; caso contrário, omita-a.
- Toda jornada de convite deve dizer claramente: quem foi convidado, para quê, qual role será recebida, como aceitar e qual é o próximo passo.
- Connection Details, IP, senha e URLs assinadas nunca aparecem em cards públicos, mensagens de canal ou Activity Events.

## Ciclo de vida e invariantes de World

- Só pode existir uma World Operation ativa por World.
- Repetir uma ação deve observar ou retomar a mesma operação; não pode criar outro Runtime, outra reserva ou outra cobrança.
- Cada efeito externo recebe chave de idempotência durável.
- Um World só fica `Online` após saúde real do jogo e Connection Details válidos.
- Se um wake nunca ficar Online, aplique a Wake Guarantee e estorne a tentativa.
- Sono seguro exige save, persistência validada e Recovery Guarantee antes de liberar a última cópia recuperável.
- Nunca destrua a última cópia recuperável de um World.
- Antes de terminar uma EC2 de produção, confirme se ela é descartável e se o estado durável necessário está protegido.

## Billing e AbacatePay

- Wallet é pré-paga, compartilhada pela Account, em BRL e nunca pode ficar negativa.
- O ledger interno imutável é a fonte da verdade; AbacatePay confirma contribuições, mas não define o saldo.
- O valor exibido como preço por hora é diferente de uma Usage Reservation temporária. A UI deve nomear e explicar ambos corretamente.
- O valor pago na AbacatePay deve coincidir exatamente com o pacote antes de creditar a Wallet.
- Webhooks exigem `webhookSecret`, assinatura HMAC-SHA256 Base64 do corpo bruto, deduplicação e conciliação.
- Não use Stripe. O Payment Provider escolhido para o MVP é AbacatePay API v2.
- Não implemente pós-pago ou Auto Recharge no MVP.
- Em diagnósticos de wake, confira sempre Runtime Usage, reserva, Wake Guarantee e efeito líquido no ledger.

## Ambientes e segredos

### Local

- Python: `.venv/bin/python`; dependências em `lambda/requirements*.txt`.
- Node: projeto da Console em `web/`, com lockfile; use `npm --prefix web ci` para instalação reproduzível.
- Console local: `http://localhost:3000` com `npm --prefix web run dev`.
- `?demo=1` serve apenas para demonstração local. Nunca faça contas reais caírem silenciosamente em dados demo.
- Use `.env.example`, `web/.env.example` e `terraform/terraform.tfvars.example` como contrato. Não leia ou imprima arquivos reais de segredo sem necessidade explícita.

### Produção

- Ambiente Terraform: `prod`; região padrão atual: `us-east-1`.
- Runtime atual do Palworld: `m6a.xlarge`, sempre criado pelo Launch Template gerenciado.
- Control plane: Lambda Function URL + Aurora PostgreSQL Serverless v2 Data API + Step Functions Standard.
- Dados de World: S3 privado, versionado e criptografado por KMS.
- Administração de Runtime: SSM. SSH permanece fechado por padrão.
- Segredos de Discord e AbacatePay entram no SSM Parameter Store por `scripts/configure-secrets.sh`.
- Nunca coloque `.env`, `.tfvars`, Terraform state, planos, tokens, senhas, chaves HMAC, arquivos de Wallet ou pacotes Lambda no Git.
- Não copie segredos para comentários, logs, tickets, mensagens do Discord ou respostas ao usuário.

## Terraform e AWS

- Prefira `scripts/deploy.sh plan` e `scripts/deploy.sh apply`; eles empacotam, inicializam, validam e preservam o plano revisado.
- Antes de apply, apresente o resumo: recursos a criar, atualizar, substituir e destruir. Destaque IAM, exposição pública, banco, retenção e impacto de custo.
- `APLICAR` autoriza o plano revisado, não uma mutação diferente. Destruição exige autorização explícita e inequívoca para aquele escopo.
- Produção usa Aurora PostgreSQL Serverless v2 + Step Functions Standard. Não reintroduza modo legacy.
- A versão do Aurora deve ser consultada/validada para a região; não fixe uma versão indisponível.
- Migrations precisam tolerar Aurora retomando de auto-pause e ser idempotentes.
- User-data EC2 tem limite de 16 KiB. Scripts grandes devem ser empacotados/baixados ou incorporados de forma compatível com esse limite; valide o tamanho no plan.
- Launch Template é a única origem aprovada para Runtimes. Não crie EC2 manual fora dele, exceto uma instância diagnóstica explicitamente autorizada e etiquetada.
- Instâncias diagnósticas usam `GameWakeManaged=true` e uma tag clara de diagnóstico, e devem ser terminadas em qualquer caminho de saída.
- Ao final de um diagnóstico, consulte instâncias `pending`, `running`, `stopping` e `stopped` para provar que nada ficou cobrando.
- Depois do apply, execute `terraform plan -detailed-exitcode` e confirme `No changes` antes de declarar produção reconciliada.
- Para operação travada, correlacione Account ID, World ID, Operation ID, execução Step Functions, Lambda worker, EC2, SSM, DLQ, operação persistida e ledger.
- Não edite fases diretamente no banco, não repita `RunInstances` e não apague mensagens da DLQ sem reconciliação.
- Logs temporários de debug devem ter prefixo único `[DEBUG-...]` e ser removidos antes do commit.

## Validação obrigatória

Use o menor teste relevante durante o ciclo e termine com os gates reais:

```bash
make validate
npm --prefix web run test:e2e
```

- `make validate` deve cobrir Pytest, Ruff, build/testes da Console, Bash/ShellCheck, pacote Lambda reproduzível e Terraform validate.
- Mudanças em persistência devem rodar os contratos PostgreSQL reais com `GAMEWAKE_TEST_DATABASE_URL` apontando apenas para banco isolado de testes.
- Mudanças de UI devem ser verificadas em desktop e mobile e incluir estados loading, vazio, sucesso, erro, permissão negada e dados longos.
- Mudanças em autorização exigem testes positivos e negativos no backend e E2E por role. Esconder um botão não substitui autorização da API.
- Mudanças em World Operations exigem teste de retomada/reload e confirmação de que ações repetidas não duplicam Runtime, reserva nem cobrança.
- Mudanças Terraform exigem `fmt`, `validate`, revisão do plan, apply autorizado e plan final sem drift.
- Não reduza o gate para uma suíte estreita quando a reclamação atravessa API, banco, workflow e Console.

## Publicação da Console

- A Console publicada e a Discord Activity usam a mesma aplicação e API.
- `NEXT_PUBLIC_GAMEWAKE_API_URL`, `NEXT_PUBLIC_DISCORD_APPLICATION_ID` e `NEXT_PUBLIC_SITE_URL` precisam estar coerentes com os outputs e com `gamewake_console_url`.
- Se a origem mudar, atualize OAuth e CORS antes de aceitar usuários.
- Para publicar em Sites, use o fluxo oficial de build/hosting do Sites e valide a versão pública, não apenas o build local.
- Depois do deploy, faça smoke test da rota pública, login Discord, callback, troca de Account/Guild, Console e jornada alterada.

## Checklist para todo pedido novo

1. Leia este arquivo, o contexto do domínio e os ADRs da área.
2. Verifique o worktree e preserve mudanças do usuário.
3. Derive requisitos observáveis do pedido, inclusive UX e estados de erro.
4. Para bug, crie e execute uma reprodução red-capable antes da hipótese.
5. Liste hipóteses falsificáveis quando a causa ainda não estiver provada.
6. Implemente a menor mudança que satisfaça o requisito completo, não uma versão reduzida do objetivo.
7. Rode testes focados e depois os gates completos proporcionais ao escopo.
8. Inspecione UI real em desktop/mobile quando houver frontend.
9. Revise segurança, autorização, cobrança, idempotência e recursos órfãos.
10. Publique conforme a política vigente e acompanhe checks/deploy.
11. Entregue um resumo com causa, mudança, evidência, estado de produção e qualquer pendência real.
