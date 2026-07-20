import json
from datetime import UTC, datetime

from ec2_service import EC2Service, human_uptime


class FakeEC2Client:
    def __init__(self):
        self.started = None
        self.stopped = None

    def describe_instances(self, **_kwargs):
        return {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "State": {"Name": "running"},
                            "PublicIpAddress": "198.51.100.7",
                            "LaunchTime": datetime(2026, 7, 19, 12, tzinfo=UTC),
                        }
                    ]
                }
            ]
        }

    def start_instances(self, **kwargs):
        self.started = kwargs

    def stop_instances(self, **kwargs):
        self.stopped = kwargs


class FakeSSMClient:
    class exceptions:
        class ParameterNotFound(Exception):
            pass

    def __init__(self):
        self.sent = None

    def send_command(self, **kwargs):
        self.sent = kwargs
        return {"Command": {"CommandId": "command-id"}}

    def get_parameter(self, **_kwargs):
        return {"Parameter": {"Value": json.dumps({"players": 1})}}


def test_service_targets_only_configured_instance() -> None:
    ec2 = FakeEC2Client()
    ssm = FakeSSMClient()
    service = EC2Service(ec2, ssm, "i-123", "/palworld/status")

    status = service.describe()
    service.start()
    command_id = service.request_safe_shutdown()

    assert status.state == "running"
    assert status.public_ip == "198.51.100.7"
    assert ec2.started == {"InstanceIds": ["i-123"]}
    assert ssm.sent["InstanceIds"] == ["i-123"]
    assert ssm.sent["DocumentName"] == "AWS-RunShellScript"
    assert command_id == "command-id"


def test_read_game_snapshot_parses_json() -> None:
    service = EC2Service(FakeEC2Client(), FakeSSMClient(), "i-123", "/palworld/status")

    assert service.read_game_snapshot() == {"players": 1}


def test_human_uptime_formats_hours_and_minutes() -> None:
    launch = datetime(2026, 7, 19, 10, 15, tzinfo=UTC)
    now = datetime(2026, 7, 19, 12, 45, tzinfo=UTC)

    assert human_uptime(launch, now) == "2h 30min"
