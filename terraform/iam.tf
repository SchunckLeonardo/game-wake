data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${local.name_prefix}-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ec2_ssm_core" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "ec2_runtime" {
  statement {
    sid    = "ReadOnlyRequiredSecrets"
    effect = "Allow"
    actions = [
      "ssm:GetParameter"
    ]
    resources = [
      aws_ssm_parameter.palworld_config.arn,
      aws_ssm_parameter.palworld_settings_overrides.arn,
      aws_ssm_parameter.discord_webhook_url.arn,
      aws_ssm_parameter.server_password.arn,
      aws_ssm_parameter.admin_password.arn,
    ]
  }

  statement {
    sid     = "PublishOnlyRuntimeStatus"
    effect  = "Allow"
    actions = ["ssm:PutParameter"]
    resources = [
      aws_ssm_parameter.server_status.arn,
    ]
  }

  dynamic "statement" {
    for_each = var.enable_s3_backup ? [1] : []
    content {
      sid    = "WriteBackupObjects"
      effect = "Allow"
      actions = [
        "s3:AbortMultipartUpload",
        "s3:PutObject",
      ]
      resources = ["${aws_s3_bucket.backups[0].arn}/saves/*"]
    }
  }

  dynamic "statement" {
    for_each = var.enable_s3_backup ? [1] : []
    content {
      sid       = "ListBackupPrefix"
      effect    = "Allow"
      actions   = ["s3:ListBucket"]
      resources = [aws_s3_bucket.backups[0].arn]
      condition {
        test     = "StringLike"
        variable = "s3:prefix"
        values   = ["saves/*"]
      }
    }
  }
}

resource "aws_iam_role_policy" "ec2_runtime" {
  name   = "${local.name_prefix}-runtime"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ec2_runtime.json
}

resource "aws_iam_instance_profile" "palworld" {
  name = "${local.name_prefix}-instance-profile"
  role = aws_iam_role.ec2.name
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name_prefix}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "lambda_runtime" {
  statement {
    sid       = "DescribeInstancesInRegion"
    effect    = "Allow"
    actions   = ["ec2:DescribeInstances"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [var.aws_region]
    }
  }

  statement {
    sid    = "StartOrEmergencyStopOnlyPalworldInstance"
    effect = "Allow"
    actions = [
      "ec2:StartInstances",
      "ec2:StopInstances",
    ]
    resources = [local.instance_arn]
  }

  statement {
    sid       = "RunOnlyApprovedDocumentOnPalworldInstance"
    effect    = "Allow"
    actions   = ["ssm:SendCommand"]
    resources = [local.ssm_document_arn, local.instance_arn]
  }

  statement {
    sid       = "ReadCommandInvocation"
    effect    = "Allow"
    actions   = ["ssm:GetCommandInvocation"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [var.aws_region]
    }
  }

  statement {
    sid    = "ReadOnlyRuntimeConfiguration"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]
    resources = [
      aws_ssm_parameter.server_status.arn,
      aws_ssm_parameter.palworld_config.arn,
      aws_ssm_parameter.palworld_settings_overrides.arn,
    ]
  }

  statement {
    sid       = "WriteOnlyPalworldSettingsOverrides"
    effect    = "Allow"
    actions   = ["ssm:PutParameter"]
    resources = [aws_ssm_parameter.palworld_settings_overrides.arn]
  }

  statement {
    sid       = "CreateOwnLogGroup"
    effect    = "Allow"
    actions   = ["logs:CreateLogGroup"]
    resources = ["arn:${data.aws_partition.current.partition}:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:${local.lambda_log_group_name}"]
  }

  statement {
    sid    = "WriteOnlyOwnLogStreams"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }
}

resource "aws_iam_role_policy" "lambda_runtime" {
  name   = "${local.name_prefix}-runtime"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_runtime.json
}
