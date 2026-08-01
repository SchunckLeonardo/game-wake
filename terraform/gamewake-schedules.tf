resource "aws_sqs_queue" "operations_dead_letter" {
  name                      = "${local.name_prefix}-operations-dlq"
  message_retention_seconds = 1209600
  kms_master_key_id         = "alias/aws/sqs"
}

data "aws_iam_policy_document" "scheduler_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${local.name_prefix}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume_role.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    sid       = "InvokeOperationWorker"
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.operation_worker.arn]
  }

  statement {
    sid       = "WriteDeadLetters"
    effect    = "Allow"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.operations_dead_letter.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "${local.name_prefix}-scheduler"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_scheduler_schedule" "data_maintenance" {
  name                = "${local.name_prefix}-maintain-world-data"
  schedule_expression = "cron(0 3 * * ? *)"
  state               = "ENABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.operation_worker.arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      action = "maintain_data"
    })

    dead_letter_config {
      arn = aws_sqs_queue.operations_dead_letter.arn
    }

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 3
    }
  }

  depends_on = [aws_iam_role_policy.scheduler]
}
