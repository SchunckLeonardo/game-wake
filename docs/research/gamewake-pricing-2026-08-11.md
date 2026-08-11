# GameWake: preco menor com margem sustentavel

**Data da consulta:** 11/08/2026

**Regiao:** AWS `us-east-1`

**Escopo:** Runtime Palworld Linux atual, AbacatePay API v2 e custos variaveis diretamente associados a uma sessao.
**Recomendacao executiva:** testar **R$ 2,49 por hora** no perfil atual `m6a.xlarge`; nao reduzir o preco recorrente para R$ 1,99 antes de medir egress, custo fixo por hora vendida e carga real.

## Resposta curta

R$ 5,50/h nao e necessario para pagar a infraestrutura variavel atual. O Runtime direto confirmado custa **US$ 0,18328/h** antes de egress e control plane. Incluindo uma estimativa conservadora do monitor por minuto, Aurora ativo no piso, Lambda e 0,1 GB/h de egress cobrado, o custo usado para decisao e **US$ 0,22729/h**, ou **R$ 1,25/h** com cambio hipotetico de R$ 5,50/US$.

Nesse cenario:

- a **R$ 2,49/h**, a contribuicao e **R$ 1,16/h (46,6%)** depois da taxa Pix do menor pacote, antes de tributos e custos fixos;
- a **R$ 1,99/h**, cai para **R$ 0,68/h (34,0%)**;
- depois de uma reserva provisoria adicional de 15% da receita para tributos, suporte, garantias e risco, restam aproximadamente **R$ 0,79/h (31,6%)** a R$ 2,49 e **R$ 0,38/h (19,0%)** a R$ 1,99.

Portanto, **R$ 2,49/h e o ponto de partida equilibrado**. Para quatro amigos, equivale a aproximadamente **R$ 0,62 por jogador-hora**, sem mensalidade. R$ 1,99/h pode ser usado como promocao limitada da beta, mas tem pouca protecao contra cambio, trafego ou baixa utilizacao.

## 1. O que esta confirmado no produto

O Terraform define `m6a.xlarge`, 50 GiB de EBS `gp3`, volume descartado ao terminar e um IPv4 publico por Runtime ([`variables.tf`](../../terraform/variables.tf), [`gamewake-runtime.tf`](../../terraform/gamewake-runtime.tf)). A AMI atual e `amd64`, portanto familias Graviton/ARM nao sao substitutas diretas ([`ec2.tf`](../../terraform/ec2.tf)).

O codigo e o plano Terraform atuais ja definem `palworld-small = 2.49` ([`variables.tf`](../../terraform/variables.tf)); a producao ainda exibe R$ 5,50/h porque esse plano nao foi aplicado. A cobranca GameWake mede o Runtime por segundo, com minimo de 60 segundos, e inclui preparo e sono seguro; nao e apenas o tempo em que jogadores estao conectados.

O checkout implementado hoje oferece somente `PIX` ([`abacatepay.py`](../../gamewake/billing/abacatepay.py)). Assim, cartao nao entra no caso-base desta nota.

## 2. Tarifas AWS confirmadas

Os precos abaixo foram consultados pela [AWS Price List Query API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-price-list-query-api.html), com publicacao do catalogo EC2 em 10/08/2026 e vigencia em 01/08/2026. Filtros: Linux, Shared tenancy, `capacitystatus=Used`, `us-east-1`.

