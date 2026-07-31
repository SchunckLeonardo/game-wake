# Protótipo Palworld legado

Este guia existe para manutenção e migração do servidor único que originou o GameWake. Ele não é a arquitetura do MVP multi-tenant. Deploys novos devem usar `enable_legacy_single_server = false` e seguir [DEPLOYMENT.md](DEPLOYMENT.md).

## O que o modo legado mantém

- uma EC2 fixa controlada pela Lambda antiga;
- comandos `/palworld ligar`, `status`, `desligar`, `configurar` e `ajuda`;
- instalação por SteamCMD e serviço systemd;
- save, health check, auto-stop e backup local/S3 opcional;
- edição guiada de `PalWorldSettings.ini` por CLI e Discord.

Para reativá-lo temporariamente:

```hcl
enable_legacy_single_server = true
```

Isso cria recursos e custos adicionais. Não misture o lifecycle da EC2 fixa com os runtimes descartáveis dos Worlds GameWake.

## Configuração do Palworld

A ferramenta local lê o catálogo validado do projeto e preserva a linha única exigida pelo jogo:

```bash
./palworld settings
```

Para aplicar um arquivo já editado:

```bash
./palworld settings apply ./PalWorldSettings.ini
```

O assistente apresenta tipo, faixa/valores aceitos e documentação. As opções incluem rates, drops, worker limit, Palbox global, regeneração, hatch, farm action, stamina, fome e supply drops. Um valor só entra em vigor depois de persistido no arquivo efetivo e de um restart/sono seguro do servidor.

## Operação legada

- `/palworld ligar`: inicia a EC2 fixa e responde imediatamente; disponibilidade chega depois.
- `/palworld status`: mostra estado do host e servidor.
- `/palworld desligar`: salva, cria backup e encerra; `forcar=true` ignora jogadores/erros e exige autorização administrativa.
- `/palworld configurar`: abre o editor guiado.

Administração usa Session Manager, sem SSH:

```bash
terraform -chdir=terraform output -raw session_manager_command
```

Logs principais no host:

```bash
sudo journalctl -u palworld -n 200 --no-pager
sudo journalctl -u palworld-autostop -n 200 --no-pager
sudo systemctl status palworld
```

## Migração para GameWake

1. Desligue com save verificado.
2. Gere um backup e guarde outra cópia fora da EC2.
3. Registre versão do jogo, `PalWorldSettings.ini` efetivo e checksums.
4. Crie uma Account/World GameWake.
5. Importe o save pelo fluxo controlado ou restaure como cópia.
6. Acorde, valide o progresso e durma novamente.
7. Só depois desabilite os recursos legados e revise o Terraform plan.

Não trate o volume raiz da EC2 como backup. Nunca destrua a última cópia recuperável.
