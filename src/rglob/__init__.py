"""Public API for the `rglob` package.

The 2.0 surface (in flight across the modernization roadmap) exposes:

- :func:`find` / :func:`find_all` — the modern Path-yielding API
- :func:`rglob` / :func:`rglob_` — legacy ``list[str]`` wrappers (flip to
  ``list[Path]`` at 2.0; see ADR-0003)
- :func:`lcount` / :func:`tsize` — line-count and size aggregation helpers
- :func:`kilobytes` / :func:`megabytes` / :func:`gigabytes` / :func:`terabytes`
  — binary-prefix conversion helpers
"""

from rglob.rglob import (
    find,
    find_all,
    gigabytes,
    kilobytes,
    lcount,
    megabytes,
    rglob,
    rglob_,
    terabytes,
    tsize,
)

__version__ = "2.0.0"

__all__ = [
    "__version__",
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
