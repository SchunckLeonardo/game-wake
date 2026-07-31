from pathlib import Path

TERRAFORM = Path(__file__).parents[4] / "terraform"


def source(name):
    return (TERRAFORM / name).read_text()


def test_aurora_serverless_v2_uses_data_api_encryption_and_private_subnets():
    database = source("gamewake-database.tf")

    assert 'resource "aws_rds_cluster" "gamewake"' in database
    assert 'engine_mode                 = "provisioned"' in database
    assert "serverlessv2_scaling_configuration" in database
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


def test_world_data_is_kms_encrypted_versioned_and_never_public():
    storage = source("gamewake-storage.tf")

    assert 'resource "aws_s3_bucket" "world_data"' in storage
    assert 'resource "aws_kms_key" "world_data"' in storage
    assert 'status = "Enabled"' in storage
    assert "restrict_public_buckets = true" in storage
    assert 'sse_algorithm     = "aws:kms"' in storage
    assert "force_destroy = false" in storage


def test_disposable_runtimes_use_a_launch_template_and_reconciliation_schedule():
    runtime = source("gamewake-runtime.tf")
    schedules = source("gamewake-schedules.tf")

    assert 'resource "aws_launch_template" "gamewake_runtime"' in runtime
    assert 'instance_initiated_shutdown_behavior = "terminate"' in runtime
    assert "metadata_options" in runtime
    assert 'http_tokens                 = "required"' in runtime
    assert 'resource "aws_scheduler_schedule" "reconciliation"' in schedules
    assert 'schedule_expression = "rate(5 minutes)"' in schedules


def test_legacy_always_on_server_is_disabled_by_default():
    variables = source("variables.tf")
    legacy = source("ec2.tf")

    assert 'variable "enable_legacy_single_server"' in variables
    assert "default     = false" in variables
    assert "count = var.enable_legacy_single_server ? 1 : 0" in legacy
