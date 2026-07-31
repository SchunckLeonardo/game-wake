import json
from pathlib import Path

STATE_MACHINE = (
    Path(__file__).parents[4] / "terraform" / "state-machines" / "world-operation.asl.json"
)


def test_world_operation_state_machine_retries_loops_and_records_failure():
    definition = json.loads(STATE_MACHINE.read_text())
    states = definition["States"]

    assert definition["StartAt"] == "AdvanceOperation"
    advance = states["AdvanceOperation"]
    assert advance["Type"] == "Task"
    assert advance["Resource"] == "${operation_worker_arn}"
    assert advance["Next"] == "OperationTerminal"
    assert advance["Retry"][0]["MaxAttempts"] == 5
    assert advance["Catch"][0]["Next"] == "RecordFailure"

    terminal = states["OperationTerminal"]
    assert terminal["Type"] == "Choice"
    assert terminal["Choices"][0] == {
        "Variable": "$.terminal",
        "BooleanEquals": True,
        "Next": "OperationComplete",
    }
    assert terminal["Default"] == "WaitBeforeNextPhase"
    assert states["WaitBeforeNextPhase"]["Next"] == "AdvanceOperation"

    failure = states["RecordFailure"]
    assert failure["Type"] == "Task"
    assert failure["Parameters"]["action"] == "record_failure"
    assert failure["End"] is True
