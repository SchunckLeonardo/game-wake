from dataclasses import replace
from datetime import UTC, datetime

import pytest

from gamewake.orchestration import advance_operation
from gamewake.worlds import (
    OperationPhase,
    OperationStatus,
    OperationType,
    WorldOperation,
)


def operation(*, status=OperationStatus.RUNNING, phase=OperationPhase.STARTING_GAME):
    return WorldOperation(
        id="operation-123",
        account_id="account-123",
        world_id="world-123",
        operation_type=OperationType.WAKE,
        status=status,
        phase=phase,
        idempotency_key="request-123",
        created_at=datetime(2026, 7, 31, tzinfo=UTC),
        version=2,
    )


class RecordingWorker:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def advance(self, account_id, operation_id):
        self.calls.append(("advance", account_id, operation_id))
        return self.result

    def mark_needs_attention(self, account_id, operation_id):
        self.calls.append(("mark_needs_attention", account_id, operation_id))
        return self.result


def test_handler_advances_one_durable_phase_and_reports_progress():
    worker = RecordingWorker(operation())

    result = advance_operation(
        {"account_id": "account-123", "operation_id": "operation-123"},
        worker=worker,
    )

    assert result == {
        "account_id": "account-123",
        "operation_id": "operation-123",
        "world_id": "world-123",
        "operation_type": "wake",
        "status": "running",
        "phase": "starting_game",
        "terminal": False,
    }
    assert worker.calls == [("advance", "account-123", "operation-123")]


def test_handler_records_a_terminal_needs_attention_result_after_retries():
    failed = replace(
        operation(),
        status=OperationStatus.NEEDS_ATTENTION,
        phase=OperationPhase.CHECKING_GAME_HEALTH,
    )
    worker = RecordingWorker(failed)

    result = advance_operation(
        {
            "action": "record_failure",
            "account_id": "account-123",
            "operation_id": "operation-123",
        },
        worker=worker,
    )

    assert result["terminal"] is True
    assert result["status"] == "needs_attention"
    assert worker.calls == [("mark_needs_attention", "account-123", "operation-123")]


@pytest.mark.parametrize(
    "event",
    [{}, {"account_id": "account-123"}, {"operation_id": "operation-123"}],
)
def test_handler_rejects_events_without_persistent_identifiers(event):
    with pytest.raises(ValueError, match="account_id and operation_id are required"):
        advance_operation(event, worker=RecordingWorker(operation()))
