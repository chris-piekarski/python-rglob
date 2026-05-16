"""Stable agent-facing API for rglob."""

from collections.abc import Iterator
from pathlib import Path

from rglob.agent._introspection import all_schemas, schema_for
from rglob.agent._models import (
    AGENT_API_VERSION,
    SCHEMA_VERSION,
    CapabilityReport,
    CountOptions,
    Duplicate,
    DuplicateSearchResult,
    ErrorCode,
    ErrorInfo,
    FileMatch,
    FileSearchResult,
    GrepOptions,
    LineMatch,
    LineSearchResult,
    Stats,
    WalkOptions,
    error_envelope,
    to_json_dict,
)

__agent_api_version__ = AGENT_API_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "CapabilityReport",
    "CountOptions",
    "Duplicate",
    "DuplicateSearchResult",
    "ErrorCode",
    "ErrorInfo",
    "FileMatch",
    "FileSearchResult",
    "GrepOptions",
    "LineMatch",
    "LineSearchResult",
    "Stats",
    "WalkOptions",
    "__agent_api_version__",
    "all_schemas",
    "count",
    "error_envelope",
    "find_duplicates",
    "grep",
    "grep_all",
    "schema_for",
    "search",
    "search_all",
    "to_json_dict",
]


def _error_from_exception(exc: Exception, path: Path | None = None) -> ErrorInfo:
    """Convert an exception into the public agent error model."""
    if isinstance(exc, ValueError):
        code = ErrorCode.BAD_PREDICATE
    elif isinstance(exc, PermissionError):
        code = ErrorCode.PERM
    else:
        code = ErrorCode.UNREADABLE
    return ErrorInfo(code=code, message=str(exc), path=path)


def _iter_paths(opts: WalkOptions, *, force_files: bool = False) -> Iterator[Path]:
    """Yield filesystem paths selected by WalkOptions."""
    from rglob import find as _find
    from rglob._filters import Kind

    kinds: list[Kind] = ["f"] if force_files else opts.kinds
    return _find(
        opts.base,
        opts.patterns,
        exclude=opts.exclude,
        max_depth=opts.max_depth,
        hidden=opts.hidden,
        follow_symlinks=opts.follow_symlinks,
        case_sensitive=opts.case_sensitive,
        sort=opts.sort,
        on_error="ignore",
        kinds=kinds,
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


def search(opts: WalkOptions) -> Iterator[FileMatch]:
    """Yield file matches for agent callers without raising operational errors."""
    return iter(search_all(opts).results)


def search_all(opts: WalkOptions) -> FileSearchResult:
    """Return a non-raising structured file search result."""
    from rglob.agent._runtime import collect_file_search

    try:
        return collect_file_search(
            _iter_paths(opts),
            base=opts.base,
            limit=opts.limit,
            max_bytes=opts.max_bytes,
            timeout_seconds=opts.timeout_seconds,
            strict_base=opts.strict_base,
            include_errors=opts.include_errors,
        )
    except Exception as exc:
        return FileSearchResult(
            results=[],
            truncated=False,
            total_files_searched=0,
            bytes_read=0,
            errors=[_error_from_exception(exc)],
            truncated_reason=None,
        )


def grep(opts: GrepOptions) -> Iterator[LineMatch]:
    """Yield content matches for agent callers without raising operational errors."""
    return iter(grep_all(opts).results)


def grep_all(opts: GrepOptions) -> LineSearchResult:
    """Return a non-raising structured content search result."""
    from rglob._grep import grep_all as _grep_all

    try:
        return _grep_all(opts)
    except Exception as exc:
        return LineSearchResult(
            results=[],
            truncated=False,
            total_files_searched=0,
            bytes_read=0,
            errors=[_error_from_exception(exc)],
            truncated_reason=None,
        )


def count(opts: CountOptions) -> Stats:
    """Return non-raising structured file, line, and byte counts."""
    from rglob._count import count_all as _count_all

    try:
        return _count_all(opts)
    except Exception as exc:
        return Stats(
            files=0,
            lines=0,
            bytes=0,
            total_files_searched=0,
            bytes_read=0,
            errors=[_error_from_exception(exc)],
            truncated=False,
            truncated_reason=None,
        )


def _duplicate_record(group: list[Path], base: Path) -> Duplicate:
    """Convert duplicate paths into a Duplicate record."""
    from rglob.agent._runtime import _absolute, _relative_path

    absolute_base = _absolute(base)
    absolute_paths = [_absolute(path) for path in group]
    size = 0
    if group:
        try:
            size = group[0].stat().st_size
        except OSError:
            size = 0
    return Duplicate(
        paths=absolute_paths,
        relative_paths=[_relative_path(path, absolute_base) for path in absolute_paths],
        size=size,
        digest=None,
    )


def find_duplicates(opts: WalkOptions) -> DuplicateSearchResult:
    """Return non-raising duplicate-file groups selected by WalkOptions."""
    from rglob._dupes import find_duplicates as _find_duplicate_groups
    from rglob.agent._runtime import (
        _absolute,
        _is_contained,
        _strict_base_error,
        check_timeout,
        deadline_from_timeout,
        timeout_error,
    )

    paths: list[Path] = []
    errors: list[ErrorInfo] = []
    try:
        deadline = deadline_from_timeout(opts.timeout_seconds)
        truncated = False
        truncated_reason = None

        def check_deadline() -> None:
            check_timeout(deadline)

        for path in _iter_paths(opts, force_files=True):
            check_deadline()
            if opts.strict_base and not _is_contained(path, opts.base):
                if opts.include_errors:
                    errors.append(_strict_base_error(path, _absolute(opts.base)))
                continue
            paths.append(path)
        groups = _find_duplicate_groups(paths, timeout_check=check_deadline)
        check_deadline()
        results = [_duplicate_record(group, opts.base) for group in groups]
        bytes_read = sum(record.size * len(record.paths) for record in results)
        if opts.limit is not None and len(results) > opts.limit:
            results = results[: opts.limit]
            truncated = True
            truncated_reason = "limit"
        return DuplicateSearchResult(
            results=results,
            truncated=truncated,
            total_files_searched=len(paths),
            bytes_read=bytes_read,
            errors=errors,
            truncated_reason=truncated_reason,
        )
    except TimeoutError:
        if opts.include_errors:
            errors.append(timeout_error())
        return DuplicateSearchResult(
            results=[],
            truncated=True,
            total_files_searched=len(paths),
            bytes_read=0,
            errors=errors,
            truncated_reason="timeout",
        )
    except Exception as exc:
        return DuplicateSearchResult(
            results=[],
            truncated=False,
            total_files_searched=0,
            bytes_read=0,
            errors=[_error_from_exception(exc)],
            truncated_reason=None,
        )
