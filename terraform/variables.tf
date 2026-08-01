variable "project_name" {
  description = "Nome curto usado em recursos, tags e caminhos do Parameter Store."
  type        = string
  default     = "gamewake"

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

variable "private_subnet_cidrs" {
  description = "Dois CIDRs privados em AZs distintas para o Aurora Serverless v2."
  type        = list(string)
  default     = ["10.42.10.0/24", "10.42.11.0/24"]

  validation {
    condition = (
      length(var.private_subnet_cidrs) >= 2 &&
      alltrue([for cidr in var.private_subnet_cidrs : can(cidrnetmask(cidr))])
    )
    error_message = "private_subnet_cidrs exige pelo menos dois CIDRs IPv4 validos."
  }
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

variable "gamewake_console_url" {
  description = "Origem HTTPS exata da Console usada por OAuth e CORS."
  type        = string
  default     = "https://gamewake-mvp.leonardorainha.chatgpt.site"

  validation {
    condition     = can(regex("^https://[^/]+$", var.gamewake_console_url))
    error_message = "gamewake_console_url deve ser uma origem HTTPS sem barra final."
  }
}

variable "abacatepay_packages" {
  description = "Pacotes de credito e produtos avulsos correspondentes na AbacatePay v2."
  type = list(object({
    id         = string
    amount     = number
    product_id = string
  }))
  default = [
    { id = "credits-25", amount = 25, product_id = "REPLACE_ME" },
    { id = "credits-50", amount = 50, product_id = "REPLACE_ME" },
    { id = "credits-100", amount = 100, product_id = "REPLACE_ME" },
  ]
}

variable "runtime_profile_hourly_rates" {
  description = "Preco final por hora em BRL de cada Runtime Profile oferecido no MVP."
  type        = map(number)
  default = {
    palworld-small = 5.50
  }

  validation {
    condition = (
      length(var.runtime_profile_hourly_rates) > 0 &&
      alltrue([for rate in values(var.runtime_profile_hourly_rates) : rate > 0])
    )
    error_message = "Todo Runtime Profile deve ter preco final positivo."
  }
}

variable "secure_parameter_placeholder" {
  description = "Placeholder inicial dos SecureStrings; substitua via AWS CLI antes do primeiro start."
  type        = string
  default     = "CHANGE_ME_BEFORE_FIRST_START"
  sensitive   = true
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

variable "world_data_bucket_name" {
  description = "Nome global opcional do bucket persistente de mundos do GameWake."
  type        = string
  default     = null
  nullable    = true
}

variable "storage_allowance_bytes" {
  description = "Armazenamento duravel incluido por GameWake Account antes do excedente."
  type        = number
  default     = 10737418240

  validation {
    condition     = var.storage_allowance_bytes >= 0
    error_message = "storage_allowance_bytes nao pode ser negativo."
  }
}

variable "storage_grace_days" {
  description = "Dias de tolerancia para excedente de armazenamento sem saldo."
  type        = number
  default     = 30

  validation {
    condition     = var.storage_grace_days >= 1
    error_message = "storage_grace_days deve ser pelo menos 1."
  }
}

variable "storage_rate_per_gib_month_brl" {
  description = "Preco mensal em BRL por GiB que excede a Storage Allowance. Validar margem antes da beta."
  type        = number
  default     = 2

  validation {
    condition     = var.storage_rate_per_gib_month_brl > 0
    error_message = "storage_rate_per_gib_month_brl deve ser positivo."
  }
}

variable "world_data_noncurrent_version_retention_days" {
  description = "Dias de seguranca antes de remover versoes S3 nao atuais que nao foram apagadas explicitamente."
  type        = number
  default     = 7

  validation {
    condition = (
      var.world_data_noncurrent_version_retention_days >= 1 &&
      var.world_data_noncurrent_version_retention_days <= 30 &&
      floor(var.world_data_noncurrent_version_retention_days) == var.world_data_noncurrent_version_retention_days
    )
    error_message = "world_data_noncurrent_version_retention_days deve ser um numero inteiro entre 1 e 30."
  }
}

variable "aurora_database_name" {
  description = "Banco PostgreSQL usado pelo control plane do GameWake."
  type        = string
  default     = "gamewake"
}

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL compativel com Serverless v2 auto-pause em zero ACUs."
  type        = string
  default     = "16.14"

  validation {
    condition     = can(regex("^16\\.([3-9]|[1-9][0-9]+)$", var.aurora_engine_version))
    error_message = "aurora_engine_version deve usar Aurora PostgreSQL 16.3 ou superior para suportar auto-pause em zero ACUs."
  }
}

variable "aurora_min_acu" {
  description = "Capacidade minima do Aurora Serverless v2."
  type        = number
  default     = 0

  validation {
    condition     = var.aurora_min_acu >= 0 && var.aurora_min_acu <= 128
    error_message = "aurora_min_acu deve ficar entre 0 e 128 ACUs."
  }
}

variable "aurora_max_acu" {
  description = "Capacidade maxima do Aurora Serverless v2."
  type        = number
  default     = 4

  validation {
    condition     = var.aurora_max_acu >= 1 && var.aurora_max_acu <= 256
    error_message = "aurora_max_acu deve ficar entre 1 e 256 ACUs."
  }
}

variable "aurora_auto_pause_seconds" {
  description = "Inatividade antes de pausar Aurora Serverless v2 quando min ACU e zero."
  type        = number
  default     = 900

  validation {
    condition = (
      var.aurora_auto_pause_seconds >= 300 &&
      var.aurora_auto_pause_seconds <= 86400
    )
    error_message = "aurora_auto_pause_seconds deve ficar entre 300 e 86400."
  }
}

variable "aurora_deletion_protection" {
  description = "Protege o banco de producao contra exclusao acidental."
  type        = bool
  default     = true
}

variable "aurora_skip_final_snapshot" {
  description = "Somente para ambientes descartaveis; producao deve manter false."
  type        = bool
  default     = false
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

variable "operations_alarm_email" {
  description = "Email opcional que recebe alarmes operacionais da Closed Beta via SNS. A assinatura precisa ser confirmada."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.operations_alarm_email == null ||
      can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.operations_alarm_email))
    )
    error_message = "operations_alarm_email deve ser null ou um email valido."
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
