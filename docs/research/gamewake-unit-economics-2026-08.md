# GameWake: custos, margem e preco inicial

**Consulta:** 01/08/2026  
**Regiao:** AWS `us-east-1`  
**Recomendacao para a beta:** **R$ 5,50 por hora de World**

Este estudo usa somente fontes oficiais e a infraestrutura definida no repositorio. Os valores nao incluem suporte humano, contabilidade nem uma conclusao fiscal. Para planejamento conservador, os calculos usam **R$ 6,00/US$**, acima da PTAX venda de R$ 5,0773 de 31/07/2026, alem de reservas hipoteticas de **10% da receita para impostos** e **5% para risco/operacao**. A aliquota real deve ser validada com contador.

## Status das correcoes

As correcoes recomendadas por este estudo foram incorporadas ao codigo em 01/08/2026:

- o preco padrao do `palworld-small` passou para **R$ 5,50/h**;
- os polls globais de um e cinco minutos foram removidos;
- cada workflow de wake monitora somente o proprio World enquanto ele permanece online;
- exclusao de World e poda de backup removem todas as versoes S3 por `VersionId`;
- um lifecycle de sete dias limita versoes nao atuais residuais de `states/` e `backups/`.

Os valores de custo fixo abaixo descrevem o risco anterior e continuam validos para qualquer ambiente ainda nao atualizado. A economia so deve ser considerada realizada depois de `terraform apply` e da confirmacao de `ServerlessDatabaseCapacity = 0` durante a ociosidade.

## Conclusao executiva

- Manter os produtos de **R$ 25, R$ 50 e R$ 100** como credito 1:1 e destacar R$ 50 como "mais popular" e R$ 100 como "melhor custo-beneficio".
- Publicar o Runtime Palworld inicialmente por **R$ 5,50/h**. R$ 4,90/h pode funcionar depois de medir trafego e corrigir os custos invisiveis; **R$ 3,60/h e arriscado para a beta**.
- Dar prioridade ao Pix. O cartao deve ficar em 1x na beta, se o checkout permitir, por causa da taxa, prazo de 32 dias, chargeback e capital de giro.
- Antes de escalar, corrigir os polls que impedem o Aurora de pausar e a retencao ilimitada de versoes S3. Os dois problemas podem consumir a margem sem aparecer para o cliente.

## 1. Custo direto de um World

O Terraform cria uma `m6a.xlarge`, um volume gp3 de 50 GiB e um IPv4 publico por World ligado.

| Componente | Preco oficial | Custo por hora |
|---|---:|---:|
| EC2 Linux On-Demand `m6a.xlarge` | US$ 0,1728/h | US$ 0,172800 |
| EBS gp3, 50 GiB | US$ 0,08/GiB-mes | US$ 0,005479 |
| IPv4 publico | US$ 0,005/IP-h | US$ 0,005000 |
| Egress cobrado, cenario 0,5-1 GB/h | US$ 0,09/GB | US$ 0,045-0,090 |
| **Total por World, antes do control plane** |  | **US$ 0,228279-0,273279/h** |
| **Total com cambio conservador de R$ 6** |  | **R$ 1,37-1,64/h** |

Os primeiros 100 GB mensais de saida para a Internet sao gratuitos, agregados entre servicos e regioes da conta. A margem, porem, nao deve depender desse beneficio. O consumo real do Palworld precisa ser medido durante a beta.

