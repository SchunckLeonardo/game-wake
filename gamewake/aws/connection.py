from __future__ import annotations

from typing import Any

from gamewake.control_plane import ConnectionDetails
from gamewake.worlds import World


class Ec2SsmConnectionDetailsProvider:
    """Resolves short-lived runtime networking and its managed per-World secret."""

    def __init__(
        self,
        *,
        parameter_prefix: str,
        ec2_client: Any | None = None,
        ssm_client: Any | None = None,
        port: int = 8211,
    ) -> None:
        if not parameter_prefix or not 1 <= port <= 65535:
            raise ValueError("parameter prefix and a valid game port are required")
        if ec2_client is None or ssm_client is None:
            import boto3

            ec2_client = ec2_client or boto3.client("ec2")
            ssm_client = ssm_client or boto3.client("ssm")
        self._parameter_prefix = parameter_prefix.rstrip("/")
        self._ec2 = ec2_client
        self._ssm = ssm_client
        self._port = port

    def issue(self, world: World, *, viewer_user_id: str) -> ConnectionDetails:
        del viewer_user_id  # Authorization is enforced by the application service.
        if world.runtime_provider_reference is None:
            raise ValueError("World does not have an active Runtime")
        response = self._ec2.describe_instances(InstanceIds=[world.runtime_provider_reference])
        instances = [
            instance
            for reservation in response.get("Reservations", [])
            for instance in reservation.get("Instances", [])
        ]
        if len(instances) != 1 or instances[0].get("State", {}).get("Name") != "running":
            raise ValueError("World Runtime is not reachable")
        host = instances[0].get("PublicIpAddress")
        if not isinstance(host, str) or not host:
            raise ValueError("World Runtime does not have a public address")
        secret_name = f"{self._parameter_prefix}/{world.account_id}/{world.id}/server-password"
        password = self._ssm.get_parameter(
            Name=secret_name,
            WithDecryption=True,
        )["Parameter"]["Value"]
        return ConnectionDetails(host=host, port=self._port, password=str(password))
