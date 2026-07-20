variable "project_name" {
  description = "Nome curto usado em recursos, tags e caminhos do Parameter Store."
  type        = string
  default     = "palworld-cloud-server"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,31}$", var.project_name))
    error_message = "project_name deve ter 3-32 caracteres minusculos, numeros ou hifens."
  }
}

variable "environment" {
  description = "Ambiente logico do deploy."
  type        = string
  default     = "prod"

  validation {
    condition     = can(regex("^[a-z0-9-]{2,16}$", var.environment))
    error_message = "environment deve ter 2-16 caracteres minusculos, numeros ou hifens."
  }
}

variable "aws_region" {
  description = "Regiao AWS para todos os recursos."
  type        = string
  default     = "us-east-1"
}

variable "availability_zone" {
  description = "AZ opcional; null usa a primeira AZ disponivel na regiao."
  type        = string
  default     = null
  nullable    = true
}

variable "vpc_cidr" {
  description = "CIDR da VPC dedicada e economica."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr deve ser um CIDR IPv4 valido."
  }
}

variable "public_subnet_cidr" {
  description = "CIDR da unica subnet publica."
  type        = string
  default     = "10.42.1.0/24"

  validation {
    condition     = can(cidrnetmask(var.public_subnet_cidr))
    error_message = "public_subnet_cidr deve ser um CIDR IPv4 valido."
  }
}

variable "instance_type" {
  description = "Tipo da EC2. m6a.xlarge oferece 4 vCPU e 16 GiB, mas nao e Free Tier eligible."
  type        = string
  default     = "m6a.xlarge"
}

variable "root_volume_size_gib" {
  description = "Tamanho do volume raiz gp3 criptografado em GiB."
  type        = number
  default     = 50

  validation {
    condition     = var.root_volume_size_gib >= 30 && var.root_volume_size_gib <= 16384
    error_message = "root_volume_size_gib deve ficar entre 30 e 16384 GiB."
  }
}

variable "root_volume_delete_on_termination" {
  description = "Remove o volume raiz ao destruir a EC2. Backups devem existir antes de habilitar."
  type        = bool
  default     = true
}

variable "enable_termination_protection" {
  description = "Impede terminacao acidental da EC2 pela API; nao impede stop."
  type        = bool
  default     = false
}

variable "palworld_port" {
  description = "Porta UDP real passada ao PalServer.sh; PublicPort sozinho nao muda o listener."
  type        = number
  default     = 8211

  validation {
    condition     = var.palworld_port >= 1024 && var.palworld_port <= 65535
    error_message = "palworld_port deve ficar entre 1024 e 65535."
  }
}

variable "palworld_allowed_cidr" {
  description = "CIDR autorizado a conectar na porta UDP do jogo. Restrinja sempre que possivel."
  type        = string
  default     = "0.0.0.0/0"

  validation {
    condition     = can(cidrnetmask(var.palworld_allowed_cidr))
    error_message = "palworld_allowed_cidr deve ser um CIDR IPv4 valido."
  }
}

variable "enable_ssh" {
  description = "Abre TCP 22 temporariamente. Session Manager e o metodo padrao."
  type        = bool
  default     = false
}

variable "ssh_allowed_cidr" {
  description = "CIDR restrito para SSH quando enable_ssh=true. Nunca use 0.0.0.0/0."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = var.ssh_allowed_cidr == null || (
      can(cidrnetmask(var.ssh_allowed_cidr)) && var.ssh_allowed_cidr != "0.0.0.0/0"
    )
    error_message = "ssh_allowed_cidr deve ser um CIDR valido e nao pode ser 0.0.0.0/0."
  }
}

variable "ssh_key_name" {
  description = "Key Pair opcional quando SSH temporario for habilitado."
  type        = string
  default     = null
  nullable    = true
}

variable "discord_application_id" {
  description = "Application ID do aplicativo Discord; usado nos comandos de pos-deploy."
  type        = string
  default     = "REPLACE_ME"
}

variable "discord_public_key" {
  description = "Public Key Ed25519 do aplicativo Discord (64 hex; nao e segredo)."
  type        = string
  default     = "REPLACE_ME"

  validation {
    condition = var.discord_public_key == "REPLACE_ME" || can(
      regex("^[0-9a-fA-F]{64}$", var.discord_public_key)
    )
    error_message = "discord_public_key deve ser REPLACE_ME ou 64 caracteres hexadecimais."
  }
}

variable "discord_guild_id" {
  description = "Guild ID unica autorizada a executar comandos."
  type        = string
  default     = "REPLACE_ME"
}

