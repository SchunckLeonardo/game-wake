from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "gamewake-operation.sh"
INSTALLER = Path(__file__).parents[1] / "install-palworld.sh"
USER_DATA = Path(__file__).parents[2] / "terraform" / "user-data.sh.tpl"


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


def test_installer_retries_transient_steamcmd_failures():
    source = INSTALLER.read_text()

    assert "steamcmd_max_attempts=3" in source
    assert "SteamCMD attempt $attempt/$steamcmd_max_attempts failed" in source
    assert 'sleep "$((attempt * steamcmd_retry_delay_seconds))"' in source


def test_configuration_action_uses_only_per_world_parameter_names():
    source = SCRIPT.read_text()

    assert "PALWORLD_CONFIG_PARAMETER_NAME=%q" in source
    assert "SERVER_PASSWORD_PARAMETER_NAME=%q" in source
    assert "ADMIN_PASSWORD_PARAMETER_NAME=%q" in source
    assert "/etc/palworld/world.env" in source


def test_runtime_bootstrap_requires_the_prepared_image_without_reinstalling_palworld():
    operation = SCRIPT.read_text()
    user_data = USER_DATA.read_text()

    assert "bootstrap-ready" in operation
    assert "exit 75" in operation
    assert "bootstrap-ready" in user_data
    assert "/opt/gamewake/image-ready" in user_data
    assert "Runtime image is not prepared" in user_data
    assert "\n/usr/local/sbin/install-palworld.sh\n" not in user_data


def test_health_distinguishes_a_starting_game_process_from_a_failed_service():
    operation = SCRIPT.read_text()

    assert "echo starting" in operation
    assert operation.index("systemctl is-active --quiet palworld.service") < operation.index(
        "echo starting"
    )
    assert operation.index("echo starting") < operation.index("echo unhealthy")


def test_bootstrap_failure_reports_a_bounded_diagnostic_tail():
    operation = SCRIPT.read_text()
    user_data = USER_DATA.read_text()

    assert "bootstrap-error" in user_data
    assert "bootstrap-error" in operation
    assert "tail -n 80 /var/log/palworld-user-data.log" in operation
    assert "tail -c 12000" in operation
    assert operation.index("bootstrap-error") < operation.index("exit 70")
