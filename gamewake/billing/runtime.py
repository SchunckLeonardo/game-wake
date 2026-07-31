from __future__ import annotations

from datetime import datetime

from gamewake.worlds import World, WorldOperation

from .service import Billing


class BillingRuntimeUsageRecorder:
    """Closes an active Runtime session and applies the failed-wake guarantee."""

    def __init__(self, billing: Billing) -> None:
        self._billing = billing

    def protect(self, world: World, *, observed_at: datetime) -> object | None:
        if (
            world.session_quote_id is None
            or world.usage_reservation_id is None
            or world.runtime_started_at is None
        ):
            return None
        return self._billing.protect_active_session(
            world.account_id,
            quote_id=world.session_quote_id,
            reservation_id=world.usage_reservation_id,
            runtime_started_at=world.runtime_started_at,
            observed_at=observed_at,
        )

    def cancel(self, operation: WorldOperation) -> object | None:
        if operation.usage_reservation_id is None:
            return None
        return self._billing.release_reservation(
            operation.account_id,
            operation.usage_reservation_id,
        )

    def record_release(
        self,
        operation: WorldOperation,
        *,
        runtime_released_at: datetime,
        reached_online: bool,
    ) -> object:
        if (
            operation.session_quote_id is None
            or operation.usage_reservation_id is None
            or operation.runtime_started_at is None
        ):
            raise RuntimeError("Runtime operation does not have a complete billing session")
        usage = self._billing.capture_runtime_usage(
            operation.account_id,
            quote_id=operation.session_quote_id,
            reservation_id=operation.usage_reservation_id,
            runtime_started_at=operation.runtime_started_at,
            runtime_released_at=runtime_released_at,
            idempotency_key=f"operation:{operation.id}:runtime-usage",
        )
        if not reached_online:
            self._billing.apply_wake_guarantee(
                operation.account_id,
                usage.id,
                reached_online=False,
                idempotency_key=f"operation:{operation.id}:wake-guarantee",
            )
        return usage
