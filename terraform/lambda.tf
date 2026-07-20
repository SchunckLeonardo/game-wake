resource "aws_lambda_function" "discord" {
  function_name = "${local.name_prefix}-discord"
  description   = "Validated Discord interactions for one Palworld EC2 instance"
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.12"
  handler       = "handler.lambda_handler"
  architectures = ["x86_64"]

  filename         = local.lambda_package_file
  source_code_hash = fileexists(local.lambda_package_file) ? filebase64sha256(local.lambda_package_file) : null

  timeout                        = var.lambda_timeout_seconds
  memory_size                    = var.lambda_memory_size_mb
  reserved_concurrent_executions = var.lambda_reserved_concurrent_executions

  environment {
    variables = {
      DISCORD_CONFIG_JSON               = local.discord_config_payload
      PALWORLD_INSTANCE_ID              = aws_instance.palworld.id
      PALWORLD_CONFIG_PARAMETER_NAME    = aws_ssm_parameter.palworld_config.name
      PALWORLD_OVERRIDES_PARAMETER_NAME = aws_ssm_parameter.palworld_settings_overrides.name
      PALWORLD_STATUS_PARAMETER_NAME    = aws_ssm_parameter.server_status.name
      PALWORLD_PORT                     = tostring(var.palworld_port)
      LOG_LEVEL                         = "INFO"
    }
  }

  logging_config {
    log_format            = "JSON"
    application_log_level = "INFO"
    system_log_level      = "WARN"
    log_group             = aws_cloudwatch_log_group.lambda.name
  }

  lifecycle {
    precondition {
      condition     = fileexists(local.lambda_package_file)
      error_message = "Pacote Lambda ausente. Execute make lambda-package antes de terraform plan."
    }
    precondition {
      condition     = var.discord_public_key != "REPLACE_ME" && var.discord_guild_id != "REPLACE_ME"
      error_message = "Preencha discord_public_key e discord_guild_id no terraform.tfvars."
    }
    precondition {
      condition     = length(var.discord_allowed_user_ids) + length(var.discord_allowed_role_ids) > 0
      error_message = "Configure pelo menos um usuario ou cargo autorizado do Discord."
    }
  }

  depends_on = [aws_iam_role_policy.lambda_runtime]
}

resource "aws_lambda_function_url" "discord" {
  function_name      = aws_lambda_function.discord.function_name
  authorization_type = "NONE"
  invoke_mode        = "BUFFERED"
}

resource "aws_lambda_permission" "function_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.discord.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "function_url_invoke" {
  statement_id             = "AllowPublicInvokeOnlyViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.discord.function_name
  principal                = "*"
  invoked_via_function_url = true
}