| Instancia | vCPU | Memoria | On-Demand US$/h | Diferenca de compute | Adequacao imediata |
| --- | ---: | ---: | ---: | ---: | --- |
| `m6a.xlarge` | 4 | 16 GiB | **0,17280** | base | **Sim; perfil atual** |
| `m6a.large` | 2 | 8 GiB | 0,08640 | -50,0% | Nao; reduz CPU e RAM pela metade |
| `r6a.large` | 2 | 16 GiB | 0,11340 | -34,4% | Somente benchmark; preserva RAM, reduz CPU |
| `r7a.large` | 2 | 16 GiB | 0,15215 | -11,9% | Mesmo risco do `r6a`, com economia menor |
| `c6a.xlarge` | 4 | 8 GiB | 0,15300 | -11,5% | Nao; reduz RAM pela metade |
| `c7a.xlarge` | 4 | 8 GiB | 0,20528 | +18,8% | Nao; mais caro e menos RAM |
| `m7a.xlarge` | 4 | 16 GiB | 0,23184 | +34,2% | Compativel em capacidade, mas mais caro |
| `t3a.xlarge` | 4 | 16 GiB | 0,15040 | -13,0% | Evitar: CPU burstable e custo de creditos |
| `m7g.xlarge` | 4 | 16 GiB | 0,16320 | -5,6% | Nao; Graviton/ARM, enquanto a AMI e `amd64` |

