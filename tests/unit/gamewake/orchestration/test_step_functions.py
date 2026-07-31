import json

from gamewake.orchestration import StepFunctionsOperationOrchestrator


class ExecutionAlreadyExists(Exception):
    pass


class FakeStepFunctionsClient:
    class exceptions:
        ExecutionAlreadyExists = ExecutionAlreadyExists

    def __init__(self):
        self.calls = []
        self.already_exists = False

    def start_execution(self, **kwargs):
        self.calls.append(kwargs)
        if self.already_exists:
            raise ExecutionAlreadyExists("execution exists")
        return {
            "executionArn": (
                "arn:aws:states:us-east-1:123456789012:execution:"
                "gamewake-world-operation:world-operation-operation-123"
            )
        }

    def describe_execution(self, **kwargs):
        self.calls.append({"describe_execution": kwargs})
        return {"status": "FAILED"}

    def redrive_execution(self, **kwargs):
        self.calls.append({"redrive_execution": kwargs})


def test_starts_a_standard_execution_with_only_persistent_identifiers():
    client = FakeStepFunctionsClient()
    orchestrator = StepFunctionsOperationOrchestrator(
        "arn:aws:states:us-east-1:123456789012:stateMachine:gamewake-world-operation",
        client=client,
    )

    execution = orchestrator.start("account-123", "operation-123")

    assert execution.name == "world-operation-operation-123"
    assert execution.arn.endswith(":world-operation-operation-123")
    assert client.calls == [
        {
            "stateMachineArn": (
                "arn:aws:states:us-east-1:123456789012:stateMachine:gamewake-world-operation"
            ),
            "name": "world-operation-operation-123",
            "input": json.dumps(
                {"account_id": "account-123", "operation_id": "operation-123"},
                separators=(",", ":"),
                sort_keys=True,
            ),
        }
    ]


def test_an_existing_execution_is_the_same_idempotent_success():
    client = FakeStepFunctionsClient()
    client.already_exists = True
    orchestrator = StepFunctionsOperationOrchestrator(
        "arn:aws:states:us-east-1:123456789012:stateMachine:gamewake-world-operation",
        client=client,
    )

    execution = orchestrator.start("account-123", "operation-123")

    assert execution.name == "world-operation-operation-123"
    assert execution.arn == (
        "arn:aws:states:us-east-1:123456789012:execution:"
        "gamewake-world-operation:world-operation-operation-123"
    )


def test_execution_names_are_safe_stable_and_bounded_to_80_characters():
    client = FakeStepFunctionsClient()
    orchestrator = StepFunctionsOperationOrchestrator(
        "arn:aws:states:us-east-1:123456789012:stateMachine:gamewake-world-operation",
        client=client,
    )
    unsafe_id = "operation/with spaces/" + ("very-long-" * 12)

    first = orchestrator.execution_name(unsafe_id)
    second = orchestrator.execution_name(unsafe_id)

    assert first == second
    assert len(first) <= 80
    assert all(character.isalnum() or character in "-_" for character in first)


def test_reconciliation_redrives_an_abnormally_failed_standard_execution():
    client = FakeStepFunctionsClient()
    client.already_exists = True
    orchestrator = StepFunctionsOperationOrchestrator(
        "arn:aws:states:us-east-1:123456789012:stateMachine:gamewake-world-operation",
        client=client,
    )

    execution = orchestrator.ensure_running("account-123", "operation-123")

    assert execution.arn.endswith(":world-operation-operation-123")
    assert client.calls[-1] == {"redrive_execution": {"executionArn": execution.arn}}
