import json
from pathlib import Path

STATE_MACHINE = (
    Path(__file__).parents[4] / "terraform" / "state-machines" / "world-operation.asl.json"
)


def test_world_operation_state_machine_retries_loops_and_records_failure():
    definition = json.loads(STATE_MACHINE.read_text())
    states = definition["States"]

    assert definition["StartAt"] == "RouteExecution"
    assert states["RouteExecution"]["Choices"][0] == {
        "And": [
            {"Variable": "$.session_monitor", "IsPresent": True},
            {"Variable": "$.session_monitor", "BooleanEquals": True},
        ],
        "Next": "WaitBeforeSessionCheck",
    }
    assert states["RouteExecution"]["Default"] == "AdvanceOperation"
    advance = states["AdvanceOperation"]
    assert advance["Type"] == "Task"
    assert advance["Resource"] == "${operation_worker_arn}"
    assert advance["Next"] == "OperationTerminal"
    assert advance["Retry"][0]["MaxAttempts"] == 5
    assert advance["Catch"][0]["Next"] == "RecordFailure"

    terminal = states["OperationTerminal"]
    assert terminal["Type"] == "Choice"
    assert terminal["Choices"][0]["Next"] == "InitializeSessionMonitor"
    assert terminal["Choices"][0]["And"] == [
        {"Variable": "$.terminal", "BooleanEquals": True},
        {"Variable": "$.status", "StringEquals": "succeeded"},
        {"Variable": "$.operation_type", "StringEquals": "wake"},
    ]
    assert terminal["Choices"][1] == {
        "Variable": "$.terminal",
        "BooleanEquals": True,
        "Next": "OperationComplete",
    }
    assert terminal["Default"] == "WaitBeforeNextPhase"
    assert states["WaitBeforeNextPhase"]["Next"] == "AdvanceOperation"

    assert states["InitializeSessionMonitor"] == {
        "Type": "Pass",
        "Parameters": {
            "account_id.$": "$.account_id",
            "world_id.$": "$.world_id",
            "session_monitor": True,
            "monitor_checks": 0,
        },
        "Next": "WaitBeforeSessionCheck",
    }

    assert states["WaitBeforeSessionCheck"] == {
        "Type": "Wait",
        "Seconds": 60,
        "Next": "MonitorSession",
    }
    monitor = states["MonitorSession"]
    assert monitor["Type"] == "Task"
    assert monitor["Parameters"] == {
        "action": "monitor_session",
        "account_id.$": "$.account_id",
        "world_id.$": "$.world_id",
        "monitor_checks.$": "$.monitor_checks",
        "state_machine_arn": "${world_operation_state_machine_arn}",
    }
    assert monitor["Next"] == "SessionStillOnline"
    assert monitor["Catch"][0]["Next"] == "SessionMonitorBackoff"
    assert states["SessionStillOnline"]["Choices"][0] == {
        "And": [
            {"Variable": "$.continue_monitoring", "BooleanEquals": True},
            {"Variable": "$.monitor_checks", "NumericGreaterThanEquals": 600},
        ],
        "Next": "RenewSessionMonitor",
    }
    assert states["SessionStillOnline"]["Choices"][1] == {
        "Variable": "$.continue_monitoring",
        "BooleanEquals": True,
        "Next": "WaitBeforeSessionCheck",
    }
    assert states["SessionStillOnline"]["Default"] == "OperationComplete"
    assert states["SessionMonitorBackoff"]["Seconds"] == 300
    assert states["SessionMonitorBackoff"]["Next"] == "MonitorSession"
    renewal = states["RenewSessionMonitor"]
    assert renewal["Resource"] == "arn:aws:states:::states:startExecution"
    assert renewal["Parameters"] == {
        "StateMachineArn": "${world_operation_state_machine_arn}",
        "Name.$": "States.Format('session-monitor-{}', States.UUID())",
        "Input": {
            "account_id.$": "$.account_id",
            "world_id.$": "$.world_id",
            "session_monitor": True,
            "monitor_checks": 0,
            "AWS_STEP_FUNCTIONS_STARTED_BY_EXECUTION_ID.$": "$$.Execution.Id",
        },
    }
    assert renewal["Next"] == "OperationComplete"

    failure = states["RecordFailure"]
    assert failure["Type"] == "Task"
    assert failure["Parameters"]["action"] == "record_failure"
    assert failure["End"] is True


def test_world_operation_retries_while_a_new_runtime_registers_with_ssm():
    definition = json.loads(STATE_MACHINE.read_text())
    retries = definition["States"]["AdvanceOperation"]["Retry"]

    [registration_retry] = [
        retry for retry in retries if "InvalidInstanceId" in retry["ErrorEquals"]
    ]
    assert registration_retry == {
        "ErrorEquals": ["InvalidInstanceId"],
        "IntervalSeconds": 10,
        "BackoffRate": 2,
        "MaxAttempts": 5,
    }
