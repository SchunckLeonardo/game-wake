# Fatos oficiais de plataforma para `palworld-cloud-server`

Verificado em: **2026-07-19**; novos parâmetros de gameplay rechecados em **2026-07-22**. Escopo: somente documentação primária da Pocketpair, Valve/Ubuntu, Discord e AWS. Quando a documentação oficial não fecha uma questão, a lacuna está registrada explicitamente; nenhum comportamento comunitário foi promovido a fato.

## 1. Palworld Dedicated Server

### `PalWorldSettings.ini`

No Linux com SteamCMD, a Pocketpair manda copiar `steamapps/common/PalServer/DefaultPalWorldSettings.ini` para `steamapps/common/PalServer/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini` e editar a cópia; alterar o arquivo `Default...` não aplica a configuração. Os diretórios surgem somente depois de o servidor ter sido iniciado uma vez. Fonte: [Configuration parameters — Pocketpair](https://docs.palworldgame.com/settings-and-operation/configuration/).

Parâmetros relevantes confirmados na documentação atual:

| Necessidade | Nome oficial | Forma/valores oficialmente descritos |
|---|---|---|
| nome | `ServerName` | texto |
| descrição | `ServerDescription` | texto |
| senha para entrar | `ServerPassword` | texto |
| senha administrativa | `AdminPassword` | texto; senha para obter privilégios administrativos |
| porta pública anunciada | `PublicPort` | número; só explicita a porta externa de **community server** e **não altera a porta de escuta** |
| máximo de jogadores | `ServerPlayerMaxNum` | número máximo de jogadores; a página atual não publica faixa nem default |
| experiência | `ExpRate` | multiplicador numérico |
| coleta | `CollectionDropRate` | multiplicador numérico de itens coletáveis |
| produção no rancho | `MonsterFarmActionSpeedRate` | multiplicador numérico da velocidade de produção de itens por pastoreio |
| fome dos Pals | `PalStomachDecreaceRate` | multiplicador numérico do consumo de fome; a grafia oficial é mesmo `Decreace` |
| meteoritos e suprimentos | `SupplyDropSpan` | intervalo numérico em minutos; a página atual não publica faixa nem default |
| spawn de Pals | `PalSpawnNumRate` | multiplicador numérico; a Pocketpair alerta que afeta desempenho |
| penalidade de morte | `DeathPenalty` | `None`, `Item`, `ItemAndEquipment` ou `All` |
| dano de Pals | `PalDamageRateAttack`, `PalDamageRateDefense` | multiplicadores de dano causado/recebido |
| dano de jogadores | `PlayerDamageRateAttack`, `PlayerDamageRateDefense` | multiplicadores de dano causado/recebido |
| stamina | `PalStaminaDecreaceRate`, `PlayerStaminaDecreaceRate` | multiplicadores de consumo; a grafia oficial é mesmo `Decreace` |
| peso de itens | `ItemWeightRate` | multiplicador de peso; **é suportado oficialmente na documentação atual** |
| permitir evolução de stamina/peso | `bAllowEnhanceStat_Stamina`, `bAllowEnhanceStat_Weight` | booleanos distintos dos multiplicadores acima |
| API REST | `RESTAPIEnabled`, `RESTAPIPort` | booleano e porta de escuta; a API exige `RESTAPIEnabled=True` |
| backup interno | `bIsUseBackupSaveData` | booleano; ao habilitar, cria `backup` dentro do diretório de save |

Para `DeathPenalty`: `None` não derruba nada; `Item` derruba itens exceto equipamento; `ItemAndEquipment` derruba itens e equipamento; `All` também derruba os Pals da equipe. Para backups internos, a retenção publicada é 5 saves de 30 s, 6 de 10 min, 12 de 1 h e 7 de 1 dia. A documentação atual **não publica limites/defaults** para os multiplicadores acima; portanto o projeto não deve inventar faixas “oficiais”. Fonte única da tabela e da retenção: [Configuration parameters — Pocketpair](https://docs.palworldgame.com/settings-and-operation/configuration/).

Ponto de implementação: a porta real do jogo é configurada na inicialização, por exemplo `./PalServer.sh -port=8211`; `PublicPort` não a muda. Fonte: [Configure the server — Pocketpair](https://docs.palworldgame.com/settings-and-operation/arguments/). O guia de requisitos identifica UDP 8211 como porta padrão do jogo: [Requirements — Pocketpair](https://docs.palworldgame.com/getting-started/requirements/).

### REST API oficial

A base usada nos exemplos atuais é `http://localhost:8212/v1/api`. A tabela de configuração chama `RESTAPIPort` de porta de escuta, mas não rotula 8212 textualmente como “default”; 8212 é o valor dos exemplos oficiais. A API usa **HTTP Basic Auth**, retorna `401` quando não autorizada e a Pocketpair diz que ela não foi projetada para exposição direta à Internet, recomendando uso apenas em LAN. Para este projeto, não abrir a porta no Security Group e restringi-la no firewall/host; a configuração INI não documenta uma opção de bind apenas em loopback. Fonte: [REST API introduction — Pocketpair](https://docs.palworldgame.com/api/rest-api/palwold-rest-api/).

| Operação | Endpoint | Corpo/comportamento documentado |
|---|---|---|
| informação | `GET /info` | retorna `version`, `servername`, `description`, `worldguid` ([fonte](https://docs.palworldgame.com/api/rest-api/info/)) |
| jogadores | `GET /players` | retorna `players[]`, inclusive nome, IDs, IP, ping, posição, nível e contagem de construções ([fonte](https://docs.palworldgame.com/api/rest-api/players/)) |
| salvar mundo | `POST /save` | sem corpo documentado; 200 indica save concluído ([fonte](https://docs.palworldgame.com/api/rest-api/save/)) |
| anúncio | `POST /announce` | JSON obrigatório `{"message":"..."}` ([fonte](https://docs.palworldgame.com/api/rest-api/announce/)) |
| desligar servidor | `POST /shutdown` | JSON com `waittime` inteiro obrigatório e `message` opcional ([fonte](https://docs.palworldgame.com/api/rest-api/shutdown/)) |

Todos esses endpoints documentam `200`, `400` e `401`. Para desligamento seguro, a sequência defensiva é anúncio, `/save`, `/shutdown`, aguardar o processo encerrar e só então desligar o Linux/EC2; a documentação de `/shutdown` não promete por si só persistência nem desligamento da máquina.

Lacunas oficiais importantes:

- A documentação diz “Basic Auth”, mas **não informa o username** nem liga explicitamente a senha HTTP a `AdminPassword`. Não registrar `admin` como fato oficial; tornar credenciais configuráveis e validar contra a versão instalada.
- A unidade de `waittime` não é declarada. O exemplo oficial usa `30`, porém a mensagem de exemplo diz “10 seconds”, portanto não resolve a unidade de forma confiável.
- Os endpoints mutáveis não publicam schema de corpo de resposta além dos códigos HTTP.

### SteamCMD e suporte Linux/Ubuntu

A instalação/atualização oficial do servidor é:

```bash
sudo add-apt-repository multiverse
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install lib32gcc-s1 steamcmd

steamcmd +login anonymous +app_update 2394010 validate +quit
cd ~/Steam/steamapps/common/PalServer
./PalServer.sh
```

A Pocketpair remete à instalação oficial do SteamCMD para a distribuição e confirma login anônimo e App ID `2394010`: [Deploy dedicated server — Pocketpair](https://docs.palworldgame.com/getting-started/deploy-dedicated-server/). A referência da Valve é [SteamCMD — Valve Developer Community](https://developer.valvesoftware.com/wiki/SteamCMD). No Ubuntu 24.04 (Noble), o pacote oficial `steamcmd` existe em `multiverse` somente para arquitetura `i386`; uma imagem x86-64 deve habilitar `multiverse`/multiarch i386 antes de `apt install steamcmd`: [pacote `steamcmd` no Ubuntu Noble](https://packages.ubuntu.com/noble/steamcmd).

A Pocketpair declara suporte a “Linux 64bit (Ubuntu, AlmaLinux etc.)”, 4+ cores e 16 GB de memória, mas não menciona especificamente Ubuntu **24.04**. Assim, “Linux/Ubuntu suportado” é confirmado; “24.04 certificado pela Pocketpair” não é. Fonte: [Requirements — Pocketpair](https://docs.palworldgame.com/getting-started/requirements/).

## 2. AWS e Discord

### Limites de resource-level permissions

| Ação | Pode restringir a recurso exato? | Política mínima relevante |
|---|---|---|
| `ec2:DescribeInstances` | **não** | requer `Resource: "*"`; pode ao menos restringir por condições suportadas, como região |
| `ec2:StartInstances`, `ec2:StopInstances` | **sim** | ARN exato `arn:aws:ec2:REGION:ACCOUNT:instance/INSTANCE_ID` |
| `ssm:SendCommand` | **sim** | autorizar tanto o documento exato quanto a instância exata; evitar `AWS-*` amplo porque documentos de shell executam com privilégio administrativo no nó |
| `ssm:GetCommandInvocation` | **não** | requer `Resource: "*"`; Run Command é eventualmente consistente, então consultas imediatamente após `SendCommand` podem ainda não refletir a execução |
| `ssm:GetParameter` | **sim** | ARN exato `arn:aws:ssm:REGION:ACCOUNT:parameter/PATH`; `kms:Decrypt` também é necessário se o `SecureString` usar uma CMK e o valor for lido com decriptação |

Evidências: o exemplo oficial da EC2 explica o wildcard obrigatório para `DescribeInstances` e ARNs de instância para start/stop ([EC2 example policies](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ExamplePolicies_EC2.html)); a matriz oficial de ações confirma os tipos de recurso ([EC2 Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html)). Para SSM, a matriz lista recursos de `SendCommand`, nenhum tipo para `GetCommandInvocation` e `parameter*` para `GetParameter` ([Systems Manager Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_awssystemsmanager.html)); a AWS mostra uma política com documento e instâncias específicos ([SSM identity-policy example 3](https://docs.aws.amazon.com/systems-manager/latest/userguide/security_iam_id-based-policy-examples.html)) e documenta a consistência eventual de `GetCommandInvocation` ([API reference](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_GetCommandInvocation.html)).

Consequência para a Lambda: `DescribeInstances` e `GetCommandInvocation` serão os únicos wildcards inevitáveis desse conjunto; start/stop, parâmetro e alvo/documento de Run Command devem ser restritos a ARNs exatos. Não enviar segredos em plaintext nos parâmetros de Run Command, pois a AWS registra a atividade; prefira `SecureString`: [Running commands on managed nodes](https://docs.aws.amazon.com/systems-manager/latest/userguide/running-commands.html).

### Lambda Function URL recebendo Discord

O Discord não assina requisições com AWS SigV4, portanto uma Function URL usada diretamente como Interactions Endpoint precisa de `AuthType=NONE`. Isso a torna pública e sem autenticação IAM; a segurança da aplicação passa a ser a verificação Ed25519 do Discord. Desde outubro de 2025, novas Function URLs públicas precisam das permissões resource-based `lambda:InvokeFunctionUrl` **e** `lambda:InvokeFunction`, preferencialmente com `lambda:InvokedViaFunctionUrl=true`: [Control access to Lambda function URLs — AWS](https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html).

A Function URL entrega eventos no formato payload v2.0, com headers, `body` e `isBase64Encoded`. Para validar o Discord, reconstruir exatamente os bytes do corpo original (decodificando Base64 quando indicado) e verificar a assinatura sobre `X-Signature-Timestamp + raw_body`; só depois fazer parse do JSON. A resposta explícita da Lambda pode usar `statusCode`, headers, `body` serializado e `isBase64Encoded=false`; por exemplo, o PONG deve sair como HTTP 200 cujo corpo JSON é `{"type":1}`. Function URLs são acessíveis apenas pela Internet pública. Fonte do envelope e do mapeamento HTTP: [Invoking Lambda function URLs — AWS](https://docs.aws.amazon.com/lambda/latest/dg/urls-invocation.html); característica do endpoint: [Creating and managing Lambda function URLs — AWS](https://docs.aws.amazon.com/lambda/latest/dg/urls-configuration.html).

O contrato do Discord exige:

- validar `X-Signature-Ed25519` e `X-Signature-Timestamp` em **toda** interação; assinatura inválida deve resultar em `401`;
- responder ao `PING` (`type: 1`) com HTTP 200 e `{"type":1}`;
- enviar a resposta inicial em até 3 segundos; depois disso o token é invalidado;
- tokens de interação permanecem válidos por 15 minutos para follow-ups.

Fontes: [Interactions overview — Discord](https://docs.discord.com/developers/interactions/overview) e [Receiving and responding — Discord](https://docs.discord.com/developers/interactions/receiving-and-responding). Portanto `/palworld ligar` deve apenas iniciar a EC2 e responder imediatamente; não deve bloquear esperando o Palworld ficar pronto.

### Ubuntu 24.04 e SSM Agent

A AWS inclui Ubuntu Server 24.04 LTS entre as AMIs em que o SSM Agent costuma vir pré-instalado, mas recomenda verificar instalação e execução porque isso pode variar conforme a AMI e a data: [Find AMIs with SSM Agent preinstalled](https://docs.aws.amazon.com/systems-manager/latest/userguide/ami-preinstalled-agent.html). Na página específica, a AWS diz que as AMIs Ubuntu 24.04 com identificador `20180627` ou posterior o instalam por padrão, recomenda Snap nas versões Ubuntu 18.04+ e fornece o fallback `sudo snap install amazon-ssm-agent --classic`: [Install SSM Agent on Ubuntu](https://docs.aws.amazon.com/systems-manager/latest/userguide/agent-install-ubuntu-64-snap.html). O user-data deve verificar e iniciar `snap.amazon-ssm-agent.amazon-ssm-agent.service`, não apenas presumir que esteja ativo.

### AWS Free Plan, Paid Plan e créditos

Para contas novas a partir de 15 de julho de 2025, a AWS oferece dois planos. O **Free account plan** dá acesso apenas a serviços/recursos selecionados, termina após seis meses ou quando os créditos acabam e evita cobrança; o **Paid account plan** libera todos os serviços, mas cobra pay-as-you-go pelo uso que exceder créditos ou não for elegível. Novos clientes recebem USD 100 e podem ganhar mais USD 100 em atividades. Um upgrade manual para Paid preserva créditos restantes, que são aplicados automaticamente a faturas futuras até expirarem: [Choosing an AWS Free Tier plan](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html) e [Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/).

`m6a.xlarge` tem 4 vCPU e 16 GiB, mas **não** está entre os tipos marcados Free Tier eligible (`t3.micro`, `t3.small`, `t4g.micro`, `t4g.small`, `c7i-flex.large`, `m7i-flex.large`) para contas criadas após 15/07/2025: [Track EC2 Free Tier usage](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html). A AWS não diz nessa página, nominalmente, “Free Plan bloqueia m6a.xlarge”; a conclusão segura é que ele não é Free Tier eligible e pode exigir o Paid Plan por causa das restrições do Free Plan. Especificação oficial da instância: [Amazon EC2 M6a](https://aws.amazon.com/ec2/instance-types/m6a/).

Exceções: contas anteriores a 15/07/2025 seguem o Free Tier legado; e upgrade provocado por ingresso no AWS Organizations/Control Tower pode expirar imediatamente os créditos, ao contrário do upgrade manual comum. Isso deve aparecer no README para não prometer preservação universal dos créditos: [Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/).

## Decisões seguras derivadas destas fontes

- Manter UDP 8211 público apenas no CIDR configurado; não criar regra pública para 8212/REST ou RCON.
- Gerar `PalWorldSettings.ini` a partir de variáveis, mas não alegar ranges/defaults que a Pocketpair não publica; proteger `ServerPassword`, `AdminPassword` e webhooks em Parameter Store `SecureString`.
- Usar `/players` para o autostop apenas quando a chamada autenticada for conclusiva; em erro/timeout/401, não desligar.
- No desligamento, preferir `/announce` → `/save` → `/shutdown` → confirmação de término → shutdown do Linux; nunca tratar uma falha de API como “zero jogadores”.
- Responder ao Discord dentro dos 3 segundos e executar verificações demoradas via fluxo posterior (SSM/webhook/follow-up), mantendo a Function URL pública protegida pela verificação Ed25519.
