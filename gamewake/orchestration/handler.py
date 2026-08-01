from collections.abc import Mapping
from typing import Any

from gamewake.worlds import OperationStatus

_TERMINAL_STATUSES = frozenset(
    {
        OperationStatus.SUCCEEDED,
        OperationStatus.CANCELLED,
        OperationStatus.FAILED,
        OperationStatus.NEEDS_ATTENTION,
    }
)


def advance_operation(event: Mapping[str, Any], *, worker: Any) -> dict[str, object]:
    """Advance exactly one persisted phase for a Step Functions execution."""
    account_id = event.get("account_id")
    operation_id = event.get("operation_id")
    if not isinstance(account_id, str) or not isinstance(operation_id, str):
        raise ValueError("account_id and operation_id are required")

    if event.get("action") == "record_failure":
        operation = worker.mark_needs_attention(account_id, operation_id)
    else:
        operation = worker.advance(account_id, operation_id)

    return {
        "account_id": account_id,
        "operation_id": operation_id,
        "world_id": operation.world_id,
        "operation_type": operation.operation_type.value,
        "status": operation.status.value,
        "phase": operation.phase.value,
        "terminal": operation.status in _TERMINAL_STATUSES,
    }
