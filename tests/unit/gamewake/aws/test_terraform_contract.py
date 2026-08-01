import base64
import gzip
import re
from pathlib import Path

TERRAFORM = Path(__file__).parents[4] / "terraform"
PROJECT_ROOT = TERRAFORM.parent
EC2_USER_DATA_LIMIT_BYTES = 16 * 1024

USER_DATA_PAYLOADS = {
    "common_script_b64": "palworld-common.sh",
    "render_settings_script_b64": "render_settings.py",
    "install_script_b64": "install-palworld.sh",
    "configure_script_b64": "configure-palworld.sh",
    "start_script_b64": "start-palworld.sh",
    "stop_script_b64": "stop-palworld.sh",
    "palworld_service_b64": "palworld.service",
    "gamewake_operation_script_b64": "gamewake-operation.sh",
}


def render_user_data() -> str:
    template = source("user-data.sh.tpl")
    values = {
        key: base64.b64encode((PROJECT_ROOT / "server" / filename).read_bytes()).decode()
        for key, filename in USER_DATA_PAYLOADS.items()
    }
    values.update(
        {
            "palworld_server_name_b64": base64.b64encode(b"n" * 100).decode(),
            "palworld_server_description_b64": base64.b64encode(b"d" * 500).decode(),
        }
    )
    rendered = re.sub(
        r"\$\{([a-z0-9_]+)\}",
        lambda match: values.get(match.group(1), "x" * 96),
        template,
    )
    assert "${" not in rendered
    return rendered


def source(name):
    return (TERRAFORM / name).read_text()


def test_ec2_bootstrap_fits_the_user_data_limit_with_headroom():
    size = len(gzip.compress(render_user_data().encode(), mtime=0))

    assert size <= EC2_USER_DATA_LIMIT_BYTES - 1024, size


def test_aurora_serverless_v2_uses_data_api_encryption_and_private_subnets():
    database = source("gamewake-database.tf")

    assert 'resource "aws_rds_cluster" "gamewake"' in database
    assert 'engine_mode                 = "provisioned"' in database
    assert "serverlessv2_scaling_configuration" in database
    assert "engine_version              = var.aurora_engine_version" in database
    assert "seconds_until_auto_pause = var.aurora_auto_pause_seconds" in database
    assert "enable_http_endpoint        = true" in database
    assert "storage_encrypted           = true" in database
    assert "manage_master_user_password = true" in database
    assert '"db.serverless"' in database
    assert 'resource "aws_db_subnet_group" "gamewake"' in database


def test_standard_workflow_invokes_the_worker_with_structured_logs():
    orchestration = source("gamewake-orchestration.tf")

    assert 'resource "aws_sfn_state_machine" "world_operation"' in orchestration
    assert 'type     = "STANDARD"' in orchestration
    assert 'templatefile("${path.module}/state-machines/world-operation.asl.json"' in orchestration
    assert "include_execution_data = false" in orchestration
    assert 'resource "aws_lambda_function" "operation_worker"' in orchestration
    assert "AURORA_CLUSTER_ARN" in orchestration
    assert "WORLD_DATA_BUCKET" in orchestration
    assert 'fileset("${path.module}/../gamewake/persistence/sql", "*.sql")' in orchestration
    assert "0001_initial.sql" not in orchestration
    assert "DISCORD_BOT_TOKEN_PARAMETER_NAME" in orchestration
    assert "ReadDiscordNotificationToken" in orchestration


def test_world_data_is_kms_encrypted_versioned_bounded_and_never_public():
    storage = source("gamewake-storage.tf")
    orchestration = source("gamewake-orchestration.tf")

    assert 'resource "aws_s3_bucket" "world_data"' in storage
    assert 'resource "aws_kms_key" "world_data"' in storage
    assert 'status = "Enabled"' in storage
    assert "restrict_public_buckets = true" in storage
    assert 'sse_algorithm     = "aws:kms"' in storage
    assert "force_destroy = false" in storage
    assert 'id     = "expire-hidden-state-versions"' in storage
    assert 'prefix = "states/"' in storage
    assert 'id     = "expire-hidden-backup-versions"' in storage
    assert 'prefix = "backups/"' in storage
    assert "noncurrent_version_expiration" in storage
    assert "var.world_data_noncurrent_version_retention_days" in storage
    assert '"s3:DeleteObjectVersion"' in orchestration
    assert '"s3:ListBucketVersions"' in orchestration


def test_disposable_runtimes_use_a_launch_template_without_idle_reconciliation_polling():
    runtime = source("gamewake-runtime.tf")
    schedules = source("gamewake-schedules.tf")

    assert 'resource "aws_launch_template" "gamewake_runtime"' in runtime
    assert 'instance_initiated_shutdown_behavior = "terminate"' in runtime
    assert "metadata_options" in runtime
    assert 'http_tokens                 = "required"' in runtime
    assert 'resource "aws_scheduler_schedule" "reconciliation"' not in schedules
    assert 'schedule_expression = "rate(5 minutes)"' not in schedules


