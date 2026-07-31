resource "aws_cloudwatch_log_group" "lambda" {
  name              = local.lambda_log_group_name
  retention_in_days = var.cloudwatch_log_retention_days
}

resource "aws_sns_topic" "operations_alerts" {
  name              = "${local.name_prefix}-operations-alerts"
  kms_master_key_id = "alias/aws/sns"
}

resource "aws_sns_topic_subscription" "operations_email" {
  count = var.operations_alarm_email == null ? 0 : 1

  topic_arn = aws_sns_topic.operations_alerts.arn
  protocol  = "email"
  endpoint  = var.operations_alarm_email
}

resource "aws_cloudwatch_metric_alarm" "gamewake_api_errors" {
  alarm_name          = "${local.name_prefix}-api-errors"
  alarm_description   = "GameWake API returned Lambda invocation errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.operations_alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.gamewake_api.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "operation_worker_errors" {
  alarm_name          = "${local.name_prefix}-operation-worker-errors"
  alarm_description   = "Durable World operation worker failed"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.operations_alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.operation_worker.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "operations_dead_letters" {
  alarm_name          = "${local.name_prefix}-operations-dead-letters"
  alarm_description   = "A scheduled operation reached the dead-letter queue"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.operations_alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.operations_dead_letter.name
  }
}

resource "aws_cloudwatch_metric_alarm" "aurora_capacity" {
  alarm_name          = "${local.name_prefix}-aurora-capacity"
  alarm_description   = "Aurora Serverless remained near its configured maximum"
  namespace           = "AWS/RDS"
  metric_name         = "ServerlessDatabaseCapacity"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = var.aurora_max_acu * 0.9
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.operations_alerts.arn]

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.gamewake.cluster_identifier
  }
}

resource "aws_cloudwatch_dashboard" "gamewake" {
  dashboard_name = "${local.name_prefix}-operations"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          region = var.aws_region
          title  = "API and worker"
          view   = "timeSeries"
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.gamewake_api.function_name],
            [".", "Errors", ".", "."],
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.operation_worker.function_name],
            [".", "Errors", ".", "."],
          ]
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          region = var.aws_region
          title  = "Durable orchestration and data"
          view   = "timeSeries"
          metrics = [
            ["AWS/States", "ExecutionsFailed", "StateMachineArn", aws_sfn_state_machine.world_operation.arn],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.operations_dead_letter.name],
            ["AWS/RDS", "ServerlessDatabaseCapacity", "DBClusterIdentifier", aws_rds_cluster.gamewake.cluster_identifier],
          ]
        }
      },
    ]
  })
}
