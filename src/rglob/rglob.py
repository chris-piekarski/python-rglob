"""Recursive filesystem walking, line counting, and size aggregation.

The package's primary public surface:

- :func:`find` — lazy generator yielding :class:`pathlib.Path` matches
- :func:`find_all` — eager :class:`list` variant of :func:`find`
- :func:`rglob` / :func:`rglob_` — legacy wrappers returning ``list[str]``
- :func:`lcount` — line counting across matching files
- :func:`tsize` — total size aggregation with unit conversion
- :func:`kilobytes` / :func:`megabytes` / :func:`gigabytes` / :func:`terabytes`
  — binary-prefix conversion helpers
"""

import fnmatch
import math
import os
import re
import sys
import warnings
from collections.abc import Callable, Iterable, Iterator, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from rglob._filters import (
    Kind,
    gitignore_matcher,
    kinds_match,
    mtime_predicate,
    size_predicate,
)

__all__ = [
    "find",
    "find_all",
    "gigabytes",
    "kilobytes",
    "lcount",
    "megabytes",
    "rglob",
    "rglob_",
    "terabytes",
    "tsize",
]

# Type alias for the on_error knob.
OnError = Literal["ignore", "warn", "raise"]


# ─── Unit helpers (kept from the 1.x API, reused by Phase 5 size parser) ──────


def kilobytes(value: float) -> float:
    """Convert bytes to kibibytes (KiB)."""
    return value / math.pow(2.0, 10.0)


def megabytes(value: float) -> float:
    """Convert bytes to mebibytes (MiB)."""
    return value / math.pow(2.0, 20.0)


def gigabytes(value: float) -> float:
    """Convert bytes to gibibytes (GiB)."""
    return value / math.pow(2.0, 30.0)


def terabytes(value: float) -> float:
    """Convert bytes to tebibytes (TiB)."""
    return value / math.pow(2.0, 40.0)


# ─── Pattern compilation ──────────────────────────────────────────────────────


def _os_default_case_sensitive() -> bool:
    """Return the platform-default case sensitivity for filename matching."""
    return sys.platform not in ("win32", "darwin")


