"""Machine-readable command descriptions and capability reporting."""

import dataclasses
import importlib.util
import os
import types
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Union, cast, get_args, get_origin, get_type_hints

import rglob
from rglob.agent import _models
from rglob.agent._models import (
    AGENT_API_VERSION,
    SCHEMA_VERSION,
    CapabilityReport,
    ErrorCode,
    ErrorInfo,
    JsonValue,
    PredicateStatus,
    error_envelope,
    to_json_dict,
)

JSON_SCHEMA_VERSION = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_BASE_ID = f"https://chris-piekarski.github.io/python-rglob/schemas/{SCHEMA_VERSION}"

PUBLIC_TYPES: tuple[type[object], ...] = (
    _models.FileMatch,
    _models.LineMatch,
    _models.Stats,
    _models.Duplicate,
    _models.ErrorInfo,
    _models.ErrorCode,
    _models.FileSearchResult,
    _models.LineSearchResult,
    _models.DuplicateSearchResult,
    _models.CapabilityReport,
    _models.WalkOptions,
    _models.GrepOptions,
    _models.CountOptions,
)

COMMAND_SCHEMAS: dict[str, tuple[str, str]] = {
    "find": ("walk_options", "file_search_result"),
    "grep": ("grep_options", "line_search_result"),
    "count": ("count_options", "stats"),
    "lcount": ("count_options", "stats"),
    "tsize": ("count_options", "stats"),
    "stats": ("count_options", "stats"),
    "tree": ("walk_options", "file_search_result"),
    "top": ("walk_options", "file_search_result"),
    "dupes": ("walk_options", "duplicate_search_result"),
}

COMMAND_ARGUMENTS: dict[str, list[dict[str, object]]] = {
    "find": [{"name": "patterns", "type": "list[str]", "required": True}],
    "grep": [{"name": "pattern", "type": "str", "required": True}],
    "count": [{"name": "patterns", "type": "list[str]", "required": True}],
    "lcount": [{"name": "pattern", "type": "str", "required": True}],
    "tsize": [{"name": "pattern", "type": "str", "required": True}],
    "stats": [{"name": "pattern", "type": "str", "required": False, "default": "*"}],
    "tree": [{"name": "pattern", "type": "str", "required": False, "default": "*"}],
    "top": [{"name": "pattern", "type": "str", "required": False, "default": "*"}],
    "dupes": [{"name": "pattern", "type": "str", "required": False, "default": "*"}],
}

COMMON_OPTIONS: list[dict[str, object]] = [
    {"name": "base", "type": "Path", "default": "."},
    {"name": "exclude", "type": "list[str]", "default": []},
    {"name": "max_depth", "type": "int | null", "default": None},
    {"name": "hidden", "type": "bool", "default": False},
    {"name": "follow_symlinks", "type": "bool", "default": False},
    {"name": "case_sensitive", "type": "bool | null", "default": None},
    {"name": "respect_gitignore", "type": "bool", "default": False},
    {"name": "limit", "type": "int | null", "default": None},
    {"name": "max_bytes", "type": "int | null", "default": None},
    {"name": "max_file_size", "type": "int | null", "default": None},
    {"name": "timeout_seconds", "type": "float | null", "default": None},
    {"name": "newer_than_file", "type": "Path | null", "default": None},
    {"name": "perm", "type": "int | str | null", "default": None},
    {"name": "uid", "type": "int | null", "default": None},
    {"name": "gid", "type": "int | null", "default": None},
]

COMMAND_SUMMARIES: dict[str, str] = {
    "find": "List paths matching one or more glob patterns.",
    "grep": "Search file contents for a regex or fixed string.",
    "count": "Count matching files, lines, and bytes.",
    "lcount": "Legacy line-count command.",
    "tsize": "Legacy total-size command.",
    "stats": "Summarise a glob result.",
    "tree": "Render a tree of matching paths.",
    "top": "Show largest matching files.",
    "dupes": "Find duplicate file groups.",
}


def _snake_case(name: str) -> str:
    """Convert a class name to a stable schema stem."""
    out: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index > 0:
            out.append("_")
        out.append(char.lower())
    return "".join(out)


def _is_union(origin: object) -> bool:
    """Return true when a typing origin represents a union."""
    return origin in (Union, types.UnionType)


def _schema_for_literal(args: tuple[object, ...]) -> dict[str, object]:
    """Build a schema for a Literal type."""
    return {"enum": sorted(args, key=str)}


def _schema_for_enum(enum_type: type[StrEnum]) -> dict[str, object]:
    """Build a schema for a StrEnum."""
    return {"type": "string", "enum": [item.value for item in enum_type]}


def _schema_for_type(tp: object) -> dict[str, object]:
    """Translate a Python annotation into a JSON Schema fragment."""
    origin = get_origin(tp)
    args = get_args(tp)

    if origin is Literal:
        return _schema_for_literal(args)
    if _is_union(origin):
        return {"anyOf": [_schema_for_type(arg) for arg in args]}
    if origin is list:
        item_type = args[0] if args else Any
        return {"type": "array", "items": _schema_for_type(item_type)}
    if origin is dict:
        value_type = args[1] if len(args) == 2 else Any
        return {"type": "object", "additionalProperties": _schema_for_type(value_type)}

    if tp is Any:
        return {}
    if tp is None or tp is type(None):
        return {"type": "null"}
    if tp is str:
        return {"type": "string"}
    if tp is int:
        return {"type": "integer"}
    if tp is float:
        return {"type": "number"}
    if tp is bool:
        return {"type": "boolean"}
    if tp is Path:
        return {"type": "string", "format": "path"}
    if tp is datetime:
        return {"type": "string", "format": "date-time"}
    if tp is timedelta:
        return {"type": "string", "format": "duration"}
    if isinstance(tp, type) and issubclass(tp, StrEnum):
        return {"$ref": f"#/$defs/{tp.__name__}"}
    if isinstance(tp, type) and dataclasses.is_dataclass(tp):
        return {"$ref": f"#/$defs/{tp.__name__}"}

    if tp is object:
        return {"type": "string"}

    raise NotImplementedError(
        f"unhandled type in schema generator: {tp!r} (origin={origin}, args={args})"
    )


