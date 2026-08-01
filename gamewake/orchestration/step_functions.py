from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

_UNSAFE_EXECUTION_NAME = re.compile(r"[^A-Za-z0-9_-]+")
_MAX_EXECUTION_NAME_LENGTH = 80


@dataclass(frozen=True)
class OperationExecution:
    name: str
    arn: str


class StepFunctionsOperationOrchestrator:
    """Starts one idempotent Standard Workflow per persistent operation."""

    def __init__(self, state_machine_arn: str, *, client: Any | None = None) -> None:
        if not state_machine_arn:
            raise ValueError("state_machine_arn is required")
        if client is None:
            import boto3

            client = boto3.client("stepfunctions")
        self._state_machine_arn = state_machine_arn
        self._client = client

    def start(self, account_id: str, operation_id: str) -> OperationExecution:
        if not account_id or not operation_id:
            raise ValueError("account_id and operation_id are required")
        name = self.execution_name(operation_id)
        try:
            response = self._client.start_execution(
                stateMachineArn=self._state_machine_arn,
                name=name,
                input=json.dumps(
                    {"account_id": account_id, "operation_id": operation_id},
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )
            arn = response["executionArn"]
        except self._client.exceptions.ExecutionAlreadyExists:
            arn = self._execution_arn(name)
        return OperationExecution(name=name, arn=arn)

    def ensure_running(self, account_id: str, operation_id: str) -> OperationExecution:
        execution = self.start(account_id, operation_id)
        status = self._client.describe_execution(executionArn=execution.arn)["status"]
        if status in {"FAILED", "TIMED_OUT", "ABORTED"}:
            self._client.redrive_execution(executionArn=execution.arn)
        return execution

    @staticmethod
    def execution_name(operation_id: str) -> str:
        cleaned = _UNSAFE_EXECUTION_NAME.sub("-", operation_id).strip("-") or "operation"
        candidate = f"world-operation-{cleaned}"
        if len(candidate) <= _MAX_EXECUTION_NAME_LENGTH:
            return candidate
        digest = hashlib.sha256(operation_id.encode()).hexdigest()[:16]
        prefix_length = _MAX_EXECUTION_NAME_LENGTH - len(digest) - 1
        return f"{candidate[:prefix_length]}-{digest}"

    def _execution_arn(self, execution_name: str) -> str:
        prefix, separator, state_machine_name = self._state_machine_arn.rpartition(":stateMachine:")
        if not separator or not state_machine_name:
            raise ValueError("invalid Step Functions state machine ARN")
        return f"{prefix}:execution:{state_machine_name}:{execution_name}"
