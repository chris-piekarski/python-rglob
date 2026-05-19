"""Structured count helpers for agent-aware commands."""

from pathlib import Path

from rglob import find as _find
from rglob.agent._models import CountOptions, ErrorCode, ErrorInfo, Stats
from rglob.agent._runtime import (
    _absolute,
    _is_contained,
    _strict_base_error,
    check_timeout,
    deadline_from_timeout,
    timeout_error,
)


def _countable(line: str, opts: CountOptions) -> bool:
    """Return true when a line should be counted."""
    stripped = line.strip()
    if opts.no_empty and not stripped:
        return False
    return not (opts.no_comments and stripped.startswith("#"))


def _iter_count_files(opts: CountOptions) -> list[Path]:
    """Return candidate files for count operations."""
    return list(
        _find(
            opts.base,
            opts.patterns,
            exclude=opts.exclude,
            max_depth=opts.max_depth,
            hidden=opts.hidden,
            follow_symlinks=opts.follow_symlinks,
            case_sensitive=opts.case_sensitive,
            sort=opts.sort,
            on_error="ignore",
            kinds=opts.kinds,
            min_size=opts.min_size,
            max_size=opts.max_file_size or opts.max_size,
            newer_than=opts.newer_than,
            older_than=opts.older_than,
            newer_than_file=opts.newer_than_file,
            perm=opts.perm,
            uid=opts.uid,
            gid=opts.gid,
            respect_gitignore=opts.respect_gitignore,
        )
    )


def count_all(opts: CountOptions) -> Stats:
    """Count files, lines, and bytes using CountOptions."""
    files = _iter_count_files(opts)
    errors: list[ErrorInfo] = []
    total_lines = 0
    total_bytes = 0
    truncated = False
    truncated_reason: str | None = None
    counted_files = 0
    deadline = deadline_from_timeout(opts.timeout_seconds)

    for path in files:
        try:
            check_timeout(deadline)
        except TimeoutError:
            truncated = True
            truncated_reason = "timeout"
            if opts.include_errors:
                errors.append(timeout_error())
            break

        if opts.limit is not None and counted_files >= opts.limit:
            truncated = True
            truncated_reason = "limit"
            break

        if opts.strict_base and not _is_contained(path, opts.base):
            if opts.include_errors:
                errors.append(_strict_base_error(path, _absolute(opts.base)))
            continue

        try:
            file_size = path.stat().st_size
        except OSError as exc:
            if opts.include_errors:
                errors.append(ErrorInfo(ErrorCode.UNREADABLE, str(exc), _absolute(path)))
            continue

        if opts.max_bytes is not None and total_bytes + file_size > opts.max_bytes:
            truncated = True
            truncated_reason = "max_bytes"
            break

        try:
            data = path.read_bytes()
        except OSError as exc:
            if opts.include_errors:
                errors.append(ErrorInfo(ErrorCode.UNREADABLE, str(exc), _absolute(path)))
            continue

        lines = data.decode(opts.encoding, errors="replace").splitlines()
        for line in lines:
            try:
                check_timeout(deadline)
            except TimeoutError:
                truncated = True
                truncated_reason = "timeout"
                if opts.include_errors:
                    errors.append(timeout_error(_absolute(path)))
                break
            if _countable(line, opts):
                total_lines += 1
        total_bytes += len(data)
        counted_files += 1
        if truncated:
            break

    return Stats(
        files=counted_files,
        lines=total_lines,
        bytes=total_bytes,
        total_files_searched=len(files),
        bytes_read=total_bytes,
        errors=errors,
        truncated=truncated,
        truncated_reason=truncated_reason,
    )
