from threading import RLock

from .model import OperationStatus, World, WorldOperation


class InMemoryWorldRepository:
    def __init__(self) -> None:
        self._worlds: dict[tuple[str, str], World] = {}
        self._operations: dict[str, WorldOperation] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._active_operations: dict[tuple[str, str], str] = {}
        self._lock = RLock()

    def create(self, world: World) -> None:
        self._worlds[(world.account_id, world.id)] = world

    def get(self, account_id: str, world_id: str) -> World:
        return self._worlds[(account_id, world_id)]

    def save(self, world: World, expected_version: int) -> None:
        key = (world.account_id, world.id)
        current = self._worlds[key]
        if current.version != expected_version:
            raise RuntimeError("World was changed concurrently")
        self._worlds[key] = world

    def begin_operation(
        self,
        world: World,
        operation: WorldOperation,
        *,
        expected_world_version: int,
    ) -> WorldOperation:
        with self._lock:
            idempotency_key = (operation.account_id, operation.idempotency_key)
            existing_id = self._idempotency.get(idempotency_key)
            if existing_id is not None:
                return self._operations[existing_id]

            world_key = (operation.account_id, operation.world_id)
            active_id = self._active_operations.get(world_key)
            if active_id is not None:
                active = self._operations[active_id]
                if active.status in {OperationStatus.PENDING, OperationStatus.RUNNING}:
                    return active

            current = self._worlds[world_key]
            if current.version != expected_world_version:
                raise RuntimeError("World was changed concurrently")
            self._worlds[world_key] = world
            self._operations[operation.id] = operation
            self._idempotency[idempotency_key] = operation.id
            self._active_operations[world_key] = operation.id
            return operation

    def list_operations(
        self,
        account_id: str,
        world_id: str,
    ) -> tuple[WorldOperation, ...]:
        return tuple(
            operation
            for operation in self._operations.values()
            if operation.account_id == account_id and operation.world_id == world_id
        )
