"""Filter parsers and predicates for the Phase 5 fun-features pass.

This module is internal-but-stable: external callers should reach it through
:func:`rglob.find` rather than importing helpers directly.
"""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

Kind = Literal["f", "d", "l", "x"]

# ─── Size strings ─────────────────────────────────────────────────────────────

_SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgtKMGT]?)([iI]?)[bB]?\s*$")

_UNIT_TO_BYTES: dict[str, int] = {
    "": 1,
    "K": 2**10,
    "M": 2**20,
    "G": 2**30,
    "T": 2**40,
}


def parse_size(value: int | float | str) -> int:
    """Parse a size into bytes.

    Accepts plain numbers (bytes) or strings like ``"1K"``, ``"2.5M"``,
    ``"3GiB"``, ``"100 KB"``. Binary prefixes are assumed (KiB == 1024 B);
    the optional ``i``/``B`` suffixes are ignored.

    Raises:
        ValueError: if the string can't be parsed.
    """
    if isinstance(value, (int, float)):
        return int(value)
    match = _SIZE_RE.match(value)
    if not match:
        raise ValueError(f"unparseable size: {value!r}")
    number, unit, _i = match.groups()
    return int(float(number) * _UNIT_TO_BYTES[unit.upper()])


# ─── Time strings ─────────────────────────────────────────────────────────────

_DURATION_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([smhdwSMHDW])\s*$")

_DURATION_UNIT_SECONDS: dict[str, float] = {
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
    "w": 604800.0,
}


def parse_time(value: datetime | timedelta | str) -> datetime:
    """Parse a time expression into a tz-aware :class:`datetime`.

    Accepts:
      - a :class:`datetime` (returned as-is — naive datetimes get UTC).
      - a :class:`timedelta` (interpreted as "now minus delta").
      - an ISO-8601-style date string (``"2026-05-14"`` or
        ``"2026-05-14T12:00:00"``).
      - a relative duration like ``"7d"``, ``"3h"``, ``"2w"``
        (interpreted as "now minus that").
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if isinstance(value, timedelta):
        return now - value
    match = _DURATION_RE.match(value)
    if match:
        number, unit = match.groups()
        return now - timedelta(seconds=float(number) * _DURATION_UNIT_SECONDS[unit.lower()])
    # Fall back to ISO parser.
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"unparseable time: {value!r}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


# ─── Kind predicates ──────────────────────────────────────────────────────────


def _entry_kind(entry: os.DirEntry[str]) -> set[Kind]:
    """Return the kind tags applicable to a DirEntry."""
    tags: set[Kind] = set()
    try:
        if entry.is_symlink():
            tags.add("l")
    except OSError:  # pragma: no cover - is_symlink is documented not to raise
        pass
    try:
        if entry.is_file(follow_symlinks=False):
            tags.add("f")
    except OSError:  # pragma: no cover - rare
        pass
    try:
        if entry.is_dir(follow_symlinks=False):
            tags.add("d")
    except OSError:  # pragma: no cover - rare
        pass
    try:
        st = entry.stat(follow_symlinks=False)
        if st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            tags.add("x")
    except OSError:  # pragma: no cover - rare
        pass
    return tags


def kinds_match(entry: os.DirEntry[str], wanted: Iterable[Kind]) -> bool:
    """Return ``True`` if the entry matches any wanted kind."""
    wanted_set = set(wanted)
    if not wanted_set:
        return True
    return bool(_entry_kind(entry) & wanted_set)


# ─── Size / mtime predicates ──────────────────────────────────────────────────


def size_predicate(
    min_size: int | float | str | None,
    max_size: int | float | str | None,
) -> Callable[[os.DirEntry[str]], bool]:
    """Build a predicate that checks an entry's size against min/max bounds."""
    lo = parse_size(min_size) if min_size is not None else None
    hi = parse_size(max_size) if max_size is not None else None
    if lo is None and hi is None:
        return lambda _entry: True

    def _check(entry: os.DirEntry[str]) -> bool:
        try:
            if not entry.is_file(follow_symlinks=False):
                # Non-files (dirs, symlinks) always pass size filters.
                return True
            size = entry.stat(follow_symlinks=False).st_size
        except OSError:  # pragma: no cover - rare
            return True
        if lo is not None and size < lo:
            return False
        return not (hi is not None and size > hi)

    return _check


def mtime_predicate(
    newer_than: datetime | timedelta | str | None,
    older_than: datetime | timedelta | str | None,
) -> Callable[[os.DirEntry[str]], bool]:
    """Build a predicate that checks an entry's mtime against bounds."""
    after = parse_time(newer_than) if newer_than is not None else None
    before = parse_time(older_than) if older_than is not None else None
    if after is None and before is None:
        return lambda _entry: True

    def _check(entry: os.DirEntry[str]) -> bool:
        try:
            mtime = entry.stat(follow_symlinks=False).st_mtime
        except OSError:  # pragma: no cover - rare
            return True
        ts = datetime.fromtimestamp(mtime, tz=UTC)
        if after is not None and ts < after:
            return False
        return not (before is not None and ts > before)

    return _check


# ─── .gitignore awareness ─────────────────────────────────────────────────────


def gitignore_matcher(base: Path) -> Callable[[Path], bool] | None:
    """Return a "should ignore" predicate honouring `.gitignore` files.

    Walks `base` collecting every `.gitignore` (top-down) and merges them
    into a per-tree :class:`pathspec.PathSpec`. Returns ``None`` if
    :mod:`pathspec` isn't installed — callers should treat that as
    "feature disabled" and fall back to the no-gitignore walk.
    """
    try:
        import pathspec
    except ImportError:  # pragma: no cover - optional extra
        return None

    patterns: list[str] = []
    for gi in base.rglob(".gitignore"):
        try:
            patterns.extend(gi.read_text(encoding="utf-8").splitlines())
        except OSError:  # pragma: no cover - unreadable .gitignore
            continue
    # pathspec >=1.0 renamed the pattern dialect from "gitwildmatch" to
    # "gitignore"; fall back to the older name on installations that haven't
    # bumped yet. Typed as `Any` so the union of generic PathSpec[...] types
    # doesn't trip mypy --strict.
    spec: object
    try:
        spec = pathspec.PathSpec.from_lines("gitignore", patterns)
    except (ValueError, LookupError):  # pragma: no cover - older pathspec
        spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def _should_ignore(path: Path) -> bool:
        try:
            rel = path.relative_to(base)
        except ValueError:  # pragma: no cover - paths are always under base
            return False
        return bool(spec.match_file(rel.as_posix()))

    return _should_ignore
