from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

from gamewake.worlds import (
    Backup,
    BackupKind,
    ConfigurationRevision,
    StoredWorldState,
    World,
    WorldExport,
    WorldExportManifest,
    WorldStatus,
)


class S3WorldArchiveStore:
    """Stores validated World states, immutable backups and portable exports in S3."""

    def __init__(
        self,
        bucket: str,
        *,
        client: Any | None = None,
        clock: Callable[[], datetime] | None = None,
        download_expiry_seconds: int = 900,
    ) -> None:
        if not bucket:
            raise ValueError("world archive bucket is required")
        if client is None:
            import boto3

            client = boto3.client("s3")
        self._bucket = bucket
        self._client = client
        self._clock = clock or (lambda: datetime.now(UTC))
        self._download_expiry_seconds = download_expiry_seconds

    def create_automatic(
        self, world: World, state: StoredWorldState, *, idempotency_key: str
    ) -> Backup:
        return self._create_backup(world, state, BackupKind.AUTOMATIC, idempotency_key)

    def create_manual(
        self, world: World, state: StoredWorldState, *, idempotency_key: str
    ) -> Backup:
        return self._create_backup(world, state, BackupKind.MANUAL, idempotency_key)

    def create_restore_point(
        self, world: World, state: StoredWorldState, *, idempotency_key: str
    ) -> Backup:
        return self._create_backup(world, state, BackupKind.RESTORE_POINT, idempotency_key)

    def create_final(
        self, world: World, state: StoredWorldState, *, idempotency_key: str
    ) -> Backup:
        return self._create_backup(world, state, BackupKind.FINAL, idempotency_key)

    def list_backups(self, account_id: str, world_id: str) -> tuple[Backup, ...]:
        backups = []
        for item in self._list(f"backups/{account_id}/{world_id}/"):
            metadata = self._client.head_object(Bucket=self._bucket, Key=item["Key"]).get(
                "Metadata", {}
            )
            backups.append(self._backup_from_metadata(metadata, item["Size"]))
        return tuple(
            sorted(
                backups,
                key=lambda backup: backup.created_at or datetime.min.replace(tzinfo=UTC),
            )
        )

    def restore(
        self,
        world: World,
        backup: Backup,
        *,
        idempotency_key: str,
    ) -> StoredWorldState:
        del idempotency_key
        if backup.account_id != world.account_id or backup.world_id != world.id:
            raise KeyError(backup.id)
        self._require_state(world, backup.state_id, backup.checksum)
        return StoredWorldState(
            id=backup.state_id,
            checksum=backup.checksum,
            validated=True,
        )

    def create_export(
        self,
        world: World,
        state: StoredWorldState,
        configuration: ConfigurationRevision,
        *,
        idempotency_key: str,
    ) -> WorldExport:
        self._require_validated_state(world, state)
        export_id = self._stable_id(idempotency_key)
        key = f"exports/{world.account_id}/{world.id}/{export_id}.json"
        created_at = self._clock()
        state_url = self._presigned(self._state_key(world, state.id))
        payload = {
            "format_version": 1,
            "game_template_id": world.game_template_id,
            "configuration_revision_id": configuration.id,
            "configuration": dict(configuration.entries),
            "world_state_id": state.id,
            "world_state_checksum": state.checksum,
            "state_download_url": state_url,
            "state_download_url_expires_in_seconds": self._download_expiry_seconds,
            "created_at": created_at.isoformat(),
        }
        if self._head_or_none(key) is None:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=json.dumps(payload, ensure_ascii=False, sort_keys=True).encode(),
                ContentType="application/json",
                ServerSideEncryption="aws:kms",
                Metadata={
                    "account_id": world.account_id,
                    "world_id": world.id,
                    "export_id": export_id,
                },
            )
        return WorldExport(
            id=export_id,
            account_id=world.account_id,
            world_id=world.id,
            download_url=self._presigned(key),
            manifest=WorldExportManifest(
                format_version=1,
                game_template_id=world.game_template_id,
                configuration_revision_id=configuration.id,
                configuration=configuration.entries,
                world_state_id=state.id,
                world_state_checksum=state.checksum,
            ),
            created_at=created_at,
        )

    def delete_world_data(
        self,
        account_id: str,
        world_id: str,
        *,
        idempotency_key: str,
    ) -> None:
        del idempotency_key
        prefixes = (
            f"states/{account_id}/{world_id}/",
            f"backups/{account_id}/{world_id}/",
            f"exports/{account_id}/{world_id}/",
        )
        versions = [item for prefix in prefixes for item in self._list_versions(prefix)]
        self._delete_versions(versions)

    def storage_usage(self, account_id: str, worlds: tuple[World, ...]) -> int:
        active_worlds = tuple(
            world
            for world in worlds
            if world.account_id == account_id and world.status is not WorldStatus.PENDING_DELETION
        )
        state_bytes = sum(
            int(head["ContentLength"])
            for world in active_worlds
            if world.stored_state_id is not None
            and (head := self._head_or_none(self._state_key(world, world.stored_state_id)))
            is not None
        )
        backup_bytes = sum(
            backup.size_bytes
            for world in active_worlds
            for backup in self.list_backups(account_id, world.id)
        )
        return state_bytes + backup_bytes

    def prune_oldest_automatic(
        self,
        account_id: str,
        worlds: tuple[World, ...],
        *,
        bytes_to_free: int,
    ) -> tuple[Backup, ...]:
        candidates = sorted(
            (
                backup
                for world in worlds
                if world.account_id == account_id
                and world.status is not WorldStatus.PENDING_DELETION
                for backup in self.list_backups(account_id, world.id)
                if backup.kind is BackupKind.AUTOMATIC
            ),
            key=lambda backup: backup.created_at or datetime.min.replace(tzinfo=UTC),
        )
        pruned = []
        freed = 0
        for backup in candidates:
            if freed >= bytes_to_free:
                break
            key = self._backup_key(backup)
            versions = tuple(item for item in self._list_versions(key) if item["Key"] == key)
            self._delete_versions(versions or ({"Key": key},))
            pruned.append(backup)
            freed += backup.size_bytes
        return tuple(pruned)

    def _create_backup(
        self,
        world: World,
        state: StoredWorldState,
        kind: BackupKind,
        idempotency_key: str,
    ) -> Backup:
        source = self._require_validated_state(world, state)
        backup_id = self._stable_id(idempotency_key)
        created_at = self._clock()
        backup = Backup(
            id=backup_id,
            account_id=world.account_id,
            world_id=world.id,
            state_id=state.id,
            checksum=state.checksum,
            kind=kind,
            size_bytes=int(source["ContentLength"]),
            created_at=created_at,
        )
        key = self._backup_key(backup)
        existing = self._head_or_none(key)
        if existing is not None:
            return self._backup_from_metadata(
                existing.get("Metadata", {}), int(existing["ContentLength"])
            )
        self._client.copy_object(
            Bucket=self._bucket,
            Key=key,
            CopySource={"Bucket": self._bucket, "Key": self._state_key(world, state.id)},
            MetadataDirective="REPLACE",
            ChecksumAlgorithm="SHA256",
            ServerSideEncryption="aws:kms",
            Metadata={
                "backup_id": backup.id,
                "account_id": backup.account_id,
                "world_id": backup.world_id,
                "state_id": backup.state_id,
                "checksum": backup.checksum,
                "kind": backup.kind.value,
                "created_at": created_at.isoformat(),
            },
        )
        return backup

    def _require_validated_state(self, world: World, state: StoredWorldState) -> dict[str, Any]:
        if not state.validated:
            raise ValueError("Backup requires a validated World state")
        return self._require_state(world, state.id, state.checksum)

    def _require_state(self, world: World, state_id: str, checksum: str) -> dict[str, Any]:
        head = self._head_or_none(self._state_key(world, state_id))
        if head is None:
            raise ValueError("validated World state does not exist in S3")
        metadata_checksum = head.get("Metadata", {}).get("sha256")
        if metadata_checksum and f"sha256:{metadata_checksum}" != checksum:
            raise ValueError("validated World state checksum does not match S3")
        return head

    def _head_or_none(self, key: str) -> dict[str, Any] | None:
        try:
            return self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    def _list(self, prefix: str) -> Iterator[dict[str, Any]]:
        token = None
        while True:
            request: dict[str, Any] = {"Bucket": self._bucket, "Prefix": prefix}
            if token is not None:
                request["ContinuationToken"] = token
            response = self._client.list_objects_v2(**request)
            yield from response.get("Contents", [])
            if not response.get("IsTruncated"):
                return
            token = response["NextContinuationToken"]

    def _list_versions(self, prefix: str) -> Iterator[dict[str, str]]:
        key_marker = None
        version_marker = None
        while True:
            request: dict[str, Any] = {"Bucket": self._bucket, "Prefix": prefix}
            if key_marker is not None:
                request["KeyMarker"] = key_marker
            if version_marker is not None:
                request["VersionIdMarker"] = version_marker
            response = self._client.list_object_versions(**request)
            for item in (*response.get("Versions", []), *response.get("DeleteMarkers", [])):
                yield {"Key": str(item["Key"]), "VersionId": str(item["VersionId"])}
            if not response.get("IsTruncated"):
                return
            key_marker = response["NextKeyMarker"]
            version_marker = response.get("NextVersionIdMarker")

    def _delete_versions(self, versions: tuple[dict[str, str], ...] | list[dict[str, str]]) -> None:
        for offset in range(0, len(versions), 1000):
            self._client.delete_objects(
                Bucket=self._bucket,
                Delete={
                    "Objects": versions[offset : offset + 1000],
                    "Quiet": True,
                },
            )

    def _presigned(self, key: str) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=self._download_expiry_seconds,
        )

    @staticmethod
    def _stable_id(idempotency_key: str) -> str:
        return hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]

    @staticmethod
    def _state_key(world: World, state_id: str) -> str:
        return f"states/{world.account_id}/{world.id}/{state_id}.tar.zst"

    @staticmethod
    def _backup_key(backup: Backup) -> str:
        return (
            f"backups/{backup.account_id}/{backup.world_id}/{backup.kind.value}/{backup.id}.tar.zst"
        )

    @staticmethod
    def _backup_from_metadata(metadata: dict[str, str], size: int) -> Backup:
        required = {
            "backup_id",
            "account_id",
            "world_id",
            "state_id",
            "checksum",
            "kind",
            "created_at",
        }
        if not required.issubset(metadata):
            raise ValueError("S3 backup metadata is incomplete")
        return Backup(
            id=metadata["backup_id"],
            account_id=metadata["account_id"],
            world_id=metadata["world_id"],
            state_id=metadata["state_id"],
            checksum=metadata["checksum"],
            kind=BackupKind(metadata["kind"]),
            size_bytes=size,
            created_at=datetime.fromisoformat(metadata["created_at"]),
        )
