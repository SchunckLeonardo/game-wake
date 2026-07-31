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

output "session_manager_command" {
  description = "Acesso administrativo sem SSH."
  value       = var.enable_legacy_single_server ? "aws ssm start-session --region ${var.aws_region} --target ${aws_instance.palworld[0].id}" : null
}

output "post_deploy_instructions" {
  description = "Passos obrigatorios sem segredos."
  value = [
    "1. Execute ./scripts/configure-secrets.sh ${local.parameter_path}",
    "2. Configure a Lambda Function URL como Interactions Endpoint no Discord",
    "3. Execute ./scripts/register-discord-commands.sh",
    "4. Confirme que a EC2 terminou o bootstrap e ficou stopped",
    "5. Use /palworld ligar no Discord",
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
  }
}

output "aurora_master_secret_arn" {
  description = "ARN do segredo gerenciado pelo RDS; o valor nunca e exposto pelo Terraform."
  value       = aws_rds_cluster.gamewake.master_user_secret[0].secret_arn
}