O catalogo oficial reproduzivel esta em [Amazon EC2 Price List para `us-east-1`](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.json). A AWS cobra EC2 Linux On-Demand por segundo, com minimo de 60 segundos ([EC2 On-Demand](https://aws.amazon.com/ec2/pricing/on-demand/)). Em instancias T2/T3 Unlimited, CPU excedente custa US$ 0,05 por vCPU-hora no Linux; por isso a pequena economia nominal da `t3a.xlarge` nao e previsivel para um game server.

Outros valores confirmados:

| Componente | Tarifa oficial | Quantidade atual | Custo normalizado |
| --- | ---: | ---: | ---: |
| EBS `gp3` | US$ 0,08/GiB-mes | 50 GiB | **US$ 0,00548/h** |
| IPv4 publico | US$ 0,005/IP-h | 1 | **US$ 0,00500/h** |
| Step Functions Standard | US$ 0,000025/transicao | variavel | conforme fluxo |
| Lambda requests | US$ 0,20/milhao | variavel | conforme fluxo |
| Aurora PostgreSQL Serverless | US$ 0,06/ACU-h no catalogo vigente | variavel | conforme ACU e concorrencia |
| S3 Standard | US$ 0,023/GiB-mes | mundo e Backups | custo persistente, nao de Runtime |
| S3 PUT/LIST | US$ 0,005/mil | por restore/backup | desprezivel isoladamente |
| S3 GET | US$ 0,004/10 mil | por restore/backup | desprezivel isoladamente |

Fontes: [EBS](https://aws.amazon.com/ebs/pricing/), [VPC/IPv4](https://aws.amazon.com/vpc/pricing/), [Step Functions](https://aws.amazon.com/step-functions/pricing/), [Lambda](https://aws.amazon.com/lambda/pricing/), [Aurora](https://aws.amazon.com/rds/aurora/pricing/) e [S3](https://aws.amazon.com/s3/pricing/). O Price List do Aurora publicado em 11/08/2026 registra SKU `HK9832HSTD4XQSKN` a US$ 0,06/ACU-h, vigente desde 01/08/2026; a pagina textual da AWS ainda contem exemplos antigos a US$ 0,12/ACU-h. Para faturamento, esta nota usa o catalogo mais recente, mas o Cost and Usage Report deve confirmar a primeira fatura.

### Custo direto do Runtime

```text
EC2 m6a.xlarge    US$ 0,172800/h
EBS gp3 50 GiB    US$ 0,005479/h
IPv4 publico      US$ 0,005000/h
---------------------------------
Runtime direto    US$ 0,183279/h
```

Reduzir o disco de 50 para 30 GiB economizaria apenas cerca de **US$ 0,00219/h**, ou **R$ 0,012/h** a R$ 5,50/US$. Nao e a alavanca principal e so deve ocorrer depois de validar espaco de atualizacao, save e backup.

## 3. Egress e control plane: custos que nao podem ser omitidos

### Egress

A AWS inclui 100 GB/mes de saida para a Internet, agregados entre servicos e regioes; depois disso, o primeiro tier custa **US$ 0,09/GB**. Entrada e transferencia direta EC2-S3 na mesma regiao nao sao cobradas ([EC2 Data Transfer](https://aws.amazon.com/ec2/pricing/on-demand/)).

Nao existe medicao de producao suficiente nesta pesquisa para afirmar quantos GB/h o Palworld usa. A formula correta e:

```text
custo_egress_USD_h = max(egress_cobrado_GB_h, 0) x 0,09
```

Sensibilidade depois de esgotada a franquia, a R$ 5,50/US$:

| Egress cobrado | Adicional por hora |
| ---: | ---: |
| 0,1 GB/h | R$ 0,05 |
| 0,5 GB/h | R$ 0,25 |
| 1,0 GB/h | R$ 0,50 |

A margem nao deve depender da franquia. Medir bytes de saida por Runtime no Cost and Usage Report ou telemetria equivalente antes de reduzir abaixo de R$ 2,49.

### Control plane por sessao

Enquanto um World esta Online, o workflow espera 60 segundos, invoca o monitor e decide se deve continuar ([`world-operation.asl.json`](../../terraform/state-machines/world-operation.asl.json)). Isso representa aproximadamente 180 transicoes de Step Functions e 60 invocacoes Lambda por hora, alem de chamadas ao Aurora.

O seguinte bloco e **estimativa de quantidade**, nao preco confirmado:

| Componente | Premissa conservadora de um unico World | Estimativa US$/h |
| --- | --- | ---: |
| Step Functions | 180 transicoes/h | 0,00450 |
| Lambda | 60 invocacoes/h, 512 MiB, 1 s cada | 0,00051 |
| Aurora | 0,5 ACU durante a sessao | 0,03000 |
| **Control plane continuo estimado** |  | **0,03501** |

O Aurora e compartilhado: com varios Worlds simultaneos, esse custo nao deve ser somado integralmente a cada World. Com apenas um World, a consulta por minuto impede o auto-pause de 15 minutos durante a sessao. Wake e safe sleep ainda adicionam poucas dezenas de transicoes, invocacoes, S3/KMS requests e logs; adotar **US$ 0,0015 por sessao** como buffer inicial e substituir pelo valor observado.

### Custo de decisao usado nesta nota

```text
Runtime direto                         US$ 0,183279/h
Control plane continuo estimado        US$ 0,035012/h
Egress cobrado de 0,1 GB/h             US$ 0,009000/h
-----------------------------------------------------
Custo variavel de decisao              US$ 0,227291/h
Conversao a R$ 5,50/US$                R$  1,250102/h
```

## 4. AbacatePay: custo e como dilui-lo

A AbacatePay publica **R$ 0,80 por Pix recebido**, sem percentual, mensalidade ou adesao ([Precos](https://www.abacatepay.com/pricing), [Pix](https://www.abacatepay.com/pix)). Como a taxa acontece na contribuicao para a Wallet, nao em cada hora jogada, pacotes maiores melhoram a margem sem aumentar o preco por hora:

| Credito comprado | Liquido recebido | Taxa efetiva |
| ---: | ---: | ---: |
| R$ 25 | R$ 24,20 | **3,2%** |
| R$ 50 | R$ 49,20 | **1,6%** |
| R$ 100 | R$ 99,20 | **0,8%** |

Saque para Pix de mesma titularidade custa R$ 0,80 do primeiro ao vigesimo saque do mes e R$ 2,50 a partir do 21o, segundo [Precos](https://www.abacatepay.com/pricing) e [Termos](https://www.abacatepay.com/termos). Sacar em lote reduz a incidencia. A calculadora oficial diverge ao dizer que o aumento ocorre no 22o; usar 20 saques baratos no planejamento e confirmar contratualmente.

Reembolso via API v2 e integral e debita o saldo da loja ([documentacao de reembolso](https://docs.abacatepay.com/pages/payment/refund)). A documentacao publica nao confirma taxa adicional nem devolucao da taxa Pix original: nao assumir custo zero. Em producao, reconciliar o `platformFee` efetivamente devolvido pela API v2 em vez de confiar em exemplos estaticos ([Pix transparente](https://docs.abacatepay.com/pages/transparents/create)).

## 5. Contas de R$ 2,49 e R$ 1,99

Premissas:

- custo AWS de decisao: **R$ 1,2501/h**;
- pagamento: pior caso atual, pacote Pix de R$ 25, taxa efetiva de **3,2%**;
- reserva adicional de estresse: **15% da receita** para tributos, suporte, Wake/Recovery Guarantee, indisponibilidade e risco. Essa reserva nao e aliquota fiscal confirmada;
- custos fixos mensais ainda nao estao incluidos.

| Preco | Receita apos Pix | Contribuicao antes da reserva | Margem antes da reserva | Contribuicao apos reserva de 15% | Margem apos reserva |
| ---: | ---: | ---: | ---: | ---: | ---: |
| **R$ 2,49/h** | R$ 2,4103 | **R$ 1,1602** | **46,6%** | **R$ 0,7867** | **31,6%** |
| **R$ 1,99/h** | R$ 1,9263 | **R$ 0,6762** | **34,0%** | **R$ 0,3777** | **19,0%** |
| R$ 5,50/h em producao antes do apply | R$ 5,3240 | R$ 4,0739 | 74,1% | R$ 3,2489 | 59,1% |

Formulas:

```text
contribuicao_bruta = preco x (1 - 0,032) - 1,2501
contribuicao_estresse = preco x (1 - 0,032 - 0,15) - 1,2501
```

Teste de estresse:

| Cenario | Custo AWS/h | R$ 2,49: contribuicao apos reserva | R$ 1,99: contribuicao apos reserva |
| --- | ---: | ---: | ---: |
| US$ a R$ 5,50; 0,1 GB/h | R$ 1,25 | R$ 0,79 (31,6%) | R$ 0,38 (19,0%) |
| US$ a R$ 6,00; 0,1 GB/h | R$ 1,36 | R$ 0,67 (27,0%) | R$ 0,26 (13,3%) |
| US$ a R$ 6,00; 0,5 GB/h | R$ 1,58 | R$ 0,46 (18,4%) | R$ 0,05 (2,4%) |

R$ 1,99 praticamente perde toda a folga no ultimo cenario. R$ 2,49 ainda absorve a variacao sem voltar ao preco de R$ 5,50.

## 6. Custos fixos e margem liquida

As margens acima sao **margens de contribuicao**, nao lucro liquido. Ainda precisam pagar:

- chaves KMS, Secrets Manager, armazenamento e I/O do Aurora;
- S3 de Worlds, Backups, versoes nao atuais e AMI snapshots;
- CloudWatch, dominios, Sites e demais servicos compartilhados;
- suporte, contabilidade, emissao fiscal, tributos reais, CAC, reembolsos e creditos;
- capacidade desperdicada por falha de wake ou sono seguro demorado.

O impacto e inversamente proporcional ao volume vendido:

```text
custo_fixo_por_hora = custo_fixo_mensal / World-hours pagas no mes
lucro_estimado = contribuicao_por_hora x World-hours - custos_fixos
```

Exemplo meramente ilustrativo: R$ 100/mes de custos fixos representam R$ 1,00/h com 100 horas vendidas, mas R$ 0,20/h com 500 horas. Por isso o preco deve ser revisto usando a fatura, Cost and Usage Report e horas capturadas no ledger, nao apenas a tabela publica da AWS. A carga tributaria real deve ser validada com contador.

## 7. Onde reduzir custo sem piorar a experiencia

### Agora

1. **Reduzir o preco para R$ 2,49/h, mantendo `m6a.xlarge`.** E uma queda de 54,7% para o cliente sem trocar a capacidade ja validada.
2. **Manter Pix e pacotes R$ 25/50/100.** Destacar R$ 50 dilui a taxa para 1,6%; nao criar taxa de ativacao por sessao.
3. **Medir egress e custo por World-hour.** Esses dados decidem se R$ 2,49 pode cair ou precisa de ajuste cambial.
4. **Aplicar piso de preco revisado mensalmente**, sem mudar o Session Quote de uma sessao ativa.

Um piso com margem-alvo `m` pode ser calculado por:

```text
preco_minimo = (AWS_BRL_h + custo_fixo_alocado_h) /
               (1 - taxa_pagamento - reserva_tributaria_operacional - m)
```

Com AWS de R$ 1,25/h, taxa de 3,2%, reserva de 15% e margem-alvo de 25%, o piso e aproximadamente **R$ 2,20/h**. R$ 2,49 cria espaco para arredondamento, sessoes ruins e custo fixo ainda pequeno.

### Depois de benchmark

- **`r6a.large`:** e a melhor candidata de right-sizing, pois reduz compute em 34,4% e preserva 16 GiB. Nao atende o mesmo envelope de CPU do perfil atual. Testar startup, p95 de CPU/memoria, estabilidade com o numero-alvo de jogadores, save, backup e recuperacao antes de oferecer.
- **Spot `m6a.xlarge`:** o snapshot oficial de 11/08/2026 variou de **US$ 0,0704 a US$ 0,0887/h**, economia de 48,7%-59,3% apenas no compute. Spot pode ser interrompido com aviso de dois minutos; a AWS recomenda tolerancia a falhas, flexibilidade entre AZs e varios tipos ([best practices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-best-practices.html)). O GameWake deve primeiro implementar checkpoint acionado por rebalance/interruption, EventBridge, safe release idempotente, multiplas subnets/AZs e fallback On-Demand. Ate la, Spot viola a expectativa de um World persistente seguro.
- **Savings Plans:** podem reduzir Compute Savings Plans em ate 66% e EC2 Instance Savings Plans em ate 72%, mas exigem compromisso em US$/hora por um ou tres anos e nao podem ser cancelados ([comparacao oficial](https://docs.aws.amazon.com/savingsplans/latest/userguide/sp-ris.html)). Para um produto que dorme quando nao ha jogadores, comprar compromisso antes de existir carga-base transfere o risco ao GameWake. Avaliar depois de 60-90 dias e comprometer apenas o piso agregado realmente usado, nunca a capacidade de pico.

## 8. Decisao proposta e gates

**Proposta:** `palworld-small` a **R$ 2,49/h** na beta, sem mensalidade e mantendo `m6a.xlarge`.

Antes de considerar R$ 1,99/h permanente:

1. pelo menos 30 dias de Cost and Usage Report com EC2, EBS, IPv4, egress, Aurora e logs;
2. custo fixo mensal dividido pelas World-hours pagas;
3. taxa Pix efetiva por mix de pacotes e `platformFee` conciliado;
4. aliquota tributaria real validada;
5. Wake Guarantee, Availability Credits, falhas e suporte incluidos;
6. margem de estresse minima de 25% com cambio e egress adversos.

Assim, a GameWake reduz fortemente o preco sem depender de Spot, compromisso de longo prazo ou uma instancia menor ainda nao validada.

## Registro de fontes e limitacoes

- Fontes de preco: somente AWS Price List/API e paginas oficiais AWS; AbacatePay em paginas, Termos e documentacao API v2 oficiais.
- Snapshot Spot: consulta `DescribeSpotPriceHistory` em 11/08/2026; valor variavel, nao promessa futura.
- Cambio de R$ 5,50 e R$ 6,00 sao cenarios, nao cotacao confirmada.
- Egress de 0,1/0,5/1 GB/h, duracao Lambda de 1 s, Aurora em 0,5 ACU e reserva de 15% sao estimativas declaradas.
- Nao foram incluidos segredos, creditos promocionais AWS, impostos finais nem hipotese de Free Tier.
- A publicacao textual do Aurora pode estar atrasada em relacao ao Price List vigente; validar no Cost and Usage Report.
