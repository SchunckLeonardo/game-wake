resource "aws_ssm_parameter" "discord_client_secret" {
  name             = "${local.parameter_path}/gamewake/discord-client-secret"
  description      = "Discord OAuth2 client secret for GameWake sign-in"
  type             = "SecureString"
  value_wo         = var.secure_parameter_placeholder
  value_wo_version = 1
}

resource "aws_ssm_parameter" "discord_bot_token" {
  name             = "${local.parameter_path}/gamewake/discord-bot-token"
  description      = "Discord Bot Token used only for non-sensitive terminal operation notifications"
  type             = "SecureString"
  value_wo         = var.secure_parameter_placeholder
  value_wo_version = 1
}

resource "aws_ssm_parameter" "abacatepay_api_key" {
  name             = "${local.parameter_path}/gamewake/abacatepay-api-key"
  description      = "AbacatePay API v2 key"
  type             = "SecureString"
  value_wo         = var.secure_parameter_placeholder
  value_wo_version = 1
}

resource "aws_ssm_parameter" "abacatepay_webhook_secret" {
  name             = "${local.parameter_path}/gamewake/abacatepay-webhook-secret"
  description      = "AbacatePay webhookSecret embedded in the webhook URL"
  type             = "SecureString"
  value_wo         = var.secure_parameter_placeholder
  value_wo_version = 1
}

resource "aws_ssm_parameter" "abacatepay_public_key" {
  name             = "${local.parameter_path}/gamewake/abacatepay-public-key"
  description      = "AbacatePay public HMAC key used to verify webhook signatures"
  type             = "SecureString"
  value_wo         = var.secure_parameter_placeholder
  value_wo_version = 1
}