variable "discord_allowed_user_ids" {
  description = "IDs de usuarios autorizados. Lista vazia nao autoriza usuarios diretamente."
  type        = list(string)
  default     = []
}

variable "discord_allowed_role_ids" {
  description = "IDs de cargos autorizados. Lista vazia nao autoriza cargos."
  type        = list(string)
  default     = []
}

variable "secure_parameter_placeholder" {
  description = "Placeholder inicial dos SecureStrings; substitua via AWS CLI antes do primeiro start."
  type        = string
  default     = "CHANGE_ME_BEFORE_FIRST_START"
  sensitive   = true
}

variable "palworld_server_name" {
  description = "ServerName oficial do Palworld."
  type        = string
  default     = "Palworld dos Amigos"
}

variable "palworld_server_description" {
  description = "ServerDescription oficial do Palworld."
  type        = string
  default     = "Servidor privado iniciado sob demanda pelo Discord"
}

variable "palworld_max_players" {
  description = "ServerPlayerMaxNum. A documentacao oficial nao publica uma faixa."
  type        = number
  default     = 16

  validation {
    condition     = var.palworld_max_players >= 1
    error_message = "palworld_max_players deve ser positivo."
  }
}

variable "palworld_exp_rate" {
  description = "ExpRate oficial."
  type        = number
  default     = 1.0

  validation {
    condition     = var.palworld_exp_rate > 0
    error_message = "palworld_exp_rate deve ser positivo."
  }
}

variable "palworld_collection_drop_rate" {
  description = "CollectionDropRate oficial."
  type        = number
  default     = 1.0

  validation {
    condition     = var.palworld_collection_drop_rate > 0
    error_message = "palworld_collection_drop_rate deve ser positivo."
  }
}

variable "palworld_spawn_rate" {
  description = "PalSpawnNumRate oficial; valores altos afetam desempenho."
  type        = number
  default     = 1.0

  validation {
    condition     = var.palworld_spawn_rate > 0
    error_message = "palworld_spawn_rate deve ser positivo."
  }
}

variable "palworld_death_penalty" {
  description = "DeathPenalty oficial: None, Item, ItemAndEquipment ou All."
  type        = string
  default     = "Item"

  validation {
    condition     = contains(["None", "Item", "ItemAndEquipment", "All"], var.palworld_death_penalty)
    error_message = "palworld_death_penalty deve ser None, Item, ItemAndEquipment ou All."
  }
}

variable "palworld_pal_damage_attack_rate" {
  description = "PalDamageRateAttack oficial."
  type        = number
  default     = 1.0
  validation {
    condition     = var.palworld_pal_damage_attack_rate > 0
    error_message = "O multiplicador deve ser positivo."
  }
}

variable "palworld_pal_damage_defense_rate" {
  description = "PalDamageRateDefense oficial."
  type        = number
  default     = 1.0
  validation {
    condition     = var.palworld_pal_damage_defense_rate > 0
    error_message = "O multiplicador deve ser positivo."
  }
}

variable "palworld_player_damage_attack_rate" {
  description = "PlayerDamageRateAttack oficial."
  type        = number
  default     = 1.0
  validation {
    condition     = var.palworld_player_damage_attack_rate > 0
    error_message = "O multiplicador deve ser positivo."
  }
}

variable "palworld_player_damage_defense_rate" {
  description = "PlayerDamageRateDefense oficial."
  type        = number
  default     = 1.0
  validation {
    condition     = var.palworld_player_damage_defense_rate > 0
    error_message = "O multiplicador deve ser positivo."
  }
}

variable "palworld_pal_stamina_decrease_rate" {
  description = "PalStaminaDecreaceRate oficial (grafia original mantida no INI)."
  type        = number
  default     = 1.0
  validation {
    condition     = var.palworld_pal_stamina_decrease_rate > 0
    error_message = "O multiplicador deve ser positivo."
  }
}

variable "palworld_player_stamina_decrease_rate" {
  description = "PlayerStaminaDecreaceRate oficial (grafia original mantida no INI)."
  type        = number
  default     = 1.0
  validation {
    condition     = var.palworld_player_stamina_decrease_rate > 0
    error_message = "O multiplicador deve ser positivo."
  }
}

variable "palworld_item_weight_rate" {
  description = "ItemWeightRate oficial."
  type        = number
  default     = 1.0
  validation {
    condition     = var.palworld_item_weight_rate > 0
    error_message = "palworld_item_weight_rate deve ser positivo."
  }
}

