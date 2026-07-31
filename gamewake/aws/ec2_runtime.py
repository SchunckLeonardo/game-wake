from __future__ import annotations

import hashlib
from typing import Any

from gamewake.worlds import Runtime, World

_REUSABLE_STATES = ("pending", "running", "stopping", "stopped")


class Ec2RuntimeProvider:
    """Provides disposable EC2 runtimes through one approved Launch Template."""

    def __init__(self, launch_template_id: str, *, client: Any | None = None) -> None:
        if not launch_template_id:
            raise ValueError("launch_template_id is required")
        if client is None:
            import boto3

            client = boto3.client("ec2")
        self._launch_template_id = launch_template_id
        self._client = client

    def provision(self, world: World, *, idempotency_key: str) -> Runtime:
        existing = self._find_by_operation(idempotency_key)
        if existing is not None:
            return self._runtime(existing["InstanceId"])

        tags = [
            {"Key": "Name", "Value": f"gamewake-world-{world.id}"},
            {"Key": "GameWakeAccount", "Value": world.account_id},
            {"Key": "GameWakeWorld", "Value": world.id},
            {"Key": "GameWakeOperation", "Value": idempotency_key},
            {"Key": "GameWakeManaged", "Value": "true"},
        ]
        response = self._client.run_instances(
            LaunchTemplate={
                "LaunchTemplateId": self._launch_template_id,
                "Version": "$Latest",
            },
            MinCount=1,
            MaxCount=1,
            ClientToken=hashlib.sha256(idempotency_key.encode()).hexdigest(),
            TagSpecifications=[{"ResourceType": "instance", "Tags": tags}],
        )
        return self._runtime(response["Instances"][0]["InstanceId"])

    def release(self, runtime: Runtime, *, idempotency_key: str) -> None:
        del idempotency_key  # EC2 termination is naturally idempotent for an instance ID.
        try:
            response = self._client.describe_instances(InstanceIds=[runtime.provider_reference])
        except Exception as error:
            response_code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if response_code == "InvalidInstanceID.NotFound":
                return
            raise
        instances = self._instances(response)
        if not instances or instances[0]["State"]["Name"] in {"shutting-down", "terminated"}:
            return
        self._client.terminate_instances(InstanceIds=[runtime.provider_reference])

    def _find_by_operation(self, idempotency_key: str) -> dict[str, Any] | None:
        response = self._client.describe_instances(
            Filters=[
                {"Name": "tag:GameWakeOperation", "Values": [idempotency_key]},
                {"Name": "instance-state-name", "Values": list(_REUSABLE_STATES)},
            ]
        )
        instances = self._instances(response)
        return instances[0] if instances else None

    @staticmethod
    def _instances(response: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            instance
            for reservation in response.get("Reservations", [])
            for instance in reservation.get("Instances", [])
        ]

    @staticmethod
    def _runtime(instance_id: str) -> Runtime:
        return Runtime(id=instance_id, provider_reference=instance_id)
