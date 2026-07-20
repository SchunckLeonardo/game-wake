"""Construcao de respostas compativeis com Discord Interactions."""

import json
from typing import Any

DISCORD_PONG = 1
DISCORD_CHANNEL_MESSAGE = 4
EPHEMERAL_FLAG = 1 << 6


def http_json(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json; charset=utf-8"},
        "body": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    }


def pong() -> dict[str, Any]:
    return http_json(200, {"type": DISCORD_PONG})


def message(content: str, *, ephemeral: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {"content": content, "allowed_mentions": {"parse": []}}
    if ephemeral:
        data["flags"] = EPHEMERAL_FLAG
    return http_json(200, {"type": DISCORD_CHANNEL_MESSAGE, "data": data})


def plain_error(status_code: int, message_text: str) -> dict[str, Any]:
    return http_json(status_code, {"error": message_text})
