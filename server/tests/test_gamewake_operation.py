from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "gamewake-operation.sh"
INSTALLER = Path(__file__).parents[1] / "install-palworld.sh"


def test_host_operation_dispatcher_has_an_idempotency_guard_without_eval():
    source = SCRIPT.read_text()

    assert "flock" in source
    assert "^[a-f0-9]{64}$" in source
    assert 'mv "$result_file.tmp" "$result_file"' in source
    assert "eval " not in source
    assert 'case "$action" in' in source


def test_host_operation_dispatcher_validates_archives_before_restore_and_upload():
    source = SCRIPT.read_text()

    assert "sha256sum" in source
    assert "ChecksumSHA256" in source
    assert "tar --zstd" in source
    assert "restore-state)" in source
    assert "persist-state)" in source


def test_installer_creates_the_private_operation_directory():
    source = INSTALLER.read_text()

    assert "/var/lib/gamewake-operations" in source


def test_configuration_action_uses_only_per_world_parameter_names():
    source = SCRIPT.read_text()

    assert "PALWORLD_CONFIG_PARAMETER_NAME=$1" in source
    assert "SERVER_PASSWORD_PARAMETER_NAME=$2" in source
    assert "ADMIN_PASSWORD_PARAMETER_NAME=$3" in source
