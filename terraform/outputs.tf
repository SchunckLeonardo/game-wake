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
    discord_client_secret     = aws_ssm_parameter.discord_client_secret.name
    discord_bot_token         = aws_ssm_parameter.discord_bot_token.name
    abacatepay_api_key        = aws_ssm_parameter.abacatepay_api_key.name
    abacatepay_webhook_secret = aws_ssm_parameter.abacatepay_webhook_secret.name
    abacatepay_public_key     = aws_ssm_parameter.abacatepay_public_key.name
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

output "gamewake_control_plane" {
  description = "Recursos nao secretos do control plane multi-tenant."
  value = {
    aurora_cluster_arn         = aws_rds_cluster.gamewake.arn
    operation_worker_name      = aws_lambda_function.operation_worker.function_name
    state_machine_arn          = aws_sfn_state_machine.world_operation.arn
    runtime_launch_template_id = aws_launch_template.gamewake_runtime.id
    runtime_image_id           = local.gamewake_runtime_image_id
    world_data_bucket          = aws_s3_bucket.world_data.id
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