def _compile_matcher(pattern: str, *, case_sensitive: bool) -> tuple[Callable[[str], bool], bool]:
    """Compile a single glob pattern into a matcher.

    Returns ``(matcher, is_path_pattern)``. ``is_path_pattern`` is ``True``
    when the pattern should match against the entry's *relative* path
    (because it contains a separator or ``**``); otherwise the matcher runs
    against the entry's basename.

    ``**`` is supported as "any number of path components, including zero".
    All other meta-characters follow ``fnmatch`` semantics.
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    has_double_star = "**" in pattern
    has_separator = "/" in pattern or os.sep in pattern

    if has_double_star:
        # Translate `**/` (slash-suffix), `/**` (slash-prefix), and bare `**`
        # separately so `**/X` also matches `X` at the top level.
        s_dstar_slash = "\x00DSTARSLASH\x00"
        s_slash_dstar = "\x00SLASHDSTAR\x00"
        s_dstar = "\x00DSTAR\x00"
        cooked: list[str] = []
        i = 0
        normalized = pattern.replace(os.sep, "/")
        while i < len(normalized):
            if normalized[i : i + 3] == "**/":
                cooked.append(s_dstar_slash)
                i += 3
            elif normalized[i : i + 3] == "/**" and (
                i + 3 == len(normalized) or normalized[i + 3] == "/"
            ):
                cooked.append(s_slash_dstar)
                i += 3
            elif normalized[i : i + 2] == "**":
                cooked.append(s_dstar)
                i += 2
            else:
                cooked.append(normalized[i])
                i += 1
        translated = fnmatch.translate("".join(cooked))
        translated = translated.replace(s_dstar_slash, "(?:.*/)?")
        translated = translated.replace(s_slash_dstar, "(?:/.*)?")
        translated = translated.replace(s_dstar, ".*")
        regex = re.compile(translated, flags)
        return (lambda s: regex.fullmatch(s) is not None, True)

    if has_separator:
        regex = re.compile(fnmatch.translate(pattern), flags)
        return (lambda s: regex.fullmatch(s) is not None, True)

    # Basename pattern — common case (legacy `rglob(base, "*.py")`).
    regex = re.compile(fnmatch.translate(pattern), flags)
    return (lambda s: regex.fullmatch(s) is not None, False)


def _compile_patterns(
    patterns: Sequence[str], *, case_sensitive: bool
) -> list[tuple[Callable[[str], bool], bool]]:
    """Compile a sequence of glob patterns."""
    return [_compile_matcher(p, case_sensitive=case_sensitive) for p in patterns]


def _matches_any(
    matchers: Iterable[tuple[Callable[[str], bool], bool]],
    *,
    basename: str,
    rel_str: str,
) -> bool:
    """Return ``True`` if any compiled matcher matches the entry."""
    for fn, is_path in matchers:
        candidate = rel_str if is_path else basename
        if fn(candidate):
            return True
    return False


# ─── Error handling ───────────────────────────────────────────────────────────


def _make_error_handler(mode: OnError) -> Callable[[OSError], None]:
    """Return a callable that disposes of OS errors per the chosen mode."""
    if mode == "raise":

        def _raise(exc: OSError) -> None:
            raise exc

        return _raise
    if mode == "warn":

        def _warn(exc: OSError) -> None:
            warnings.warn(f"rglob walk: {exc}", RuntimeWarning, stacklevel=2)

        return _warn
    # "ignore"
    return lambda _exc: None


# ─── Core walker ──────────────────────────────────────────────────────────────


def _scandir_sorted(
    path: Path,
    *,
    sort: bool,
    on_error: Callable[[OSError], None],
) -> list[os.DirEntry[str]]:
    """Return the entries of ``path`` (optionally sorted by name)."""
    try:
        with os.scandir(path) as it:
            entries = list(it)
    except OSError as exc:
        on_error(exc)
        return []
    if sort:
        entries.sort(key=lambda e: e.name)
    return entries


def _walk(
    base: Path,
    current: Path,
    depth: int,
    *,
    matchers: list[tuple[Callable[[str], bool], bool]],
    excluders: list[tuple[Callable[[str], bool], bool]],
    max_depth: int | None,
    hidden: bool,
    follow_symlinks: bool,
    sort: bool,
    on_error: Callable[[OSError], None],
    visited: set[str],
    kinds: frozenset[Kind],
    size_filter: Callable[[os.DirEntry[str]], bool],
    mtime_filter: Callable[[os.DirEntry[str]], bool],
    gitignore: Callable[[Path], bool] | None,
) -> Iterator[Path]:
    """Depth-first walker producing matching paths."""
    for entry in _scandir_sorted(current, sort=sort, on_error=on_error):
        name = entry.name
        if not hidden and name.startswith("."):
            continue

        path = Path(entry.path)
        try:
            rel = path.relative_to(base)
            rel_str = rel.as_posix()
        except ValueError:  # pragma: no cover - DirEntry paths are always under base
            continue

        if excluders and _matches_any(excluders, basename=name, rel_str=rel_str):
            continue
        if gitignore is not None and gitignore(path):
            continue

        passes_kind = kinds_match(entry, kinds)
        passes_size = size_filter(entry)
        passes_mtime = mtime_filter(entry)

        if (
            (not matchers or _matches_any(matchers, basename=name, rel_str=rel_str))
            and passes_kind
            and passes_size
            and passes_mtime
        ):
            yield path

        try:
            is_dir = entry.is_dir(follow_symlinks=follow_symlinks)
        except OSError as exc:
            on_error(exc)
            continue
        if not is_dir:
            continue
        if max_depth is not None and depth >= max_depth:
            continue

        try:
            real = os.path.realpath(path)
        except OSError as exc:  # pragma: no cover - realpath is documented not to raise
            on_error(exc)
            continue
        if real in visited:
            continue
        visited.add(real)

        yield from _walk(
            base,
            path,
            depth + 1,
            matchers=matchers,
            excluders=excluders,
            max_depth=max_depth,
            hidden=hidden,
            follow_symlinks=follow_symlinks,
            sort=sort,
            on_error=on_error,
            visited=visited,
            kinds=kinds,
            size_filter=size_filter,
            mtime_filter=mtime_filter,
            gitignore=gitignore,
        )


def find(
    base: str | os.PathLike[str],
    patterns: str | Sequence[str] = "*",
    *,
    exclude: str | Sequence[str] = (),
    max_depth: int | None = None,
    hidden: bool = False,
    follow_symlinks: bool = False,
    case_sensitive: bool | None = None,
    sort: bool = True,
    on_error: OnError = "warn",
    kinds: Iterable[Kind] = (),
    min_size: int | float | str | None = None,
    max_size: int | float | str | None = None,
    newer_than: datetime | timedelta | str | None = None,
    older_than: datetime | timedelta | str | None = None,
    respect_gitignore: bool = False,
) -> Iterator[Path]:
    """Recursively yield filesystem entries matching ``patterns`` under ``base``.

    Args:
        base: Root directory to walk.
        patterns: Glob pattern or sequence of patterns. ``"*"`` (the default)
            matches everything. Patterns without separators match against
            entry basenames; patterns with ``/`` or ``**`` match against the
            relative path from ``base``. ``**`` matches any number of path
            components, including zero.
        exclude: Pattern or patterns to exclude. Same syntax as ``patterns``;
            matching entries are skipped *and* not descended into (i.e.
            pruning behaviour for directories).
        max_depth: Maximum recursion depth. ``None`` means unbounded; ``0``
            limits to direct children of ``base``.
        hidden: When ``False`` (default), entries whose name starts with
            ``"."`` are skipped (no descent into hidden directories).
        follow_symlinks: When ``False`` (default), symbolic links to
            directories are *not* descended into. When ``True``, symlink
            cycles are terminated by a per-call ``realpath`` memo.
        case_sensitive: Force case-sensitive (``True``) or case-insensitive
            (``False``) matching. ``None`` (default) follows the host OS
            (case-sensitive on Linux, case-insensitive on macOS/Windows).
        sort: When ``True`` (default), entries within each directory are
            yielded in sorted order, giving a deterministic depth-first
            traversal. Set ``False`` for raw ``scandir`` order.
        on_error: How to handle ``OSError`` / ``PermissionError`` while
            walking. ``"warn"`` (default) emits a :class:`RuntimeWarning`;
            ``"ignore"`` swallows the error; ``"raise"`` re-raises.
        kinds: Iterable of ``"f"`` (regular file), ``"d"`` (directory),
            ``"l"`` (symlink), ``"x"`` (executable). Empty (default) means
            "all kinds".
        min_size: Minimum file size as bytes (``int``/``float``) or string
            ("1K", "5MiB", "100 MB"). Directories and symlinks bypass this
            filter.
        max_size: Maximum file size — same format as ``min_size``.
        newer_than: Only yield entries with mtime strictly after this
            timestamp. Accepts :class:`datetime`, :class:`timedelta`
            (interpreted as "now minus delta"), an ISO date string, or a
            relative duration like ``"7d"`` / ``"3h"`` / ``"2w"``.
        older_than: Only yield entries with mtime strictly before this
            timestamp — same format as ``newer_than``.
        respect_gitignore: When ``True``, skip files that any `.gitignore`
            under ``base`` would ignore. Requires the optional ``pathspec``
            dependency (``pip install rglob[gitignore]``); silently
            no-ops if not installed.

    Yields:
        :class:`pathlib.Path` instances for each match, in deterministic
        order when ``sort=True``.

    Examples:
        >>> from rglob import find
        >>> list(find("/tmp", "*.txt"))            # doctest: +SKIP
        >>> list(find("/tmp", ["*.py", "*.pyx"]))  # doctest: +SKIP
        >>> list(find(".", "**/test_*.py"))        # doctest: +SKIP
    """
    base_path = Path(base)
    if isinstance(patterns, str):
        patterns = (patterns,)
    if isinstance(exclude, str):
        exclude = (exclude,)
    if case_sensitive is None:
        case_sensitive = _os_default_case_sensitive()

    matchers = _compile_patterns(patterns, case_sensitive=case_sensitive)
    excluders = _compile_patterns(exclude, case_sensitive=case_sensitive)
    handler = _make_error_handler(on_error)
    visited: set[str] = {os.path.realpath(base_path)}

    size_check = size_predicate(min_size, max_size)
    mtime_check = mtime_predicate(newer_than, older_than)
    gitignore_check = gitignore_matcher(base_path) if respect_gitignore else None

    return _walk(
        base_path,
        base_path,
        0,
        matchers=matchers,
        excluders=excluders,
        max_depth=max_depth,
        hidden=hidden,
        follow_symlinks=follow_symlinks,
        sort=sort,
        on_error=handler,
        visited=visited,
        kinds=frozenset(kinds),
        size_filter=size_check,
        mtime_filter=mtime_check,
        gitignore=gitignore_check,
    )


def find_all(
    base: str | os.PathLike[str],
    patterns: str | Sequence[str] = "*",
    **kwargs: object,
) -> list[Path]:
    """Eager variant of :func:`find` — returns ``list[Path]``."""
    return list(find(base, patterns, **kwargs))  # type: ignore[arg-type]


# ─── Legacy API (Phase 6 flips rglob/rglob_ to list[Path]) ────────────────────


def rglob(base: str | os.PathLike[str], pattern: str) -> list[Path]:
    """Recursively glob entries under ``base`` matching ``pattern``.

    **Breaking change in 2.0**: now returns ``list[Path]`` (was ``list[str]``
    in 1.x). See the migration guide and ADR-0003 for context. To restore
    the old behaviour locally:

        paths = [str(p) for p in rglob(base, pattern)]
    """
    return list(find(base, pattern, sort=False, on_error="ignore"))


def rglob_(pattern: str) -> list[Path]:
    """Recursively glob entries under the current working directory."""
    return rglob(str(Path.cwd()), pattern)


def _count(files: Iterable[Path | str], func: Callable[[str], bool]) -> int:
    """Count lines in ``files`` that satisfy ``func``."""
    total = 0
    for path in files:
        with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
            total += sum(1 for line in handle if func(line))
    return total


def _sum_sizes(files: Iterable[Path | str]) -> int:
    """Sum sizes of file entries (directories are skipped)."""
    total = 0
    for path in files:
        p = Path(path)
        if not p.is_dir():
            total += p.stat().st_size
    return total


def lcount(
    base: str | os.PathLike[str],
    pattern: str,
    func: Callable[[str], bool] = lambda _line: True,
) -> int:
    """Count lines across files matching ``pattern`` under ``base``.

    Args:
        base: root directory to walk.
        pattern: glob pattern (e.g. ``"*.py"``).
        func: per-line predicate; only lines for which it returns truthy
            are counted. Defaults to "count every line".

    Returns:
        Integer total line count.
    """
    return _count(rglob(base, pattern), func)


def tsize(
    base: str | os.PathLike[str],
    pattern: str,
    func: Callable[[float], float] = megabytes,
) -> float:
    """Sum the total size of files matching ``pattern`` under ``base``.

    Args:
        base: root directory to walk.
        pattern: glob pattern (e.g. ``"*.jpg"``).
        func: unit-conversion function from bytes to the desired unit.
            Defaults to :func:`megabytes`.

    Returns:
        The total size converted by ``func`` (a float).
    """
    return func(_sum_sizes(rglob(base, pattern)))


if __name__ == "__main__":  # pragma: no cover - manual smoke entry

    def _filter(line: str) -> bool:
        return bool(line.strip()) and not line.strip().startswith("#")

    here = Path(__file__).parent
    print(f"{lcount(str(here), '*.py', _filter)} non-blank/non-comment lines")
