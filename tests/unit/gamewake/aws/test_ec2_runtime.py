from gamewake.aws import Ec2RuntimeProvider
from gamewake.worlds import World, WorldStatus


def world():
    return World(
        id="world-123",
        account_id="account-123",
        name="Palpagos",
        game_template_id="palworld:1",
        region="us-east-1",
        runtime_profile_id="palworld-small",
        status=WorldStatus.WAKING,
        runtime_id=None,
        runtime_provider_reference=None,
        configuration_revision_id="configuration-123",
        pending_configuration_revision_id=None,
        stored_state_id=None,
        stored_state_checksum=None,
        version=1,
    )


class FakeEc2Client:
    def __init__(self):
        self.instances = []
        self.describe_calls = []
        self.run_calls = []
        self.terminate_calls = []

    def describe_instances(self, **kwargs):
        self.describe_calls.append(kwargs)
        if "InstanceIds" in kwargs:
            matching = [
                instance
                for instance in self.instances
                if instance["InstanceId"] in kwargs["InstanceIds"]
            ]
        else:
            matching = self.instances
        return {"Reservations": [{"Instances": matching}] if matching else []}

    def run_instances(self, **kwargs):
        self.run_calls.append(kwargs)
        instance = {
            "InstanceId": "i-new123",
            "State": {"Name": "pending"},
            "Tags": kwargs["TagSpecifications"][0]["Tags"],
        }
        self.instances.append(instance)
        return {"Instances": [instance]}

    def terminate_instances(self, **kwargs):
        self.terminate_calls.append(kwargs)


def test_provision_reconciles_an_existing_runtime_before_creating_one():
    client = FakeEc2Client()
    client.instances.append(
        {
            "InstanceId": "i-existing",
            "State": {"Name": "running"},
            "Tags": [{"Key": "GameWakeOperation", "Value": "wake-123"}],
        }
    )
    provider = Ec2RuntimeProvider("lt-123", client=client)

    runtime = provider.provision(world(), idempotency_key="wake-123")

    assert runtime.id == "i-existing"
    assert runtime.provider_reference == "i-existing"
    assert client.run_calls == []
    assert client.describe_calls[0]["Filters"] == [
        {"Name": "tag:GameWakeOperation", "Values": ["wake-123"]},
        {
            "Name": "instance-state-name",
            "Values": ["pending", "running", "stopping", "stopped"],
        },
    ]


def test_provision_uses_launch_template_client_token_and_tenant_tags():
    client = FakeEc2Client()
    provider = Ec2RuntimeProvider("lt-123", client=client)

    runtime = provider.provision(world(), idempotency_key="wake/unsafe 123")

    assert runtime.id == "i-new123"
    request = client.run_calls[0]
    assert request["LaunchTemplate"] == {"LaunchTemplateId": "lt-123", "Version": "$Latest"}
    assert request["MinCount"] == request["MaxCount"] == 1
    assert len(request["ClientToken"]) == 64
    tags = {tag["Key"]: tag["Value"] for tag in request["TagSpecifications"][0]["Tags"]}
    assert tags == {
        "Name": "gamewake-world-world-123",
        "GameWakeAccount": "account-123",
        "GameWakeWorld": "world-123",
        "GameWakeOperation": "wake/unsafe 123",
        "GameWakeManaged": "true",
    }


def test_release_terminates_a_disposable_runtime_once():
    client = FakeEc2Client()
    client.instances.append({"InstanceId": "i-existing", "State": {"Name": "running"}, "Tags": []})
    provider = Ec2RuntimeProvider("lt-123", client=client)
    runtime = provider.provision(world(), idempotency_key="wake-123")

    provider.release(runtime, idempotency_key="sleep-123")

    assert client.terminate_calls == [{"InstanceIds": ["i-existing"]}]


def test_release_accepts_an_already_terminated_runtime():
    client = FakeEc2Client()
    client.instances.append(
        {"InstanceId": "i-existing", "State": {"Name": "terminated"}, "Tags": []}
    )
    provider = Ec2RuntimeProvider("lt-123", client=client)

    provider.release(
        type("Runtime", (), {"provider_reference": "i-existing"})(),
        idempotency_key="sleep-123",
    )

    assert client.terminate_calls == []
