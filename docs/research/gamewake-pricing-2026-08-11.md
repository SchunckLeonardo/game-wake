# Nota de precificação da GameWake — 11/08/2026

## Recomendação

Adotar **R$ 2,49 por hora** para o `m6a.xlarge` agora. Esse preço mantém o caso simples acessível e, sob as premissas conservadoras abaixo, deixa contribuição estimada de **R$ 1,05 por hora**, equivalente a **42,3% do preço**.

Usar **R$ 1,99 por hora** apenas como preço temporário de beta: a contribuição estimada cai para **R$ 0,62 por hora**. Antes de oferecer um perfil a **R$ 1,79 por hora**, executar benchmark real do `r6a.large` com Palworld e os critérios de saúde, capacidade e persistência da GameWake.

## Dados confirmados em 11/08/2026

### Infraestrutura AWS

Preços On-Demand consultados na AWS Price List API para Linux, Shared, Used, em `us-east-1`:

| Instância | On-Demand |
| --- | ---: |
| `m6a.xlarge` | US$ 0,17280/h |
| `r6a.large` | US$ 0,11340/h |
| `m7a.xlarge` | US$ 0,23184/h |

A [AWS Price List Query API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-price-list-query-api.html) é a fonte usada para esses valores. Instâncias EC2 Linux On-Demand são cobradas por segundo, com mínimo de 60 segundos, conforme a [página oficial de preços On-Demand](https://aws.amazon.com/ec2/pricing/on-demand/).

Outros componentes do Runtime atual:

- IPv4 público: **US$ 0,005/h**, segundo a [tabela oficial da Amazon VPC](https://aws.amazon.com/vpc/pricing/).
- EBS `gp3`: **US$ 0,08/GiB-mês** em `us-east-1`; com os 50 GiB usados pela GameWake, são **US$ 4,00/mês**, ou aproximadamente **US$ 0,00548/h enquanto o volume existir**. Fonte: [AWS Storage Blog sobre gp3](https://aws.amazon.com/blogs/storage/migrate-your-amazon-ebs-volumes-from-gp2-to-gp3-and-save-up-to-20-on-costs/).

Para a configuração atual, o custo variável conservador é:

`US$ 0,17280 + US$ 0,00500 + US$ 0,00548 = US$ 0,18328/h`

O repositório usa `m6a.xlarge`, volume `gp3` de 50 GiB, cobrança ao cliente por segundo e reserva inicial de 25 minutos. Antes desta decisão, o preço ilustrativo era **R$ 5,50/h**; o preço adotado para a Closed Beta passa a ser **R$ 2,49/h**. O smoke test real anterior, de 510 segundos, cobrou **R$ 0,78** com a tarifa antiga e serve apenas como validação histórica do medidor, não como referência do preço atual.

### Spot e compromissos

Os preços Spot observados pela API do EC2 foram:

| Instância | Faixa observada |
| --- | ---: |
| `m6a.xlarge` | US$ 0,0704–0,0887/h |
| `r6a.large` | US$ 0,0447–0,0583/h |

Esses valores são observações pontuais, não preços garantidos. Spot não é recomendado agora porque a AWS pode interromper a instância com aviso de dois minutos; isso aumenta o risco sobre save e Recovery Guarantee. Fonte: [avisos de interrupção de Spot da AWS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-instance-termination-notices.html).

Savings Plans devem ser avaliados apenas depois de existir uma carga-base mensurável, pois exigem compromisso de uso por **um ou três anos**. Fonte: [documentação oficial de Savings Plans](https://docs.aws.amazon.com/savingsplans/latest/userguide/what-is-savings-plans.html).

### Pagamentos

Segundo a [precificação oficial da AbacatePay](https://www.abacatepay.com/pricing):

- Pix recebido: **R$ 0,80 fixo**, sem mensalidade;
- cartão em 1x: **3,5% + R$ 0,60**;
- saque: **R$ 0,80** nos 20 primeiros e **R$ 2,50** a partir do 21º.

Os [termos da AbacatePay](https://www.abacatepay.com/termos) também devem reger a operação. Para um pacote Pix de R$ 25,00, a taxa fixa de R$ 0,80 representa **3,2%** do valor recebido.

## Premissas do cenário recomendado

Estas não são preços ou obrigações confirmadas:

- câmbio de planejamento: **R$ 5,50/US$**;
- buffer cambial e operacional: **10%** sobre o custo AWS convertido;
- reserva tributária provisória: **10% da receita**;
- pagamento por Pix em pacote de R$ 25,00, com taxa efetiva de 3,2%;
- exclusão, por enquanto, de custos fixos ainda não atribuídos por World/hora.

Com câmbio e buffer, o custo variável estimado é:

`US$ 0,18328/h × R$ 5,50/US$ × 1,10 = R$ 1,11/h`

Comparação dos preços ao cliente:

| Preço | Líquido após Pix e reserva tributária | Contribuição após AWS | Contribuição / preço |
| ---: | ---: | ---: | ---: |
| R$ 2,49/h | R$ 2,16/h | R$ 1,05/h | 42,3% |
| R$ 1,99/h | R$ 1,73/h | R$ 0,62/h | 31,1% |

Os números são unit economics preliminares, não margem líquida. Antes de cravar lucro fixo, ativar e validar cost allocation tags para atribuir EC2, EBS, IPv4 e demais custos aos Worlds e Accounts. Também devem entrar no modelo os custos fixos reais, impostos validados, estornos da Wake Guarantee, ociosidade e meios de pagamento efetivamente usados.

O ponto de equilíbrio mensal deve ser recalculado com dados reais:

`horas para break-even = custo fixo mensal / contribuição por hora`