def _field_default(schema: dict[str, object], field: dataclasses.Field[object]) -> None:
    """Attach a JSON-safe default to a property schema when one exists."""
    if field.default is not dataclasses.MISSING:
        schema["default"] = to_json_dict(field.default)
        return

    default_factory: Callable[[], object] | object = field.default_factory
    if default_factory is dataclasses.MISSING:
        return
    schema["default"] = to_json_dict(cast("Callable[[], object]", default_factory)())


def _schema_for_dataclass(cls: type[object]) -> dict[str, object]:
    """Build an object schema for a dataclass."""
    hints = get_type_hints(cls, include_extras=True)
    properties: dict[str, object] = {}
    required: list[str] = []

    for field in dataclasses.fields(cast("Any", cls)):
        prop = _schema_for_type(hints[field.name])
        _field_default(prop, field)
        properties[field.name] = prop
        if field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING:
            required.append(field.name)

    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def _definitions(root: type[object]) -> dict[str, object]:
    """Return definitions needed by generated schemas."""
    defs: dict[str, object] = {"ErrorCode": _schema_for_enum(_models.ErrorCode)}
    for typ in PUBLIC_TYPES:
        if typ is root or typ is _models.ErrorCode:
            continue
        defs[typ.__name__] = _schema_for_dataclass(typ)
    return defs


def _schema_for_public_type(typ: type[object]) -> dict[str, object]:
    """Build the complete schema document for a public contract type."""
    schema_name = _snake_case(typ.__name__)
    body = _schema_for_enum(typ) if issubclass(typ, StrEnum) else _schema_for_dataclass(typ)

    document: dict[str, object] = {
        "$schema": JSON_SCHEMA_VERSION,
        "$id": f"{SCHEMA_BASE_ID}/{schema_name}.json",
        "title": typ.__name__,
        "version": SCHEMA_VERSION,
        **body,
    }
    document["$defs"] = _definitions(typ)
    return document


def _schema_types() -> dict[str, type[object]]:
    """Return public schema types keyed by stable stem."""
    return {_snake_case(typ.__name__): typ for typ in PUBLIC_TYPES}


def schema_for(name: str) -> dict[str, Any]:
    """Generate a public JSON Schema document by stable stem."""
    try:
        typ = _schema_types()[name]
    except KeyError as exc:
        raise ValueError(f"unknown schema: {name}") from exc
    return cast("dict[str, Any]", _schema_for_public_type(typ))


def all_schemas() -> dict[str, dict[str, Any]]:
    """Generate every public JSON Schema document keyed by stable stem."""
    return {name: schema_for(name) for name in sorted(_schema_types())}


def command_schema(name: str) -> dict[str, Any]:
    """Return input and output schemas for a command."""
    try:
        input_name, output_name = COMMAND_SCHEMAS[name]
    except KeyError as exc:
        raise ValueError(f"unknown subcommand: {name}") from exc
    return {
        "input": schema_for(input_name),
        "output": schema_for(output_name),
    }


def describe_command(name: str) -> dict[str, Any]:
    """Return a JSON-serializable command manifest."""
    schemas = command_schema(name)
    return {
        "name": name,
        "summary": COMMAND_SUMMARIES[name],
        "agent_api_version": AGENT_API_VERSION,
        "schema_version": SCHEMA_VERSION,
        "arguments": COMMAND_ARGUMENTS[name],
        "options": COMMON_OPTIONS,
        "schemas": schemas,
        "default_limits": {
            "limit": None,
            "max_bytes": None,
            "max_file_size": None,
            "timeout_seconds": None,
        },
        "supported_extras": list(capability_report().extras.keys()),
    }


def capability_report() -> CapabilityReport:
    """Report installed optional features and platform predicate support."""
    has_gitignore = importlib.util.find_spec("pathspec") is not None
    has_ext = importlib.util.find_spec("xxhash") is not None
    has_mcp = importlib.util.find_spec("mcp") is not None
    posix_status: PredicateStatus = "POSIX-only" if os.name == "posix" else "unsupported"
    return CapabilityReport(
        agent_api_version=AGENT_API_VERSION,
        schema_version=SCHEMA_VERSION,
        package_version=rglob.__version__,
        extras={"mcp": has_mcp, "gitignore": has_gitignore, "ext": has_ext},
        predicates={
            "perm": "supported",
            "uid": posix_status,
            "gid": posix_status,
            "newer_than": "supported",
            "older_than": "supported",
            "respect_gitignore": "supported" if has_gitignore else "unsupported",
        },
        mcp={"available": has_mcp, "transport": "stdio"},
    )


def unknown_command_envelope(name: str) -> dict[str, JsonValue]:
    """Return a stable error envelope for an unknown command name."""
    return error_envelope(
        ErrorInfo(
            code=ErrorCode.BAD_PREDICATE,
            message=f"unknown subcommand: {name}",
            path=None,
        )
    )


def json_ready(value: object) -> JsonValue:
    """Return a JSON-ready representation for introspection payloads."""
    return to_json_dict(value)
