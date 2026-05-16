"""Shared agent contract models and JSON serialization helpers."""

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Literal, TypeAlias

from rglob._filters import Kind

AGENT_API_VERSION = "1.0"
SCHEMA_VERSION = "1.0"

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list[object] | dict[str, object]
PredicateStatus: TypeAlias = Literal["supported", "POSIX-only", "unsupported"]


class ErrorCode(StrEnum):
    """Stable operational error codes for the v1 agent contract."""

    PERM = "PERM"
    UNREADABLE = "UNREADABLE"
    BINARY = "BINARY"
    TIMEOUT = "TIMEOUT"
    REGEX = "REGEX"
    BAD_PREDICATE = "BAD_PREDICATE"
    UNSUPPORTED_PLATFORM = "UNSUPPORTED_PLATFORM"


@dataclass(frozen=True, slots=True)
class ErrorInfo:
    """Machine-readable operational error."""

    code: ErrorCode
    message: str
    path: Path | None


@dataclass(frozen=True, slots=True)
class FileMatch:
    """A filesystem entry matched by an agent search."""

    path: Path
    relative_path: str
    size: int
    mtime: datetime
    kinds: list[Kind]
    errors: list[ErrorInfo]


@dataclass(frozen=True, slots=True)
class LineMatch:
    """A content match returned by an agent grep operation."""

    path: Path
    line_number: int
    content: str
    before: list[str]
    after: list[str]
    encoding: str


@dataclass(frozen=True, slots=True)
class Duplicate:
    """A duplicate-file group."""

    paths: list[Path]
    relative_paths: list[str]
    size: int
    digest: str | None


@dataclass(frozen=True, slots=True)
class Stats:
    """Structured count result for files, lines, and bytes."""

    files: int
    lines: int
    bytes: int
    total_files_searched: int
    bytes_read: int
    errors: list[ErrorInfo]
    truncated: bool
    truncated_reason: str | None


@dataclass(frozen=True, slots=True)
class FileSearchResult:
    """Concrete result wrapper for file searches."""

    results: list[FileMatch]
    truncated: bool
    total_files_searched: int
    bytes_read: int
    errors: list[ErrorInfo]
    truncated_reason: str | None


@dataclass(frozen=True, slots=True)
class LineSearchResult:
    """Concrete result wrapper for content searches."""

    results: list[LineMatch]
    truncated: bool
    total_files_searched: int
    bytes_read: int
    errors: list[ErrorInfo]
    truncated_reason: str | None


@dataclass(frozen=True, slots=True)
class DuplicateSearchResult:
    """Concrete result wrapper for duplicate searches."""

    results: list[Duplicate]
    truncated: bool
    total_files_searched: int
    bytes_read: int
    errors: list[ErrorInfo]
    truncated_reason: str | None


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    """Installed capabilities and version metadata."""

    agent_api_version: str
    schema_version: str
    package_version: str
    extras: dict[str, bool]
    predicates: dict[str, PredicateStatus]
    mcp: dict[str, str | bool]


@dataclass(frozen=True, slots=True)
class WalkOptions:
    """Options for agent-facing filename searches."""

    patterns: list[str] = field(default_factory=lambda: ["*"])
    base: Path = Path()
    exclude: list[str] = field(default_factory=list)
    max_depth: int | None = None
    hidden: bool = False
    kinds: list[Kind] = field(default_factory=list)
    min_size: int | float | str | None = None
    max_size: int | float | str | None = None
    newer_than: datetime | timedelta | str | None = None
    older_than: datetime | timedelta | str | None = None
    newer_than_file: Path | None = None
    perm: int | str | None = None
    uid: int | None = None
    gid: int | None = None
    limit: int | None = None
    max_bytes: int | None = None
    max_file_size: int | None = None
    timeout_seconds: float | None = None
    strict_base: bool = True
    follow_symlinks: bool = False
    respect_gitignore: bool = False
    include_errors: bool = True
    case_sensitive: bool | None = None
    sort: bool = True


@dataclass(frozen=True, slots=True)
class GrepOptions:
    """Options for agent-facing content searches."""

    pattern: str
    paths: list[str] = field(default_factory=lambda: ["*"])
    base: Path = Path()
    exclude: list[str] = field(default_factory=list)
    max_depth: int | None = None
    hidden: bool = False
    kinds: list[Kind] = field(default_factory=lambda: ["f"])
    min_size: int | float | str | None = None
    max_size: int | float | str | None = None
    newer_than: datetime | timedelta | str | None = None
    older_than: datetime | timedelta | str | None = None
    newer_than_file: Path | None = None
    perm: int | str | None = None
    uid: int | None = None
    gid: int | None = None
    limit: int | None = None
    max_bytes: int | None = None
    max_file_size: int | None = None
    timeout_seconds: float | None = None
    strict_base: bool = True
    follow_symlinks: bool = False
    respect_gitignore: bool = False
    include_errors: bool = True
    case_sensitive: bool | None = None
    sort: bool = True
    fixed_string: bool = False
    ignore_case: bool = False
    context: int = 0
    before: int = 0
    after: int = 0
    max_count: int | None = None
    word: bool = False
    invert: bool = False
    encoding: str = "utf-8"
    text: bool = False
    files_with_matches: bool = False
    count_only: bool = False


@dataclass(frozen=True, slots=True)
class CountOptions:
    """Options for agent-facing file, line, and byte counts."""

    patterns: list[str] = field(default_factory=lambda: ["*"])
    base: Path = Path()
    exclude: list[str] = field(default_factory=list)
    max_depth: int | None = None
    hidden: bool = False
    kinds: list[Kind] = field(default_factory=lambda: ["f"])
    min_size: int | float | str | None = None
    max_size: int | float | str | None = None
    newer_than: datetime | timedelta | str | None = None
    older_than: datetime | timedelta | str | None = None
    newer_than_file: Path | None = None
    perm: int | str | None = None
    uid: int | None = None
    gid: int | None = None
    limit: int | None = None
    max_bytes: int | None = None
    max_file_size: int | None = None
    timeout_seconds: float | None = None
    strict_base: bool = True
    follow_symlinks: bool = False
    respect_gitignore: bool = False
    include_errors: bool = True
    case_sensitive: bool | None = None
    sort: bool = True
    no_empty: bool = False
    no_comments: bool = False
    encoding: str = "utf-8"


def _datetime_to_wire(value: datetime) -> str:
    """Serialize a datetime as UTC ISO 8601 with a Z suffix."""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat().replace("+00:00", "Z")


def to_json_dict(value: object) -> JsonValue:
    """Convert agent dataclasses into JSON-safe built-in containers."""
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_json_dict(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return _datetime_to_wire(value)
    if isinstance(value, StrEnum):
        return str(value)
    if isinstance(value, list | tuple):
        return [to_json_dict(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_json_dict(item) for key, item in value.items()}
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def error_envelope(error: ErrorInfo) -> dict[str, JsonValue]:
    """Return the stable agent error envelope."""
    return {"ok": False, "error": to_json_dict(error)}
