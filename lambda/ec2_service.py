"""Operacoes estritamente limitadas a uma unica instancia Palworld."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class InstanceStatus:
    state: str
    public_ip: str | None
    launch_time: datetime | None


class EC2Service:
    def __init__(
        self,
        ec2_client: Any,
        ssm_client: Any | None,
        instance_id: str,
        status_parameter_name: str,
        *,
        ssm_client_factory: Callable[[], Any] | None = None,
    ):
        self._ec2 = ec2_client
        self._ssm = ssm_client
        self._ssm_client_factory = ssm_client_factory
        self.instance_id = instance_id
        self._status_parameter_name = status_parameter_name

    def _get_ssm_client(self) -> Any:
        if self._ssm is None:
            if self._ssm_client_factory is None:
                raise RuntimeError("SSM client is not configured")
            self._ssm = self._ssm_client_factory()
        return self._ssm

    def describe(self) -> InstanceStatus:
        response = self._ec2.describe_instances(InstanceIds=[self.instance_id])
        reservations = response.get("Reservations", [])
        instances = reservations[0].get("Instances", []) if reservations else []
        if not instances:
            return InstanceStatus("terminated", None, None)

        instance = instances[0]
        launch_time = instance.get("LaunchTime")
        if launch_time and launch_time.tzinfo is None:
            launch_time = launch_time.replace(tzinfo=UTC)
        return InstanceStatus(
            state=instance["State"]["Name"],
            public_ip=instance.get("PublicIpAddress"),
            launch_time=launch_time,
        )

    def start(self) -> None:
        self._ec2.start_instances(InstanceIds=[self.instance_id])

    def stop(self) -> None:
        """Parada de emergencia da EC2; o fluxo normal usa SSM e shutdown do Linux."""
        self._ec2.stop_instances(InstanceIds=[self.instance_id])

    def request_safe_shutdown(self, *, force: bool = False) -> str:
        ssm = self._get_ssm_client()
        command = "sudo /usr/local/sbin/stop-palworld.sh --shutdown"
        if force:
            command += " --force"
        response = ssm.send_command(
            InstanceIds=[self.instance_id],
            DocumentName="AWS-RunShellScript",
            Comment="Palworld safe shutdown requested by Discord",
            TimeoutSeconds=300,
            Parameters={"commands": [command], "executionTimeout": ["300"]},
        )
        return str(response["Command"]["CommandId"])

    def read_game_snapshot(self) -> dict[str, Any] | None:
        ssm = self._get_ssm_client()
        try:
            response = ssm.get_parameter(Name=self._status_parameter_name, WithDecryption=False)
        except ssm.exceptions.ParameterNotFound:
            return None

        try:
            return json.loads(response["Parameter"]["Value"])
        except (KeyError, TypeError, json.JSONDecodeError):
            return None


def human_uptime(launch_time: datetime | None, now: datetime | None = None) -> str:
    if not launch_time:
        return "indisponivel"
    now = now or datetime.now(UTC)
    seconds = max(0, int((now - launch_time).total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}min"
    return f"{minutes}min"
