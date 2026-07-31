from dataclasses import replace

from .contracts import (
    GameTemplateResolver,
    RuntimeProvider,
    WorldRepository,
    WorldStateStore,
)
from .model import (
    OperationPhase,
    OperationStatus,
    Runtime,
    WorldOperation,
    WorldStatus,
)


class WorldOperationWorker:
    def __init__(
        self,
        repository: WorldRepository,
        *,
        runtime_provider: RuntimeProvider,
        state_store: WorldStateStore,
        game_templates: GameTemplateResolver,
    ) -> None:
        self._repository = repository
        self._runtime_provider = runtime_provider
        self._state_store = state_store
        self._game_templates = game_templates

    def run_to_completion(
        self,
        account_id: str,
        operation_id: str,
    ) -> WorldOperation:
        while True:
            operation = self._repository.get_operation(account_id, operation_id)
            if operation.status in {
                OperationStatus.SUCCEEDED,
                OperationStatus.NEEDS_ATTENTION,
            }:
                return operation
            self.advance(account_id, operation_id)

    def advance(self, account_id: str, operation_id: str) -> WorldOperation:
        operation = self._repository.get_operation(account_id, operation_id)
        world = self._repository.get(account_id, operation.world_id)
        template = self._game_templates.resolve(world.game_template_id)

        if operation.phase is OperationPhase.REQUESTED:
            return self._move_to_phase(operation, OperationPhase.PROVISIONING_RUNTIME)

        if operation.phase is OperationPhase.PROVISIONING_RUNTIME:
            runtime = self._runtime_provider.provision(
                world,
                idempotency_key=self._effect_key(operation, "provision"),
            )
            updated_operation = replace(
                operation,
                phase=OperationPhase.RESTORING_WORLD,
                runtime_id=runtime.id,
                runtime_provider_reference=runtime.provider_reference,
                version=operation.version + 1,
            )
            updated_world = replace(
                world,
                runtime_id=runtime.id,
                version=world.version + 1,
            )
            self._repository.save_operation(
                updated_operation,
                expected_operation_version=operation.version,
                world=updated_world,
                expected_world_version=world.version,
            )
            return updated_operation

        runtime = self._runtime_for(operation)
        if operation.phase is OperationPhase.RESTORING_WORLD:
            self._state_store.restore(
                world,
                runtime,
                idempotency_key=self._effect_key(operation, "restore"),
            )
            return self._move_to_phase(operation, OperationPhase.APPLYING_CONFIGURATION)

        if operation.phase is OperationPhase.APPLYING_CONFIGURATION:
            template.apply_configuration(
                world,
                runtime,
                idempotency_key=self._effect_key(operation, "configure"),
            )
            return self._move_to_phase(operation, OperationPhase.STARTING_GAME)

        if operation.phase is OperationPhase.STARTING_GAME:
            template.start(
                world,
                runtime,
                idempotency_key=self._effect_key(operation, "start"),
            )
            return self._move_to_phase(operation, OperationPhase.CHECKING_GAME_HEALTH)

        if operation.phase is OperationPhase.CHECKING_GAME_HEALTH:
            healthy = template.is_healthy(world, runtime)
            completed = replace(
                operation,
                status=(
                    OperationStatus.SUCCEEDED
                    if healthy
                    else OperationStatus.NEEDS_ATTENTION
                ),
                phase=(
                    OperationPhase.COMPLETE
                    if healthy
                    else OperationPhase.CHECKING_GAME_HEALTH
                ),
                version=operation.version + 1,
            )
            updated_world = replace(
                world,
                status=(WorldStatus.ONLINE if healthy else WorldStatus.NEEDS_ATTENTION),
                version=world.version + 1,
            )
            self._repository.save_operation(
                completed,
                expected_operation_version=operation.version,
                world=updated_world,
                expected_world_version=world.version,
            )
            return completed

        raise RuntimeError(f"unsupported operation phase: {operation.phase}")

    def _move_to_phase(
        self,
        operation: WorldOperation,
        phase: OperationPhase,
    ) -> WorldOperation:
        updated = replace(
            operation,
            status=OperationStatus.RUNNING,
            phase=phase,
            version=operation.version + 1,
        )
        self._repository.save_operation(
            updated,
            expected_operation_version=operation.version,
        )
        return updated

    @staticmethod
    def _runtime_for(operation: WorldOperation) -> Runtime:
        if operation.runtime_id is None or operation.runtime_provider_reference is None:
            raise RuntimeError("the operation has no persisted Runtime")
        return Runtime(
            id=operation.runtime_id,
            provider_reference=operation.runtime_provider_reference,
        )

    @staticmethod
    def _effect_key(operation: WorldOperation, effect: str) -> str:
        return f"{operation.id}:{effect}"
