# Automação de segurança no GitHub

O GameWake executa SAST, SCA e DAST em toda Pull Request destinada à `main` e em todo push na `main`. Os checks usam somente ferramentas gratuitas e o `GITHUB_TOKEN` efêmero criado automaticamente pelo GitHub Actions; nenhum token pessoal ou segredo adicional é necessário.

## Cobertura

| Categoria | Ferramenta | Cobertura | Gate |
|---|---|---|---|
| SAST | CodeQL `security-extended` | GitHub Actions, Python e JavaScript/TypeScript | High e Critical |
| SAST | Trivy | Terraform, outras configurações de infraestrutura e padrões de segredo | High e Critical |
| SCA | Trivy | Dependências de produção e desenvolvimento registradas nos lockfiles Python e npm | High e Critical |
| SCA | Dependency Review e `npm audit` | Mudanças de dependências em PR e auditoria npm já existentes no CI | Política do CI |
| DAST | OWASP ZAP Baseline | Console iniciada de forma isolada no runner e varredura passiva das rotas descobertas | Medium, High e Critical |

O DAST não acessa produção, AWS, banco ou credenciais reais. Ele inicia uma Console descartável em `localhost:3000`, espera a aplicação responder e executa o baseline passivo do ZAP.

O baseline usa `web/zap-rules.tsv` para excluir somente sinais não acionáveis: resposta dinâmica sem cache, identificação de aplicação moderna, ausência de SRI em assets versionados da própria origem e COEP, que é incompatível com a incorporação da Discord Activity. As proteções acionáveis continuam obrigatórias na resposta real: CSP com `frame-ancestors`, `X-Content-Type-Options`, `Referrer-Policy` e `Permissions-Policy`.

## Workflows

- `.github/workflows/security.yml`: executa Trivy e ZAP em paralelo e consolida o resultado no check obrigatório `Security gate`.
- `.github/workflows/codeql.yml`: executa a análise semântica do CodeQL e publica os resultados no code scanning do GitHub.
- `.github/workflows/security-issues.yml`: após os scanners terminarem, lê somente o artefato normalizado e sincroniza issues.

O workflow que analisa uma PR possui apenas `contents: read`. Ele nunca recebe permissão para criar issues. A escrita acontece em um `workflow_run` separado, que faz checkout explícito da automação confiável da branch padrão, não executa código da PR e valida tamanho, schema, categorias e severidades do artefato antes de usar o `GITHUB_TOKEN` com `issues: write`.

## Issues automáticas

Cada combinação de scanner e categoria mantém uma issue deduplicada com os labels `security` e `security-automation`. Uma nova detecção cria a issue; uma recorrência atualiza e reabre a mesma issue. O conteúdo inclui o workflow, commit, regra, severidade e localização, mas nunca o valor de um possível segredo.

A automação não fecha issues. Depois de corrigir o achado e confirmar os checks verdes, a pessoa responsável fecha a issue. Se a vulnerabilidade reaparecer, a próxima execução a reabre.

## Política de bloqueio

- CodeQL e Trivy bloqueiam High e Critical.
- ZAP bloqueia Medium, High e Critical porque headers e políticas do navegador fazem parte da proteção da Console.
- Falha, cancelamento ou ausência de relatório de qualquer scanner também falha o `Security gate`; o pipeline não interpreta scanner quebrado como aplicação segura.

Relatórios brutos ficam disponíveis como artefatos por 14 dias. O relatório consolidado e redigido `security-findings` fica disponível por 30 dias e alimenta as issues.

## Exceções auditáveis

Exceções conhecidas ficam em `.trivyignore.yaml`, limitadas por regra e caminho, com justificativa e data de expiração. O baseline atual aceita apenas decisões arquiteturais explícitas: IP público dinâmico exigido pelo servidor de jogo, egress dos runtimes para Steam/AWS/Discord e criptografia com chaves gerenciadas pela AWS para evitar custo fixo de KMS nos componentes que não guardam saves ou segredos do World.

Uma exceção expirada volta automaticamente ao gate. Não adicione um ID global, uma exceção sem motivo ou uma supressão para segredo. Achados novos continuam falhando o check e gerando issue.

## Validação local

Os contratos do normalizador e do isolamento de permissões rodam no gate principal:

```bash
.venv/bin/python -m pytest -q tests/test_security_automation.py
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make validate
npm --prefix web run test:e2e
```

O Trivy e o ZAP completos rodam no GitHub Actions para reproduzir o ambiente do check obrigatório. Não adicione tokens pessoais, chaves de scanners ou credenciais AWS a esses workflows.
