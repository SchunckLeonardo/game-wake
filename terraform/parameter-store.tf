resource "aws_ssm_parameter" "discord_config" {
  name        = "${local.parameter_path}/discord/config"
  description = "Guild, public key and allowlists used by the Discord Lambda"
  type        = "String"
  value       = local.discord_config_payload
}

resource "aws_ssm_parameter" "palworld_config" {
  name        = "${local.parameter_path}/palworld/config"
  description = "Non-secret game, monitor and backup configuration loaded on every start"
  type        = "String"
  value       = local.palworld_config_payload
}

resource "aws_ssm_parameter" "palworld_settings_overrides" {
  name        = "${local.parameter_path}/palworld/settings-overrides"
  description = "Non-secret Palworld settings changed through the Discord panel"
  type        = "String"
  value       = "{}"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "discord_webhook_url" {
  name             = "${local.parameter_path}/discord/webhook-url"
  description      = "Discord webhook used by the EC2 for ready/autostop notifications"
  type             = "SecureString"
  value_wo         = var.secure_parameter_placeholder
  value_wo_version = 1
}

resource "aws_ssm_parameter" "server_password" {
  name             = "${local.parameter_path}/palworld/server-password"
  description      = "Palworld ServerPassword"
  type             = "SecureString"
  value_wo         = var.secure_parameter_placeholder
  value_wo_version = 1
}

resource "aws_ssm_parameter" "admin_password" {
  name             = "${local.parameter_path}/palworld/admin-password"
  description      = "Palworld AdminPassword and REST credential secret"
  type             = "SecureString"
  value_wo         = var.secure_parameter_placeholder
  value_wo_version = 1
}

resource "aws_ssm_parameter" "server_status" {
  name        = "${local.parameter_path}/runtime/status"
  description = "Non-secret EC2-published snapshot consumed by the Discord status command"
  type        = "String"
  value = jsonencode({
    service_state = "offline"
    players       = null
    updated_at    = null
  })

  lifecycle {
    ignore_changes = [value]
  }
}
