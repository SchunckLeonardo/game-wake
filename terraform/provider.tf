provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Application = "PalworldDedicatedServer"
    },
    var.extra_tags
  )

  name_prefix           = "${var.project_name}-${var.environment}"
  parameter_path        = "/${var.project_name}/${var.environment}"
  lambda_package_file   = abspath("${path.module}/${var.lambda_package_path}")
  s3_backup_bucket_name = var.s3_backup_bucket_name != null ? var.s3_backup_bucket_name : "${var.project_name}-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  s3_backup_uri         = var.enable_s3_backup ? "s3://${local.s3_backup_bucket_name}/saves" : ""
  ssm_document_arn      = "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}::document/AWS-RunShellScript"
  instance_arn          = "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/${aws_instance.palworld.id}"
  lambda_log_group_name = "/aws/lambda/${local.name_prefix}-discord"
  discord_config_payload = jsonencode({
    public_key       = var.discord_public_key
    guild_id         = var.discord_guild_id
    allowed_user_ids = var.discord_allowed_user_ids
    allowed_role_ids = var.discord_allowed_role_ids
  })
  palworld_config_payload = jsonencode({
    server_name                  = var.palworld_server_name
    server_description           = var.palworld_server_description
    port                         = var.palworld_port
    max_players                  = var.palworld_max_players
    exp_rate                     = var.palworld_exp_rate
    collection_drop_rate         = var.palworld_collection_drop_rate
    pal_spawn_rate               = var.palworld_spawn_rate
    death_penalty                = var.palworld_death_penalty
    pal_damage_attack_rate       = var.palworld_pal_damage_attack_rate
    pal_damage_defense_rate      = var.palworld_pal_damage_defense_rate
    player_damage_attack_rate    = var.palworld_player_damage_attack_rate
    player_damage_defense_rate   = var.palworld_player_damage_defense_rate
    pal_stamina_decrease_rate    = var.palworld_pal_stamina_decrease_rate
    player_stamina_decrease_rate = var.palworld_player_stamina_decrease_rate
    item_weight_rate             = var.palworld_item_weight_rate
    rest_api_port                = var.palworld_rest_api_port
    rest_api_username            = var.palworld_rest_api_username
    autostop_check_minutes       = var.autostop_check_minutes
    autostop_idle_minutes        = var.autostop_idle_minutes
    healthcheck_timeout_minutes  = var.healthcheck_timeout_minutes
    local_backup_retention_days  = var.local_backup_retention_days
    s3_backup_uri                = local.s3_backup_uri
  })
}
