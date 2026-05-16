"""Internal helpers shared by agent-aware CLI and future public APIs."""

import json
import stat
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from rglob._filters import Kind
from rglob.agent._models import ErrorCode, ErrorInfo, FileMatch, FileSearchResult, to_json_dict


def _absolute(path: Path) -> Path:
    """Return an absolute normalized path without requiring the path to exist."""
    return path.expanduser().resolve(strict=False)


def _lexical_absolute(path: Path) -> Path:
    """Return an absolute path without following symlink targets."""
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return Path.cwd() / expanded


def _relative_path(path: Path, base: Path) -> str:
    """Return a POSIX-style path relative to base."""
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.name


def _error_from_oserror(exc: OSError, path: Path) -> ErrorInfo:
    """Convert an OSError into a stable agent error."""
    code = ErrorCode.PERM if isinstance(exc, PermissionError) else ErrorCode.UNREADABLE
    return ErrorInfo(code=code, message=str(exc), path=path)


def deadline_from_timeout(timeout_seconds: float | None) -> float | None:
    """Return a monotonic deadline for a cooperative timeout."""
    if timeout_seconds is None:
        return None
    if timeout_seconds < 0.1:
        raise ValueError("timeout_seconds must be at least 0.1")
    return time.monotonic() + timeout_seconds


def check_timeout(deadline: float | None) -> None:
    """Raise TimeoutError when a cooperative deadline expires."""
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("search timed out")


def timeout_error(path: Path | None = None) -> ErrorInfo:
    """Build the stable timeout ErrorInfo."""
    return ErrorInfo(ErrorCode.TIMEOUT, "search timed out", path)


def _strict_base_error(path: Path, base: Path) -> ErrorInfo:
    """Build an ErrorInfo for a strict-base containment violation."""
    return ErrorInfo(
        ErrorCode.PERM,
        f"path escapes strict base {base}",
        _lexical_absolute(path),
    )


def _is_contained(path: Path, base: Path) -> bool:
    """Return true when a resolved path is within the resolved base."""
    resolved_base = _absolute(base)
    resolved_path = _absolute(path)
    try:
        resolved_path.relative_to(resolved_base)
    except ValueError:
        return False
    return True


def _path_kinds(path: Path) -> list[Kind]:
    """Return kind tags for a path."""
    kinds: list[Kind] = []
    try:
        if path.is_symlink():
            kinds.append("l")
        if path.is_file():
            kinds.append("f")
        if path.is_dir():
            kinds.append("d")
        mode = path.stat().st_mode
        if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            kinds.append("x")
    except OSError:
        return kinds
    return kinds


def file_match(path: Path, base: Path, *, include_errors: bool) -> FileMatch:
    """Convert a Path into the stable FileMatch shape."""
    absolute_path = _absolute(path)
    absolute_base = _absolute(base)
    errors: list[ErrorInfo] = []
    size = 0
    mtime = datetime.fromtimestamp(0, tz=UTC)

    try:
        file_stat = path.stat()
        size = file_stat.st_size if path.is_file() else 0
        mtime = datetime.fromtimestamp(file_stat.st_mtime, tz=UTC)
    except OSError as exc:
        if include_errors:
            errors.append(_error_from_oserror(exc, absolute_path))

    return FileMatch(
        path=absolute_path,
        relative_path=_relative_path(absolute_path, absolute_base),
        size=size,
        mtime=mtime,
        kinds=_path_kinds(path),
        errors=errors,
    )


def collect_file_search(
    paths: Iterable[Path],
    *,
    base: Path,
    limit: int | None,
    max_bytes: int | None,
    include_errors: bool,
    timeout_seconds: float | None = None,
    strict_base: bool = False,
) -> FileSearchResult:
    """Collect path matches into a FileSearchResult with truncation metadata."""
    results: list[FileMatch] = []
    errors: list[ErrorInfo] = []
    total = 0
    bytes_read = 0
    truncated = False
    truncated_reason: str | None = None
    deadline = deadline_from_timeout(timeout_seconds)

    for path in paths:
        try:
            check_timeout(deadline)
        except TimeoutError:
            truncated = True
            truncated_reason = "timeout"
            if include_errors:
                errors.append(timeout_error())
            break
        total += 1
        if limit is not None and len(results) >= limit:
            truncated = True
            truncated_reason = "limit"
            break

        if strict_base and not _is_contained(path, base):
            if include_errors:
                errors.append(_strict_base_error(path, _absolute(base)))
            continue

        match = file_match(path, base, include_errors=include_errors)
        record_size = len(json.dumps(to_json_dict(match), separators=(",", ":")).encode())
        if max_bytes is not None and bytes_read + record_size > max_bytes:
            truncated = True
            truncated_reason = "max_bytes"
            break

        results.append(match)
        errors.extend(match.errors)
        bytes_read += record_size

    return FileSearchResult(
        results=results,
        truncated=truncated,
        total_files_searched=total,
        bytes_read=bytes_read,
        errors=errors,
        truncated_reason=truncated_reason,
    )
