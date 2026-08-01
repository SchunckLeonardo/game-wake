import json
from datetime import UTC, datetime

import pytest

from gamewake.aws import S3WorldArchiveStore
from gamewake.worlds import (
    BackupKind,
    ConfigurationRevision,
    StoredWorldState,
    World,
    WorldStatus,
)

NOW = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)


def world():
    return World(
        id="world-123",
        account_id="account-123",
        name="Palpagos",
        game_template_id="palworld:1",
        region="us-east-1",
        runtime_profile_id="palworld-small",
        status=WorldStatus.SLEEPING,
        runtime_id=None,
        runtime_provider_reference=None,
        configuration_revision_id="configuration-123",
        pending_configuration_revision_id=None,
        stored_state_id="state-123",
        stored_state_checksum="sha256:abc123",
        version=1,
    )


class NoSuchKey(Exception):
    pass


class FakeS3Client:
    class exceptions:
        NoSuchKey = NoSuchKey

    def __init__(self):
        self.objects = {
            "states/account-123/world-123/state-123.tar.zst": {
                "Body": b"world-state",
                "ContentLength": 11,
                "Metadata": {"sha256": "abc123"},
            }
        }
        self.copy_calls = []
        self.delete_calls = []

    def head_object(self, *, Bucket, Key, **kwargs):
        del Bucket, kwargs
        try:
            return self.objects[Key]
        except KeyError as error:
            missing = NoSuchKey(Key)
            missing.response = {"Error": {"Code": "404"}}
            raise missing from error

    def copy_object(self, *, Bucket, Key, CopySource, Metadata, **kwargs):
        del Bucket, kwargs
        self.copy_calls.append((Key, CopySource, Metadata))
        source = self.objects[CopySource["Key"]]
        self.objects[Key] = {
            "Body": source["Body"],
            "ContentLength": source["ContentLength"],
            "Metadata": Metadata,
            "LastModified": NOW,
        }

    def list_objects_v2(self, *, Bucket, Prefix, **kwargs):
        del Bucket, kwargs
        return {
            "Contents": [
                {
                    "Key": key,
                    "Size": value["ContentLength"],
                    "LastModified": value.get("LastModified", NOW),
                }
                for key, value in self.objects.items()
                if key.startswith(Prefix)
            ],
            "IsTruncated": False,
        }

    def put_object(self, *, Bucket, Key, Body, Metadata, **kwargs):
        del Bucket, kwargs
        self.objects[Key] = {
            "Body": Body,
            "ContentLength": len(Body),
            "Metadata": Metadata,
            "LastModified": NOW,
        }

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        assert operation == "get_object"
        return f"https://signed.invalid/{Params['Key']}?expires={ExpiresIn}"

    def delete_objects(self, *, Bucket, Delete):
        del Bucket
        self.delete_calls.append(Delete)
        for entry in Delete["Objects"]:
            self.objects.pop(entry["Key"], None)


def test_automatic_backup_copies_a_validated_state_once_with_durable_metadata():
    client = FakeS3Client()
    archive = S3WorldArchiveStore("world-data", client=client, clock=lambda: NOW)
    state = StoredWorldState(id="state-123", checksum="sha256:abc123", validated=True)

    first = archive.create_automatic(world(), state, idempotency_key="sleep-123:backup")
    second = archive.create_automatic(world(), state, idempotency_key="sleep-123:backup")

    assert first == second
    assert first.kind is BackupKind.AUTOMATIC
    assert first.size_bytes == 11
    assert first.created_at == NOW
    assert len(client.copy_calls) == 1
    _, source, metadata = client.copy_calls[0]
    assert source == {
        "Bucket": "world-data",
        "Key": "states/account-123/world-123/state-123.tar.zst",
    }
    assert metadata["checksum"] == "sha256:abc123"
    assert metadata["kind"] == "automatic"


def test_backup_rejects_an_unvalidated_or_missing_state():
    archive = S3WorldArchiveStore("world-data", client=FakeS3Client(), clock=lambda: NOW)

    with pytest.raises(ValueError, match="validated World state"):
        archive.create_manual(
            world(),
            StoredWorldState(id="state-123", checksum="sha256:abc123", validated=False),
            idempotency_key="manual-123",
        )
    with pytest.raises(ValueError, match="does not exist"):
        archive.create_manual(
            world(),
            StoredWorldState(id="missing", checksum="sha256:missing", validated=True),
            idempotency_key="manual-456",
        )


def test_export_writes_a_portable_manifest_with_a_short_lived_state_url():
    client = FakeS3Client()
    archive = S3WorldArchiveStore("world-data", client=client, clock=lambda: NOW)
    configuration = ConfigurationRevision(
        id="configuration-123",
        account_id="account-123",
        world_id="world-123",
        game_template_id="palworld:1",
        number=1,
        entries=(("enemy_drop_item_rate", 3.0),),
        idempotency_key="initial",
        created_at=NOW,
    )

    exported = archive.create_export(
        world(),
        StoredWorldState(id="state-123", checksum="sha256:abc123", validated=True),
        configuration,
        idempotency_key="export-123",
    )

    manifest_key = next(key for key in client.objects if key.startswith("exports/"))
    manifest = json.loads(client.objects[manifest_key]["Body"])
    assert exported.download_url.startswith("https://signed.invalid/exports/")
    assert manifest["format_version"] == 1
    assert manifest["configuration"] == {"enemy_drop_item_rate": 3.0}
    assert manifest["world_state_checksum"] == "sha256:abc123"
    assert manifest["state_download_url"].startswith(
        "https://signed.invalid/states/account-123/world-123/state-123.tar.zst"
    )


def test_delete_world_data_removes_only_the_selected_tenant_prefixes():
    client = FakeS3Client()
    client.objects["states/other-account/world-123/keep.tar.zst"] = {
        "Body": b"keep",
        "ContentLength": 4,
        "Metadata": {},
    }
    archive = S3WorldArchiveStore("world-data", client=client, clock=lambda: NOW)
    archive.create_automatic(
        world(),
        StoredWorldState(id="state-123", checksum="sha256:abc123", validated=True),
        idempotency_key="sleep-123:backup",
    )

    archive.delete_world_data(
        "account-123",
        "world-123",
        idempotency_key="delete-123",
    )

    assert set(client.objects) == {"states/other-account/world-123/keep.tar.zst"}
