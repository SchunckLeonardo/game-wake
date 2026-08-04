from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from gamewake.aws.connection import Ec2SsmConnectionDetailsProvider
from gamewake.aws.ec2_runtime import Ec2RuntimeProvider
from gamewake.aws.s3_archive import S3WorldArchiveStore
from gamewake.orchestration.step_functions import StepFunctionsOperationOrchestrator
from gamewake.worlds import (
    ConfigurationRevision,
    StoredWorldState,
    World,
    WorldStatus,
)

pytestmark = pytest.mark.localstack


def make_test_world(
    world_id: str = "wld_1234567890abcdef",
    account_id: str = "acc_1234567890abcdef",
    status: WorldStatus = WorldStatus.ONLINE,
    runtime_provider_reference: str | None = None,
) -> World:
    return World(
        id=world_id,
        account_id=account_id,
        name="LocalStack Test World",
        game_template_id="palworld-v1",
        region="us-east-1",
        runtime_profile_id="prof_default",
        status=status,
        runtime_id=None,
        runtime_provider_reference=runtime_provider_reference,
        configuration_revision_id="cfg_001",
        pending_configuration_revision_id=None,
        stored_state_id=None,
        stored_state_checksum=None,
        version=1,
    )


class TestLocalStackS3WorldArchiveStore:
    def test_s3_archive_store_backup_and_export_lifecycle(self, s3_client):
        bucket_name = f"test-gamewake-world-backups-{uuid.uuid4().hex[:8]}"
        s3_client.create_bucket(Bucket=bucket_name)

        archive_store = S3WorldArchiveStore(bucket=bucket_name, client=s3_client)
        world = make_test_world()

        state = StoredWorldState(
            id="st_1234567890abcdef",
            checksum="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            validated=True,
        )

        state_key = f"states/{world.account_id}/{world.id}/{state.id}.tar.zst"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=state_key,
            Body=b"test-world-state-binary-data",
            Metadata={"sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
        )

        backup = archive_store.create_automatic(world, state, idempotency_key="op_backup_001")
        assert backup.world_id == world.id
        assert backup.account_id == world.account_id
        assert backup.checksum == state.checksum

        backups = archive_store.list_backups(world.account_id, world.id)
        assert len(backups) == 1
        assert backups[0].id == backup.id

        restored_state = archive_store.restore(world, backup, idempotency_key="op_restore_001")
        assert restored_state.id == state.id
        assert restored_state.checksum == state.checksum

        config_rev = ConfigurationRevision(
            id="cfg_1234567890abcdef",
            account_id=world.account_id,
            world_id=world.id,
            game_template_id=world.game_template_id,
            number=1,
            entries=(("ServerName", "LocalStack Server"),),
            idempotency_key="op_cfg_001",
            created_at=datetime.now(UTC),
        )
        export = archive_store.create_export(
            world, state, config_rev, idempotency_key="op_export_001"
        )
        assert export.world_id == world.id
        assert "http" in export.download_url

        archive_store.delete_world_data(world.account_id, world.id, idempotency_key="op_delete_001")
        backups_after_delete = archive_store.list_backups(world.account_id, world.id)
        assert len(backups_after_delete) == 0


class TestLocalStackEc2AndSsmConnection:
    def test_connection_details_resolution(self, ec2_client, ssm_client):
        run_resp = ec2_client.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t3.micro",
        )
        instance_id = run_resp["Instances"][0]["InstanceId"]

        account_id = "acc_test_123"
        world_id = "wld_test_456"
        prefix = "/gamewake"

        secret_name = f"{prefix}/{account_id}/{world_id}/server-password"
        ssm_client.put_parameter(
            Name=secret_name,
            Value="super-secret-password-123",
            Type="SecureString",
            Overwrite=True,
        )

        world = make_test_world(
            world_id=world_id,
            account_id=account_id,
            status=WorldStatus.ONLINE,
            runtime_provider_reference=instance_id,
        )

        provider = Ec2SsmConnectionDetailsProvider(
            parameter_prefix=prefix,
            ec2_client=ec2_client,
            ssm_client=ssm_client,
            port=8211,
        )

        conn = provider.issue(world, viewer_user_id="usr_viewer_001")
        assert conn.port == 8211
        assert conn.password == "super-secret-password-123"


class TestLocalStackEc2RuntimeProvider:
    def test_ec2_runtime_provision_and_release(self, ec2_client):
        lt_name = f"gamewake-lt-{uuid.uuid4().hex[:8]}"
        lt_resp = ec2_client.create_launch_template(
            LaunchTemplateName=lt_name,
            LaunchTemplateData={
                "ImageId": "ami-12345678",
                "InstanceType": "t3.medium",
            },
        )
        lt_id = lt_resp["LaunchTemplate"]["LaunchTemplateId"]

        provider = Ec2RuntimeProvider(launch_template_id=lt_id, client=ec2_client)

        world = make_test_world(
            world_id="wld_ec2_001",
            account_id="acc_ec2_001",
            status=WorldStatus.WAKING,
        )

        runtime = provider.provision(world, idempotency_key="op_prov_001")
        assert runtime.provider_reference.startswith("i-")

        runtime_again = provider.provision(world, idempotency_key="op_prov_001")
        assert runtime_again.provider_reference == runtime.provider_reference

        provider.release(runtime, idempotency_key="op_rel_001")


class TestLocalStackStepFunctionsOrchestrator:
    def test_step_functions_orchestrator(self, stepfunctions_client):
        definition = (
            '{"Comment": "Test", "StartAt": "Pass", '
            '"States": {"Pass": {"Type": "Pass", "End": true}}}'
        )
        sm_name = f"GamewakeWorkflowTest-{uuid.uuid4().hex[:8]}"
        sm_resp = stepfunctions_client.create_state_machine(
            name=sm_name,
            definition=definition,
            roleArn="arn:aws:iam::000000000000:role/DummyRole",
        )
        sm_arn = sm_resp["stateMachineArn"]

        orchestrator = StepFunctionsOperationOrchestrator(
            state_machine_arn=sm_arn,
            client=stepfunctions_client,
        )

        exec_info = orchestrator.start(
            account_id="acc_sfn_001",
            operation_id="op_sfn_001",
        )
        assert "op_sfn_001" in exec_info.name
        assert sm_arn in exec_info.arn or "arn:aws:states" in exec_info.arn

        exec_info_2 = orchestrator.ensure_running(
            account_id="acc_sfn_001",
            operation_id="op_sfn_001",
        )
        assert exec_info_2.arn == exec_info.arn
