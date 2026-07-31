output "instance_id" {
  description = "ID da unica EC2 controlada pela Lambda."
  value       = var.enable_legacy_single_server ? aws_instance.palworld[0].id : null
}

output "lambda_function_url" {
  description = "URL publica a configurar como Interactions Endpoint no Discord."
  value       = var.enable_legacy_single_server ? aws_lambda_function_url.discord[0].function_url : null
}

output "aws_region" {
  description = "Regiao do deploy."
  value       = var.aws_region
}

output "palworld_port" {
  description = "Porta UDP do servidor."
  value       = var.palworld_port
}

output "parameter_store_names" {
  description = "Nomes dos parametros; nenhum valor secreto e exposto."
  value = {
    discord_config              = aws_ssm_parameter.discord_config.name
    palworld_config             = aws_ssm_parameter.palworld_config.name
    palworld_settings_overrides = aws_ssm_parameter.palworld_settings_overrides.name
    discord_webhook             = aws_ssm_parameter.discord_webhook_url.name
    server_password             = aws_ssm_parameter.server_password.name
    admin_password              = aws_ssm_parameter.admin_password.name
    runtime_status              = aws_ssm_parameter.server_status.name
    discord_client_secret       = aws_ssm_parameter.discord_client_secret.name
    discord_bot_token           = aws_ssm_parameter.discord_bot_token.name
    abacatepay_api_key          = aws_ssm_parameter.abacatepay_api_key.name
    abacatepay_webhook_secret   = aws_ssm_parameter.abacatepay_webhook_secret.name
    abacatepay_public_key       = aws_ssm_parameter.abacatepay_public_key.name
  }
}

output "register_discord_commands_command" {
  description = "Comando local apos preencher .env."
  value       = "./scripts/register-discord-commands.sh"
}

output "configure_secrets_command" {
  description = "Comando local para substituir os placeholders SecureString."
  value       = "./scripts/configure-secrets.sh ${local.parameter_path}"
}

output "parameter_path" {
  description = "Prefixo nao secreto usado pelos parametros SSM deste ambiente."
  value       = local.parameter_path
}

output "session_manager_command" {
  description = "Acesso administrativo sem SSH."
  value       = var.enable_legacy_single_server ? "aws ssm start-session --region ${var.aws_region} --target ${aws_instance.palworld[0].id}" : null
}

output "post_deploy_instructions" {
  description = "Passos obrigatorios sem segredos."
  value = [
    "1. Execute ./scripts/configure-secrets.sh ${local.parameter_path}",
    "2. Configure o output gamewake_api.discord_interactions como Interactions Endpoint no Discord",
    "3. Configure o output gamewake_api.discord_oauth_callback como OAuth2 Redirect URL",
    "4. Execute ./scripts/register-discord-commands.sh para registrar /gamewake",
    "5. Publique a Console com NEXT_PUBLIC_GAMEWAKE_API_URL e NEXT_PUBLIC_DISCORD_APPLICATION_ID",
    "6. Confirme a assinatura do email SNS quando operations_alarm_email estiver configurado",
    "7. Execute o smoke test iniciando por /gamewake comecar",
  ]
}

output "s3_backup_bucket" {
  description = "Bucket privado de backups quando habilitado."
  value       = var.enable_s3_backup ? aws_s3_bucket.backups[0].id : null
}

output "gamewake_control_plane" {
  description = "Recursos nao secretos do control plane multi-tenant."
  value = {
    aurora_cluster_arn         = aws_rds_cluster.gamewake.arn
    operation_worker_name      = aws_lambda_function.operation_worker.function_name
    state_machine_arn          = aws_sfn_state_machine.world_operation.arn
    runtime_launch_template_id = aws_launch_template.gamewake_runtime.id
    world_data_bucket          = aws_s3_bucket.world_data.id
    reconciliation_schedule    = aws_scheduler_schedule.reconciliation.arn
    session_monitor_schedule   = aws_scheduler_schedule.session_monitor.arn
    data_maintenance_schedule  = aws_scheduler_schedule.data_maintenance.arn
    operations_dead_letter_url = aws_sqs_queue.operations_dead_letter.url
    operations_dashboard       = aws_cloudwatch_dashboard.gamewake.dashboard_name
    operations_alert_topic_arn = aws_sns_topic.operations_alerts.arn
  }
}

output "aurora_master_secret_arn" {
  description = "ARN do segredo gerenciado pelo RDS; o valor nunca e exposto pelo Terraform."
  value       = aws_rds_cluster.gamewake.master_user_secret[0].secret_arn
}

output "gamewake_api" {
  description = "Endpoints publicos autenticados na aplicacao; nenhum segredo e exposto."
  value = {
    base_url               = aws_lambda_function_url.gamewake_api.function_url
    discord_interactions   = "${aws_lambda_function_url.gamewake_api.function_url}discord/interactions"
    discord_oauth_callback = "${aws_lambda_function_url.gamewake_api.function_url}auth/discord/callback"
    abacatepay_webhook     = "${aws_lambda_function_url.gamewake_api.function_url}webhooks/abacatepay"
  }
}
