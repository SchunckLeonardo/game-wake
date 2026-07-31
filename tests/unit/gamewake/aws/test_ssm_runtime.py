import json

import pytest

from gamewake.aws import S3WorldStateStore, SsmCommandRunner, SsmPalworldTemplate
from gamewake.worlds import Runtime, World, WorldStatus


def world(*, state_id="state-123", checksum="sha256:abc123"):
    return World(
        id="world-123",
        account_id="account-123",
        name="Palpagos",
        game_template_id="palworld:1",
        region="us-east-1",
        runtime_profile_id="palworld-small",
        status=WorldStatus.WAKING,
        runtime_id="i-123",
        runtime_provider_reference="i-123",
        configuration_revision_id="configuration-123",
        pending_configuration_revision_id=None,
        stored_state_id=state_id,
        stored_state_checksum=checksum,
        version=1,
    )


class FakeWaiter:
    def __init__(self):
        self.calls = []

    def wait(self, **kwargs):
        self.calls.append(kwargs)


class FakeSsmClient:
    def __init__(self, *, status="Success", output="done"):
        self.status = status
        self.output = output
        self.send_calls = []
        self.invocation_calls = []
        self.waiter = FakeWaiter()

    def send_command(self, **kwargs):
        self.send_calls.append(kwargs)
        return {"Command": {"CommandId": "command-123"}}

    def get_waiter(self, name):
        assert name == "command_executed"
        return self.waiter

    def get_command_invocation(self, **kwargs):
        self.invocation_calls.append(kwargs)
        return {
            "Status": self.status,
            "StandardOutputContent": self.output,
            "StandardErrorContent": "failure details",
        }


def test_command_runner_uses_a_remote_idempotency_guard_and_waits_for_success():
    client = FakeSsmClient(output="healthy")
    runner = SsmCommandRunner(client=client)

    output = runner.run(
        "i-123",
        "health",
        idempotency_key="operation-123:health",
        arguments=("world with spaces",),
    )

    assert output == "healthy"
    request = client.send_calls[0]
    assert request["InstanceIds"] == ["i-123"]
    assert request["DocumentName"] == "AWS-RunShellScript"
    [command] = request["Parameters"]["commands"]
    assert command.startswith("sudo /opt/gamewake/bin/gamewake-operation ")
    assert "health" in command
    assert "'world with spaces'" in command
    assert "operation-123:health" not in command
    assert client.waiter.calls == [
        {
            "CommandId": "command-123",
            "InstanceId": "i-123",
            "WaiterConfig": {"Delay": 2, "MaxAttempts": 150},
        }
    ]


def test_command_runner_raises_with_redacted_failure_details():
    runner = SsmCommandRunner(client=FakeSsmClient(status="Failed"))

    with pytest.raises(RuntimeError, match="SSM action start failed"):
        runner.run("i-123", "start", idempotency_key="operation-123:start")


class RecordingRunner:
    def __init__(self, outputs=None):
        self.outputs = dict(outputs or {})
        self.calls = []

    def run(self, instance_id, action, *, idempotency_key, arguments=()):
        self.calls.append((instance_id, action, idempotency_key, tuple(arguments)))
        return self.outputs.get(action, "")


def test_palworld_template_maps_domain_actions_to_idempotent_host_actions():
    runner = RecordingRunner(outputs={"health": "healthy\n", "player-count": "3\n"})
    template = SsmPalworldTemplate(runner)
    runtime = Runtime(id="runtime-123", provider_reference="i-123")
    target = world()

    template.apply_configuration(target, runtime, idempotency_key="op:configure")
    template.start(target, runtime, idempotency_key="op:start")
    assert template.is_healthy(target, runtime) is True
    assert template.player_count(target, runtime) == 3
    template.save(target, runtime, idempotency_key="op:save")
    template.stop(target, runtime, idempotency_key="op:stop")

    assert runner.calls == [
        ("i-123", "apply-configuration", "op:configure", ("configuration-123",)),
        ("i-123", "start", "op:start", ()),
        ("i-123", "health", "health:world-123", ()),
        ("i-123", "player-count", "player-count:world-123", ()),
        ("i-123", "save", "op:save", ()),
        ("i-123", "stop", "op:stop", ()),
    ]


def test_world_state_store_restores_the_persisted_object_and_validates_upload():
    runner = RecordingRunner(
        outputs={
            "persist-state": json.dumps(
                {
                    "state_id": "state-456",
                    "checksum": "sha256:def456",
                    "validated": True,
                }
            )
        }
    )
    store = S3WorldStateStore("gamewake-world-data", runner=runner)
    runtime = Runtime(id="runtime-123", provider_reference="i-123")
    target = world()

    store.restore(target, runtime, idempotency_key="op:restore")
    state = store.persist_and_validate(target, runtime, idempotency_key="op:persist")

    assert state.id == "state-456"
    assert state.checksum == "sha256:def456"
    assert state.validated is True
    assert runner.calls == [
        (
            "i-123",
            "restore-state",
            "op:restore",
            (
                "gamewake-world-data",
                "states/account-123/world-123/state-123.tar.zst",
                "sha256:abc123",
            ),
        ),
        (
            "i-123",
            "persist-state",
            "op:persist",
            ("gamewake-world-data", "states/account-123/world-123/"),
        ),
    ]


def test_world_state_store_initializes_a_new_world_without_an_object():
    runner = RecordingRunner()
    store = S3WorldStateStore("gamewake-world-data", runner=runner)
    runtime = Runtime(id="runtime-123", provider_reference="i-123")

    store.restore(
        world(state_id=None, checksum=None),
        runtime,
        idempotency_key="op:restore",
    )

    assert runner.calls == [("i-123", "initialize-state", "op:restore", ())]


@pytest.mark.parametrize(
    "output",
    ["not json", "{}", '{"state_id":"x","checksum":"y","validated":false}'],
)
def test_world_state_store_rejects_unverified_upload_results(output):
    runner = RecordingRunner(outputs={"persist-state": output})
    store = S3WorldStateStore("gamewake-world-data", runner=runner)

    with pytest.raises(ValueError, match="validated World state"):
        store.persist_and_validate(
            world(),
            Runtime(id="runtime-123", provider_reference="i-123"),
            idempotency_key="op:persist",
        )
