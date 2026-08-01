#!/usr/bin/env python3
"""Patch selected Palworld settings while preserving the installed official defaults."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def _format_value(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        if key == "DeathPenalty":
            if value not in {"None", "Item", "ItemAndEquipment", "All"}:
                raise ValueError("unsupported DeathPenalty")
            return value
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    raise TypeError(f"unsupported setting value: {type(value).__name__}")


def render_settings(default_text: str, updates: dict[str, Any]) -> str:
    if (
        "[/Script/Pal.PalGameWorldSettings]" not in default_text
        or "OptionSettings=(" not in default_text
    ):
        raise ValueError("DefaultPalWorldSettings.ini has an unexpected format")

    rendered = default_text
    for key, value in updates.items():
        pattern = re.compile(
            rf"(?P<prefix>(?<![A-Za-z0-9_]){re.escape(key)}=)"
            r'(?P<value>"(?:\\.|[^"\\])*"|[^,)]*)'
        )
        formatted_value = _format_value(key, value)
        rendered, replacements = pattern.subn(
            lambda match, replacement=formatted_value: match.group("prefix") + replacement,
            rendered,
            count=1,
        )
        if replacements != 1:
            raise ValueError(f"setting not found exactly once in official default: {key}")
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    updates = json.load(sys.stdin)
    if not isinstance(updates, dict):
        raise ValueError("updates payload must be a JSON object")

    default_text = args.base.read_text(encoding="utf-8-sig")
    rendered = render_settings(default_text, updates)
    args.output.write_text(rendered, encoding="utf-8")
    os.chmod(args.output, 0o600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
