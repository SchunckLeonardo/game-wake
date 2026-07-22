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

  name_prefix                = "${var.project_name}-${var.environment}"
  parameter_path             = "/${var.project_name}/${var.environment}"
  lambda_package_file        = abspath("${path.module}/${var.lambda_package_path}")
  s3_backup_bucket_name      = var.s3_backup_bucket_name != null ? var.s3_backup_bucket_name : "${var.project_name}-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  s3_backup_uri              = var.enable_s3_backup ? "s3://${local.s3_backup_bucket_name}/saves" : ""
  ssm_document_arn           = "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}::document/AWS-RunShellScript"
  instance_arn               = "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/${aws_instance.palworld.id}"
  lambda_log_group_name      = "/aws/lambda/${local.name_prefix}-discord"
  palworld_settings_path     = fileexists("${path.module}/../config/palworld-settings.json") ? "${path.module}/../config/palworld-settings.json" : "${path.module}/../config/palworld-settings.json.example"
  palworld_settings_document = jsondecode(file(local.palworld_settings_path))
  palworld_settings          = local.palworld_settings_document.settings
  palworld_settings_keys = toset([
    "server_name",
    "server_description",
    "max_players",
    "exp_rate",
    "collection_drop_rate",
    "enemy_drop_item_rate",
    "base_camp_worker_max_num",
    "allow_global_palbox_export",
    "allow_global_palbox_import",
    "pal_auto_hp_regen_rate_in_sleep",
    "pal_egg_default_hatching_time",
    "pal_spawn_rate",
    "death_penalty",
    "pal_damage_attack_rate",
    "pal_damage_defense_rate",
    "player_damage_attack_rate",
    "player_damage_defense_rate",
    "pal_stamina_decrease_rate",
    "player_stamina_decrease_rate",
    "item_weight_rate",
  ])
  palworld_positive_number_keys = toset([
    "exp_rate",
    "collection_drop_rate",
    "enemy_drop_item_rate",
    "pal_auto_hp_regen_rate_in_sleep",
    "pal_spawn_rate",
    "pal_damage_attack_rate",
    "pal_damage_defense_rate",
    "player_damage_attack_rate",
    "player_damage_defense_rate",
    "pal_stamina_decrease_rate",
    "player_stamina_decrease_rate",
    "item_weight_rate",
  ])
  discord_config_payload = jsonencode({
    public_key       = var.discord_public_key
    guild_id         = var.discord_guild_id
    allowed_user_ids = var.discord_allowed_user_ids
    allowed_role_ids = var.discord_allowed_role_ids
  })
  palworld_config_payload = jsonencode({
    server_name                     = local.palworld_settings.server_name
    server_description              = local.palworld_settings.server_description
    port                            = var.palworld_port
    max_players                     = local.palworld_settings.max_players
    exp_rate                        = local.palworld_settings.exp_rate
    collection_drop_rate            = local.palworld_settings.collection_drop_rate
    enemy_drop_item_rate            = local.palworld_settings.enemy_drop_item_rate
    base_camp_worker_max_num        = local.palworld_settings.base_camp_worker_max_num
    allow_global_palbox_export      = local.palworld_settings.allow_global_palbox_export
    allow_global_palbox_import      = local.palworld_settings.allow_global_palbox_import
    pal_auto_hp_regen_rate_in_sleep = local.palworld_settings.pal_auto_hp_regen_rate_in_sleep
    pal_egg_default_hatching_time   = local.palworld_settings.pal_egg_default_hatching_time
    pal_spawn_rate                  = local.palworld_settings.pal_spawn_rate
    death_penalty                   = local.palworld_settings.death_penalty
    pal_damage_attack_rate          = local.palworld_settings.pal_damage_attack_rate
    pal_damage_defense_rate         = local.palworld_settings.pal_damage_defense_rate
    player_damage_attack_rate       = local.palworld_settings.player_damage_attack_rate
    player_damage_defense_rate      = local.palworld_settings.player_damage_defense_rate
    pal_stamina_decrease_rate       = local.palworld_settings.pal_stamina_decrease_rate
    player_stamina_decrease_rate    = local.palworld_settings.player_stamina_decrease_rate
    item_weight_rate                = local.palworld_settings.item_weight_rate
    rest_api_port                   = var.palworld_rest_api_port
    rest_api_username               = var.palworld_rest_api_username
    autostop_check_minutes          = var.autostop_check_minutes
    autostop_idle_minutes           = var.autostop_idle_minutes
    healthcheck_timeout_minutes     = var.healthcheck_timeout_minutes
    local_backup_retention_days     = var.local_backup_retention_days
    s3_backup_uri                   = local.s3_backup_uri
  })
}

check "palworld_settings_document" {
  assert {
    condition     = try(local.palworld_settings_document.schema_version == 1, false)
    error_message = "config/palworld-settings.json must use schema_version 1. Run ./palworld settings validate."
  }

  assert {
    condition = try(
      length(setsubtract(local.palworld_settings_keys, toset(keys(local.palworld_settings)))) == 0 &&
      length(setsubtract(toset(keys(local.palworld_settings)), local.palworld_settings_keys)) == 0,
      false,
    )
    error_message = "config/palworld-settings.json has missing or unknown settings. Run ./palworld settings validate."
  }

  assert {
    condition = try(
      local.palworld_settings.server_name != "" &&
      length(local.palworld_settings.server_name) <= 100 &&
      length(local.palworld_settings.server_description) <= 500 &&
      local.palworld_settings.max_players >= 1 &&
      floor(local.palworld_settings.max_players) == local.palworld_settings.max_players &&
      local.palworld_settings.base_camp_worker_max_num >= 1 &&
      local.palworld_settings.base_camp_worker_max_num <= 50 &&
      floor(local.palworld_settings.base_camp_worker_max_num) == local.palworld_settings.base_camp_worker_max_num &&
      contains(["true", "false"], jsonencode(local.palworld_settings.allow_global_palbox_export)) &&
      contains(["true", "false"], jsonencode(local.palworld_settings.allow_global_palbox_import)) &&
      local.palworld_settings.pal_egg_default_hatching_time >= 0 &&
      alltrue([
        for key in local.palworld_positive_number_keys : local.palworld_settings[key] > 0
      ]) &&
      contains(["None", "Item", "ItemAndEquipment", "All"], local.palworld_settings.death_penalty),
      false,
    )
    error_message = "config/palworld-settings.json contains invalid values. Run ./palworld settings validate."
  }
}
