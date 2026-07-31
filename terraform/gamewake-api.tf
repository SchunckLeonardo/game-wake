locals {
  gamewake_api_name = "${local.name_prefix}-api"
}

resource "aws_kms_key" "sessions" {
  description              = "HMAC signing key for short-lived GameWake sessions"
  key_usage                = "GENERATE_VERIFY_MAC"
  customer_master_key_spec = "HMAC_256"
  deletion_window_in_days  = 30
}

resource "aws_kms_alias" "sessions" {
  name          = "alias/${local.name_prefix}-sessions"
  target_key_id = aws_kms_key.sessions.key_id
}

resource "aws_cloudwatch_log_group" "gamewake_api" {
  name              = "/aws/lambda/${local.gamewake_api_name}"
  retention_in_days = var.cloudwatch_log_retention_days
}

data "aws_iam_policy_document" "gamewake_api_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "gamewake_api" {
  name               = local.gamewake_api_name
  assume_role_policy = data.aws_iam_policy_document.gamewake_api_assume_role.json
}

data "aws_iam_policy_document" "gamewake_api" {
  statement {
    sid    = "AuroraDataApi"
    effect = "Allow"
    actions = [
      "rds-data:BeginTransaction",
      "rds-data:CommitTransaction",
      "rds-data:ExecuteStatement",
      "rds-data:RollbackTransaction",
    ]
    resources = [aws_rds_cluster.gamewake.arn]
  }

  statement {
    sid       = "ReadAuroraCredentials"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_rds_cluster.gamewake.master_user_secret[0].secret_arn]
  }

  statement {
    sid     = "ReadOnlyProviderSecrets"
    effect  = "Allow"
    actions = ["ssm:GetParameter"]
    resources = [
      aws_ssm_parameter.discord_client_secret.arn,
      aws_ssm_parameter.abacatepay_api_key.arn,
      aws_ssm_parameter.abacatepay_webhook_secret.arn,
      aws_ssm_parameter.abacatepay_public_key.arn,
      "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${local.parameter_path}/gamewake/worlds/*",
    ]
  }

  statement {
    sid       = "DescribeWorldRuntime"
    effect    = "Allow"
    actions   = ["ec2:DescribeInstances"]
    resources = ["*"]
  }

  statement {
    sid    = "AuthenticateSessions"
    effect = "Allow"
    actions = [
      "kms:GenerateMac",
      "kms:VerifyMac",
    ]
    resources = [aws_kms_key.sessions.arn]
  }

  statement {
    sid       = "StartWorldOperations"
    effect    = "Allow"
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.world_operation.arn]
  }

  statement {
    sid    = "WriteApiLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.gamewake_api.arn}:*"]
  }
}

resource "aws_iam_role_policy" "gamewake_api" {
  name   = local.gamewake_api_name
  role   = aws_iam_role.gamewake_api.id
  policy = data.aws_iam_policy_document.gamewake_api.json
}

resource "aws_lambda_function" "gamewake_api" {
  function_name = local.gamewake_api_name
  description   = "GameWake OAuth, Control Plane, Discord and AbacatePay HTTP edge"
  role          = aws_iam_role.gamewake_api.arn
  runtime       = "python3.12"
  handler       = "gamewake_api.lambda_handler"
  architectures = ["x86_64"]

  filename         = local.lambda_package_file
  source_code_hash = fileexists(local.lambda_package_file) ? filebase64sha256(local.lambda_package_file) : null
  timeout          = 29
  memory_size      = 512

  environment {
    variables = {
      ABACATEPAY_API_KEY_PARAMETER_NAME = aws_ssm_parameter.abacatepay_api_key.name
      ABACATEPAY_PACKAGES_JSON = jsonencode([
        for package in var.abacatepay_packages : {
          id        = package.id
          amount    = package.amount
          productId = package.product_id
        }
      ])
      ABACATEPAY_PUBLIC_KEY_PARAMETER_NAME     = aws_ssm_parameter.abacatepay_public_key.name
      ABACATEPAY_WEBHOOK_SECRET_PARAMETER_NAME = aws_ssm_parameter.abacatepay_webhook_secret.name
      AURORA_CLUSTER_ARN                       = aws_rds_cluster.gamewake.arn
      AURORA_DATABASE_NAME                     = var.aurora_database_name
      AURORA_SECRET_ARN                        = aws_rds_cluster.gamewake.master_user_secret[0].secret_arn
      DISCORD_APPLICATION_ID                   = var.discord_application_id
      DISCORD_CLIENT_SECRET_PARAMETER_NAME     = aws_ssm_parameter.discord_client_secret.name
      DISCORD_PUBLIC_KEY                       = var.discord_public_key
      GAMEWAKE_CONSOLE_URL                     = var.gamewake_console_url
      GAMEWAKE_WORLD_PARAMETER_PREFIX          = "${local.parameter_path}/gamewake/worlds"
      PALWORLD_PORT                            = tostring(var.palworld_port)
      RUNTIME_PROFILE_HOURLY_RATES_JSON        = jsonencode(var.runtime_profile_hourly_rates)
      SESSION_KMS_KEY_ID                       = aws_kms_key.sessions.key_id
      WORLD_OPERATION_STATE_MACHINE_ARN        = aws_sfn_state_machine.world_operation.arn
    }
  }

  logging_config {
    log_format            = "JSON"
    application_log_level = "INFO"
    system_log_level      = "WARN"
    log_group             = aws_cloudwatch_log_group.gamewake_api.name
  }

  lifecycle {
    precondition {
      condition     = fileexists(local.lambda_package_file)
      error_message = "Pacote Lambda ausente. Execute make lambda-package antes de terraform plan."
    }
    precondition {
      condition = (
        var.discord_application_id != "REPLACE_ME" &&
        var.discord_public_key != "REPLACE_ME"
      )
      error_message = "Preencha discord_application_id e discord_public_key."
    }
    precondition {
      condition = alltrue([
        for package in var.abacatepay_packages : package.product_id != "REPLACE_ME"
      ])
      error_message = "Mapeie todos os pacotes para Product IDs reais da AbacatePay."
    }
  }

  depends_on = [
    aws_iam_role_policy.gamewake_api,
    aws_lambda_invocation.database_migrations,
  ]
}

resource "aws_lambda_function_url" "gamewake_api" {
  function_name      = aws_lambda_function.gamewake_api.function_name
  authorization_type = "NONE"
  invoke_mode        = "BUFFERED"

  cors {
    allow_credentials = false
    allow_headers     = ["authorization", "content-type", "idempotency-key"]
    allow_methods     = ["GET", "POST", "PATCH", "DELETE"]
    allow_origins     = [var.gamewake_console_url]
    max_age           = 300
  }
}

resource "aws_lambda_permission" "gamewake_api_url" {
  statement_id           = "AllowPublicGameWakeFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.gamewake_api.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "gamewake_api_url_invoke" {
  statement_id             = "AllowPublicGameWakeInvokeOnlyViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.gamewake_api.function_name
  principal                = "*"
  invoked_via_function_url = true
}
