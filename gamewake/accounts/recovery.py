from typing import Protocol


class InvalidRecoveryCodeError(PermissionError):
    """Raised when a recovery code is invalid or was already consumed."""


class RecoverySecretStore(Protocol):
    def put(
        self,
        owner_user_id: str,
        verified_email: str,
        recovery_code_hashes: frozenset[str],
    ) -> None: ...

    def is_enabled(self, owner_user_id: str) -> bool: ...

    def consume(self, owner_user_id: str, recovery_code_hash: str) -> bool: ...


class NoOpRecoverySecretStore:
    def put(
        self,
        owner_user_id: str,
        verified_email: str,
        recovery_code_hashes: frozenset[str],
    ) -> None:
        raise RuntimeError("an Owner Recovery secret store must be configured")

    def is_enabled(self, owner_user_id: str) -> bool:
        return False

    def consume(self, owner_user_id: str, recovery_code_hash: str) -> bool:
        return False


class InMemoryRecoverySecretStore:
    def __init__(self) -> None:
        self._profiles: dict[str, tuple[str, set[str]]] = {}

    def put(
        self,
        owner_user_id: str,
        verified_email: str,
        recovery_code_hashes: frozenset[str],
    ) -> None:
        self._profiles[owner_user_id] = (verified_email, set(recovery_code_hashes))

    def is_enabled(self, owner_user_id: str) -> bool:
        return owner_user_id in self._profiles

    def consume(self, owner_user_id: str, recovery_code_hash: str) -> bool:
        profile = self._profiles.get(owner_user_id)
        if profile is None or recovery_code_hash not in profile[1]:
            return False
        profile[1].remove(recovery_code_hash)
        return True
