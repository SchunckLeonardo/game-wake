from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from functools import lru_cache
from types import ModuleType
from typing import Any


def _type_name(value_type: type[object]) -> str:
    return f"{value_type.__module__}.{value_type.__qualname__}"


@lru_cache(maxsize=1)
def _domain_types() -> dict[str, type[object]]:
    from gamewake.accounts import model as account_model
    from gamewake.accounts import policy as account_policy
    from gamewake.accounts import repository as account_repository
    from gamewake.accounts import security as account_security
    from gamewake.billing import model as billing_model
    from gamewake.worlds import model as world_model
    from gamewake.worlds import storage as world_storage

    modules: tuple[ModuleType, ...] = (
        account_model,
        account_policy,
        account_repository,
        account_security,
        billing_model,
        world_model,
        world_storage,
    )
    allowed: dict[str, type[object]] = {}
    for module in modules:
        for candidate in vars(module).values():
            if not isinstance(candidate, type):
                continue
            if is_dataclass(candidate) or issubclass(candidate, Enum):
                allowed[_type_name(candidate)] = candidate
    return allowed


def _encode(value: object) -> object:
    if isinstance(value, Enum):
        return {"__enum__": _type_name(type(value)), "value": value.value}
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Decimal):
        return {"__decimal__": str(value)}
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, date):
        return {"__date__": value.isoformat()}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "__type__": _type_name(type(value)),
            "fields": {field.name: _encode(getattr(value, field.name)) for field in fields(value)},
        }
    if isinstance(value, tuple):
        return {"__tuple__": [_encode(item) for item in value]}
    if isinstance(value, frozenset):
        return {"__frozenset__": [_encode(item) for item in sorted(value, key=repr)]}
    if isinstance(value, list):
        return {"__list__": [_encode(item) for item in value]}
    if isinstance(value, dict):
        return {"__map__": [[_encode(key), _encode(item)] for key, item in value.items()]}
    raise TypeError(f"unsupported persisted domain value: {type(value).__name__}")


def encode_domain(value: object) -> str:
    return json.dumps(_encode(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _registered(name: str) -> type[object]:
    value_type = _domain_types().get(name)
    if value_type is None:
        raise ValueError(f"unknown persisted domain type: {name}")
    return value_type


def _decode(value: object) -> Any:
    if not isinstance(value, dict):
        return value
    if "__decimal__" in value:
        return Decimal(str(value["__decimal__"]))
    if "__datetime__" in value:
        return datetime.fromisoformat(str(value["__datetime__"]))
    if "__date__" in value:
        return date.fromisoformat(str(value["__date__"]))
    if "__enum__" in value:
        enum_type = _registered(str(value["__enum__"]))
        if not issubclass(enum_type, Enum):
            raise ValueError(f"persisted type is not an enum: {_type_name(enum_type)}")
        return enum_type(value["value"])
    if "__type__" in value:
        value_type = _registered(str(value["__type__"]))
        if not is_dataclass(value_type):
            raise ValueError(f"persisted type is not a dataclass: {_type_name(value_type)}")
        raw_fields = value.get("fields")
        if not isinstance(raw_fields, dict):
            raise ValueError("persisted dataclass fields must be an object")
        return value_type(**{name: _decode(item) for name, item in raw_fields.items()})
    if "__tuple__" in value:
        return tuple(_decode(item) for item in value["__tuple__"])
    if "__frozenset__" in value:
        return frozenset(_decode(item) for item in value["__frozenset__"])
    if "__list__" in value:
        return [_decode(item) for item in value["__list__"]]
    if "__map__" in value:
        return {_decode(key): _decode(item) for key, item in value["__map__"]}
    raise ValueError("unknown persisted domain object")


def decode_domain[T](payload: str, expected_type: type[T] | None = None) -> T | Any:
    value = _decode(json.loads(payload))
    if expected_type is not None and not isinstance(value, expected_type):
        raise ValueError(
            f"persisted value must be {expected_type.__name__}, got {type(value).__name__}"
        )
    return value
