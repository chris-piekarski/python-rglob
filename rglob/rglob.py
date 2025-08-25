"""Lightweight recursive glob helpers for files, line counts, and sizes."""

from __future__ import annotations

import glob
import math
import os
from typing import Callable, Iterable, List


def kilobytes(value: float) -> float:
    """Convert bytes to kilobytes (KiB)."""

    return value / math.pow(2.0, 10.0)


def megabytes(value: float) -> float:
    """Convert bytes to megabytes (MiB)."""

    return value / math.pow(2.0, 20.0)


def gigabytes(value: float) -> float:
    """Convert bytes to gigabytes (GiB)."""

    return value / math.pow(2.0, 30.0)


def terabytes(value: float) -> float:
    """Convert bytes to terabytes (TiB)."""

    return value / math.pow(2.0, 40.0)


def _get_dirs(base: str) -> List[str]:
    """Return immediate sub-paths under base that are directories."""

    return [
        path for path in glob.iglob(os.path.join(base, "*")) if os.path.isdir(path)
    ]


def _count(files: Iterable[str], func: Callable[[str], bool]) -> int:
    """Count lines across files that satisfy predicate func."""

    total = 0
    for path in files:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            total += sum(1 for line in handle if func(line))
    return total


def _sum(files: Iterable[str]) -> int:
    """Sum sizes of file paths (ignores directories)."""

    total_size = 0
    for path in files:
        if not os.path.isdir(path):
            total_size += os.path.getsize(path)
    return total_size


def rglob(base: str, pattern: str) -> list[str]:
    """Recursive glob starting in specified directory."""

    matches: list[str] = []
    matches.extend(glob.glob(os.path.join(base, pattern)))
    dirs = _get_dirs(base)
    if dirs:
        for dpath in dirs:
            matches.extend(rglob(dpath, pattern))
    return matches


def rglob_(pattern: str) -> list[str]:
    """Recursive glob using the current working directory as base."""

    return rglob(os.getcwd(), pattern)


def lcount(
    base: str, pattern: str, func: Callable[[str], bool] = lambda _line: True
) -> int:
    """Count number of lines across files found matching pattern.

    Params:
        base: root directory to start the search
        pattern: pattern for glob to match (e.g. "*.py")
        func: boolean filter function applied per line
            example: lambda line: bool(line.strip())  # don't count empty lines
            default: lambda line: True
    """

    all_files = rglob(base, pattern)
    return _count(all_files, func)


def tsize(base: str, pattern: str, func: Callable[[float], float] = megabytes) -> float:
    """Sum and return the total size of every file found from glob(base, pattern).

    Params:
        base: root directory to start the search
        pattern: pattern for glob to match (e.g. "*.py")
        func: unit prefix conversion function
            example: lambda x: x / math.pow(2.0, 20.0)  # megabytes
            default: megabytes
    """

    all_files = rglob(base, pattern)
    total_size = _sum(all_files)
    return func(total_size)


if __name__ == "__main__":
    # Filter out empty lines and comments.
    def filter_func(line: str) -> bool:
        """Return True for non-empty, non-comment lines."""
        return bool(line.strip()) and not line.strip().startswith("#")

    py_files = rglob(os.path.dirname(__file__), "*.py")
    print(f"{_count(py_files, filter_func)} total lines")

    py_files_cwd = rglob_("*.py")
    print(f"{_count(py_files_cwd, filter_func)} total lines")
    print(
        f"{lcount(os.path.dirname(__file__), '*.py', filter_func)} total lines"
    )
