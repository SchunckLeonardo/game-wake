from __future__ import annotations

import hashlib
import json
import shlex
from collections.abc import Sequence
from secrets import token_urlsafe
from typing import Any

from gamewake.control_plane import WorldPasswordSettings
from gamewake.worlds import Runtime, StoredWorldState, World
from gamewake.worlds.contracts import WorldRepository

_HOST_ACTIONS = frozenset(
    {
        "apply-configuration",
        "health",
        "initialize-state",
        "persist-state",
        "player-count",
        "restore-state",
        "save",
        "start",
        "stop",
    }
)


class RuntimeNotReady(RuntimeError):
    """The managed host is registered in SSM but is still bootstrapping."""


class SsmWorldPasswordManager:
    """Keeps Palworld entry credentials in SecureString parameters, never in World data."""

    _MODES = frozenset({"fixed", "random_each_run"})

    def __init__(
        self,
        *,
        parameter_prefix: str,
        client: Any | None = None,
        password_factory: Any | None = None,
    ) -> None:
        if not parameter_prefix:
            raise ValueError("per-World parameter prefix is required")
        if client is None:
            import boto3

            client = boto3.client("ssm")
        self._parameter_prefix = parameter_prefix.rstrip("/")
        self._client = client
        self._password_factory = password_factory or (lambda: token_urlsafe(12))

    def get(self, world: World) -> WorldPasswordSettings:
        mode = self._read_optional(self._name(world, "server-password-mode")) or "fixed"
        if mode not in self._MODES:
            raise ValueError("stored World password mode is invalid")
        return WorldPasswordSettings(mode=mode)

    def configure(
        self,
        world: World,
        *,
        mode: str,
        password: str | None,
    ) -> WorldPasswordSettings:
        if mode not in self._MODES:
            raise ValueError("password mode must be fixed or random_each_run")
        if mode == "fixed":
            self._validate_password(password)
            self._client.put_parameter(
                Name=self._name(world, "server-password"),
                Description="GameWake managed per-World Palworld entry credential",
                Type="SecureString",
                Value=password,
                Overwrite=True,
            )
        elif password is not None:
            raise ValueError("random_each_run does not accept a fixed password")
        self._client.put_parameter(
            Name=self._name(world, "server-password-mode"),
            Description="GameWake per-World Palworld password rotation mode",
            Type="String",
            Value=mode,
            Overwrite=True,
        )
        return WorldPasswordSettings(mode=mode)

    def prepare_for_run(self, world: World, *, idempotency_key: str) -> None:
        settings = self.get(world)
        password_name = self._name(world, "server-password")
        if settings.mode == "fixed":
            self._ensure_secret(password_name)
            return

        rotation_name = self._name(world, "server-password-rotation")
        if self._read_optional(rotation_name) == idempotency_key:
            return
        generated = self._password_factory()
        self._validate_password(generated)
        self._client.put_parameter(
            Name=password_name,
            Description="GameWake managed per-World Palworld entry credential",
            Type="SecureString",
            Value=generated,
            Overwrite=True,
        )
        self._client.put_parameter(
            Name=rotation_name,
            Description="Idempotency marker for the current World password rotation",
            Type="String",
            Value=idempotency_key,
            Overwrite=True,
        )

    def _ensure_secret(self, name: str) -> None:
        if self._read_optional(name) is not None:
            return
        try:
            self._client.put_parameter(
                Name=name,
                Description="GameWake managed per-World Palworld entry credential",
                Type="SecureString",
                Value=self._password_factory(),
                Overwrite=False,
            )
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code != "ParameterAlreadyExists":
                raise

    def _read_optional(self, name: str) -> str | None:
        try:
            return str(
                self._client.get_parameter(Name=name, WithDecryption=False)["Parameter"]["Value"]
            )
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code == "ParameterNotFound":
                return None
            raise

    def _name(self, world: World, suffix: str) -> str:
        return f"{self._parameter_prefix}/{world.account_id}/{world.id}/{suffix}"

    @staticmethod
    def _validate_password(password: object) -> None:
        if not isinstance(password, str) or not 6 <= len(password) <= 64:
            raise ValueError("fixed password must contain between 6 and 64 characters")
        if any(ord(character) < 32 or ord(character) == 127 for character in password):
            raise ValueError("fixed password cannot contain control characters")