def test_legacy_single_server_stack_is_removed():
    variables = source("variables.tf")
    runtime = source("gamewake-runtime.tf")
    bootstrap = source("user-data.sh.tpl")

    assert 'variable "enable_legacy_single_server"' not in variables
    assert 'resource "aws_instance" "palworld"' not in source("ec2.tf")
    assert not (TERRAFORM / "lambda.tf").exists()
    assert "host_mode" not in runtime
    assert "host_mode" not in bootstrap


def test_public_api_uses_kms_sessions_exact_cors_and_managed_provider_secrets():
    api = source("gamewake-api.tf")
    parameters = source("parameter-store.tf")

    assert 'resource "aws_lambda_function" "gamewake_api"' in api
    assert 'resource "aws_lambda_function_url" "gamewake_api"' in api
    assert 'authorization_type = "NONE"' in api
    assert "allow_origins     = [var.gamewake_console_url]" in api
    assert 'key_usage                = "GENERATE_VERIFY_MAC"' in api
    assert 'customer_master_key_spec = "HMAC_256"' in api
    assert "GAMEWAKE_WORLD_PARAMETER_PREFIX" in api
    assert "WORLD_DATA_BUCKET" in api
    assert 'sid    = "ManageWorldArchives"' in api
    assert '"s3:GetObject"' in api
    assert '"s3:PutObject"' in api
    assert 'resource "aws_ssm_parameter" "discord_client_secret"' in parameters
    assert 'resource "aws_ssm_parameter" "discord_bot_token"' in parameters
    assert 'resource "aws_ssm_parameter" "abacatepay_api_key"' in parameters


def test_disposable_world_configuration_is_isolated_under_a_tenant_path():
    orchestration = source("gamewake-orchestration.tf")
    runtime = source("gamewake-runtime.tf")
    api = source("gamewake-api.tf")

    expected_path = "${local.parameter_path}/gamewake/worlds/*"
    assert expected_path in orchestration
    assert expected_path in runtime
    assert expected_path in api
    assert "PALWORLD_BASE_CONFIG_JSON" in orchestration


def test_runtime_pricing_is_injected_into_api_and_usage_meter_worker():
    variables = source("variables.tf")
    orchestration = source("gamewake-orchestration.tf")
    api = source("gamewake-api.tf")

    assert 'variable "runtime_profile_hourly_rates"' in variables
    assert "RUNTIME_PROFILE_HOURLY_RATES_JSON" in api
    assert "PostgresBillingRepository" not in orchestration
    assert "AURORA_CLUSTER_ARN" in orchestration
    assert "palworld-small = 5.50" in variables


def test_online_session_monitor_runs_inside_the_active_world_workflow_only():
    schedules = source("gamewake-schedules.tf")
    orchestration = source("gamewake-orchestration.tf")
    state_machine = source("state-machines/world-operation.asl.json")

    assert 'resource "aws_scheduler_schedule" "session_monitor"' not in schedules
    assert 'resource "aws_scheduler_schedule" "reconciliation"' not in schedules
    assert 'schedule_expression = "rate(1 minute)"' not in schedules
    assert 'schedule_expression = "rate(5 minutes)"' not in schedules
    assert 'action            = "monitor_sessions"' not in schedules
    assert "world_operation_state_machine_arn" in orchestration
    assert '"WaitBeforeSessionCheck"' in state_machine
    assert '"action": "monitor_session"' in state_machine
    assert '"RenewSessionMonitor"' in state_machine
    assert '"states:StartExecution"' in orchestration


def test_daily_data_maintenance_enforces_pending_deletion_and_storage_grace():
    schedules = source("gamewake-schedules.tf")
    orchestration = source("gamewake-orchestration.tf")
    api = source("gamewake-api.tf")

    assert 'resource "aws_scheduler_schedule" "data_maintenance"' in schedules
    assert 'action = "maintain_data"' in schedules
    assert "STORAGE_ALLOWANCE_BYTES" in orchestration
    assert "STORAGE_GRACE_DAYS" in orchestration
    assert "STORAGE_ALLOWANCE_BYTES" in api


def test_closed_beta_observability_covers_api_worker_database_and_dead_letters():
    cloudwatch = source("cloudwatch.tf")

    assert 'resource "aws_cloudwatch_dashboard" "gamewake"' in cloudwatch
    assert 'resource "aws_cloudwatch_metric_alarm" "gamewake_api_errors"' in cloudwatch
    assert 'resource "aws_cloudwatch_metric_alarm" "operation_worker_errors"' in cloudwatch
    assert 'resource "aws_cloudwatch_metric_alarm" "operations_dead_letters"' in cloudwatch
    assert 'resource "aws_cloudwatch_metric_alarm" "aurora_capacity"' in cloudwatch
    assert 'resource "aws_sns_topic" "operations_alerts"' in cloudwatch
    assert 'resource "aws_sns_topic_subscription" "operations_email"' in cloudwatch
    assert "alarm_actions" in cloudwatch
    assert "[aws_sns_topic.operations_alerts.arn]" in cloudwatch
