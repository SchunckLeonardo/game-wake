from dataclasses import replace

from .contracts import (
    BackupStore,
    GameTemplateResolver,
    RuntimeProvider,
    WorldRepository,
    WorldStateStore,
)
from .model import (
    OperationPhase,
    OperationStatus,
    OperationType,
    Runtime,
    StoredWorldState,
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
        backup_store: BackupStore | None = None,
    ) -> None:
        self._repository = repository
        self._runtime_provider = runtime_provider
        self._state_store = state_store
        self._game_templates = game_templates
        self._backup_store = backup_store

    def run_to_completion(
        self,
        account_id: str,
        operation_id: str,
    ) -> WorldOperation:
        while True:
            operation = self._repository.get_operation(account_id, operation_id)
            if operation.status in {
                OperationStatus.SUCCEEDED,
                OperationStatus.CANCELLED,
                OperationStatus.FAILED,
                OperationStatus.NEEDS_ATTENTION,
            }:
                return operation
            self.advance(account_id, operation_id)

    def advance(self, account_id: str, operation_id: str) -> WorldOperation:
        operation = self._repository.get_operation(account_id, operation_id)
        world = self._repository.get(account_id, operation.world_id)
        template = self._game_templates.resolve(world.game_template_id)

        if operation.operation_type is OperationType.SLEEP:
            return self._advance_sleep(operation, world, template)
        if operation.operation_type is OperationType.RECOVER:
            return self._advance_recovery(operation, world, template)

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
                runtime_provider_reference=runtime.provider_reference,
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
            if world.pending_configuration_revision_id is not None:
                configured = replace(
                    operation,
                    status=OperationStatus.RUNNING,
                    phase=OperationPhase.STARTING_GAME,
                    version=operation.version + 1,
                )
                updated_world = replace(
                    world,
                    configuration_revision_id=world.pending_configuration_revision_id,
                    pending_configuration_revision_id=None,
                    version=world.version + 1,
                )
                self._repository.save_operation(
                    configured,
                    expected_operation_version=operation.version,
                    world=updated_world,
                    expected_world_version=world.version,
                )
                return configured
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
                status=(OperationStatus.SUCCEEDED if healthy else OperationStatus.NEEDS_ATTENTION),
                phase=(OperationPhase.COMPLETE if healthy else OperationPhase.CHECKING_GAME_HEALTH),
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

    def mark_needs_attention(
        self,
        account_id: str,
        operation_id: str,
    ) -> WorldOperation:
        operation = self._repository.get_operation(account_id, operation_id)
        if operation.status in {
            OperationStatus.SUCCEEDED,
            OperationStatus.CANCELLED,
            OperationStatus.FAILED,
            OperationStatus.NEEDS_ATTENTION,
        }:
            return operation
        world = self._repository.get(account_id, operation.world_id)
        return self._needs_attention(operation, world)

    def _advance_sleep(self, operation, world, template) -> WorldOperation:
        runtime = self._runtime_for(operation)
        if operation.phase is OperationPhase.REQUESTED:
            return self._move_to_phase(operation, OperationPhase.CHECKING_PLAYERS)

        if operation.phase is OperationPhase.CHECKING_PLAYERS:
            if template.player_count(world, runtime) > 0 and not operation.force:
                cancelled = replace(
                    operation,
                    status=OperationStatus.CANCELLED,
                    phase=OperationPhase.COMPLETE,
                    version=operation.version + 1,
                )
                online = replace(
                    world,
                    status=WorldStatus.ONLINE,
                    version=world.version + 1,
                )
                self._repository.save_operation(
                    cancelled,
                    expected_operation_version=operation.version,
                    world=online,
                    expected_world_version=world.version,
                )
                return cancelled
            return self._move_to_phase(operation, OperationPhase.SAVING_GAME)

        if operation.phase is OperationPhase.SAVING_GAME:
            template.save(
                world,
                runtime,
                idempotency_key=self._effect_key(operation, "save"),
            )
            return self._move_to_phase(operation, OperationPhase.STOPPING_GAME)

        if operation.phase is OperationPhase.STOPPING_GAME:
            template.stop(
                world,
                runtime,
                idempotency_key=self._effect_key(operation, "stop"),
            )
            return self._move_to_phase(operation, OperationPhase.PERSISTING_WORLD)

        if operation.phase is OperationPhase.PERSISTING_WORLD:
            state = self._state_store.persist_and_validate(
                world,
                runtime,
                idempotency_key=self._effect_key(operation, "persist"),
            )
            if not state.validated:
                return self._needs_attention(operation, world)
            persisted = replace(
                operation,
                phase=OperationPhase.CREATING_BACKUP,
                stored_state_id=state.id,
                stored_state_checksum=state.checksum,
                version=operation.version + 1,
            )
            self._repository.save_operation(
                persisted,
                expected_operation_version=operation.version,
            )
            return persisted

        if operation.phase is OperationPhase.CREATING_BACKUP:
            if self._backup_store is None:
                raise RuntimeError("safe sleep requires a Backup Store")
            backup = self._backup_store.create_automatic(
                world,
                self._stored_state_for(operation),
                idempotency_key=self._effect_key(operation, "backup"),
            )
            backed_up = replace(
                operation,
                phase=OperationPhase.RELEASING_RUNTIME,
                backup_id=backup.id,
                version=operation.version + 1,
            )
            self._repository.save_operation(
                backed_up,
                expected_operation_version=operation.version,
            )
            return backed_up

        if operation.phase is OperationPhase.RELEASING_RUNTIME:
            self._runtime_provider.release(
                runtime,
                idempotency_key=self._effect_key(operation, "release"),
            )
            completed = replace(
                operation,
                status=OperationStatus.SUCCEEDED,
                phase=OperationPhase.COMPLETE,
                version=operation.version + 1,
            )
            sleeping = replace(
                world,
                status=WorldStatus.SLEEPING,
                runtime_id=None,
                runtime_provider_reference=None,
                stored_state_id=operation.stored_state_id,
                stored_state_checksum=operation.stored_state_checksum,
                version=world.version + 1,
            )
            self._repository.save_operation(
                completed,
                expected_operation_version=operation.version,
                world=sleeping,
                expected_world_version=world.version,
            )
            return completed

        raise RuntimeError(f"unsupported sleep phase: {operation.phase}")

    def _advance_recovery(self, operation, world, template) -> WorldOperation:
        runtime = self._runtime_for(operation)
        if operation.phase is OperationPhase.REQUESTED:
            return self._move_to_phase(operation, OperationPhase.STARTING_GAME)

        if operation.phase is OperationPhase.STARTING_GAME:
            template.start(
                world,
                runtime,
                idempotency_key=self._effect_key(operation, "restart"),
            )
            return self._move_to_phase(operation, OperationPhase.CHECKING_GAME_HEALTH)

        if operation.phase is OperationPhase.CHECKING_GAME_HEALTH:
            healthy = template.is_healthy(world, runtime)
            exhausted = operation.attempt_number >= 3
            completed = replace(
                operation,
                status=(
                    OperationStatus.SUCCEEDED
                    if healthy
                    else (OperationStatus.NEEDS_ATTENTION if exhausted else OperationStatus.FAILED)
                ),
                phase=OperationPhase.COMPLETE,
                version=operation.version + 1,
            )
            updated_world = replace(
                world,
                status=(
                    WorldStatus.ONLINE
                    if healthy
                    else (WorldStatus.NEEDS_ATTENTION if exhausted else WorldStatus.WAKING)
                ),
                version=world.version + 1,
            )
            self._repository.save_operation(
                completed,
                expected_operation_version=operation.version,
                world=updated_world,
                expected_world_version=world.version,
            )
            return completed

        raise RuntimeError(f"unsupported recovery phase: {operation.phase}")

    def _needs_attention(self, operation, world) -> WorldOperation:
        failed = replace(
            operation,
            status=OperationStatus.NEEDS_ATTENTION,
            version=operation.version + 1,
        )
        attention = replace(
            world,
            status=WorldStatus.NEEDS_ATTENTION,
            version=world.version + 1,
        )
        self._repository.save_operation(
            failed,
            expected_operation_version=operation.version,
            world=attention,
            expected_world_version=world.version,
        )
        return failed

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
    def _stored_state_for(operation: WorldOperation) -> StoredWorldState:
        if operation.stored_state_id is None or operation.stored_state_checksum is None:
            raise RuntimeError("the operation has no validated stored state")
        return StoredWorldState(
            id=operation.stored_state_id,
            checksum=operation.stored_state_checksum,
            validated=True,
        )

    @staticmethod
    def _effect_key(operation: WorldOperation, effect: str) -> str:
        return f"{operation.id}:{effect}"