class SsmCommandRunner:
    """Runs one allowlisted host action behind a durable remote idempotency guard."""

    def __init__(self, *, client: Any | None = None) -> None:
        if client is None:
            import boto3

            client = boto3.client("ssm")
        self._client = client

    def run(
        self,
        instance_id: str,
        action: str,
        *,
        idempotency_key: str,
        arguments: Sequence[str] = (),
    ) -> str:
        if action not in _HOST_ACTIONS:
            raise ValueError(f"unsupported GameWake host action: {action}")
        marker = hashlib.sha256(idempotency_key.encode()).hexdigest()
        command = " ".join(
            shlex.quote(value)
            for value in (
                "sudo",
                "/opt/gamewake/bin/gamewake-operation",
                marker,
                action,
                *arguments,
            )
        )
        response = self._client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [command]},
            TimeoutSeconds=300,
        )
        command_id = response["Command"]["CommandId"]
        try:
            self._client.get_waiter("command_executed").wait(
                CommandId=command_id,
                InstanceId=instance_id,
                WaiterConfig={"Delay": 2, "MaxAttempts": 150},
            )
        except Exception as waiter_error:
            result = self._client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
            self._raise_for_failure(result, action, cause=waiter_error)
            raise RuntimeError(f"SSM action {action} failed") from waiter_error
        result = self._client.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id,
        )
        self._raise_for_failure(result, action)
        return str(result.get("StandardOutputContent", "")).strip()

    @staticmethod
    def _raise_for_failure(
        result: dict[str, Any],
        action: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        if result.get("Status") == "Success":
            return
        response_code = str(result.get("ResponseCode"))
        if response_code == "75":
            raise RuntimeNotReady("GameWake runtime bootstrap is still running") from cause
        if response_code == "-1":
            raise RuntimeNotReady("GameWake runtime has not received the command yet") from cause
        raise RuntimeError(f"SSM action {action} failed") from cause


class SsmPalworldTemplate:
    """Palworld lifecycle operations executed through the managed host agent."""

    def __init__(
        self,
        runner: SsmCommandRunner,
        *,
        repository: WorldRepository | None = None,
        parameter_prefix: str | None = None,
        base_configuration: dict[str, Any] | None = None,
        client: Any | None = None,
        password_factory: Any = token_urlsafe,
        password_manager: SsmWorldPasswordManager | None = None,
    ) -> None:
        self._runner = runner
        self._repository = repository
        self._parameter_prefix = parameter_prefix.rstrip("/") if parameter_prefix else None
        self._base_configuration = dict(base_configuration or {})
        if client is None and repository is not None:
            import boto3

            client = boto3.client("ssm")
        self._client = client
        self._password_factory = password_factory
        self._password_manager = password_manager
        if (
            self._password_manager is None
            and repository is not None
            and self._parameter_prefix is not None
            and client is not None
        ):
            self._password_manager = SsmWorldPasswordManager(
                parameter_prefix=self._parameter_prefix,
                client=client,
                password_factory=password_factory,
            )

    def apply_configuration(
        self,
        world: World,
        runtime: Runtime,
        *,
        idempotency_key: str,
    ) -> None:
        arguments = (world.configuration_revision_id,)
        if self._repository is not None:
            revision_id = world.pending_configuration_revision_id or world.configuration_revision_id
            revision = self._repository.get_configuration(
                world.account_id,
                world.id,
                revision_id,
            )
            parameter_base = self._world_parameter_base(world)
            config_parameter = f"{parameter_base}/config"
            server_password_parameter = f"{parameter_base}/server-password"
            admin_password_parameter = f"{parameter_base}/admin-password"
            configuration = {**self._base_configuration, **revision.values}
            self._client.put_parameter(
                Name=config_parameter,
                Description="Effective non-secret GameWake World configuration",
                Type="String",
                Value=json.dumps(configuration, separators=(",", ":"), sort_keys=True),
                Overwrite=True,
            )
            if self._password_manager is None:
                raise RuntimeError("per-World password manager is not configured")
            self._password_manager.prepare_for_run(world, idempotency_key=idempotency_key)
            self._ensure_secret(admin_password_parameter)
            arguments = (
                config_parameter,
                server_password_parameter,
                admin_password_parameter,
            )
        self._runner.run(
            runtime.provider_reference,
            "apply-configuration",
            idempotency_key=idempotency_key,
            arguments=arguments,
        )

    def _world_parameter_base(self, world: World) -> str:
        if self._parameter_prefix is None:
            raise RuntimeError("per-World parameter prefix is not configured")
        return f"{self._parameter_prefix}/{world.account_id}/{world.id}"

    def _ensure_secret(self, name: str) -> None:
        try:
            self._client.get_parameter(Name=name, WithDecryption=False)
            return
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code != "ParameterNotFound":
                raise
        try:
            self._client.put_parameter(
                Name=name,
                Description="GameWake managed per-World Palworld credential",
                Type="SecureString",
                Value=self._password_factory(),
                Overwrite=False,
            )
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code != "ParameterAlreadyExists":
                raise

    def start(
        self,
        world: World,
        runtime: Runtime,
        *,
        idempotency_key: str,
    ) -> None:
        del world
        self._runner.run(
            runtime.provider_reference,
            "start",
            idempotency_key=idempotency_key,
        )

    def is_healthy(self, world: World, runtime: Runtime) -> bool:
        result = self._runner.run(
            runtime.provider_reference,
            "health",
            idempotency_key=f"health:{world.id}",
        )
        health = result.strip().casefold()
        if health == "starting":
            raise RuntimeNotReady("Palworld game process is still starting")
        return health == "healthy"

    def player_count(self, world: World, runtime: Runtime) -> int:
        result = self._runner.run(
            runtime.provider_reference,
            "player-count",
            idempotency_key=f"player-count:{world.id}",
        )
        try:
            count = int(result.strip())
        except ValueError as error:
            raise ValueError("Palworld host returned an invalid player count") from error
        if count < 0:
            raise ValueError("Palworld host returned an invalid player count")
        return count

    def save(
        self,
        world: World,
        runtime: Runtime,
        *,
        idempotency_key: str,
    ) -> None:
        del world
        self._runner.run(
            runtime.provider_reference,
            "save",
            idempotency_key=idempotency_key,
        )

    def stop(
        self,
        world: World,
        runtime: Runtime,
        *,
        idempotency_key: str,
    ) -> None:
        del world
        self._runner.run(
            runtime.provider_reference,
            "stop",
            idempotency_key=idempotency_key,
        )


class S3WorldStateStore:
    """Coordinates validated world archives written by a disposable runtime to S3."""

    def __init__(self, bucket: str, *, runner: SsmCommandRunner) -> None:
        if not bucket:
            raise ValueError("world state bucket is required")
        self._bucket = bucket
        self._runner = runner

    def restore(
        self,
        world: World,
        runtime: Runtime,
        *,
        idempotency_key: str,
    ) -> None:
        if world.stored_state_id is None or world.stored_state_checksum is None:
            self._runner.run(
                runtime.provider_reference,
                "initialize-state",
                idempotency_key=idempotency_key,
            )
            return
        self._runner.run(
            runtime.provider_reference,
            "restore-state",
            idempotency_key=idempotency_key,
            arguments=(
                self._bucket,
                self._state_key(world, world.stored_state_id),
                world.stored_state_checksum,
            ),
        )

    def persist_and_validate(
        self,
        world: World,
        runtime: Runtime,
        *,
        idempotency_key: str,
    ) -> StoredWorldState:
        output = self._runner.run(
            runtime.provider_reference,
            "persist-state",
            idempotency_key=idempotency_key,
            arguments=(self._bucket, self._state_prefix(world)),
        )
        try:
            result = json.loads(output)
            state_id = result["state_id"]
            checksum = result["checksum"]
            validated = result["validated"] is True
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("runtime did not return a validated World state") from error
        if (
            not validated
            or not isinstance(state_id, str)
            or not state_id
            or not isinstance(checksum, str)
            or not checksum.startswith("sha256:")
        ):
            raise ValueError("runtime did not return a validated World state")
        return StoredWorldState(id=state_id, checksum=checksum, validated=True)

    @staticmethod
    def _state_prefix(world: World) -> str:
        return f"states/{world.account_id}/{world.id}/"

    @classmethod
    def _state_key(cls, world: World, state_id: str) -> str:
        return f"{cls._state_prefix(world)}{state_id}.tar.zst"
