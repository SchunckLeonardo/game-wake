locals {
  operation_worker_name              = "${local.name_prefix}-operation-worker"
  world_operation_state_machine_name = "${local.name_prefix}-world-operation"
  world_operation_state_machine_arn  = "arn:${data.aws_partition.current.partition}:states:${var.aws_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${local.world_operation_state_machine_name}"
}

resource "aws_cloudwatch_log_group" "operation_worker" {
  name              = "/aws/lambda/${local.operation_worker_name}"
  retention_in_days = var.cloudwatch_log_retention_days
}

resource "aws_cloudwatch_log_group" "world_operation" {
  name              = "/aws/vendedlogs/states/${local.world_operation_state_machine_name}"
  retention_in_days = var.cloudwatch_log_retention_days
}

data "aws_iam_policy_document" "operation_worker_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "operation_worker" {
  name               = "${local.name_prefix}-operation-worker"
  assume_role_policy = data.aws_iam_policy_document.operation_worker_assume_role.json
}

data "aws_iam_policy_document" "operation_worker" {
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
    sid    = "ProvisionRuntimeFromApprovedTemplate"
    effect = "Allow"
    actions = [
      "ec2:RunInstances",
    ]
    resources = [
      aws_launch_template.gamewake_runtime.arn,
      aws_subnet.public.arn,
      aws_security_group.palworld.arn,
      aws_iam_instance_profile.palworld.arn,
      "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}::image/${local.gamewake_runtime_image_id}",
      "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/*",
      "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:network-interface/*",
      "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:volume/*",
    ]
  }

  statement {
    sid     = "TagRuntimeDuringProvisioning"
    effect  = "Allow"
    actions = ["ec2:CreateTags"]
    resources = [
      "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/*",
      "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:volume/*",
    ]

    condition {
      test     = "StringEquals"
      variable = "ec2:CreateAction"
      values   = ["RunInstances"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/GameWakeManaged"
      values   = ["true"]
    }
  }

  statement {
    sid       = "DescribeRuntime"
    effect    = "Allow"
    actions   = ["ec2:DescribeInstances"]
    resources = ["*"]
  }

  statement {
    sid       = "TerminateManagedRuntime"
    effect    = "Allow"
    actions   = ["ec2:TerminateInstances"]
    resources = ["arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/*"]

    condition {
      test     = "StringEquals"
      variable = "ec2:ResourceTag/GameWakeManaged"
      values   = ["true"]
    }
  }

  statement {
    sid       = "PassOnlyRuntimeRole"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.ec2.arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ec2.amazonaws.com"]
    }
  }

  statement {
    sid     = "RunManagedHostActions"
    effect  = "Allow"
    actions = ["ssm:SendCommand"]
    resources = [
      local.ssm_document_arn,
      "arn:${data.aws_partition.current.partition}:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/*",
    ]
  }

  statement {
    sid       = "ReadManagedHostAction"
    effect    = "Allow"
    actions   = ["ssm:GetCommandInvocation"]
    resources = ["*"]
  }

  statement {
    sid    = "ManagePerWorldConfiguration"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:PutParameter",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${local.parameter_path}/gamewake/worlds/*",
    ]
  }

  statement {
    sid       = "ReadDiscordNotificationToken"
    effect    = "Allow"
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.discord_bot_token.arn]
  }

  statement {
    sid    = "ManageWorldData"
    effect = "Allow"
    actions = [
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      "s3:GetObject",
      "s3:ListBucket",
      "s3:ListBucketVersions",
      "s3:PutObject",
    ]
    resources = [
      aws_s3_bucket.world_data.arn,
      "${aws_s3_bucket.world_data.arn}/*",
    ]
  }

  statement {
    sid    = "UseWorldDataKey"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey",
    ]
    resources = [aws_kms_key.world_data.arn]
  }

  statement {
    sid    = "ReconcileWorldOperations"
    effect = "Allow"
    actions = [
      "states:DescribeExecution",
      "states:RedriveExecution",
      "states:StartExecution",
    ]
    resources = [
      local.world_operation_state_machine_arn,
      "arn:${data.aws_partition.current.partition}:states:${var.aws_region}:${data.aws_caller_identity.current.account_id}:execution:${local.world_operation_state_machine_name}:*",
    ]
  }

  statement {
    sid    = "WriteWorkerLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.operation_worker.arn}:*"]
  }
}