Fontes: [EC2 On-Demand](https://aws.amazon.com/ec2/pricing/on-demand/), [catalogo oficial EC2/EBS de us-east-1](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.json), [EBS](https://aws.amazon.com/ebs/pricing/) e [IPv4/VPC](https://aws.amazon.com/vpc/pricing/).

## 2. Custo fixo anterior e piso apos a correcao

| Componente antes da correcao | Estimativa mensal |
|---|---:|
| Aurora ativo no piso de 0,5 ACU | US$ 43,80 |
| Aurora storage minimo, 10 GiB | US$ 1,00 |
| Secret gerenciado do Aurora | US$ 0,40 |
| Duas chaves KMS proprias | US$ 2,00 |
| **Piso mensal identificado** | **US$ 47,20 / R$ 283,20** |

Depois do deploy desta correcao, o piso identificado cai para aproximadamente **US$ 3,40 / R$ 20,40 por mes**, composto pelos 10 GiB iniciais do Aurora, Secrets Manager e duas chaves KMS. O compute do Aurora passa a acompanhar os periodos de uso real e a manutencao diaria; essa reducao depende de o cluster atingir capacidade zero em producao.

I/O, compute durante uso, logs, requests KMS e crescimento do banco ficam fora desse piso. Lambda, Step Functions, Scheduler, SQS, SNS, dashboard e os quatro alarmes tendem a caber nos respectivos Free Tiers durante a beta, mas os limites sao compartilhados pela conta e devem ser monitorados.

### Problema critico: o Aurora tende a nunca pausar

`terraform/gamewake-schedules.tf` executa `monitor_sessions` a cada minuto e `reconcile` a cada cinco minutos. Ambos abrem transacao e consultam o Aurora em `lambda/gamewake_worker.py`. O auto-pause esta configurado para 15 minutos sem conexoes.

Como existe atividade de banco em intervalos menores que 15 minutos, o cluster tende a permanecer ativo em pelo menos 0,5 ACU:

```text
0,5 ACU x US$ 0,12 x 730 horas = US$ 43,80/mes
```

Isso transforma um custo que deveria acompanhar o uso em aproximadamente **R$ 263/mes somente de compute** no cambio conservador. A correcao recomendada e executar o monitor somente enquanto houver Worlds online e eliminar o polling permanente quando nao houver operacoes. Depois da correcao, medir `ServerlessV2Usage` e `ServerlessDatabaseCapacity` antes de reduzir o preco.

Fonte: [precos do Aurora](https://aws.amazon.com/rds/aurora/pricing/) e [regras oficiais do auto-pause](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2-auto-pause.html).

## 3. AbacatePay e valor liquido dos produtos

O checkout atual oferece Pix e cartao. As taxas publicadas sao R$ 0,80 por Pix e, no cartao 1x, 3,5% + R$ 0,60.

| Produto | Liquido Pix | Taxa efetiva Pix | Liquido cartao 1x | Taxa efetiva cartao |
|---:|---:|---:|---:|---:|
| R$ 25 | R$ 24,20 | 3,20% | R$ 23,52 | 5,92% |
| R$ 50 | R$ 49,20 | 1,60% | R$ 47,65 | 4,70% |
| R$ 100 | R$ 99,20 | 0,80% | R$ 95,90 | 4,10% |

No cartao, 2x-6x custa 4% + R$ 0,60 e 7x-12x custa 4,5% + R$ 0,60. A parcela minima e R$ 10. Cartao 1x fica disponivel para saque apos 32 dias. Saque custa R$ 0,80 ate o 20o do mes e R$ 2,50 a partir do 21o; por isso, acumular e sacar em lote preserva margem.

Uma disputa de cartao perdida pode devolver o valor integral e adicionar R$ 20 de tarifa. A taxa real de chargeback do GameWake ainda nao existe; uma reserva de risco precisa ser recalibrada com dados reais. Reembolso e integral e a documentacao nao confirma devolucao da taxa original.

Fontes: [precos da AbacatePay](https://www.abacatepay.com/pricing), [termos oficiais](https://www.abacatepay.com/termos), [parcelamento](https://docs.abacatepay.com/pages/payment/installments), [saques](https://docs.abacatepay.com/pages/payouts/create) e [reembolsos](https://docs.abacatepay.com/pages/payment/refund).

## 4. Comparacao dos precos por hora

O cenario abaixo e deliberadamente severo:

- produto de R$ 25 pago no cartao 1x, a maior taxa efetiva dos tres pacotes: 5,92%;
- reserva hipotetica de 10% sobre a receita para impostos;
- reserva hipotetica de 5% para risco, creditos de disponibilidade e operacao;
- 0,5-1 GB/h de egress cobrado;
- cambio de R$ 6/US$;
- o piso atual de R$ 283,20/mes do control plane e tratado separadamente.

| Preco ao cliente | Valor restante/h apos gateway e reservas | Contribuicao/h antes dos fixos | Margem sobre preco antes dos fixos | Horas/mes para cobrir R$ 283,20 |
|---:|---:|---:|---:|---:|
| **R$ 3,60/h** | R$ 2,85 | R$ 1,21-1,48 | 33,5%-41,0% | **192-235 h** |
| **R$ 4,90/h** | R$ 3,87 | R$ 2,24-2,51 | 45,6%-51,1% | **113-127 h** |
| **R$ 5,50/h** | R$ 4,35 | R$ 2,71-2,98 | 49,3%-54,2% | **95-105 h** |

Formula usada:

```text
valor_restante = preco_hora x (1 - taxa_gateway - 10% - 5%)
contribuicao = valor_restante - custo_AWS_do_World
break_even_horas = custo_fixo_mensal / contribuicao
```

Em aproximadamente 100 World-hours pagas por mes, R$ 5,50/h fica perto do break-even conservador da arquitetura anterior; R$ 4,90/h ainda tenderia a dar prejuizo e R$ 3,60/h nao cobriria o piso antigo do control plane. Com 200 horas pagas, R$ 5,50/h geraria aproximadamente **R$ 259-R$ 313/mes** apos as reservas adotadas e o piso AWS anterior, mas antes de suporte humano e outras despesas empresariais.

Se os polls do Aurora forem corrigidos, o break-even cai materialmente. Esse ganho deve ser comprovado pela fatura e pelas metricas antes de ser convertido em desconto.

## 5. O que os tres produtos compram

Com o preco recomendado:

| Produto | Credito na Wallet | Horas aproximadas a R$ 5,50/h |
|---:|---:|---:|
| `credits-25` | R$ 25 | 4h32min |
| `credits-50` | R$ 50 | 9h05min |
| `credits-100` | R$ 100 | 18h11min |

Nao e necessario dar bonus de credito agora. Os pacotes maiores ja reduzem a taxa efetiva da AbacatePay para o GameWake. Primeiro valide conversao, consumo e suporte; depois um bonus pode ser testado dentro de um limite de CAC promocional separado.

## 6. Armazenamento: boa margem aparente, risco oculto grave

O S3 Standard custa US$ 0,023/GiB-mes. A franquia de 10 GiB custa cerca de US$ 0,23, ou R$ 1,38 por conta/mes no cambio conservador. Cobrar R$ 2/GiB-mes pelo excedente deixa margem bruta alta contra o storage atual.

Entretanto, o bucket possui versionamento e o lifecycle expira versoes antigas somente em `exports/`. O codigo remove `states/` e `backups/` sem `VersionId`. Em bucket versionado, isso cria um delete marker e preserva a versao antiga, que continua cobrada. O medidor do GameWake consulta objetos atuais, nao as versoes antigas; assim, pode considerar o espaco liberado e parar de cobra-lo enquanto a AWS continua cobrando.

Antes da beta paga, e necessario:

1. expirar versoes nao atuais de `states/` e `backups/` com uma politica de retencao explicita; ou
2. listar e excluir `VersionId`s na limpeza; e
3. reconciliar mensalmente bytes atuais, versoes nao atuais e delete markers com S3 Storage Lens ou inventario equivalente.

Fonte: [precos do S3](https://aws.amazon.com/s3/pricing/) e [exclusao de versoes de objetos](https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeletingObjectVersions.html).

## 7. Guardrails antes de cobrar clientes

1. Aplicar as correcoes de Aurora e S3 e confirmar o resultado nas metricas antes de ampliar a beta.
2. Publicar R$ 5,50/h e manter os creditos R$ 25/50/100 sem desconto.
3. Priorizar Pix; restringir cartao a 1x na beta, se possivel.
4. Sacar saldo da AbacatePay em lote e manter capital de giro para os 32 dias do cartao.
5. Criar AWS Budget e alarmes de custo para EC2, Aurora, S3, data transfer e KMS.
6. Medir por World: segundos EC2, bytes de egress, GiB atuais e versionados, forma de pagamento, reembolsos e creditos de SLA.
7. Recalcular a margem semanalmente no primeiro mes e mensalmente depois.
8. Validar regime tributario, emissao fiscal e aliquota efetiva com contador; os 10% deste estudo sao apenas uma hipotese de seguranca.

## Referencias adicionais oficiais

- [Lambda](https://aws.amazon.com/lambda/pricing/)
- [Step Functions](https://aws.amazon.com/step-functions/pricing/)
- [EventBridge Scheduler](https://aws.amazon.com/eventbridge/pricing/)
- [CloudWatch](https://aws.amazon.com/cloudwatch/pricing/)
- [SQS](https://aws.amazon.com/sqs/pricing/)
- [SNS](https://aws.amazon.com/sns/pricing/)
- [KMS](https://aws.amazon.com/kms/pricing/)
- [Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/)
- [Parameter Store](https://aws.amazon.com/systems-manager/pricing/)
- [PTAX/BCB](https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoMoedaPeriodo%28moeda%3D%40moeda%2CdataInicial%3D%40dataInicial%2CdataFinalCotacao%3D%40dataFinalCotacao%29?%40moeda=%27USD%27&%40dataInicial=%2707-01-2026%27&%40dataFinalCotacao=%2708-01-2026%27&%24format=json)
