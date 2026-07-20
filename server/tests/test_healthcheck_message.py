import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HEALTHCHECK = PROJECT_ROOT / "server" / "healthcheck.sh"


def test_ready_notification_uses_discord_markdown_and_real_newlines() -> None:
    script = HEALTHCHECK.read_text(encoding="utf-8")
    common_source = "source /usr/local/lib/palworld/palworld-common.sh"
    fake_common = r"""
load_palworld_config() {
  HEALTHCHECK_TIMEOUT_MINUTES=1
  PALWORLD_PORT=8211
  AUTOSTOP_IDLE_MINUTES=20
}
publish_status() { :; }
palworld_api() { return 0; }
palworld_player_count() { printf '0'; }
current_public_ipv4() { printf '100.59.24.135'; }
discord_webhook_send() { printf '%s' "$1"; }
palworld_log() { :; }
rm() { :; }
touch() { :; }
chown() { :; }
"""
    assert common_source in script

    completed = subprocess.run(
        ["bash"],
        input=script.replace(common_source, fake_common),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert r"\n" not in completed.stdout
    assert completed.stdout == (
        "🟢 **Servidor Palworld disponível!**\n\n"
        "🎮 **Endereço para conectar**\n"
        "`100.59.24.135:8211`\n\n"
        "_Desligamento automático após 20 minutos sem jogadores._"
    )
