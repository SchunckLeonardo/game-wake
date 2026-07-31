from dataclasses import replace
from uuid import uuid4

from gamewake.accounts import Permission, PermissionDeniedError

from .contracts import AccessControl, WorldRepository
from .model import (
    OperationPhase,
    OperationStatus,
    OperationType,
    World,
    WorldOperation,
    WorldStatus,
)


class Worlds:
    def __init__(self, repository: WorldRepository, *, access: AccessControl) -> None:
        self._repository = repository
        self._access = access

    def create_world(
        self,
        account_id: str,
        *,
        actor_user_id: str,
        name: str,
        game_template_id: str,
        region: str,
        runtime_profile_id: str,
    ) -> World:
        if not self._access.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.CREATE_WORLD,
        ):
            raise PermissionDeniedError("creating a World requires Owner permission")
        world = World(
            id=str(uuid4()),
            account_id=account_id,
            name=name,
            game_template_id=game_template_id,
            region=region,
            runtime_profile_id=runtime_profile_id,
            status=WorldStatus.SLEEPING,
            runtime_id=None,
            version=1,
        )
        self._repository.create(world)
        return world

    def get_world(
        self,
        account_id: str,
        world_id: str,
        *,
        viewer_user_id: str,
    ) -> World:
        if not self._access.authorize(
            account_id,
            user_id=viewer_user_id,
            permission=Permission.VIEW_WORLD,
            world_id=world_id,
        ):
            raise PermissionDeniedError("the User cannot view this World")
        return self._repository.get(account_id, world_id)

    def request_wake(
        self,
        account_id: str,
        world_id: str,
        *,
        actor_user_id: str,
        idempotency_key: str,
    ) -> WorldOperation:
        if not self._access.authorize(
            account_id,
            user_id=actor_user_id,
            permission=Permission.WAKE_WORLD,
            world_id=world_id,
        ):
            raise PermissionDeniedError("the User cannot wake this World")
        world = self._repository.get(account_id, world_id)
        operation = WorldOperation(
            id=str(uuid4()),
            account_id=account_id,
            world_id=world_id,
            operation_type=OperationType.WAKE,
            status=OperationStatus.PENDING,
            phase=OperationPhase.REQUESTED,
            idempotency_key=idempotency_key,
            version=1,
        )
        return self._repository.begin_operation(
            replace(
                world,
                status=WorldStatus.WAKING,
                version=world.version + 1,
            ),
            operation,
            expected_world_version=world.version,
        )

    def list_operations(
        self,
        account_id: str,
        world_id: str,
        *,
        viewer_user_id: str,
    ) -> list[WorldOperation]:
        if not self._access.authorize(
            account_id,
            user_id=viewer_user_id,
            permission=Permission.VIEW_WORLD,
            world_id=world_id,
        ):
            raise PermissionDeniedError("the User cannot view this World's operations")
        return list(self._repository.list_operations(account_id, world_id))
