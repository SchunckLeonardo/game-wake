from .model import World


class InMemoryWorldRepository:
    def __init__(self) -> None:
        self._worlds: dict[tuple[str, str], World] = {}

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