variable "palworld_rest_api_port" {
  description = "RESTAPIPort local. Nao e aberto no Security Group."
  type        = number
  default     = 8212

  validation {
    condition     = var.palworld_rest_api_port >= 1024 && var.palworld_rest_api_port <= 65535
    error_message = "palworld_rest_api_port deve ficar entre 1024 e 65535."
  }
}

variable "palworld_rest_api_username" {
  description = "Username de Basic Auth da REST API. A documentacao oficial nao o define; valide na versao instalada."
  type        = string
  default     = "admin"
}

variable "autostop_check_minutes" {
  description = "Intervalo do timer de verificacao de jogadores."
  type        = number
  default     = 5

  validation {
    condition     = var.autostop_check_minutes >= 1
    error_message = "autostop_check_minutes deve ser pelo menos 1."
  }
}

variable "autostop_idle_minutes" {
  description = "Tempo vazio antes do save e shutdown automatico."
  type        = number
  default     = 20

  validation {
    condition     = var.autostop_idle_minutes >= var.autostop_check_minutes
    error_message = "autostop_idle_minutes deve ser maior ou igual ao intervalo de verificacao."
  }
}

variable "healthcheck_timeout_minutes" {
  description = "Tempo maximo de uma tentativa de healthcheck antes de o systemd repetir."
  type        = number
  default     = 10

  validation {
    condition     = var.healthcheck_timeout_minutes >= 1
    error_message = "healthcheck_timeout_minutes deve ser pelo menos 1."
  }
}

variable "local_backup_retention_days" {
  description = "Retencao dos arquivos tar.gz locais."
  type        = number
  default     = 14

  validation {
    condition     = var.local_backup_retention_days >= 1
    error_message = "local_backup_retention_days deve ser pelo menos 1."
  }
}

variable "enable_s3_backup" {
  description = "Cria bucket privado e envia backups para S3."
  type        = bool
  default     = false
}

variable "s3_backup_bucket_name" {
  description = "Nome global opcional do bucket; null gera nome com project/account/region."
  type        = string
  default     = null
  nullable    = true
}

variable "s3_backup_versioning" {
  description = "Habilita versionamento do bucket de backups."
  type        = bool
  default     = true
}

variable "s3_backup_retention_days" {
  description = "Expira objetos/versoes de backup no S3 apos este periodo."
  type        = number
  default     = 30

  validation {
    condition     = var.s3_backup_retention_days >= 1
    error_message = "s3_backup_retention_days deve ser pelo menos 1."
  }
}

variable "stop_after_initial_bootstrap" {
  description = "Agenda stop da EC2 depois do primeiro bootstrap para evitar ociosidade inicial."
  type        = bool
  default     = true
}

variable "cloudwatch_log_retention_days" {
  description = "Retencao dos logs estruturados da Lambda."
  type        = number
  default     = 7

  validation {
    condition = contains(
      [1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653],
      var.cloudwatch_log_retention_days
    )
    error_message = "cloudwatch_log_retention_days deve ser um valor aceito pelo CloudWatch Logs."
  }
}

variable "lambda_timeout_seconds" {
  description = "Timeout curto para respeitar a janela de resposta do Discord."
  type        = number
  default     = 5

  validation {
    condition     = var.lambda_timeout_seconds >= 3 && var.lambda_timeout_seconds <= 10
    error_message = "lambda_timeout_seconds deve ficar entre 3 e 10 segundos."
  }
}

variable "lambda_memory_size_mb" {
  description = "Memoria da Lambda; mais memoria tambem fornece mais CPU para cumprir o prazo do Discord."
  type        = number
  default     = 512

  validation {
    condition     = var.lambda_memory_size_mb >= 256 && var.lambda_memory_size_mb <= 1024
    error_message = "lambda_memory_size_mb deve ficar entre 256 e 1024 MB."
  }
}

variable "lambda_reserved_concurrent_executions" {
  description = "Concorrencia reservada da Lambda; -1 usa o limite nao reservado da conta."
  type        = number
  default     = -1

  validation {
    condition = (
      var.lambda_reserved_concurrent_executions == -1 ||
      var.lambda_reserved_concurrent_executions >= 1
    )
    error_message = "lambda_reserved_concurrent_executions deve ser -1 ou pelo menos 1."
  }
}

variable "lambda_package_path" {
  description = "Caminho relativo ao diretorio terraform para o ZIP gerado."
  type        = string
  default     = "../build/lambda.zip"
}

variable "extra_tags" {
  description = "Tags adicionais aplicadas pelo provider."
  type        = map(string)
  default     = {}
}
