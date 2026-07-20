#!/usr/bin/env python3
"""Human-friendly configuration interface for Palworld server settings."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.palworld_settings_catalog import (
    FIELDS,
    FIELDS_BY_KEY,
    SCHEMA_VERSION,
    SECTIONS,
    SettingField,
    SettingsValidationError,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "palworld-settings.json"
DEFAULT_TEMPLATE_PATH = PROJECT_ROOT / "config" / "palworld-settings.json.example"
LEGACY_TFVARS_KEYS = {
    "palworld_server_name": "server_name",
    "palworld_server_description": "server_description",
    "palworld_max_players": "max_players",
    "palworld_exp_rate": "exp_rate",
    "palworld_collection_drop_rate": "collection_drop_rate",
    "palworld_spawn_rate": "pal_spawn_rate",
    "palworld_death_penalty": "death_penalty",
    "palworld_pal_damage_attack_rate": "pal_damage_attack_rate",
    "palworld_pal_damage_defense_rate": "pal_damage_defense_rate",
    "palworld_player_damage_attack_rate": "player_damage_attack_rate",
    "palworld_player_damage_defense_rate": "player_damage_defense_rate",
    "palworld_pal_stamina_decrease_rate": "pal_stamina_decrease_rate",
    "palworld_player_stamina_decrease_rate": "player_stamina_decrease_rate",
    "palworld_item_weight_rate": "item_weight_rate",
}


@dataclass(frozen=True)
class SettingChange:
    key: str
    label: str
    before: str | int | float
    after: str | int | float


def _validate_document(raw_document: object) -> dict[str, Any]:
    if not isinstance(raw_document, dict):
        raise SettingsValidationError("settings file must contain a JSON object")
    if raw_document.get("schema_version") != SCHEMA_VERSION:
        raise SettingsValidationError(f"schema_version must be {SCHEMA_VERSION}")

    raw_settings = raw_document.get("settings")
    if not isinstance(raw_settings, dict):
        raise SettingsValidationError("settings must be a JSON object")

    expected = set(FIELDS_BY_KEY)
    actual = set(raw_settings)
    missing = sorted(expected - actual)
    if missing:
        raise SettingsValidationError(f"missing settings: {', '.join(missing)}")
    extra = sorted(actual - expected)
    if extra:
        raise SettingsValidationError(f"unknown settings: {', '.join(extra)}")

    normalized = {field.key: field.parse(raw_settings[field.key]) for field in FIELDS}
    return {"schema_version": SCHEMA_VERSION, "settings": normalized}


def _display_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _read_legacy_tfvars(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}

    updates: dict[str, object] = {}
    assignment_pattern = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.+?)\s*$")
    decoder = json.JSONDecoder()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = assignment_pattern.match(line)
        if not match or match.group(1) not in LEGACY_TFVARS_KEYS:
            continue
        raw_value = match.group(2)
        try:
            value, end = decoder.raw_decode(raw_value)
        except json.JSONDecodeError as error:
            raise SettingsValidationError(
                f"could not migrate {match.group(1)} from {path}"
            ) from error
        if raw_value[end:].strip() and not raw_value[end:].lstrip().startswith("#"):
            raise SettingsValidationError(f"could not migrate {match.group(1)} from {path}")
        updates[LEGACY_TFVARS_KEYS[match.group(1)]] = value
    return updates


class SettingsDocument:
    """Validated, canonical Palworld settings document."""

    def __init__(self, path: Path, document: object):
        self.path = path
        self._document = _validate_document(document)

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        template_path: Path | None = None,
        legacy_tfvars_path: Path | None = None,
    ) -> SettingsDocument:
        path = path.expanduser().resolve()
        created = False
        if not path.exists():
            if template_path is None:
                raise SettingsValidationError(
                    f"settings file not found: {path}. Run './palworld settings' to create it"
                )
            template_path = template_path.expanduser().resolve()
            if not template_path.is_file():
                raise SettingsValidationError(f"settings template not found: {template_path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(template_path, path)
            os.chmod(path, 0o600)
            created = True

        try:
            raw_document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise SettingsValidationError(
                f"invalid JSON in {path}: line {error.lineno}, column {error.colno}"
            ) from error
        document = cls(path, raw_document)
        if created and legacy_tfvars_path is not None:
            legacy_updates = _read_legacy_tfvars(legacy_tfvars_path.expanduser().resolve())
            if legacy_updates:
                document.update(legacy_updates)
                document.save()
        return document

    @property
    def values(self) -> Mapping[str, str | int | float]:
        return dict(self._document["settings"])

    def copy(self) -> SettingsDocument:
        return SettingsDocument(self.path, json.loads(json.dumps(self._document)))

    def update(self, updates: Mapping[str, object]) -> list[SettingChange]:
        unknown = sorted(set(updates) - set(FIELDS_BY_KEY))
        if unknown:
            raise SettingsValidationError(f"unknown setting: {', '.join(unknown)}")

        candidate = dict(self._document["settings"])
        changes: list[SettingChange] = []
        for key, raw_value in updates.items():
            field = FIELDS_BY_KEY[key]
            parsed = field.parse(raw_value)
            before = candidate[key]
            if before != parsed:
                candidate[key] = parsed
                changes.append(SettingChange(key, field.label, before, parsed))

        self._document = _validate_document(
            {"schema_version": SCHEMA_VERSION, "settings": candidate}
        )
        return changes

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_name(f".{self.path.name}.tmp")
        serialized = json.dumps(self._document, indent=2, ensure_ascii=False) + "\n"
        temporary_path.write_text(serialized, encoding="utf-8")
        os.chmod(temporary_path, 0o600)
        temporary_path.replace(self.path)

    def summary_lines(self, *, section: str | None = None) -> list[str]:
        lines: list[str] = []
        for current_section in SECTIONS:
            if section is not None and current_section != section:
                continue
            lines.append(current_section)
            for field in FIELDS:
                if field.section == current_section:
                    lines.append(
                        f"  {field.label}: {_display_value(self._document['settings'][field.key])}"
                    )
        return lines


def _emit_lines(lines: Iterable[str], output_fn: Callable[[str], None]) -> None:
    for line in lines:
        output_fn(line)


def _prompt_field(
    document: SettingsDocument,
    field: SettingField,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> SettingChange | None:
    current = document.values[field.key]
    while True:
        raw_value = input_fn(f"{field.label} [{_display_value(current)}]: ")
        if not raw_value.strip():
            return None
        try:
            changes = document.update({field.key: raw_value})
            return changes[0] if changes else None
        except SettingsValidationError as error:
            output_fn(f"Invalid value: {error}")


def _interactive_edit(
    document: SettingsDocument,
    *,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> bool:
    working = document.copy()
    changes_by_key: dict[str, SettingChange] = {}

    while True:
        output_fn("")
        output_fn("Palworld settings")
        for index, section in enumerate(SECTIONS, start=1):
            output_fn(f"  {index}. {section}")
        output_fn(f"  {len(SECTIONS) + 1}. Review and save")
        output_fn("  0. Cancel")
        choice = input_fn("Choose a category: ").strip()

        if choice == "0":
            output_fn("No settings were saved.")
            return False
        if choice == str(len(SECTIONS) + 1):
            if not changes_by_key:
                output_fn("No changes to save.")
                return False
            output_fn("")
            output_fn("Pending changes")
            for change in changes_by_key.values():
                output_fn(
                    f"  {change.label}: {_display_value(change.before)} -> "
                    f"{_display_value(change.after)}"
                )
            confirmation = input_fn("Save these changes? [y/N]: ").strip().casefold()
            if confirmation not in {"y", "yes"}:
                output_fn("No settings were saved.")
                return False
            document._document = working._document
            document.save()
            output_fn(f"Settings saved to {document.path}")
            return True

        try:
            section = SECTIONS[int(choice) - 1]
        except (ValueError, IndexError):
            output_fn("Choose one of the listed options.")
            continue

        output_fn("")
        output_fn(section)
        for field in FIELDS:
            if field.section != section:
                continue
            change = _prompt_field(working, field, input_fn, output_fn)
            if change:
                original = changes_by_key.get(change.key)
                changes_by_key[change.key] = SettingChange(
                    change.key,
                    change.label,
                    original.before if original else change.before,
                    change.after,
                )


def _run_passthrough(command: Sequence[str]) -> int:
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return completed.returncode


def _run_capture(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _terraform_output(name: str) -> str:
    completed = _run_capture(["terraform", "-chdir=terraform", "output", "-raw", name])
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"could not read Terraform output {name}")
    return completed.stdout.strip()


def _activate_when_empty(output_fn: Callable[[str], None]) -> int:
    instance_id = _terraform_output("instance_id")
    region = _terraform_output("aws_region")
    state_result = _run_capture(
        [
            "aws",
            "ec2",
            "describe-instances",
            "--region",
            region,
            "--instance-ids",
            instance_id,
            "--query",
            "Reservations[0].Instances[0].State.Name",
            "--output",
            "text",
        ]
    )
    if state_result.returncode != 0:
        raise RuntimeError(state_result.stderr.strip() or "could not read the EC2 state")
    state = state_result.stdout.strip()
    if state == "stopped":
        output_fn("Settings published. They will be activated on the next server start.")
        return 0
    if state in {"pending", "stopping"}:
        output_fn(
            f"Settings published while the instance is {state}. "
            "They will be activated on the next safe server start."
        )
        return 0
    if state != "running":
        output_fn(f"Settings published, but the instance state is {state}; activation was skipped.")
        return 0

    remote_script = "\n".join(
        [
            "set -Eeuo pipefail",
            "sudo /usr/local/sbin/stop-palworld.sh",
            "sudo systemctl start palworld.service",
            "sudo systemctl restart palworld-notify.service",
        ]
    )
    send_result = _run_capture(
        [
            "aws",
            "ssm",
            "send-command",
            "--region",
            region,
            "--instance-ids",
            instance_id,
            "--document-name",
            "AWS-RunShellScript",
            "--comment",
            "Apply Palworld settings after a safe player check",
            "--parameters",
            json.dumps({"commands": [remote_script]}),
            "--query",
            "Command.CommandId",
            "--output",
            "text",
        ]
    )
    if send_result.returncode != 0:
        raise RuntimeError(send_result.stderr.strip() or "could not send the activation command")

    command_id = send_result.stdout.strip()
    output_fn(f"Waiting for safe activation command {command_id}...")
    deadline = time.monotonic() + 360
    while time.monotonic() < deadline:
        invocation = _run_capture(
            [
                "aws",
                "ssm",
                "get-command-invocation",
                "--region",
                region,
                "--command-id",
                command_id,
                "--instance-id",
                instance_id,
                "--output",
                "json",
            ]
        )
        if invocation.returncode != 0:
            if "InvocationDoesNotExist" in invocation.stderr:
                time.sleep(2)
                continue
            raise RuntimeError(invocation.stderr.strip() or "could not read the activation result")
        payload = json.loads(invocation.stdout)
        status = payload.get("Status")
        if status == "Success":
            output_fn("Settings activated after a safe save, backup, and restart.")
            return 0
        if status in {"Cancelled", "TimedOut", "Failed", "Cancelling"}:
            details = (
                payload.get("StandardErrorContent") or payload.get("StandardOutputContent") or ""
            ).strip()
            output_fn(
                f"Settings were published, but immediate activation did not complete ({status})."
            )
            if details:
                output_fn(details)
            output_fn(
                "No player was treated as disconnected; the change remains pending "
                "for a safe start."
            )
            return 10
        time.sleep(2)
    raise RuntimeError("timed out waiting for the safe activation command")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="./palworld settings",
        description="Interactively edit Palworld server settings and apply them safely.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path(os.environ.get("PALWORLD_SETTINGS_FILE", DEFAULT_SETTINGS_PATH)),
        help=argparse.SUPPRESS,
    )
    subparsers = parser.add_subparsers(dest="action", metavar="{edit,show,validate,plan,apply}")
    subparsers.add_parser("edit", help="open the interactive settings assistant")
    subparsers.add_parser("show", help="show the current settings")
    subparsers.add_parser("validate", help="validate the settings file")
    subparsers.add_parser("plan", help="validate settings and generate a Terraform plan")
    apply_parser = subparsers.add_parser("apply", help="apply settings and activate them safely")
    apply_parser.add_argument(
        "--activate",
        choices=("when-empty", "next-start"),
        default="when-empty",
        help="activate now only when no players are connected, or wait for the next start",
    )
    return parser


def run_settings_cli(
    argv: Sequence[str] | None = None,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    action = args.action or "edit"

    try:
        document = SettingsDocument.load(
            args.file,
            template_path=DEFAULT_TEMPLATE_PATH,
            legacy_tfvars_path=PROJECT_ROOT / "terraform" / "terraform.tfvars",
        )
        if action == "show":
            _emit_lines(document.summary_lines(), output_fn)
            return 0
        if action == "validate":
            output_fn(f"Settings are valid: {document.path}")
            return 0
        if action == "edit":
            _interactive_edit(document, input_fn=input_fn, output_fn=output_fn)
            return 0
        if action == "plan":
            output_fn(f"Settings are valid: {document.path}")
            return _run_passthrough([str(PROJECT_ROOT / "scripts" / "deploy.sh"), "plan"])
        if action == "apply":
            output_fn(f"Settings are valid: {document.path}")
            exit_code = _run_passthrough([str(PROJECT_ROOT / "scripts" / "deploy.sh"), "apply"])
            if exit_code != 0:
                return exit_code
            if args.activate == "next-start":
                output_fn(
                    "Settings published. Activation was deferred until the next server start."
                )
                return 0
            return _activate_when_empty(output_fn)
    except (OSError, RuntimeError, SettingsValidationError, json.JSONDecodeError) as error:
        output_fn(f"Error: {error}")
        return 2

    parser.error(f"unsupported action: {action}")
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    return run_settings_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