resource "aws_iam_role_policy" "operation_worker" {
  name   = "${local.name_prefix}-operation-worker"
  role   = aws_iam_role.operation_worker.id
  policy = data.aws_iam_policy_document.operation_worker.json
}

resource "aws_lambda_function" "operation_worker" {
  function_name = local.operation_worker_name
  description   = "Advances one durable GameWake World operation phase"
  role          = aws_iam_role.operation_worker.arn
  runtime       = "python3.12"
  handler       = "gamewake_worker.lambda_handler"
  architectures = ["x86_64"]

  filename         = local.lambda_package_file
  source_code_hash = fileexists(local.lambda_package_file) ? filebase64sha256(local.lambda_package_file) : null
  timeout          = 900
  memory_size      = 512

  environment {
    variables = {
      AURORA_CLUSTER_ARN               = aws_rds_cluster.gamewake.arn
      AURORA_DATABASE_NAME             = var.aurora_database_name
      AURORA_SECRET_ARN                = aws_rds_cluster.gamewake.master_user_secret[0].secret_arn
      DISCORD_BOT_TOKEN_PARAMETER_NAME = aws_ssm_parameter.discord_bot_token.name
      GAMEWAKE_WORLD_PARAMETER_PREFIX  = "${local.parameter_path}/gamewake/worlds"
      PALWORLD_BASE_CONFIG_JSON        = local.palworld_config_payload
      RUNTIME_LAUNCH_TEMPLATE_ID       = aws_launch_template.gamewake_runtime.id
      STORAGE_ALLOWANCE_BYTES          = tostring(var.storage_allowance_bytes)
      STORAGE_GRACE_DAYS               = tostring(var.storage_grace_days)
      STORAGE_RATE_PER_GIB_MONTH_BRL   = tostring(var.storage_rate_per_gib_month_brl)
      WORLD_DATA_BUCKET                = aws_s3_bucket.world_data.id
    }
  }

  logging_config {
    log_format            = "JSON"
    application_log_level = "INFO"
    system_log_level      = "WARN"
    log_group             = aws_cloudwatch_log_group.operation_worker.name
  }

  lifecycle {
    precondition {
      condition     = fileexists(local.lambda_package_file)
      error_message = "Pacote Lambda ausente. Execute make lambda-package antes de terraform plan."
    }
  }

  depends_on = [aws_iam_role_policy.operation_worker]
}

data "aws_iam_policy_document" "step_functions_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "step_functions" {
  name               = "${local.name_prefix}-world-operations"
  assume_role_policy = data.aws_iam_policy_document.step_functions_assume_role.json
}

data "aws_iam_policy_document" "step_functions" {
  statement {
    sid       = "InvokeOperationWorker"
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.operation_worker.arn]
  }

  statement {
    sid       = "RenewLongRunningSessionMonitor"
    effect    = "Allow"
    actions   = ["states:StartExecution"]
    resources = [local.world_operation_state_machine_arn]
  }

  statement {
    sid    = "DeliverWorkflowLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:DescribeLogGroups",
      "logs:DescribeResourcePolicies",
      "logs:GetLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:UpdateLogDelivery",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "step_functions" {
  name   = "${local.name_prefix}-world-operations"
  role   = aws_iam_role.step_functions.id
  policy = data.aws_iam_policy_document.step_functions.json
}

resource "aws_sfn_state_machine" "world_operation" {
  name     = local.world_operation_state_machine_name
  role_arn = aws_iam_role.step_functions.arn
  type     = "STANDARD"
  definition = templatefile("${path.module}/state-machines/world-operation.asl.json", {
    operation_worker_arn              = aws_lambda_function.operation_worker.arn
    world_operation_state_machine_arn = local.world_operation_state_machine_arn
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.world_operation.arn}:*"
    include_execution_data = false
    level                  = "ERROR"
  }

  depends_on = [aws_iam_role_policy.step_functions]
}

resource "aws_lambda_invocation" "database_migrations" {
  function_name = aws_lambda_function.operation_worker.function_name
  input         = jsonencode({ action = "migrate" })

  triggers = {
    lambda_source = aws_lambda_function.operation_worker.source_code_hash
    migration = sha256(join("", [
      for migration in sort(fileset("${path.module}/../gamewake/persistence/sql", "*.sql")) :
      filesha256("${path.module}/../gamewake/persistence/sql/${migration}")
    ]))
  }

  depends_on = [aws_rds_cluster_instance.gamewake]
}
